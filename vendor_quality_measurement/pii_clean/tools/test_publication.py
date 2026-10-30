"""Compute vendors once and validate stored candidates before publication."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pipeline as p


class PublicationTests(unittest.TestCase):
    def run_build(self, failure=None, batched=True, preserve=False):
        writes = []
        events = []
        stored = [{'source': source, 'metric_rows': 1, 'duplicate_keys': 0,
                     'evidence_checksum': source} for source in sorted(p.SOURCES)]

        def explain(db, sql):
            if 'union_models' in sql:
                if failure == 'unrelated_plan':
                    raise RuntimeError('PERMISSION_DENIED')
                if batched:
                    raise RuntimeError('QUERY_HAS_TOO_MANY_STAGES')
            return 20

        def query(db, sql):
            events.append(('query', sql))
            if sql.startswith('DESCRIBE '):
                if (failure == 'vendor_schema' and 'int_medscape__metrics' in sql
                        or failure == 'candidate_schema' and 'candidate_' in sql
                        or failure == 'published_schema' and sql == 'DESCRIBE ' + p.relation(p.FINAL_MODEL)):
                    return [{'Column': 'source', 'Type': 'bigint'}]
                return [{'Column': 'source', 'Type': 'varchar'}, {'Column': 'metric_row_id', 'Type': 'varchar'}]
            self.assertNotRegex(sql, r'pii__int_[a-z]+__metrics', 'Validation must not recompute vendor views')
            if 'evidence_checksum' in sql:
                rows = [dict(row) for row in stored]
                if 'candidate_' in sql:
                    if failure == 'missing_source':
                        return rows[:-1]
                    if failure == 'unexpected_source':
                        rows[0]['source'] = 'unexpected'
                    if failure == 'duplicate_keys':
                        rows[0]['duplicate_keys'] = 1
                    if failure == 'empty_source':
                        rows[0]['metric_rows'] = 0
                elif failure == 'published_checksum':
                    rows[0]['evidence_checksum'] = 'changed'
                return rows
            if failure == 'integrity' and 'source_integrity' in sql:
                return [{'reason': 'duplicate_keys', 'failures': 1}]
            if failure == 'metric' and 'cookie_location' in sql:
                return [{'reason': 'invalid_status', 'failures': 1}]
            return []

        def write(sql, **kwargs):
            writes.append(sql)
            events.append(('write', sql))
            if failure == 'write' and (sql.startswith('INSERT INTO') if batched else sql.startswith('CREATE TABLE')):
                raise RuntimeError('writer failed')

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            for test in ('source_integrity', 'email_npi_multiplicity', 'email_linkage_history',
                         'name_consistency', 'conflicting_names', 'conflicting_states', 'conflicting_facilities', 'conflicting_specialties', 'registry_status', 'vendor_facility_state', 'cookie_location', 'link_freshness'):
                (root / f'tests/{test}.sql').write_text('SELECT ' + test)
            with patch.object(p, 'ROOT', root), patch.object(p, 'query', query), \
                    patch.object(p, 'read_model', return_value='SELECT * FROM union_models'), \
                    patch.object(p, 'render_sql', side_effect=lambda sql, variables, overrides:
                                 sql + ' FROM ' + overrides[p.FINAL_MODEL]), \
                    patch.object(p, 'explain_fragments', explain), patch.object(p, 'run_write', write), \
                    contextlib.redirect_stdout(io.StringIO()):
                preservation = {'columns': ['source'], 'rows': stored[:-1] if failure == 'preservation' else stored}
                if failure:
                    with self.assertRaises((ValueError, RuntimeError)):
                        p.build_final(Mock(), preservation=preservation if preserve or failure == 'preservation' else None)
                else:
                    p.build_final(Mock(), preservation=preservation if preserve else None)
            manifest = json.loads((root / 'results/final_build.json').read_text())
        self.assertEqual(manifest['verified'], failure is None)
        return writes, events, manifest

    def test_success_publishes_only_after_all_candidate_batches(self):
        writes, events, manifest = self.run_build(preserve=True)
        self.assertEqual(len(writes), 8)
        self.assertTrue(writes[0].startswith('CREATE TABLE iceberg.jteixeira_ipa.pii_clean_candidate_'))
        self.assertTrue(all(s.startswith('INSERT INTO') for s in writes[1:7]))
        self.assertTrue(writes[-1].startswith('CREATE OR REPLACE TABLE iceberg.jteixeira_ipa.pii_clean WITH'))
        for source in p.SOURCES:
            self.assertEqual(sum(p.relation(f'int_{source}__metrics') in sql for sql in writes), 1)
            self.assertIn('materialized', manifest['sources'][source])
            self.assertNotIn('baseline', manifest['sources'][source])
        self.assertIn('previous_column_validation', manifest)
        self.assert_validation_precedes_publication(events)

    def assert_validation_precedes_publication(self, events):
        publish_index = next(i for i, (kind, sql) in enumerate(events)
                             if kind == 'write' and sql.startswith('CREATE OR REPLACE TABLE'))
        tests = [(i, sql) for i, (kind, sql) in enumerate(events)
                 if kind == 'query' and sql.startswith('SELECT ') and 'evidence_checksum' not in sql]
        self.assertEqual(len(tests), 12)
        self.assertTrue(all(i < publish_index and 'candidate_' in sql for i, sql in tests))

    def test_union_also_validates_candidate_before_publication(self):
        writes, events, manifest = self.run_build(batched=False, preserve=True)
        self.assertEqual(len(writes), 2)
        self.assertTrue(writes[0].startswith('CREATE TABLE'))
        self.assertIn('union_models', writes[0])
        self.assertIn('SELECT * FROM iceberg.jteixeira_ipa.pii_clean_candidate_', writes[1])
        self.assertEqual(manifest['publication_mode'], 'union_candidate')
        self.assertIn('previous_column_validation', manifest)
        self.assert_validation_precedes_publication(events)

    def test_failed_candidate_never_changes_canonical(self):
        for batched in (False, True):
            for failure in ('missing_source', 'unexpected_source', 'duplicate_keys', 'empty_source',
                            'integrity', 'metric', 'write', 'unrelated_plan', 'preservation',
                            'vendor_schema', 'candidate_schema'):
                with self.subTest(failure=failure, batched=batched):
                    writes, _, _ = self.run_build(failure, batched=batched)
                    self.assertFalse(any(s.startswith('CREATE OR REPLACE TABLE') for s in writes))

    def test_published_schema_and_checksums_are_verified(self):
        for batched in (False, True):
            for failure in ('published_checksum', 'published_schema'):
                with self.subTest(failure=failure, batched=batched):
                    writes, _, manifest = self.run_build(failure, batched=batched)
                    self.assertTrue(writes[-1].startswith('CREATE OR REPLACE TABLE'))
                    self.assertIn('published_validation', manifest)


if __name__ == '__main__':
    unittest.main()
