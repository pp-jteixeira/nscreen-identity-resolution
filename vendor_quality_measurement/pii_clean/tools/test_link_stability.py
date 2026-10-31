"""Distinct dated history measures presence and overlap without changing record grain."""
import re
import unittest

import pipeline as p
from test_models import execute


def fixture_sql():
    records = """SELECT * FROM (VALUES
        ('vendor', 'shared@test', 'A', 'a1', ARRAY[DATE '2020-01-01', DATE '2020-01-02', DATE '2020-01-03'], ARRAY[DATE '2020-01-02'], 0),
        ('vendor', 'shared@test', 'A', 'a2', ARRAY[DATE '2020-01-03', DATE '2020-01-05'], CAST(ARRAY[] AS array(date)), 0),
        ('vendor', 'shared@test', 'A', 'a-position', ARRAY[DATE '2020-01-02'], ARRAY[DATE '2020-01-02'], 0),
        ('vendor', 'shared@test', 'B', 'b', ARRAY[DATE '2020-01-02', DATE '2020-01-04'], ARRAY[DATE '2020-01-02'], 0),
        ('other', 'shared@test', 'A', 'other-source', ARRAY[DATE '2020-02-01'], CAST(ARRAY[] AS array(date)), 0),
        ('mixed', 'mixed@test', 'A', 'mixed-known', ARRAY[DATE '2020-01-01', DATE '2020-02-01'], CAST(ARRAY[] AS array(date)), 0),
        ('mixed', 'mixed@test', 'B', 'undated-peer', CAST(ARRAY[] AS array(date)), CAST(ARRAY[] AS array(date)), 2),
        ('mixed', 'mixed@test', 'A', 'mixed-undated', CAST(ARRAY[] AS array(date)), CAST(ARRAY[] AS array(date)), 1),
        ('unknown', 'shared@test', 'A', 'unknown-a', CAST(ARRAY[] AS array(date)), CAST(ARRAY[] AS array(date)), 1),
        ('unknown', 'shared@test', 'B', 'unknown-b', CAST(ARRAY[] AS array(date)), CAST(ARRAY[] AS array(date)), 1),
        ('vendor', 'different@test', 'A', 'other-email', ARRAY[DATE '2021-01-01'], CAST(ARRAY[] AS array(date)), 0)
    ) AS t(source, email, npi, metric_row_id, observed_days, conflict_days, undated_observation_count)"""
    return p.render_sql("WITH records AS (" + records + "), evaluated AS ("
                        "{{ link_stability_records('records') }}) SELECT * FROM evaluated")


def check_fixture(rows):
    by_id = {r['metric_row_id']: r for r in rows}
    assert len(rows) == len(by_id) == 11
    for key in ('a1', 'a2', 'a-position'):
        r = by_id[key]
        assert (r['email_observed_day_count'], r['link_observed_day_count'], r['link_conflict_day_count']) == (5, 4, 1), r
        assert (r['link_presence_share'], r['link_overlap_share']) == (0.8, 0.25), r
        assert not r['link_stability_has_undated_observations']
    assert (by_id['b']['link_presence_share'], by_id['b']['link_overlap_share']) == (0.4, 0.5)
    for key in ('other-source', 'other-email'):
        assert (by_id[key]['email_observed_day_count'], by_id[key]['link_presence_share'], by_id[key]['link_overlap_share']) == (1, 1, 0)
    for key in ('mixed-known', 'mixed-undated', 'undated-peer'):
        assert by_id[key]['email_observed_day_count'] == 2
        assert by_id[key]['link_stability_has_undated_observations']
    for key in ('mixed-known', 'mixed-undated'):
        assert (by_id[key]['link_observed_day_count'], by_id[key]['link_presence_share'], by_id[key]['link_overlap_share']) == (2, 1, 0)
    for key in ('unknown-a', 'unknown-b', 'undated-peer'):
        r = by_id[key]
        assert r['link_observed_day_count'] == r['link_conflict_day_count'] == 0
        assert r['link_presence_share'] is None and r['link_overlap_share'] is None
        assert r['link_stability_has_undated_observations']
    assert by_id['unknown-a']['email_observed_day_count'] == 0
    assert len(by_id['a1']['observed_days']) == 3
    assert by_id['mixed-undated']['observed_days'] == []


class LinkStabilityTests(unittest.TestCase):
    def test_scope_distinct_days_overlap_and_unknown_history(self):
        check_fixture(execute(fixture_sql()))

    def test_independent_invariant_detects_each_corrupted_field(self):
        sql = fixture_sql()
        template = (p.ROOT / 'tests/link_stability.sql').read_text()
        def check(records):
            return execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL},
                                        {p.FINAL_MODEL: '(' + records + ')'}))
        self.assertEqual(check(sql), [])
        replacements = {c: 'cast(99 AS bigint)' for c in ('email_observed_day_count', 'link_observed_day_count', 'link_conflict_day_count')}
        replacements.update(link_presence_share='cast(0 AS double)', link_overlap_share='cast(0 AS double)',
                            link_stability_has_undated_observations='false')
        columns = list(execute(sql)[0])
        for field, value in replacements.items():
            with self.subTest(field=field):
                projection = ', '.join(value + ' AS ' + c if c == field else c for c in columns)
                self.assertTrue(check('SELECT ' + projection + ' FROM (' + sql + ')'))

    def test_population_counts_links_and_excludes_unknown_shares(self):
        documented = (p.ROOT / 'sql/statistics/21_link_stability.sql').read_text()
        # Documentation pins its measured snapshot; live profiles use the current table.
        unpinned, pins = re.subn(re.escape(p.relation(p.FINAL_MODEL)) + r' FOR VERSION AS OF [0-9]+\b',
                                 p.relation(p.FINAL_MODEL), documented)
        self.assertEqual(pins, 1)
        self.assertEqual(p.render_profile('link_stability_profile.sql') + '\n',
                         unpinned)
        sql = p.render_profile('link_stability_profile.sql').replace(p.relation(p.FINAL_MODEL), '(' + fixture_sql() + ')')
        rows = {r['source']: r for r in execute(sql)}
        self.assertEqual(rows['vendor']['metric_rows'], 5)
        self.assertEqual(rows['vendor']['distinct_links'], 3)
        self.assertEqual(rows['vendor']['full_presence_links'], 1)
        self.assertEqual(rows['vendor']['links_with_overlap'], 2)
        self.assertAlmostEqual(rows['vendor']['mean_presence_pct_of_dated_links'], 100 * (0.8 + 0.4 + 1) / 3)
        self.assertEqual(rows['mixed']['links_with_incomplete_email_dates'], 2)
        self.assertEqual(rows['mixed']['undated_links'], 1)
        self.assertIsNone(rows['unknown']['mean_presence_pct_of_dated_links'])
        self.assertIsNone(rows['unknown']['overlap_pct_of_dated_links'])


if __name__ == '__main__':
    unittest.main()
