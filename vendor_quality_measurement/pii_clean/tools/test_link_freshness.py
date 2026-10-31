"""Freshness uses vendor-relative link history without losing source records."""
from datetime import date
import re
import unittest

import pipeline as p
from test_models import execute


def fixture_sql(as_of='2026-10-30'):
    # Same email across NPIs/vendors, repeated positions, mixed dates and future dates.
    records = """SELECT * FROM (VALUES
        ('dated', 'x@example.test', '1', 'old', DATE '2026-10-10'),
        ('dated', 'x@example.test', '1', 'recent', DATE '2026-10-28'),
        ('dated', 'x@example.test', '1', 'repeat-position', DATE '2026-10-28'),
        ('dated', 'x@example.test', '1', 'undated-same-link', CAST(NULL AS date)),
        ('dated', 'x@example.test', '2', 'lagging', DATE '2026-10-10'),
        ('dated', 'y@example.test', '1', 'undated-link', CAST(NULL AS date)),
        ('old-feed', 'x@example.test', '1', 'old-feed-link', DATE '2026-09-30'),
        ('unknown', 'x@example.test', '1', 'unknown', CAST(NULL AS date)),
        ('future', 'x@example.test', '1', 'future', DATE '2026-11-01'),
        ('future', 'y@example.test', '2', 'past-in-future-feed', DATE '2026-10-10')
    ) AS t(source, email, npi, metric_row_id, last_seen_day)"""
    return p.render_sql("WITH records AS (" + records + "), evaluated AS ("
                        "{{ link_freshness_records('records') }}) SELECT * FROM evaluated",
                        {'link_freshness_as_of_day': as_of})


def check_fixture(rows):
    by_id = {r['metric_row_id']: r for r in rows}
    assert len(rows) == len(by_id) == 10
    for key in ('old', 'recent', 'repeat-position', 'undated-same-link'):
        r = by_id[key]
        assert str(r['link_last_observed_day']) == '2026-10-28', r
        assert (r['source_age_days'], r['link_lag_days']) == (2, 0), r
    assert str(by_id['old']['last_seen_day']) == '2026-10-10'
    assert by_id['undated-same-link']['last_seen_day'] is None
    assert (by_id['lagging']['source_age_days'], by_id['lagging']['link_lag_days']) == (2, 18)
    assert (by_id['old-feed-link']['source_age_days'], by_id['old-feed-link']['link_lag_days']) == (30, 0)
    assert by_id['undated-link']['source_age_days'] == 2
    assert by_id['undated-link']['link_lag_days'] is None
    for key in ('unknown', 'future', 'past-in-future-feed'):
        assert by_id[key]['source_age_days'] is None
        assert by_id[key]['link_lag_days'] is None
    assert str(by_id['future']['source_latest_observed_day']) == '2026-11-01'
    assert by_id['unknown']['source_latest_observed_day'] is None
    assert all(str(r['link_freshness_as_of_day']) == '2026-10-30' for r in rows)


class LinkFreshnessTests(unittest.TestCase):
    def test_link_scope_missing_dates_future_dates_and_record_preservation(self):
        check_fixture(execute(fixture_sql()))

    def test_evaluation_date_only_changes_age_and_future_eligibility(self):
        rows = {r['metric_row_id']: r for r in execute(fixture_sql('2026-11-02'))}
        self.assertEqual(rows['old']['source_age_days'], 5)
        self.assertEqual(rows['lagging']['link_lag_days'], 18)
        self.assertEqual(rows['future']['source_age_days'], 1)
        self.assertEqual(rows['past-in-future-feed']['link_lag_days'], 22)
        self.assertEqual(rows['old']['link_last_observed_day'], date(2026, 10, 28))

    def test_independent_integrity_query_detects_each_corrupted_field(self):
        sql = fixture_sql()
        template = (p.ROOT / 'tests/link_freshness.sql').read_text()
        def check(records):
            return execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL},
                                        {p.FINAL_MODEL: '(' + records + ')'}))
        self.assertEqual(check(sql), [])
        replacements = {
            'link_freshness_as_of_day': 'CAST(NULL AS date)',
            'source_latest_observed_day': "DATE '2000-01-01'",
            'link_last_observed_day': "DATE '2000-01-01'",
            'source_age_days': 'cast(0 AS bigint)',
            'link_lag_days': 'cast(0 AS bigint)',
        }
        columns = list(execute(sql)[0])
        for field, expression in replacements.items():
            with self.subTest(field=field):
                projection = ', '.join(expression + ' AS ' + c if c == field else c for c in columns)
                self.assertTrue(check('SELECT ' + projection + ' FROM (' + sql + ')'))

    def test_statistics_use_links_not_repeated_records(self):
        documented = (p.ROOT / 'sql/statistics/20_link_freshness.sql').read_text()
        # Documentation pins its measured snapshot; live profiles use the current table.
        unpinned, pins = re.subn(re.escape(p.relation(p.FINAL_MODEL)) + r' FOR VERSION AS OF [0-9]+\b',
                                 p.relation(p.FINAL_MODEL), documented)
        self.assertEqual(pins, 1)
        self.assertEqual(p.render_profile('link_freshness_profile.sql') + '\n',
                         unpinned)
        profile = p.render_profile('link_freshness_profile.sql').replace(p.relation(p.FINAL_MODEL), '(' + fixture_sql() + ')')
        rows = {r['source']: r for r in execute(profile)}
        self.assertEqual(rows['dated']['metric_rows'], 6)
        self.assertEqual(rows['dated']['distinct_links'], 3)
        self.assertEqual(rows['dated']['known_lag_links'], 2)
        self.assertEqual(rows['dated']['p50_lag_days'], 0)
        self.assertEqual(rows['dated']['p95_lag_days'], 18)
        self.assertEqual(rows['dated']['links_at_source_latest_day'], 1)
        self.assertEqual(rows['dated']['latest_day_pct_of_known_lag_links'], 50)
        self.assertEqual(rows['unknown']['undated_link_pct'], 100)
        self.assertIsNone(rows['unknown']['latest_day_pct_of_known_lag_links'])
        self.assertEqual(rows['future']['unknown_lag_links'], 2)
        self.assertIsNone(rows['future']['p50_lag_days'])
        self.assertIsNone(rows['unknown']['p95_lag_days'])


if __name__ == '__main__':
    unittest.main()
