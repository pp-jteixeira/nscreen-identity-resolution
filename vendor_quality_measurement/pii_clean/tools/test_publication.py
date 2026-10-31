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
    def run_build(self, failure=None, batched=True, preserve=False, staged=False, forced=False, reused=False, direct=False, resume=False, core_staged=False):
        writes = []
        checkpoints = []

        def capture(*args, **kwargs):
            if args and isinstance(args[0], str) and args[0].startswith("{"):
                checkpoints.append(json.loads(args[0]))

        events = []
        stored = [{'source': source, 'metric_rows': 1, 'duplicate_keys': 0,
                     'evidence_checksum': source} for source in sorted(p.SOURCES)]

        def explain(db, sql, session_properties=None):
            if staged and p.relation('int_medscape__metrics') in sql:
                raise RuntimeError('QUERY_HAS_TOO_MANY_STAGES')
            if failure == 'base_plan' and 'core_models' in sql:
                raise RuntimeError('QUERY_HAS_TOO_MANY_STAGES')
            if 'base_models' in sql:
                if failure == 'base_plan':
                    raise RuntimeError('QUERY_HAS_TOO_MANY_STAGES')
                if core_staged:
                    raise RuntimeError('QUERY_HAS_TOO_MANY_STAGES')
                return 140
            if 'union_models' in sql:
                if failure == 'unrelated_plan':
                    raise RuntimeError('PERMISSION_DENIED')
                if batched:
                    raise RuntimeError('QUERY_HAS_TOO_MANY_STAGES')
            return 20

        def query(db, sql):
            events.append(('query', sql))
            if 'AS metric_rows FROM' in sql and 'retained_history_input' in sql:
                return [{'source': 'medscape' if failure == 'retained_source' else 'healthlink', 'metric_rows': 1}]
            if sql.startswith('DESCRIBE '):
                if (failure == 'vendor_schema' and 'int_medscape__metrics' in sql
                        or failure == 'candidate_schema' and 'candidate_' in sql
                        or failure in ('published_schema', 'resume_schema') and sql == 'DESCRIBE ' + p.relation(p.CORE_MODEL)):
                    return [{'Column': 'source', 'Type': 'bigint'}]
                return [{'Column': 'source', 'Type': 'varchar'}, {'Column': 'metric_row_id', 'Type': 'varchar'}]
            self.assertNotRegex(sql, r'pii__int_(?:'+'|'.join(p.SOURCES)+r')__metrics', 'Validation must not recompute vendor views')
            if 'count(DISTINCT ROW(source, metric_row_id))' in sql and 'evidence_checksum' not in sql:
                return [{'source': source, 'metric_rows': 1,
                         'duplicate_keys': 1 if failure == 'resume_duplicates' else 0}
                        for source in ('healthlink', 'quantummedica')]
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
            if failure == 'metric' and 'link_stability' in sql:
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
                         'name_consistency', 'conflicting_names', 'conflicting_states', 'conflicting_facilities', 'conflicting_specialties', 'registry_status', 'vendor_facility_state', 'cookie_location', 'link_freshness', 'link_stability', 'npi_identity', 'vendor_professional', 'medscape_optout', 'sequential_history'):
                (root / f'tests/{test}.sql').write_text('SELECT ' + test)
            with patch.object(p, 'ROOT', root), patch.object(p, 'query', query), \
                    patch.object(p, 'publication_schema', side_effect=lambda schema: schema), \
                    patch.object(p, 'read_model', side_effect=lambda name, **kwargs:
                                 'SELECT * FROM core_models' if kwargs.get('variables', {}).get('defer_quality_enrichments')
                                 else 'SELECT * FROM base_models' if kwargs.get('variables', {}).get('defer_sequential_history')
                                 else 'SELECT * FROM union_models'), \
                    patch.object(p, 'quality_from_stored_records', side_effect=lambda table, source: 'SELECT * FROM ' + table), \
                    patch.object(p, 'history_from_stored_records', side_effect=lambda table, source: 'SELECT * FROM ' + table), \
                    patch.object(p, 'render_sql', side_effect=lambda sql, variables, overrides:
                                 sql + ' FROM ' + overrides[p.CORE_MODEL]), \
                    patch.object(p, 'explain_fragments', explain), patch.object(p, 'run_write', write), \
                    patch.object(p, 'print', side_effect=capture, create=True), \
                    contextlib.redirect_stdout(io.StringIO()):
                preservation = {'columns': ['source'], 'rows': stored[:-1] if failure == 'preservation' else stored}
                if failure:
                    with self.assertRaises((ValueError, RuntimeError)):
                        p.build_core(Mock(), preservation=preservation if preserve or failure == 'preservation' else None,
                                      history_inputs={'healthlink': p.SCHEMA + '.retained_history_input'} if reused else None, direct=direct, resume_direct=resume)
                else:
                    p.build_core(Mock(), preservation=preservation if preserve else None, vendor_batches=forced,
                                  history_inputs={'healthlink': p.SCHEMA + '.retained_history_input'} if reused else None, direct=direct, resume_direct=resume)
            manifest = checkpoints[-1]
            self.assertFalse((root / 'results').exists())
        self.assertEqual(manifest['verified'], failure is None)
        return writes, events, manifest

    def test_success_publishes_only_after_all_candidate_batches(self):
        writes, events, manifest = self.run_build(preserve=True)
        self.assertEqual(len(writes), 8)
        self.assertTrue(writes[0].startswith('CREATE TABLE iceberg.jteixeira_ipa.pii_clean_candidate_'))
        self.assertTrue(all(s.startswith('INSERT INTO') for s in writes[1:7]))
        self.assertTrue(writes[-1].startswith('CREATE OR REPLACE TABLE iceberg.jteixeira_ipa.pii__int_pii__metrics WITH'))
        for source in p.SOURCES:
            self.assertEqual(sum(p.relation(f'int_{source}__metrics') in sql for sql in writes), 1)
            self.assertIn('materialized', manifest['sources'][source])
            self.assertNotIn('baseline', manifest['sources'][source])
        self.assertIn('previous_column_validation', manifest)
        self.assert_validation_precedes_publication(events)

    def test_large_vendor_materializes_base_before_attaching_history(self):
        writes, events, manifest = self.run_build(staged=True)
        self.assertEqual(len(writes), 9)
        base = manifest['history_input_writes'][0]
        self.assertTrue(base['completed'])
        self.assertEqual(base['source'], 'medscape')
        self.assertIn('base_models', base['sql'])
        final_batch = next(e for e in manifest['candidate_writes'] if e['source'] == 'medscape')
        self.assertEqual(final_batch['history_input'], base['table'])
        self.assertIn(base['table'], final_batch['sql'])
        self.assert_validation_precedes_publication(events)

    def test_core_staging_uses_exact_keys_before_base_and_history(self):
        writes, events, manifest = self.run_build(staged=True, core_staged=True)
        self.assertEqual(len(writes), 10)
        core = manifest['quality_input_writes'][0]
        base = manifest['history_input_writes'][0]
        self.assertTrue(core['completed'])
        self.assertTrue(base['completed'])
        self.assertIn(core['table'], base['sql'])
        self.assertTrue(base['session_properties']['use_exact_partitioning'])
        self.assertEqual(base['session_properties']['max_writer_task_count'], 8)
        self.assertEqual(base['session_properties']['task_max_writer_count'], 1)
        self.assertFalse(base['session_properties']['task_scale_writers_enabled'])
        self.assert_validation_precedes_publication(events)

    def test_explicit_vendor_batches_skip_combined_plan(self):
        writes, events, manifest = self.run_build(forced=True)
        self.assertEqual(len(writes), 8)
        self.assertEqual(manifest['union_plan_skipped'], 'explicit vendor batching')
        self.assertNotIn('candidate_plan_fragments', manifest)
        self.assert_validation_precedes_publication(events)

    def test_retained_input_is_validated_and_reused(self):
        writes, events, manifest = self.run_build(reused=True)
        self.assertEqual(len(writes), 8)
        self.assertIn('retained_history_input', writes[0])
        self.assertEqual(manifest['reused_history_inputs']['healthlink']['coverage'],
                         [{'source': 'healthlink', 'metric_rows': 1}])
        self.assertFalse(manifest.get('history_input_writes'))
        self.assertTrue(manifest['candidate_writes'][0]['session_properties']['use_exact_partitioning'])
        self.assert_validation_precedes_publication(events)

    def test_direct_build_writes_target_without_candidate_copy(self):
        writes, events, manifest = self.run_build(direct=True, reused=True)
        self.assertEqual(len(writes), 7)
        self.assertTrue(writes[0].startswith('CREATE OR REPLACE TABLE ' + p.relation(p.CORE_MODEL)))
        self.assertTrue(all(sql.startswith('INSERT INTO ' + p.relation(p.CORE_MODEL)) for sql in writes[1:]))
        self.assertNotIn('candidate_table', manifest)
        self.assertNotIn('candidate_writes', manifest)
        self.assertEqual(len(manifest['vendor_writes']), 7)
        self.assertEqual(manifest['build_table'], p.relation(p.CORE_MODEL))
        last_write = max(i for i, event in enumerate(events) if event[0] == 'write')
        self.assertTrue(any(i > last_write and 'source_integrity' in sql
                            for i, (kind, sql) in enumerate(events) if kind == 'query'))

    def test_direct_failure_leaves_verification_incomplete(self):
        writes, _, manifest = self.run_build(failure='metric', direct=True)
        self.assertEqual(len(writes), 7)
        self.assertFalse(manifest['verified'])

    def test_direct_resume_preserves_completed_vendors(self):
        writes, _, manifest = self.run_build(direct=True, resume=True)
        self.assertEqual(len(writes), 5)
        self.assertTrue(all(sql.startswith('INSERT INTO ' + p.relation(p.CORE_MODEL)) for sql in writes))
        self.assertTrue(all('int_healthlink__metrics' not in sql and 'int_quantummedica__metrics' not in sql for sql in writes))
        self.assertEqual({r['source'] for r in manifest['resumed_sources']}, {'healthlink', 'quantummedica'})

    def test_direct_resume_rejects_duplicate_keys(self):
        writes, _, _ = self.run_build(failure='resume_duplicates', direct=True, resume=True)
        self.assertFalse(writes)

    def test_direct_resume_rejects_old_target_schema(self):
        writes, _, _ = self.run_build(failure='resume_schema', direct=True, resume=True)
        self.assertFalse(writes)

    def test_retained_input_with_wrong_source_cannot_publish(self):
        writes, _, _ = self.run_build(failure='retained_source', reused=True)
        self.assertFalse(writes)

    def test_supplied_candidate_cannot_overwrite_existing_table(self):
        with patch.object(p, 'query', return_value=[{'table_name': 'pii_clean_candidate_taken'}]), \
                patch.object(p, 'run_write') as write:
            with self.assertRaisesRegex(ValueError, 'already exists'):
                p.build_core(Mock(), candidate_table=p.SCHEMA + '.pii_clean_candidate_taken')
            write.assert_not_called()

    def test_unplannable_base_cannot_publish(self):
        writes, _, _ = self.run_build(failure='base_plan', staged=True)
        self.assertFalse(any(sql.startswith('CREATE OR REPLACE TABLE') for sql in writes))

    def assert_validation_precedes_publication(self, events):
        publish_index = next(i for i, (kind, sql) in enumerate(events)
                             if kind == 'write' and sql.startswith('CREATE OR REPLACE TABLE'))
        tests = [(i, sql) for i, (kind, sql) in enumerate(events)
                 if kind == 'query' and sql.startswith('SELECT ') and 'evidence_checksum' not in sql
                 and 'AS metric_rows FROM' not in sql]
        self.assertEqual(len(tests), 16)
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
