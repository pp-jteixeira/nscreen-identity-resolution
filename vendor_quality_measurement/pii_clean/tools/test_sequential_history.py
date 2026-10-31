"""Causal daily histories, content versions and registration-scoped supersession."""
import json
import unittest

import pipeline as p
from test_models import execute, literal, inlined
from test_record_grain import source_values


def fixture_sql(rows, day='2026-01-03', minimum=3):
    values = []
    for i, row in enumerate(rows):
        source, email, npi, days, guid = row[:5]
        missing = row[5] if len(row) > 5 else 0
        values.append('(' + ','.join([literal(source), literal(email), literal(npi), literal(str(i)),
            literal(json.dumps({'guid': guid})),
            'cast(ARRAY[' + ','.join("DATE '" + d + "'" for d in days) + '] AS array(date))', str(missing)]) + ')')
    records = 'SELECT * FROM (VALUES ' + ','.join(values) + ') AS t(source,email,npi,metric_row_id,record_payload,observed_days,undated_observation_count)'
    return p.render_sql("WITH records AS (" + records + "), sequence AS ("
        "{{ sequential_history_records('records', 'records') }}), evaluated AS ("
        "{{ registration_supersession_records('sequence', 'medscape', 'records') }}) SELECT * FROM evaluated ORDER BY cast(metric_row_id AS bigint)",
        {'sequence_as_of_day': day, 'stability_min_versions': minimum})


def scenario(source='medscape'):
    return [(source, 'abc', 'n1', ['2026-01-01', '2026-01-03'], 'g'),
            (source, 'abc', 'n2', ['2026-01-02', '2026-01-03'], 'g'),
            (source, 'abc', 'n3', ['2026-01-02'], 'g')]


