#!/usr/bin/env python3
"""Name history, fuzzy disagreement and vendor isolation fixtures."""
import unittest
import pipeline as p
from test_models import execute, inlined
from test_record_grain import source_values


CASES = {
    'nickname': ([('1', 'ROBERT', 'SMITH'), ('1', 'BOB', 'SMITH')], 2, False),
    'different': ([('1', 'JOHN', 'SMITH'), ('1', 'JOHN', 'JONES')], 2, True),
    'normalized': ([('1', ' José ', 'Smith'), ('1', 'JOSE', 'SMITH')], 1, False),
    'missing': ([('1', None, None), ('1', 'JOHN', None)], 0, None),
    'one_usable': ([('1', 'JOHN', 'SMITH'), ('1', None, 'SMITH')], 1, False),
    'different_npis': ([('1', 'JOHN', 'SMITH'), ('2', 'JANE', 'JONES')], 2, False),
    'nontransitive': ([('1', 'JOHN', 'SMITH'), ('1', 'JOHN', 'SMITH-JONES'), ('1', 'JOHN', 'JONES')], 3, True),
    'shared_first_token': ([('1', 'JOHN PAUL', 'SMITH'), ('1', 'PAUL ANDREW', 'SMITH')], 2, False),
    'typo': ([('1', 'JOHN', 'JOHNSON'), ('1', 'JOHN', 'JOHNSTON')], 2, False),
    'unusable': ([('1', "'", 'SMITH'), ('1', 'JOHN', 'S')], 0, None),
}


def history_fixture(debug=False):
    rows = []
    for case, (names, _, _) in CASES.items():
        for i, (npi, first, last) in enumerate(names):
            rows.append({'day': f'2026-01-{i + 1:02d}', 'email_address': case + '@example.test',
                         'npi': npi, 'first_name': first, 'last_name': last})
    rows += [dict(rows[0]), dict(rows[0], day='2026-02-01')]
    return inlined('int_medscape__metrics', variables={'debug': debug}, fixtures={
        'stg_medscape__global': source_values('stg_medscape__global', rows),
        'stg_npi__reference': "(SELECT * FROM (VALUES ('1','REGISTRY','ONLY'), ('1','ANOTHER','PERSON'), ('1','REGISTRY','ONLY')) AS t(npi,first_name,last_name))"})


def check_history(rows):
    assert len(rows) == sum(len(c[0]) for c in CASES.values())
    assert len({r['metric_row_id'] for r in rows}) == len(rows)
    for row in rows:
        case = row['email'].split('@')[0]
        _, count, conflict = CASES[case]
        assert row['email_name_count'] == count, case
        assert row['email_npi_has_name_conflict'] is conflict, case
    assert max(r['observation_count'] for r in rows) == 3


def healthlink_fixture():
    return inlined('int_healthlink__metrics', fixtures={
        'stg_healthlink__email': source_values('stg_healthlink__email', [
            {'day':'2026-01-01','npi':'1','hld_email':'same@example.test'},
            {'day':'2026-01-02','npi':'1','hld_email':'same@example.test'},
            {'day':'2026-01-01','npi':'missing','hld_email':'unknown@example.test'}]),
        'stg_healthlink__hcp': "(SELECT *, CAST(NULL AS varchar) AS day, CAST(NULL AS varchar) AS state, CAST(NULL AS varchar) AS phone FROM (VALUES ('1','JOHN','SMITH'),('1','JOHN','SMITH'),('1','JANE','JONES')) AS t(npi,firstname,lastname))"})


def check_healthlink(rows):
    assert len(rows) == 2
    known = next(r for r in rows if r['npi'] == '1')
    unknown = next(r for r in rows if r['npi'] == 'missing')
    assert known['email_name_count'] == 2 and known['email_npi_has_name_conflict'] is True
    assert known['observation_count'] == 2
    assert unknown['email_name_count'] == 0 and unknown['email_npi_has_name_conflict'] is None


def vendor_isolation_fixture():
    # Override only two vendor outputs; the final model's shared windows must keep sources apart.
    a = history_fixture()
    b = a.replace("CAST('medscape' AS varchar)", "CAST('drdb' AS varchar)")
    # Both vendors retain the same keys and IDs, but use different source names.
    b = b.replace("'ROBERT'", "'ALICE'").replace("'BOB'", "'ALICIA'")
    inputs = f'SELECT * FROM ({a}) UNION ALL SELECT * FROM ({b})'
    return p.render_sql("WITH records AS (" + inputs + "), measured AS ({{ name_consistency_metrics('records') }}) SELECT * FROM measured")


def check_isolation(rows):
    assert len(rows) == 2 * sum(len(c[0]) for c in CASES.values())
    assert all(r['email_name_count'] == CASES[r['email'].split('@')[0]][1] for r in rows)


FIXTURES = {'name_history': (history_fixture, check_history),
            'healthlink_reference': (healthlink_fixture, check_healthlink),
            'name_vendor_isolation': (vendor_isolation_fixture, check_isolation)}


class NameConsistencyTests(unittest.TestCase):
    def test_fixtures(self):
        for name, (make_sql, check) in FIXTURES.items():
            with self.subTest(case=name):
                check(execute(make_sql()))

    def test_debug_retains_metric_values(self):
        expected = {r['metric_row_id']: r for r in execute(history_fixture())}
        rows = execute(history_fixture(debug=True))
        self.assertGreater(len(rows), len(expected))
        for row in rows:
            for column in ('email_name_count', 'email_npi_has_name_conflict'):
                self.assertEqual(row[column], expected[row['metric_row_id']][column])


if __name__ == '__main__':
    unittest.main()
