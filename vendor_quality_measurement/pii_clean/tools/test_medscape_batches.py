"""Email batching preserves full histories, source-relative freshness and opt-outs."""
import hashlib
import unittest

import build_medscape_batches as b
import pipeline as p
from test_models import execute, inlined
from test_record_grain import source_values


class MedscapeBatchTests(unittest.TestCase):
    def test_batch_union_matches_all_core_fields(self):
        raw = [dict(email_address=email, npi=npi, day=day, guid=guid)
               for email, npi, day, guid in [
                   ('abc@test', '1', '2026-01-01', 'g'),
                   ('ABC@test', '1', '2026-01-01', 'g'),
                   ('abc@test', '2', '2026-01-02', 'g'),
                   ('abc@test', '3', '2026-01-02', 'g'),
                   ('abc@test', '1', '2026-01-03', 'g'),
                   ('abc@test', '2', '2026-01-03', 'g'),
                   ('later@test', '8', '2026-01-20', 'latest'),
                   ('abc@test', 'excluded', '2026-01-30', 'g'),
                   ('blank@test', '', '2026-02-01', 'invalid')]]
        stage = 'stg_medscape__global'
        data = source_values(stage, raw)
        optout = "(SELECT 'excluded' AS npi, '2026-01-30' AS day, CAST(NULL AS varchar) AS optout_day)"
        variables = {name: '2026-02-01' for name in ('sequence_as_of_day', 'link_freshness_as_of_day',
            'registry_status_as_of_day', 'npi_identity_as_of_day', 'location_evidence_day')}
        fixtures = {stage: data, 'stg_medscape__optout': optout}
        direct = execute(inlined('int_medscape__metrics', fixtures=fixtures, variables=variables))
        batches = sorted({hashlib.sha256(email.encode()).hexdigest()[0].upper() for email in ('abc@test', 'later@test')})
        assembled = []
        for batch in batches:
            filtered = '(SELECT * FROM ' + data + ' WHERE ' + b.bucket_sql('lower(trim(email_address))') + " = '" + batch + "')"
            assembled.extend(execute(inlined('int_medscape__metrics', fixtures={**fixtures, stage: filtered},
                variables={**variables, 'source_latest_observed_day': '2026-01-20'})))
        def keyed(rows):
            return {r['metric_row_id']: {k: v for k, v in r.items() if k != 'computed_at'} for r in rows}
        self.assertEqual(keyed(assembled), keyed(direct))
        self.assertEqual(len(assembled), len(direct))
        abc = next(r for r in assembled if r['email'] == 'abc@test' and r['npi'] == '1')
        self.assertEqual((abc['n_swaps'], abc['n_flipbacks']), (2, 1))
        self.assertEqual(abc['link_lag_days'], 17)
        self.assertEqual(abc['source_age_days'], 12)

    def test_batch_renderer_filters_before_grouping_and_fixes_source_date(self):
        sql = b.batch_select('SELECT * FROM global_stage', 'SELECT * FROM optout_stage',
                             'SELECT * FROM meta_stage', 'A', '2026-01-20', '2026-02-01')
        self.assertIn("FROM (SELECT * FROM (SELECT * FROM global_stage) WHERE " + b.bucket_sql('email_clean') + " = 'A')", sql)
        self.assertIn("DATE '2026-01-20' AS source_latest_observed_day", sql)
        self.assertNotIn('liveintent_idsync', sql)
        with self.assertRaises(ValueError):
            b.batch_select('s', 'o', 'm', "A'", '2026-01-20', '2026-02-01')

    def test_expected_history_matches_model_record_keys(self):
        data = source_values('stg_medscape__global', [
            dict(email_address='abc@test', npi='1', day='2026-01-01', guid='g'),
            dict(email_address='abc@test', npi='1', day='2026-01-01', guid='g'),
            dict(email_address='abc@test', npi='1', day='2026-01-02', guid='g')])
        fixtures = {'stg_medscape__global': data, 'stg_medscape__optout':
            '(SELECT CAST(NULL AS varchar) AS npi, CAST(NULL AS varchar) AS day, CAST(NULL AS varchar) AS optout_day WHERE false)'}
        stage = inlined('stg_medscape__global', fixtures=fixtures)
        optout = inlined('stg_medscape__optout', fixtures=fixtures)
        expected = execute(b.expected_records_sql(stage, optout))
        direct = execute(inlined('int_medscape__metrics', fixtures=fixtures))
        self.assertEqual(expected, [{k: r[k] for k in b.HISTORY_FIELDS} for r in direct])
        self.assertEqual(expected[0]['observation_count'], 3)

    def test_stored_versions_preserve_complete_model_values(self):
        data = source_values('stg_medscape__global', [
            dict(email_address='abc@test', npi=npi, day=day, guid='g')
            for npi, day in [('1', '2026-01-01'), ('2', '2026-01-02'), ('1', '2026-01-03')]])
        fixtures = {'stg_medscape__global': data, 'stg_medscape__optout':
            "(SELECT 'removed' AS npi, CAST(NULL AS varchar) AS day, CAST(NULL AS varchar) AS optout_day)"}
        versions = p.render_sql("{{ record_versions('stg_medscape__global', exclude_npis_model='stg_medscape__optout') }}",
            ref_overrides={n: '(' + inlined(n, fixtures=fixtures) + ')' for n in fixtures})
        direct = execute(inlined('int_medscape__metrics', fixtures=fixtures))
        cached = execute(inlined('int_medscape__metrics', fixtures=fixtures,
            variables={'medscape_versioned_records': '(' + versions + ')'}))
        def keyed(rows):
            return {r['metric_row_id']: {k: v for k, v in r.items() if k != 'computed_at'} for r in rows}
        self.assertEqual(keyed(direct), keyed(cached))


if __name__ == '__main__':
    unittest.main()
