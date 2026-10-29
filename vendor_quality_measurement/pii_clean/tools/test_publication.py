"""Canonical publication is atomic when vendor batching is needed for stage limits."""
import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pipeline as p


class BatchedPublicationTests(unittest.TestCase):
    def run_build(self, failure=None):
        writes = []
        baseline = [{'source': source, 'metric_rows': 1, 'duplicate_keys': 0,
                     'evidence_checksum': source} for source in sorted(p.SOURCES)]

        def explain(db, sql):
            if 'union_models' in sql:
                if failure == 'unrelated_plan':
                    raise RuntimeError('PERMISSION_DENIED')
                raise RuntimeError('QUERY_HAS_TOO_MANY_STAGES')
            return 20

        def query(db, sql):
            if sql.startswith('DESCRIBE '):
                return [{'Column': 'source', 'Type': 'varchar'}, {'Column': 'metric_row_id', 'Type': 'varchar'}]
            if 'evidence_checksum' in sql:
                source = re.search(r'pii__int_([a-z]+)__metrics', sql)
                if source:
                    return [r for r in baseline if r['source'] == source[1]]
                if failure == 'checksum' and 'candidate_' in sql:
                    return baseline[:-1]
                return baseline
            if failure == 'integrity' and 'source_integrity' in sql:
                return [{'reason': 'duplicate_keys', 'failures': 1}]
            return []

        def write(sql, **kwargs):
            writes.append(sql)
            if failure == 'insert' and sql.startswith('INSERT INTO'):
                raise RuntimeError('writer failed')

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            for test in ('source_integrity', 'email_npi_multiplicity', 'email_linkage_history',
                         'name_consistency', 'conflicting_names', 'conflicting_states', 'conflicting_facilities', 'conflicting_specialties', 'registry_status', 'vendor_facility_state', 'cookie_location'):
                (root / f'tests/{test}.sql').write_text('SELECT ' + test)
            with patch.object(p, 'ROOT', root), patch.object(p, 'query', query), \
                    patch.object(p, 'read_model', return_value='SELECT * FROM union_models'), \
                    patch.object(p, 'render_sql', side_effect=lambda sql, *args: sql), \
                    patch.object(p, 'explain_fragments', explain), patch.object(p, 'run_write', write), \
                    contextlib.redirect_stdout(io.StringIO()):
                if failure:
                    with self.assertRaises((ValueError, RuntimeError)):
                        p.build_final(Mock(), preservation={'columns': ['source'], 'rows': baseline[:-1]}
                                      if failure == 'preservation' else None)
                else:
                    p.build_final(Mock())
        return writes

    def test_success_publishes_only_after_all_candidate_batches(self):
        writes = self.run_build()
        self.assertEqual(len(writes), 8)
        self.assertTrue(writes[0].startswith('CREATE TABLE iceberg.jteixeira_ipa.pii_clean_candidate_'))
        self.assertTrue(all(s.startswith('INSERT INTO') for s in writes[1:7]))
        self.assertTrue(writes[-1].startswith('CREATE OR REPLACE TABLE iceberg.jteixeira_ipa.pii_clean WITH'))

    def test_failed_candidate_never_changes_canonical(self):
        for failure in ('checksum', 'integrity', 'insert', 'unrelated_plan', 'preservation'):
            with self.subTest(failure=failure):
                writes = self.run_build(failure)
                self.assertFalse(any(s.startswith('CREATE OR REPLACE TABLE') for s in writes))


if __name__ == '__main__':
    unittest.main()
