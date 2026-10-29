#!/usr/bin/env python3
"""Within-vendor linkage fixtures, executable locally and on native Trino."""
import unittest

import pipeline as p
from test_models import execute, inlined
from test_record_grain import source_values, quantum_fixture


def multiplicity_fixture():
    base = {'day': '2026-01-01', 'npi': '123', 'email_address': 'same@example.test'}
    rows = [base, base, dict(base, day='2026-01-02'),
            dict(base, first_name='changed'), dict(base, npi='456', day='2026-02-01'),
            dict(base, npi='invalid-npi'), dict(base, npi=' '), dict(base, npi=None)]
    return inlined('int_medscape__metrics', fixtures={
        'stg_medscape__global': source_values('stg_medscape__global', rows)})


def check_multiplicity(rows):
    assert len(rows) == 4
    assert len({r['metric_row_id'] for r in rows}) == 4
    assert sorted(r['observation_count'] for r in rows) == [1, 1, 1, 3]
    assert all(r['email_npi_count'] == 3 and r['email_has_multiple_npis'] is True for r in rows)


def vendor_isolation_fixture():
    inputs = {
        'healthlink': ('stg_healthlink__email', 'hld_email', 'npi'),
        'quantummedica': ('stg_quantummedica__hcpdata', 'email', 'npi'),
        'medscape': ('stg_medscape__global', 'email_address', 'npi'),
        'endato': ('stg_endato__pii', 'email_1_address', 'npi'),
        'rocketreach': ('stg_rocketreach__lookup', 'recommended_email', 'npi'),
        'drdb': ('stg_drdb__npi', 'emailaddress', 'npi'),
        'haymarket': ('stg_haymarket__npi', 'email', 'npi_number'),
    }
    fixtures = {stage: source_values(stage, [{email: 'same@example.test', npi: str(i), 'day': '2026-01-01'}])
                for i, (stage, email, npi) in enumerate(inputs.values(), 1)}
    fixtures['stg_drdb__enrich'] = source_values('stg_drdb__enrich', [{}])
    return inlined('pii_clean', fixtures=fixtures)


def check_vendor_isolation(rows):
    assert len(rows) == 7
    assert {r['source'] for r in rows} == set(p.SOURCES)
    assert len({r['npi'] for r in rows}) == 7
    assert all(r['email_npi_count'] == 1 and r['email_has_multiple_npis'] is False for r in rows)
    assert all(r['has_conflict_linkage'] is False and r['has_been_reassigned'] is False for r in rows)


def drdb_feeds_fixture():
    return inlined('int_drdb__metrics', fixtures={
        'stg_drdb__npi': source_values('stg_drdb__npi', [{'emailaddress': 'same@example.test', 'npi': '123'}]),
        'stg_drdb__enrich': source_values('stg_drdb__enrich', [
            {'email': 'same@example.test', 'npi': '123'}, {'email': 'same@example.test', 'npi': '456'}])})


def check_drdb_feeds(rows):
    assert len(rows) == 3
    assert all(r['email_npi_count'] == 2 and r['email_has_multiple_npis'] is True for r in rows)
    assert all(r['has_conflict_linkage'] is True and r['has_been_reassigned'] is None for r in rows)


