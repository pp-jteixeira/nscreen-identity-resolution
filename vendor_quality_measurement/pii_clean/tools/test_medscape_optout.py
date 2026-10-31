"""Medscape cumulative opt-outs precede all intermediate linkage and evidence metrics."""
import unittest

import pipeline as p
from test_models import execute, inlined
from test_record_grain import source_values


def fixtures(opted_out=True):
    rows = [{'npi': '1', 'day': day, 'guid': 'removed', 'email_address': 'shared@example.test'}
            for day in ['2026-01-01', '2026-01-01', '2026-01-09']]
    rows += [{'npi': '2', 'day': day, 'guid': 'kept', 'email_address': 'shared@example.test'}
             for day in ['2026-01-01', '2026-01-03']]
    rows += [{'npi': '3', 'day': '2026-01-02', 'guid': 'other', 'email_address': 'other@example.test'}]
    # Duplicate, future, invalid and missing dates do not change NPI membership.
    optout = ("(SELECT * FROM (VALUES (' 1 ', '2050-01-01', '2050-01-01'),"
              "('1', 'bad-date', NULL), (NULL, '2026-01-01', NULL), (' ', NULL, NULL)) AS t(npi,day,optout_day))")
    if not opted_out:
        optout = '(SELECT CAST(NULL AS varchar) AS npi, CAST(NULL AS varchar) AS day, CAST(NULL AS varchar) AS optout_day WHERE false)'
    return {'stg_medscape__global': source_values('stg_medscape__global', rows),
            'stg_medscape__optout': optout}


def fixture_sql(debug=False):
    return inlined('int_medscape__metrics', fixtures=fixtures(), variables={'debug': debug})


def check_filtered(rows):
    assert len(rows) == 2
    assert {row['npi'] for row in rows} == {'2', '3'}
    assert len({row['metric_row_id'] for row in rows}) == 2
    kept = next(row for row in rows if row['npi'] == '2')
    assert kept['observation_count'] == 2
    assert kept['observed_day_count'] == 2
    assert kept['email_npi_count'] == 1
    assert kept['has_conflict_linkage'] is False
    assert kept['has_been_reassigned'] is False
    assert kept['conflict_days'] == []
    assert kept['conflicting_npi_vendor_specialty_comparisons'] == []
    assert kept['conflicting_npi_name_comparisons'] == []
    assert str(kept['source_latest_observed_day'])[:10] == '2026-01-03'
    assert kept['email_observed_day_count'] == 2


class MedscapeOptoutTests(unittest.TestCase):
    def test_cumulative_exclusion_recomputes_every_metric_context(self):
        check_filtered(execute(fixture_sql()))
        before = execute(inlined('int_medscape__metrics', fixtures=fixtures(False)))
        self.assertEqual(len(before), 3)
        self.assertTrue(next(r for r in before if r['npi'] == '2')['has_conflict_linkage'])

    def test_staging_preserves_vendor_and_optout_rows(self):
        self.assertEqual(len(execute(inlined('stg_medscape__global', fixtures=fixtures()))), 6)
        optouts = execute(inlined('stg_medscape__optout', fixtures=fixtures()))
        self.assertEqual(len(optouts), 4)
        self.assertEqual(sum(r['npi_clean'] == '1' for r in optouts), 2)
        self.assertEqual(sum(r['npi_clean'] is None for r in optouts), 2)

    def test_debug_output_and_unrelated_vendor_remain_eligible(self):
        check_filtered(execute(fixture_sql(debug=True)))
        other = execute(inlined('int_haymarket__metrics', fixtures=fixtures()))
        self.assertTrue(any(r['npi'] == '123' for r in other))
        self.assertNotIn('stg_medscape__optout', p.source_plan('haymarket'))
        self.assertIn('stg_medscape__optout', p.source_plan('medscape'))

    def test_independent_integrity_rejects_unfiltered_rows(self):
        template = (p.ROOT / 'tests/medscape_optout.sql').read_text()
        optout = p.read_model('stg_medscape__optout', source_overrides={
            p.stage_input('stg_medscape__optout'): fixtures()['stg_medscape__optout']})
        def check(query):
            return execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL},
                {p.FINAL_MODEL: '(' + query + ')', 'stg_medscape__optout': '(' + optout + ')'}))
        self.assertEqual(check(fixture_sql()), [])
        unfiltered = inlined('int_medscape__metrics', fixtures=fixtures(False))
        self.assertEqual(check(unfiltered), [{'source': 'medscape', 'opted_out_metric_rows': 1}])


if __name__ == '__main__':
    unittest.main()
