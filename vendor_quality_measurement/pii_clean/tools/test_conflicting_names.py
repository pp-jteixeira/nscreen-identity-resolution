#!/usr/bin/env python3
"""Record-local names, temporal overlap and nullable cross-NPI comparisons."""
import unittest

import pipeline as p
from test_models import execute, inlined
from test_record_grain import source_values


# Each observation: NPI, day, first, last, expected flag for that exact record.
CASES = {
    'nickname': [('1', '01', 'ROBERT', 'SMITH', True), ('2', '01', 'BOB', 'SMITH', True)],
    'surname_token': [('1', '01', 'JOHN', 'SMITH-JONES', True), ('2', '01', 'JOHN', 'SMITH', True)],
    'different': [('1', '01', 'JOHN', 'SMITH', False), ('2', '01', 'JOHN', 'JONES', False)],
    'missing': [('1', '01', 'JOHN', 'SMITH', None), ('2', '01', None, None, None)],
    'partial': [('1', '01', 'JOHN', 'SMITH', None), ('2', '01', 'JOHN', None, None)],
    'reassigned_only': [('1', '01', 'JOHN', 'SMITH', None), ('2', '02', 'JOHN', 'SMITH', None)],
    'later_conflict': [('1', '01', 'JOHN', 'SMITH', None), ('2', '02', 'JOHN', 'SMITH', False),
                       ('3', '02', 'JANE', 'JONES', False)],
    'no_inferred_overlap': [('1', '01', 'JOHN', 'SMITH', None), ('1', '03', 'JOHN', 'SMITH', None),
                            ('2', '02', 'JOHN', 'SMITH', None)],
    'same_npi': [('1', '01', 'JOHN', 'SMITH', None), ('1', '01', 'JOHN', 'JONES', None)],
    'changed_name': [('1', '01', 'JOHN', 'SMITH', False), ('1', '02', 'JANE', 'JONES', True),
                     ('2', '01', 'JANE', 'JONES', False), ('2', '02', 'JANE', 'JONES', False)],
    'match_and_missing': [('1', '01', 'JOHN', 'SMITH', True), ('2', '01', 'JOHN', 'SMITH', True),
                          ('3', '01', None, None, None)],
    'mismatch_and_missing': [('1', '01', 'JOHN', 'SMITH', None), ('2', '01', 'JANE', 'JONES', None),
                             ('3', '01', None, None, None)],
    'unknown_dates': [('1', None, 'JOHN', 'SMITH', None), ('2', None, 'JOHN', 'SMITH', None)],
}
# NPI 2's otherwise-identical changed_name rows combine; its day-2 match wins.


def dated_fixture(debug=False):
    rows = [{'email_address': case + '@example.test', 'npi': npi,
             'day': '2026-01-' + day if day else None, 'first_name': first, 'last_name': last}
            for case, observations in CASES.items() for npi, day, first, last, _ in observations]
    rows += [dict(rows[0])]
    return inlined('int_medscape__metrics', variables={'debug': debug}, fixtures={
        'stg_medscape__global': source_values('stg_medscape__global', rows)})


def check_dated(rows):
    expected = {}
    for case, observations in CASES.items():
        for npi, _, first, last, flag in observations:
            expected[(case, npi, first, last)] = flag
    expected[('changed_name', '2', 'JANE', 'JONES')] = True
    assert len(rows) == len(expected)
    assert len({r['metric_row_id'] for r in rows}) == len(rows)
    import json
    for r in rows:
        raw = json.loads(r['record_payload'])
        key = (r['email'].split('@')[0], r['npi'], raw['first_name'], raw['last_name'])
        assert r['conflicting_npis_share_name'] is expected[key], (key, r['conflicting_npis_share_name'])
        peers = r['conflicting_npi_name_comparisons']
        assert bool(peers) == (r['has_conflict_linkage'] is True), key
        for peer in peers:
            # DuckDB returns dicts; Trino's named rows support positional access.
            npi, days = (peer['npi'], peer['conflict_days']) if isinstance(peer, dict) else peer[:2]
            assert npi != r['npi'] and days, key
            assert set(days).issubset(r['conflict_days']), key