HISTORY_CASES = {
    'stable': ([('123', '2026-01-01'), ('123', '2026-01-02')], False, False),
    'changed': ([('123', '2026-01-01'), ('456', '2026-01-02')], True, False),
    'conflict': ([('123', '2026-01-01'), ('456', '2026-01-01')], False, True),
    'returns_with_gap': ([('123', '2026-01-01'), ('456', '2026-01-02'), ('123', '2026-01-03')], True, False),
    'conflict_later_change': ([('123', '2026-01-01'), ('456', '2026-01-01'), ('789', '2026-01-02')], True, {'123': True, '456': True, '789': False}),
    'undated_single': ([('123', None)], False, False),
    'undated_multiple': ([('123', None), ('456', None)], None, None),
    'partial_dates': ([('123', '2026-01-01'), ('456', None)], None, {'123': False, '456': None}),
    'invalid_date': ([('123', '2026-01-01'), ('456', 'bad-date')], None, {'123': False, '456': None}),
    'conflict_plus_undated': ([('123', '2026-01-01'), ('456', '2026-01-01'), ('789', None)], None, {'123': True, '456': True, '789': None}),
    'undated_copy': ([('123', '2026-01-01'), ('123', None), ('456', '2026-01-02')], True, {'123': None, '456': False}),
    'replacement_with_conflict': ([('123', '2026-01-01'), ('456', '2026-01-02'), ('789', '2026-01-02')], True, {'123': False, '456': True, '789': True}),
    'stable_conflict': ([('123', '2026-01-01'), ('456', '2026-01-01'), ('123', '2026-01-02'), ('456', '2026-01-02')], False, True),
    'expanding_conflict': ([('123', '2026-01-01'), ('123', '2026-01-02'), ('456', '2026-01-02')], True, True),
    'contracting_conflict': ([('123', '2026-01-01'), ('456', '2026-01-01'), ('123', '2026-01-02')], True, True),
}


def history_fixture():
    rows = [{'email_address': case + '@example.test', 'npi': npi, 'day': day}
            for case, (observations, _, _) in HISTORY_CASES.items() for npi, day in observations]
    # Repeated observations on the same day must not manufacture a conflict.
    rows += [dict(rows[0]), dict(rows[0])]
    return inlined('int_medscape__metrics', fixtures={
        'stg_medscape__global': source_values('stg_medscape__global', rows)})


def check_history(rows):
    assert len(rows) == sum(len({npi for npi, _ in observations}) for observations, _, _ in HISTORY_CASES.values())
    for row in rows:
        observations, reassigned, conflict = HISTORY_CASES[row['email'].split('@')[0]]
        assert row['has_been_reassigned'] is reassigned, row['email']
        expected_conflict = conflict[row['npi']] if isinstance(conflict, dict) else conflict
        assert row['has_conflict_linkage'] is expected_conflict, (row['email'], row['npi'])
        expected_days = sorted({day for npi, day in observations if npi == row['npi'] and day and day != 'bad-date'})
        assert [str(d)[:10] for d in row['observed_days']] == expected_days, row['email']
        assert set(str(d)[:10] for d in row['conflict_days']).issubset(expected_days)
        if expected_conflict is True:
            assert row['conflict_days']
    assert len({r['metric_row_id'] for r in rows}) == len(rows)


FIXTURES = {'multiplicity': (multiplicity_fixture, check_multiplicity),
            'vendor_isolation': (vendor_isolation_fixture, check_vendor_isolation),
            'drdb_feeds': (drdb_feeds_fixture, check_drdb_feeds),
            'history': (history_fixture, check_history)}


class EmailLinkageTests(unittest.TestCase):
    def test_linkage_fixtures(self):
        for name, (make_sql, check) in FIXTURES.items():
            with self.subTest(case=name):
                check(execute(make_sql()))

    def test_repeated_email_slots_do_not_inflate_count(self):
        rows = execute(quantum_fixture())
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['email_npi_count'] == 1 for r in rows))

    def test_population_checks_reject_corrupted_metrics(self):
        model = 'int_medscape__metrics'
        correct = history_fixture()
        fields = list(execute(correct)[0])
        for test, column, bad in [('email_npi_multiplicity.sql', 'email_npi_count', '999'),
                                  ('email_linkage_history.sql', 'has_been_reassigned', 'false'),
                                  ('email_linkage_history.sql', 'has_conflict_linkage', 'false')]:
            with self.subTest(test=test, column=column):
                template = (p.ROOT / 'tests' / test).read_text()
                sql = p.render_sql(template, {'metric_model': model}, {model: '(' + correct + ')'})
                self.assertEqual(execute(sql), [])
                # Replace only the projected stored indicator; keep the observations intact.
                projection = ', '.join(f'{bad} AS {c}' if c == column else c for c in fields)
                corrupted = f'(SELECT {projection} FROM ({correct}))'
                sql = p.render_sql(template, {'metric_model': model}, {model: corrupted})
                self.assertTrue(execute(sql))


if __name__ == '__main__':
    unittest.main()
