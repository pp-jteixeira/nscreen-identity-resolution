#!/usr/bin/env python3
"""Cross-source agreement over synthetic links."""
import unittest

import pipeline as p
from test_models import execute, literal


def names(*pairs):
    items = ', '.join("CAST(ROW(%s, %s, ARRAY[%s]) AS ROW(first_name varchar, last_name varchar, first_variants array(varchar)))"
                      % (literal(f), literal(l), literal(f)) for f, l in pairs)
    return 'cast(ARRAY[%s] AS array(row(first_name varchar, last_name varchar, first_variants array(varchar))))' % items if items else \
        'cast(ARRAY[] AS array(row(first_name varchar, last_name varchar, first_variants array(varchar))))'


def states(*values):
    return 'cast(ARRAY[%s] AS array(varchar))' % ', '.join(literal(v) for v in values)


ROWS = [
    # shared email and NPI: name agrees with b, disagrees with c, state agrees with b, disagrees with c
    ('a', 'x@e.example', '1', names(('JOHN', 'SMITH')), states('NY')),
    ('b', 'x@e.example', '1', names(('JOHN', 'SMITH')), states('NY', 'NJ')),
    ('c', 'x@e.example', '1', names(('MARY', 'JONES')), states('CA')),
    # d reports the email with another NPI only
    ('d', 'x@e.example', '2', names(('JOHN', 'SMITH')), states('NY')),
    # unknown names and states leave state and name arrays empty
    ('a', 'y@e.example', '5', names(), states()),
    ('b', 'y@e.example', '5', names(('JOHN', 'SMITH')), states('NY')),
    # nobody else has this email
    ('a', 'solo@e.example', '7', names(('JOHN', 'SMITH')), states('NY')),
    # empty NPI is never compared
    ('a', 'z@e.example', '', names(), states()),
    ('b', 'z@e.example', '', names(), states()),
]


def fixture_sql():
    body = ', '.join('(' + ', '.join([literal(s + e + n), literal(s), literal(e), literal(n), nm, st]) + ')'
                     for s, e, n, nm, st in ROWS)
    links = ('(SELECT * FROM (VALUES ' + body + ') AS t(link_id, source, email, npi, source_name_values, source_state_values))')
    return p.render_sql("WITH links AS " + links + " {{ cross_source_evidence_records('links', 'links') }}")


class CrossSourceEvidenceTests(unittest.TestCase):
    def rows(self):
        return {(r['source'], r['email'], r['npi']): r for r in execute(fixture_sql())}

    def test_npi_agreement_and_disagreement(self):
        rows = self.rows()
        a = rows[('a', 'x@e.example', '1')]
        self.assertEqual(a['xsrc_npi_agree_sources'], ['b', 'c'])
        self.assertEqual(a['xsrc_npi_disagree_sources'], ['d'])
        self.assertEqual((a['xsrc_npi_agree_count'], a['xsrc_npi_disagree_count'], a['xsrc_email_source_count']), (2, 1, 3))
        d = rows[('d', 'x@e.example', '2')]
        self.assertEqual((d['xsrc_npi_agree_sources'], d['xsrc_npi_disagree_sources']), ([], ['a', 'b', 'c']))

    def test_state_and_name_use_only_npi_agreeing_sources(self):
        a = self.rows()[('a', 'x@e.example', '1')]
        self.assertEqual((a['xsrc_state_agree_sources'], a['xsrc_state_disagree_sources']), (['b'], ['c']))
        self.assertEqual((a['xsrc_name_agree_sources'], a['xsrc_name_disagree_sources']), (['b'], ['c']))
        d = self.rows()[('d', 'x@e.example', '2')]
        for field in ('xsrc_state_agree_sources', 'xsrc_state_disagree_sources', 'xsrc_name_agree_sources', 'xsrc_name_disagree_sources'):
            self.assertEqual(d[field], [], field)

    def test_unknown_values_and_missing_sources_appear_in_no_array(self):
        rows = self.rows()
        y = rows[('a', 'y@e.example', '5')]
        self.assertEqual(y['xsrc_npi_agree_sources'], ['b'])
        for field in ('xsrc_state_agree_sources', 'xsrc_state_disagree_sources', 'xsrc_name_agree_sources', 'xsrc_name_disagree_sources'):
            self.assertEqual(y[field], [], field)
        solo = rows[('a', 'solo@e.example', '7')]
        self.assertEqual(solo['xsrc_email_source_count'], 0)
        self.assertEqual(solo['xsrc_npi_agree_sources'], [])
        blank = rows[('a', 'z@e.example', '')]
        self.assertEqual((blank['xsrc_npi_agree_sources'], blank['xsrc_email_source_count']), ([], 0))
        self.assertEqual({r['cross_source_evidence_version'] for r in rows.values()}, {'cross_source_evidence_v1'})

    def test_integrity_check_passes_and_detects_corruption(self):
        template = (p.ROOT / 'tests/cross_source_evidence.sql').read_text()
        good = fixture_sql()
        self.assertEqual(execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + good + ')'})), [])
        for corruption in ["999 AS xsrc_npi_agree_count", "ARRAY['a'] AS xsrc_state_agree_sources",
                           "ARRAY['d'] AS xsrc_npi_agree_sources"]:
            bad = 'SELECT * REPLACE (' + corruption + ') FROM (' + good + ')'
            self.assertTrue(execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + bad + ')'})), corruption)


if __name__ == '__main__':
    unittest.main()
