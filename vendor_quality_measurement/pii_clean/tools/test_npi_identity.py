"""Identifier validation, independent registry evidence and record preservation."""
import re
import unittest

import pipeline as p
from test_models import execute, literal


def with_check_digit(body):
    # Standard Luhn over the full prefixed number, independent of SQL's constant 24.
    for last in range(10):
        digits = [int(c) for c in ('80840' + body + str(last))[::-1]]
        total = sum((2 * d // 10 + 2 * d % 10) if i % 2 else d for i, d in enumerate(digits))
        if total % 10 == 0:
            return body + str(last)
    raise AssertionError(body)


CASES = [
    (None, None, None, 'missing'), ('', None, None, 'missing'), (' ', None, None, 'missing'),
    ('123', False, None, 'malformed'), ('123456789X', False, None, 'malformed'),
    ('1234567893 ', False, None, 'malformed'), ('1234567893\n', False, None, 'malformed'), ('１２３４５６７８９３', False, None, 'malformed'),
    ('1234567893', True, True, 'valid'), ('1234567894', True, False, 'checksum_failure'),
    ('0000000000', False, False, 'unsupported_prefix'),
] + [(with_check_digit(str(prefix) + '23456789'), prefix in (1, 2, 3, 4), True,
      'valid' if prefix in (1, 2, 3, 4) else 'unsupported_prefix') for prefix in (2, 3, 4, 5, 9)]


def reference_fixture():
    rows = [('1234567893', '1'), ('1234567893', '1'), ('1234567893', ' 1 '),
            (with_check_digit('223456789'), '2'), (with_check_digit('323456789'), None),
            (with_check_digit('423456789'), '1'), (with_check_digit('423456789'), '2'),
            ('1234567894', '2'), ('missing-code', ''), ('bad-code', '9'),
            ('partial-code', '1'), ('partial-code', None)]
    return '(SELECT * FROM (VALUES ' + ', '.join('(' + literal(n) + ', ' + literal(c) + ')' for n, c in rows) + ') AS t(npi, entity_type_code))'


def fixture_sql():
    npis = [c[0] for c in CASES] + ['missing-code', 'bad-code', 'partial-code', 'absent', '1234567893']
    values = ', '.join('(' + str(i) + ', ' + literal(n) + ')' for i, n in enumerate(npis))
    return p.render_sql("WITH records AS (SELECT *, 'fixture' AS source, 'preserved' AS raw_value FROM (VALUES " + values +
                        ") AS t(metric_row_id, npi)), evaluated AS ({{ npi_identity_records('records') }}) SELECT * FROM evaluated",
                        {'npi_identity_as_of_day': '2026-10-30'}, source_overrides={
                            ('iceberg__npi', 'nppes_npidata_latest'): reference_fixture()})


def check_fixture(rows):
    assert len(rows) == len(CASES) + 5
    assert len({r['metric_row_id'] for r in rows}) == len(rows)
    by_id = {r['metric_row_id']: r for r in rows}
    for i, (npi, fmt, checksum, reason) in enumerate(CASES):
        r = by_id[i]
        assert r['npi'] == npi and r['raw_value'] == 'preserved'
        assert (r['npi_format_valid'], r['npi_checksum_valid'], r['npi_structure_reason']) == (fmt, checksum, reason), r
        assert r['npi_structure_valid'] is (None if reason == 'missing' else reason == 'valid'), r
    by_npi = {r['npi']: r for r in rows}
    for npi, kind, reason in [('1234567893', 'individual', 'registry_consensus'),
                              ('1234567894', 'organization', 'registry_consensus'),
                              (with_check_digit('223456789'), 'organization', 'registry_consensus'),
                              (with_check_digit('323456789'), 'unknown', 'missing_entity_type'),
                              (with_check_digit('423456789'), 'unknown', 'conflicting_reference_records'),
                              ('missing-code', 'unknown', 'missing_entity_type'),
                              ('bad-code', 'unknown', 'unrecognized_entity_type'),
                              ('partial-code', 'unknown', 'conflicting_reference_records'),
                              ('absent', 'unknown', 'not_found')]:
        assert (by_npi[npi]['npi_entity_type'], by_npi[npi]['npi_entity_type_reason']) == (kind, reason)
    assert by_npi['1234567893']['npi_entity_type_reference_row_count'] == 3
    assert by_npi['1234567893']['npi_entity_type_variant_count'] == 1
    assert {r['entity_type_code'] if isinstance(r, dict) else r[0] for r in by_npi['1234567893']['npi_entity_type_evidence']} == {'1', ' 1 '}
    assert by_npi['absent']['npi_entity_type_evidence'] == []


class NpiIdentityTests(unittest.TestCase):
    def test_structure_entity_consensus_and_preservation(self):
        check_fixture(execute(fixture_sql()))

    def test_independent_invariant_detects_corrupted_fields(self):
        records = fixture_sql()
        template = (p.ROOT / 'tests/npi_identity.sql').read_text()
        def check(sql):
            return execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + sql + ')'}))
        self.assertEqual(check(records), [])
        fields = list(execute(records)[0])
        corruptions = {'npi_format_valid': 'false', 'npi_checksum_valid': 'false', 'npi_structure_valid': 'false',
                       'npi_structure_reason': "'valid'", 'npi_entity_type': "'individual'",
                       'npi_entity_type_reason': "'registry_consensus'", 'npi_entity_type_evidence': 'cast(NULL AS array(row(entity_type_code varchar)))',
                       'npi_entity_type_reference_row_count': 'cast(-1 AS bigint)', 'npi_entity_type_variant_count': 'cast(99 AS bigint)',
                       'npi_identity_as_of_day': 'cast(NULL AS date)', 'npi_identity_reference_table': "'wrong'",
                       'npi_identity_definition_version': "'wrong'"}
        for name, value in corruptions.items():
            with self.subTest(field=name):
                projection = ', '.join(value + ' AS ' + f if f == name else f for f in fields)
                self.assertTrue(check('SELECT ' + projection + ' FROM (' + records + ')'))

    def test_statistics_distinguish_records_and_identifiers(self):
        profile = p.render_profile('npi_identity_profile.sql')
        documented = (p.ROOT / 'sql/statistics/22_npi_identity.sql').read_text()
        # Documentation pins its measured snapshot; live profiles use the current table.
        unpinned, pins = re.subn(re.escape(p.relation(p.FINAL_MODEL)) + r' FOR VERSION AS OF [0-9]+\b',
                                 p.relation(p.FINAL_MODEL), documented)
        self.assertEqual(pins, 1)
        self.assertEqual(profile + '\n', unpinned)
        rows = execute(profile.replace(p.relation(p.FINAL_MODEL), '(' + fixture_sql() + ')'))
        for dimension in ('structure', 'entity_type', 'entity_reason'):
            selected = [r for r in rows if r['dimension'] == dimension]
            self.assertEqual(sum(r['metric_rows'] for r in selected), len(CASES) + 5)
            self.assertEqual(sum(r['distinct_npis'] for r in selected), len(CASES) + 4)
            self.assertAlmostEqual(sum(r['distinct_npi_pct'] for r in selected), 100)


if __name__ == '__main__':
    unittest.main()
