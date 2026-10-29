#!/usr/bin/env python3
"""Check layer boundaries and source dependencies without a warehouse."""
import contextlib
import io
import re
import unittest
from unittest.mock import Mock, patch

import sqlglot
from sqlglot import exp
import yaml

import pipeline

SHARED = {'nicknames', 'int_name__variants', 'stg_npi__reference', 'int_npi__names'}

class LayerContractTests(unittest.TestCase):
    def test_staging_has_one_input_and_no_row_transformations(self):
        stages = [n for n in pipeline.model_paths() if n.startswith('stg_')]
        self.assertEqual(len(stages), 13)
        for name in stages:
            with self.subTest(model=name):
                sql = pipeline.read_model(name)
                tree = sqlglot.parse_one(sql, read='trino')
                self.assertIn('s.*', sql)
                for node in (exp.Where, exp.Join, exp.Unnest, exp.Group, exp.Distinct,
                             exp.Union, exp.Limit, exp.Having, exp.Qualify):
                    self.assertIsNone(tree.find(node), (name, node.__name__))
                self.assertEqual(len(list(tree.find_all(exp.Table))), 1)
                pipeline.stage_input(name)

    def test_all_vendor_tables_are_staged_and_dependencies_stay_local(self):
        for source in pipeline.SOURCES:
            plan = pipeline.source_plan(source)
            stages = [n for n in pipeline.model_paths() if n.startswith(f'stg_{source}__')]
            self.assertTrue(set(stages).issubset(plan), source)
            self.assertEqual(plan[-1], f'int_{source}__metrics')
            for name in plan:
                self.assertTrue(f'_{source}__' in name or name in SHARED, name)
                refs = []
                pipeline.read_model(name, dependencies=refs)
                self.assertTrue(all(f'_{source}__' in ref or ref in SHARED for ref in refs), (name, refs))
                for ref in refs:
                    self.assertLess(plan.index(ref), plan.index(name))

    def test_evidence_preserves_vendor_history_and_unknowns(self):
        from test_models import execute
        dependencies = []
        pipeline.read_model('pii_clean', dependencies=dependencies)
        self.assertEqual(dependencies, [f'int_{s}__metrics' for s in pipeline.SOURCES])
        fields = ['first_seen_day', 'last_seen_day', 'observed_day_count', 'observation_count',
                  'undated_observation_count', 'invalid_day_observation_count', 'source_tables',
                  'source_feeds', 'computed_at', 'definition_version', 'email_format_valid',
                  'email_role_account', 'email_domain_class', *pipeline.NAME_METRICS,
                  'source_name_usable', 'registry_name_usable', 'registry_npi_present',
                  'record_id', 'email_ordinal', 'email_origin', 'record_payload',
                  'email_npi_count', 'email_has_multiple_npis',
                  'has_been_reassigned', 'has_conflict_linkage', 'observed_days', 'conflict_days']
        overrides = {f'int_{s}__metrics': f"(SELECT '{s}' AS source, 'same@example.test' AS email, npi, metric_row_id, "
                     + ', '.join(f'NULL AS {c}' for c in fields)
                     + ', CAST(ARRAY[] AS array(row(first_name varchar, last_name varchar, first_variants array(varchar)))) AS source_name_values'
                     + " FROM (VALUES ('older_npi', 'record_1'), ('older_npi', 'record_2'), ('newer_npi', 'record_3')) AS records(npi, metric_row_id))" for s in pipeline.SOURCES}
        rows = execute(pipeline.read_model('pii_clean', ref_overrides=overrides))
        self.assertEqual(len(rows), 21)
        self.assertEqual(len({(r['source'], r['metric_row_id']) for r in rows}), 21)
        self.assertEqual(len({(r['source'], r['email'], r['npi']) for r in rows}), 14)
        self.assertTrue(all(r[m] is None for r in rows for m in pipeline.NAME_METRICS))
        config = yaml.safe_load((pipeline.PROJECT / 'dbt_project.yml').read_text())
        self.assertEqual(config['models']['pii_clean']['final']['+materialized'], 'table')

    def test_build_creates_shared_views_only_once(self):
        statements = []
        with contextlib.redirect_stdout(io.StringIO()), patch.object(pipeline, 'run_write', statements.append):
            pipeline.build_views()
        targets = [s.split(' AS\n')[0] for s in statements]
        expected = {n for source in pipeline.SOURCES for n in pipeline.source_plan(source)}
        self.assertEqual(len(targets), len(expected))
        self.assertEqual(len(set(targets)), len(expected))

    def test_rendering_is_strict(self):
        with self.assertRaisesRegex(ValueError, 'Undeclared source'):
            pipeline.render_sql("SELECT * FROM {{ source('iceberg__thirdparty', 'not_a_table') }}")
        with self.assertRaisesRegex(ValueError, 'Unknown model'):
            pipeline.render_sql("SELECT * FROM {{ ref('not_a_model') }}")

    def test_evidence_write_waits_for_completion_and_closes_connection(self):
        db = Mock()
        connection = db.get_trino_connection.return_value
        cursor = connection.cursor.return_value
        statement = 'CREATE OR REPLACE TABLE evidence AS SELECT 1'
        with patch.object(pipeline, 'bootstrap', return_value=(db, {})):
            pipeline.run_write(statement, session_properties=pipeline.EVIDENCE_SESSION_PROPERTIES)
        db.get_trino_connection.assert_called_once_with(session_properties=pipeline.EVIDENCE_SESSION_PROPERTIES)
        cursor.execute.assert_called_once_with(statement)
        cursor.fetchall.assert_called_once()
        cursor.close.assert_called_once()
        connection.close.assert_called_once()
        cursor.reset_mock()
        connection.close.reset_mock()
        cursor.fetchall.side_effect = RuntimeError('write failed')
        with patch.object(pipeline, 'bootstrap', return_value=(db, {})):
            with self.assertRaisesRegex(RuntimeError, 'write failed'):
                pipeline.run_write(statement, session_properties=pipeline.EVIDENCE_SESSION_PROPERTIES)
        cursor.close.assert_called_once()
        connection.close.assert_called_once()

    def test_source_command_only_creates_views_for_that_vendor(self):
        statements = []
        with contextlib.redirect_stdout(io.StringIO()), patch.object(pipeline, 'run_write', statements.append):
            pipeline.create_source('healthlink')
        self.assertTrue(statements)
        self.assertTrue(all(s.startswith('CREATE OR REPLACE VIEW ') for s in statements))
        allowed = {pipeline.relation(n) for n in pipeline.source_plan('healthlink')}
        self.assertTrue(all(s.split(' AS\n')[0].removeprefix('CREATE OR REPLACE VIEW ') in allowed
                            for s in statements))
        self.assertFalse(any('CREATE TABLE' in s for s in statements))


if __name__ == '__main__':
    unittest.main()