class SequentialHistoryTests(unittest.TestCase):
    def test_agreed_multinpi_scenario_and_duplicate_rows(self):
        rows = execute(fixture_sql(scenario() + scenario()[:1]))
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertEqual([row[k] for k in ['n_versions_observed', 'n_npis_window', 'n_npi_changes', 'n_swaps', 'n_flipbacks']], [3, 3, 2, 2, 1])
            self.assertTrue(row['stability_history_sufficient'])
            evidence = row['sequence_daily_evidence']
            self.assertEqual([(d['versions_observed'], d['npis_observed'], d['changes'], d['swaps'], d['flipbacks']) for d in evidence],
                             [(1, 1, 0, 0, 0), (2, 3, 1, 1, 0), (3, 3, 2, 2, 1)])
            self.assertEqual(evidence[2]['returned_npis'], ['n1'])
            self.assertEqual(row['registration_link_status'], 'ambiguous_latest')

    def test_cutoff_causality_and_no_future_distinct_counts(self):
        for day, expected in [('01', (1, 1, 0, 0)), ('02', (2, 3, 1, 0)), ('03', (3, 3, 2, 1))]:
            row = execute(fixture_sql(scenario(), day='2026-01-' + day))[0]
            self.assertEqual(tuple(row[k] for k in ['n_versions_observed', 'n_npis_window', 'n_swaps', 'n_flipbacks']), expected)
            self.assertEqual(len(row['sequence_daily_evidence']), int(day))
        prefix = execute(fixture_sql(scenario(), day='2026-01-02'))[0]['sequence_daily_evidence']
        full = execute(fixture_sql(scenario()))[0]['sequence_daily_evidence']
        self.assertEqual(prefix, full[:2])

    def test_repeated_content_returns_and_absent_email(self):
        rows = [('healthlink', 'abc', 'A', ['2026-01-01', '2026-01-02', '2026-01-05'], 'g'),
                ('healthlink', 'abc', 'B', ['2026-01-04'], 'g'),
                ('healthlink', 'other', 'Z', ['2026-01-01', '2026-01-02', '2026-01-03', '2026-01-04', '2026-01-05'], 'x')]
        a = execute(fixture_sql(rows, '2026-01-05'))[0]
        self.assertEqual((a['n_versions_observed'], a['n_swaps'], a['n_flipbacks']), (3, 2, 1))
        self.assertEqual([d['versions_observed'] for d in a['sequence_daily_evidence']], [1, 1, 2, 3])
        # An identical delivery repeated after different content remains a new version.
        self.assertEqual(str(a['sequence_daily_evidence'][2]['previous_observed_day']), '2026-01-02')

    def test_addition_removal_without_swap_and_return_without_removal(self):
        rows = [('medscape', 'abc', 'A', ['2026-01-01', '2026-01-02', '2026-01-04'], 'g'),
                ('medscape', 'abc', 'B', ['2026-01-02', '2026-01-03', '2026-01-04'], 'g')]
        r = execute(fixture_sql(rows, '2026-01-04'))[0]
        self.assertEqual((r['n_npi_changes'], r['n_swaps'], r['n_flipbacks']), (3, 0, 0))

    def test_source_email_isolation_unknown_dates_and_threshold(self):
        rows = scenario() + [('other', 'abc', 'A', [], 'g', 1),
                            ('medscape', 'else', 'A', ['2026-01-01'], 'h'),
                            ('medscape', 'abc', 'unknown', [], 'u', 1)]
        result = execute(fixture_sql(rows, minimum=4))
        self.assertTrue(all(not r['stability_history_sufficient'] for r in result))
        unknown = result[3]
        self.assertIsNone(unknown['n_swaps'])
        self.assertEqual(unknown['sequence_daily_evidence'], [])
        self.assertEqual(unknown['sequence_history_status'], 'no_dated_history')
        self.assertEqual(result[0]['sequence_history_status'], 'incomplete_dates')
        self.assertEqual(result[4]['n_versions_observed'], 1)

    def test_registration_supersession_reappearance_and_missing_guid(self):
        rows = [('medscape', 'abc', 'A', ['2026-01-01'], 'g'),
                ('medscape', 'abc', 'B', ['2026-01-02', '2026-01-03'], 'g'),
                ('medscape', 'abc', 'A', ['2026-01-03'], 'another'),
                ('medscape', 'abc', 'C', ['2026-01-01'], None)]
        result = execute(fixture_sql(rows))
        self.assertEqual([r['registration_link_status'] for r in result], ['superseded', 'latest_observed', 'latest_observed', 'unknown'])
        self.assertEqual(result[0]['registration_superseded_by_npis'], ['B'])
        self.assertEqual(str(result[0]['registration_superseded_since_day']), '2026-01-02')
        self.assertEqual(execute(fixture_sql(rows, '2026-01-01'))[0]['registration_link_status'], 'latest_observed')
        rows[0] = ('medscape', 'abc', 'A', ['2026-01-01', '2026-01-04'], 'g')
        result = execute(fixture_sql(rows, '2026-01-04'))
        self.assertEqual(result[0]['registration_link_status'], 'latest_observed')
        self.assertEqual(result[1]['registration_link_status'], 'superseded')
        self.assertIsNone(result[0]['registration_superseded_since_day'])

    def test_undated_registration_prevents_supersession(self):
        rows = [('medscape', 'abc', 'A', ['2026-01-01'], 'g'),
                ('medscape', 'abc', 'B', ['2026-01-02'], 'g', 1)]
        self.assertEqual({r['registration_link_status'] for r in execute(fixture_sql(rows))}, {'unknown'})

    def test_stored_integrity_and_corrupted_counts(self):
        sql = fixture_sql(scenario())
        template = (p.ROOT / 'tests/sequential_history.sql').read_text()
        def check(query):
            return execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL},
                                        {p.FINAL_MODEL: '(' + query + ')'}))
        self.assertEqual(check(sql), [])
        columns = list(execute(sql)[0])
        for field in ['n_versions_observed', 'n_npis_window', 'n_npi_changes', 'n_swaps', 'n_flipbacks']:
            projection = ','.join('cast(99 AS bigint) AS ' + c if c == field else c for c in columns)
            self.assertTrue(check('SELECT ' + projection + ' FROM (' + sql + ')'))
        unknown = fixture_sql([('medscape', 'abc', 'A', [], None, 1)])
        self.assertEqual(check(unknown), [])

    def test_profiles_use_distinct_email_and_registration_denominators(self):
        sql = fixture_sql(scenario() + scenario()[:1])
        report = p.render_profile('sequential_history_profile.sql').replace(p.relation(p.FINAL_MODEL), '(' + sql + ')')
        row = execute(report)[0]
        self.assertEqual((row['emails'], row['emails_with_swaps'], row['emails_with_flipbacks']), (1, 1, 1))
        self.assertEqual(row['swap_pct_of_dated_emails'], 100)
        report = p.render_profile('registration_supersession_profile.sql').replace(p.relation(p.FINAL_MODEL), '(' + sql + ')')
        self.assertEqual(execute(report)[0]['registration_links'], 3)

    def test_medscape_eligibility_and_payload_guid_in_complete_model(self):
        data = [{'npi': n, 'day': day, 'guid': 'g', 'email_address': 'abc@test'}
                for n, day in [('1', '2026-01-01'), ('2', '2026-01-02'), ('1', '2026-01-03')]]
        rows = execute(inlined('int_medscape__metrics', fixtures={'stg_medscape__global': source_values('stg_medscape__global', data)},
                               variables={'sequence_as_of_day': '2026-01-03'}))
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['n_swaps'] for r in rows}, {2})
        self.assertEqual({r['n_flipbacks'] for r in rows}, {1})
        self.assertEqual({r['registration_guid'] for r in rows}, {'g'})

    def test_materialized_base_matches_direct_metrics_and_order(self):
        for source in ['medscape', 'healthlink', 'endato']:
            model = 'int_' + source + '__metrics'
            direct = {r['metric_row_id']: r for r in execute(inlined(model))}
            base = inlined(model, variables={'defer_sequential_history': True})
            staged = {r['metric_row_id']: r for r in execute(p.history_from_stored_records('(' + base + ')', source))}
            self.assertEqual(direct.keys(), staged.keys())
            for key in direct:
                self.assertEqual(list(direct[key]), list(staged[key]))
                self.assertEqual({k: v for k, v in direct[key].items() if k != 'computed_at'},
                                 {k: v for k, v in staged[key].items() if k != 'computed_at'})

    def test_materialized_core_matches_quality_and_history(self):
        for source in ['medscape', 'healthlink', 'endato']:
            model = 'int_' + source + '__metrics'
            direct = {r['metric_row_id']: r for r in execute(inlined(model))}
            core = inlined(model, variables={'defer_quality_enrichments': True})
            quality = p.quality_from_stored_records('(' + core + ')', source)
            for name in ['stg_medscape__meta', 'stg_healthlink__hcp', 'stg_quantummedica__hcpmeta']:
                quality = quality.replace(p.relation(name), '(' + inlined(name) + ')')
            quality = quality.replace('FROM iceberg.npi.nppes_npidata_latest',
                "FROM (SELECT CAST(NULL AS bigint) AS npi, CAST(NULL AS varchar) AS entity_type_code WHERE false)")
            staged = {r['metric_row_id']: r for r in execute(p.history_from_stored_records('(' + quality + ')', source))}
            self.assertEqual(direct.keys(), staged.keys())
            for key in direct:
                self.assertEqual(list(direct[key]), list(staged[key]))
                self.assertEqual({k: v for k, v in direct[key].items() if k != 'computed_at'},
                                 {k: v for k, v in staged[key].items() if k != 'computed_at'})


if __name__ == '__main__':
    unittest.main()
