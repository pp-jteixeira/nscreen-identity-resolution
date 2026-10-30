"""Complete lookup returns stored evidence unchanged, with display helpers only."""
import hashlib
import unittest

import sqlglot
from sqlglot import exp

import pipeline as p
from render_email_lookup import published_columns, render_lookup
from test_models import execute


def fixture():
    # Distinct sentinels detect dropped or recomputed stored columns, including
    # evidence and evaluation dates. No reference tables are available here.
    peers_type = 'array(row(shares_name boolean))'
    fields = {
        'source': "CASE WHEN row_id = 2 THEN 'drdb' ELSE 'endato' END",
        'email': "CASE WHEN row_id = 4 THEN 'other@example.test' ELSE 'team@example.test' END",
        'npi': "CASE WHEN row_id = 2 THEN '1000000002' ELSE '1000000001' END",
        'metric_row_id': 'cast(row_id AS varchar)',
        'computed_at': "TIMESTAMP '2020-01-01 12:34:56'",
        'last_seen_day': "DATE '2020-01-01'",
        'link_freshness_as_of_day': "DATE '2020-01-03'",
        'source_latest_observed_day': "DATE '2020-01-02'",
        'link_last_observed_day': "DATE '2020-01-01'",
        'source_age_days': 'cast(1 AS bigint)',
        'npi_format_valid': 'true',
        'npi_checksum_valid': 'row_id <> 3',
        'npi_structure_valid': 'row_id <> 3',
        'npi_entity_type_evidence': "ARRAY[CAST(ROW('1') AS row(entity_type_code varchar)), CAST(ROW(NULL) AS row(entity_type_code varchar))]",
        'npi_entity_type_reference_row_count': 'cast(2 AS bigint)',
        'npi_entity_type_variant_count': 'cast(2 AS bigint)',
        'npi_identity_as_of_day': "DATE '2020-01-03'",
        'email_observed_day_count': 'cast(5 AS bigint)',
        'link_observed_day_count': 'cast(4 AS bigint)',
        'link_conflict_day_count': 'cast(1 AS bigint)',
        'link_presence_share': 'cast(0.8 AS double)',
        'link_overlap_share': 'CASE WHEN row_id = 3 THEN CAST(NULL AS double) ELSE cast(0.25 AS double) END',
        'link_stability_has_undated_observations': 'row_id = 3',
        'link_lag_days': 'CASE WHEN row_id = 3 THEN CAST(NULL AS bigint) ELSE cast(1 AS bigint) END',
        'npi_registry_status_as_of_day': "DATE '2020-01-02'",
        'cookie_location_window_start': "DATE '2019-12-26'",
        'cookie_location_window_end': "DATE '2020-01-01'",
        'source_name_values': "ARRAY[CAST(ROW('ALICE', 'SMITH') AS ROW(first_name varchar, last_name varchar)), CAST(ROW('BOB', 'JONES') AS ROW(first_name varchar, last_name varchar))]",
        'source_state_values': "ARRAY['NY', 'CA']",
        'conflicting_npi_name_comparisons': f"CASE WHEN row_id = 2 THEN CAST(NULL AS {peers_type}) WHEN row_id = 3 THEN CAST(ARRAY[] AS {peers_type}) ELSE CAST(ARRAY[ROW(true), ROW(false), ROW(cast(NULL AS boolean))] AS {peers_type}) END",
    }
    expressions = [fields.get(name, "'stored_" + name + "'") + ' AS ' + name for name in published_columns()]
    stored = 'SELECT ' + ', '.join(expressions) + ' FROM (VALUES (1), (2), (3), (4)) AS records(row_id)'
    sql = render_lookup(' TEAM@EXAMPLE.TEST ', {p.FINAL_MODEL: '(' + stored + ')'})
    return stored, sql


class EmailLookupTests(unittest.TestCase):
    def test_hash_matches_independent_sha256(self):
        rows = execute(p.render_sql("SELECT {{ cookie_hash(\"'team@example.test'\") }} AS hash"))
        self.assertEqual(rows[0]['hash'], hashlib.sha256(b'team@example.test').hexdigest())

    def test_complete_lookup_and_preservation(self):
        stored, sql = fixture()
        rows = execute(sql)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({(r['source'], r['metric_row_id']) for r in rows}), 3)
        before = {r['metric_row_id']: r for r in execute(stored) if r['email'] == 'team@example.test'}
        for row in rows:
            for name in published_columns():
                self.assertEqual(row[name], before[row['metric_row_id']][name], name)
            self.assertEqual(row['name'], 'ALICE SMITH; BOB JONES')
            self.assertEqual(row['state'], 'NY; CA')
            expected = 1 if row['metric_row_id'] == '1' else 0
            for name in ('name_mismatch_count', 'shared_name_count', 'unknown_name_match_count'):
                self.assertEqual(row[name], expected)
            self.assertEqual(row['name_comparison_count'], 3 * expected)
            self.assertEqual(len(row), 132)
        tree = sqlglot.parse_one(render_lookup(), read='trino')
        self.assertEqual(['.'.join(part.name for part in t.parts) for t in tree.find_all(exp.Table)],
                         ['iceberg.jteixeira_ipa.pii_clean', 'params'])
        self.assertEqual(len(tree.expressions), 132)
        self.assertEqual(len({e.alias_or_name for e in tree.expressions}), 132)
        self.assertEqual(execute(render_lookup('absent@example.test', {p.FINAL_MODEL: '(' + stored + ')'})), [])

    def test_email_literal_escaping_and_single_edit(self):
        sql = render_lookup("o'neil@example.test")
        self.assertEqual(sql.count("o''neil@example.test"), 1)
        self.assertNotIn('CREATE ', sql)

    def test_generated_lookup_matches_sqltools_safe_artifact(self):
        sql = render_lookup()
        self.assertEqual(sql + '\n', (p.ROOT / 'sql/email_lookup_full.sql').read_text())
        self.assertNotIn(';', sql)
        self.assertTrue(all(line.strip() for line in sql.splitlines()))
        special = render_lookup("o'neil;tag@example.test")
        self.assertNotIn(';', special)
        self.assertIn("'o''neil' || chr(59) || 'tag@example.test'", special)


if __name__ == '__main__':
    unittest.main()