def undated_fixture():
    return inlined('int_drdb__metrics', fixtures={
        'stg_drdb__npi': source_values('stg_drdb__npi', [
            {'emailaddress':'nickname@example.test', 'npi':'1', 'firstname':'ROBERT', 'lastname':'SMITH'},
            {'emailaddress':'different@example.test', 'npi':'1', 'firstname':'JOHN', 'lastname':'SMITH'},
            {'emailaddress':'missing@example.test', 'npi':'1', 'firstname':'JOHN', 'lastname':'SMITH'}]),
        'stg_drdb__enrich': source_values('stg_drdb__enrich', [
            {'email':'nickname@example.test', 'npi':'2', 'name':'BOB SMITH'},
            {'email':'different@example.test', 'npi':'2', 'name':'JANE JONES'},
            {'email':'missing@example.test', 'npi':'2', 'name':None}])})


def check_undated(rows):
    assert len(rows) == 6
    for r in rows:
        assert r['conflicting_npis_share_name'] is {'nickname':True, 'different':False, 'missing':None}[r['email'].split('@')[0]]
        assert r['conflict_days'] == [] and r['has_conflict_linkage'] is True


def isolation_fixture():
    rows = [{'email_address':'isolation@example.test', 'npi':npi, 'day':'2026-01-01',
             'first_name':first, 'last_name':last}
            for npi, first, last in [('1','JOHN','SMITH'), ('2','JANE','JONES')]]
    a = inlined('int_medscape__metrics', fixtures={
        'stg_medscape__global':source_values('stg_medscape__global', rows)})
    # Names on opposite NPIs match across sources only, which must not affect either flag.
    b = a.replace("CAST('medscape' AS varchar)", "CAST('haymarket' AS varchar)")
    b = b.replace("'JOHN'", "'TEMP'").replace("'JANE'", "'JOHN'").replace("'TEMP'", "'JANE'")
    b = b.replace("'SMITH'", "'TEMP'").replace("'JONES'", "'SMITH'").replace("'TEMP'", "'JONES'")
    return p.render_sql("WITH records AS (SELECT * FROM (" + a + ") UNION ALL SELECT * FROM (" + b + ")), measured AS ({{ name_consistency_metrics('records') }}) SELECT * FROM measured")


def check_isolation(rows):
    assert len(rows) == 4
    assert {r['source'] for r in rows} == {'medscape','haymarket'}
    assert all(r['conflicting_npis_share_name'] is False for r in rows)
    assert all(len(r['conflicting_npi_name_comparisons']) == 1 for r in rows)


FIXTURES = {'dated_conflicting_names': (dated_fixture, check_dated),
            'undated_conflicting_names': (undated_fixture, check_undated),
            'conflicting_name_vendor_isolation': (isolation_fixture, check_isolation)}


class ConflictingNamesTests(unittest.TestCase):
    def test_fixtures(self):
        for name, (make_sql, check) in FIXTURES.items():
            with self.subTest(case=name):
                check(execute(make_sql()))

    def test_debug_preserves_results(self):
        expected = {r['metric_row_id']:r for r in execute(dated_fixture())}
        for r in execute(dated_fixture(debug=True)):
            for field in ('conflicting_npis_share_name', 'conflicting_npi_name_comparisons'):
                self.assertEqual(r[field], expected[r['metric_row_id']][field])

    def test_independent_check_rejects_corruption(self):
        correct = dated_fixture()
        fields = list(execute(correct)[0])
        template = (p.ROOT / 'tests/conflicting_names.sql').read_text()
        def validate(sql):
            return execute(p.render_sql(template, {'metric_model':'pii_clean'}, {'pii_clean':'(' + sql + ')'}))
        self.assertEqual(validate(correct), [])
        projection = ', '.join('false AS ' + c if c == 'conflicting_npis_share_name' else c for c in fields)
        self.assertTrue(validate(f'SELECT {projection} FROM ({correct})'))


if __name__ == '__main__':
    unittest.main()
