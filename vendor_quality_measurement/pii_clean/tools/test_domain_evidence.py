#!/usr/bin/env python3
"""Per-source domain aggregates over synthetic links."""
import unittest

import pipeline as p
from test_models import execute, literal


def fixture_sql():
    rows = [('a@hosp.example', '1', 'institutional', 'NY', ['F1', 'F2']),
            ('b@hosp.example', '2', 'institutional', 'NY', ['F1']),
            ('c@hosp.example', '3', 'institutional', 'CA', []),
            ('d@hosp.example', '3', 'institutional', 'CA', []),
            ('x@gmail.example', '1', 'free', 'NY', ['F1']),
            ('y@gmail.example', '4', 'free', None, []),
            ('p@tie.example', '5', 'custom', 'TX', ['F8']),
            ('q@tie.example', '6', 'custom', 'OH', ['F9']),
            ('nodomain', '7', 'unknown', None, [])]
    def array(values):
        return 'cast(ARRAY[' + ', '.join(literal(v) for v in values) + '] AS array(varchar))'
    body = ', '.join('(' + ', '.join([literal('src'), literal(e), literal(n), literal(c), literal(s), array(f)]) + ')'
                     for e, n, c, s, f in rows)
    # The same domain in another source never mixes into 'src'.
    body += ", ('other', 'z@hosp.example', '9', 'institutional', 'FL', ARRAY['F1'])"

    links = ('(SELECT * FROM (VALUES ' + body + ') AS t(source, email, npi, email_domain_class, facility_primary_state, facility_npi_values))')
    return p.render_sql("WITH links AS " + links + " {{ domain_evidence_records('links') }}")


class DomainEvidenceTests(unittest.TestCase):
    def test_domain_aggregates(self):
        rows = {r['email']: r for r in execute(fixture_sql())}
        other = rows.pop('z@hosp.example')
        self.assertEqual((other['source'], other['domain_npi_count'], other['domain_top_state_share']), ('other', 1, 1.0))
        self.assertEqual(len(rows), 9)
        h = rows['a@hosp.example']
        self.assertEqual((h['email_domain'], h['domain_email_count'], h['domain_npi_count']), ('hosp.example', 4, 3))
        self.assertEqual((h['domain_npis_with_state'], h['domain_state_count']), (3, 2))
        self.assertAlmostEqual(h['domain_top_state_share'], 2 / 3)
        self.assertEqual((h['domain_npis_with_facility'], h['domain_top_facility_npi']), (2, 'F1'))
        self.assertEqual(h['domain_top_facility_share'], 1.0)
        for email in ['b@hosp.example', 'c@hosp.example', 'd@hosp.example']:
            for field in ['domain_npi_count', 'domain_top_facility_npi', 'domain_top_state_share']:
                self.assertEqual(rows[email][field], h[field])
        free = rows['x@gmail.example']
        self.assertEqual((free['domain_email_count'], free['domain_npi_count']), (2, 2))
        for field in ['domain_npis_with_state', 'domain_state_count', 'domain_top_state_share',
                      'domain_npis_with_facility', 'domain_top_facility_npi', 'domain_top_facility_share']:
            self.assertIsNone(free[field], field)
        tie = rows['p@tie.example']
        self.assertEqual((tie['domain_state_count'], tie['domain_top_state_share']), (2, 0.5))
        self.assertEqual((tie['domain_top_facility_npi'], tie['domain_top_facility_share']), ('F9', 0.5))
        none = rows['nodomain']
        self.assertIsNone(none['email_domain'])
        self.assertIsNone(none['domain_npi_count'])
        self.assertEqual({r['domain_evidence_version'] for r in rows.values()}, {'domain_evidence_v1'})

    def test_integrity_check_passes_and_detects_corruption(self):
        template = (p.ROOT / 'tests/domain_evidence.sql').read_text()
        good = fixture_sql()
        self.assertEqual(execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + good + ')'})), [])
        bad = 'SELECT * REPLACE (999 AS domain_npis_with_state) FROM (' + good + ')'
        self.assertTrue(execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + bad + ')'})))


if __name__ == '__main__':
    unittest.main()
