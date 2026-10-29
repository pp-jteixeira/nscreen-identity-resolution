#!/usr/bin/env python3
"""Lifecycle chronology, contradictory evidence, missing references and grain preservation."""
import unittest

import pipeline as p
from test_models import execute, inlined, literal

CASES = [
    ('1000000001', None, None, None, None, 'active_as_reported', 'no_deactivation_reported'),
    ('1000000002', '2020-01-01', None, None, None, 'deactivated', 'latest_event_deactivation'),
    ('1000000003', '2020-01-01', '2021-01-01', None, None, 'reactivated', 'latest_event_reactivation'),
    ('1000000004', '2025-01-01', '2021-01-01', None, None, 'deactivated', 'latest_event_deactivation'),
    ('1000000005', '2020-01-01', None, '1999999999', None, 'replaced', 'replacement_reported'),
    ('1000000006', None, None, '1999999999', None, 'replaced', 'replacement_reported'),
    ('1000000007', '2020-01-01', '2021-01-01', '1999999999', None, 'unknown', 'replacement_with_reactivation'),
    ('1000000008', 'bad-date', None, None, None, 'unknown', 'invalid_lifecycle_date'),
    ('1000000009', '2026-10-30', None, None, None, 'unknown', 'future_lifecycle_date'),
    ('1000000010', '2020-01-01', '2020-01-01', None, None, 'unknown', 'ambiguous_event_order'),
    ('1000000011', None, None, None, '1', 'unknown', 'reason_without_deactivation'),
    ('1000000012', None, None, '1000000012', None, 'unknown', 'self_replacement'),
    ('1000000013', None, None, '0', None, 'unknown', 'invalid_replacement_npi'),
    ('1000000014', None, None, None, None, 'unknown', 'conflicting_reference_records'),
    ('1000000015', None, '2021-01-01', None, None, 'reactivated', 'latest_event_reactivation'),
    ('1000000016', None, 'bad-date', None, None, 'unknown', 'invalid_lifecycle_date'),
    ('1000000017', None, '2026-10-30', None, None, 'unknown', 'future_lifecycle_date'),
    ('1000000018', '2020-01-01', None, None, '1', 'deactivated', 'latest_event_deactivation'),
]


def reference_fixture():
    rows = [c[:5] for c in CASES]
    rows += [CASES[0][:5], ('1000000001', '', ' ', None, None),
             ('1000000014', '2020-01-01', None, None, None)]
    return '(SELECT *, ' + ', '.join(f'CAST(NULL AS varchar) AS healthcare_provider_taxonomy_code_{i}'
                                   for i in range(1, 16)) + ' FROM (VALUES ' + ', '.join(
        '(' + ', '.join(literal(x) for x in row) + ')' for row in rows) + \
        ') AS t(npi, npi_deactivation_date, npi_reactivation_date, replacement_npi, npi_deactivation_reason_code))'


def fixture_sql():
    records = '(SELECT * FROM (VALUES ' + ', '.join(
        '(' + literal(c[0]) + ', ' + literal('record-' + c[0]) + ')' for c in CASES) + \
        ", ('absent', 'missing'), ('1000000001', 'second-email-position')) AS t(npi, metric_row_id))"
    return p.render_sql("WITH records AS (SELECT *, 'preserved' AS raw_attribute FROM " + records + "), "
                        "evaluated AS ({{ registry_status_records('records') }}) SELECT * FROM evaluated",
                        {'registry_status_as_of_day': '2026-10-29'}, source_overrides={
                            ('iceberg__npi', 'nppes_npidata_latest'): reference_fixture()})


def check_fixture(rows):
    expected = {c[0]: c[5:] for c in CASES}
    expected['absent'] = ('not_found', 'no_nppes_record')
    assert len(rows) == len(CASES) + 2
    assert len({r['metric_row_id'] for r in rows}) == len(rows)
    for row in rows:
        assert (row['npi_registry_status'], row['npi_registry_status_reason']) == expected[row['npi']], row
        assert row['raw_attribute'] == 'preserved'
        if row['npi'] == '1000000001':
            assert row['npi_registry_reference_row_count'] == 3
            assert row['npi_registry_variant_count'] == 1
        if row['npi'] == '1000000014':
            assert row['npi_registry_variant_count'] == 2
            assert row['npi_registry_deactivation_date'] is None
        if row['npi'] == 'absent':
            assert row['npi_registry_lifecycle_evidence'] == []
            assert row['npi_registry_reference_row_count'] == 0


class RegistryStatusTests(unittest.TestCase):
    def test_lifecycle_cases_and_preservation(self):
        check_fixture(execute(fixture_sql()))

    def test_all_sources_missing_reference_and_identical_schema(self):
        schema = None
        for source in p.SOURCES:
            rows = execute(inlined(f'int_{source}__metrics'))
            if schema is not None:
                self.assertEqual(list(rows[0]), schema)
            schema = list(rows[0])
            self.assertTrue(all(r['npi_registry_status'] == 'not_found' for r in rows))

    def test_independent_invariant_check_detects_corruption(self):
        template = (p.ROOT / 'tests/registry_status.sql').read_text()
        records = fixture_sql()
        # The integrity check also needs source, while lifecycle lookup itself is source-independent.
        records = "SELECT 'fixture' AS source, x.* FROM (" + records + ') x'
        def check(sql):
            return execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + sql + ')'}))
        self.assertEqual(check(records), [])
        columns = list(execute(records)[0])
        projection = ', '.join("'active_as_reported' AS npi_registry_status" if c == 'npi_registry_status' else c for c in columns)
        self.assertTrue(check('SELECT ' + projection + ' FROM (' + records + ')'))


if __name__ == '__main__':
    unittest.main()
