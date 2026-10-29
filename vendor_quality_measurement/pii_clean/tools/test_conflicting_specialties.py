#!/usr/bin/env python3
"""Specialty identifiers, missing evidence, exact conflict dates and row preservation."""
import unittest

import pipeline as p
from test_models import execute, inlined, literal
from test_record_grain import source_values


def association_fixture():
    # Slot 15 contributes a match; duplicates and unknown dictionary codes do not.
    rows = [('1', {1: '207Q00000X', 15: ' 207r00000x '}),
            ('1', {1: '207Q00000X'}), ('2', {1: '207R00000X'}),
            ('3', {1: '208D00000X'}), ('4', {}), ('5', {1: '888888888X'})]
    values = []
    for npi, slots in rows:
        values.append('(' + literal(npi) + ', ' + ', '.join(literal(slots.get(i)) for i in range(1, 16)) + ')')
    return '(SELECT * FROM (VALUES ' + ', '.join(values) + ') AS t(npi, ' + ', '.join(
        f'healthcare_provider_taxonomy_code_{i}' for i in range(1, 16)) + '))'


def dictionary_fixture():
    return "(SELECT * FROM (VALUES ('207Q00000X'),('207R00000X'),('208D00000X'),('207R00000X')) AS t(code))"


CASES = {
    'same': [('1', '01', True), ('2', '01', True)],
    'different': [('1', '01', False), ('3', '01', False)],
    'missing': [('1', '01', None), ('4', '01', None)],
    'absent': [('1', '01', None), ('6', '01', None)],
    'invalid': [('1', '01', None), ('5', '01', None)],
    'true_missing': [('1', '01', True), ('2', '01', True), ('4', '01', None)],
    'false_missing': [('1', '01', None), ('3', '01', None), ('4', '01', None)],
    'nonoverlap': [('1', '01', None), ('2', '02', None)],
    'gaps': [('1', '01', None), ('1', '03', None), ('2', '02', None)],
    'unknown_date': [('1', None, None), ('2', None, None)],
    'own_npi': [('1', '01', None)],
    'mixed_dates': [('1', '01', True), ('2', '01', True), ('3', '02', None)],
}


def dated_fixture(debug=False):
    rows = [{'email_address': case + '@example.test', 'npi': npi,
             'day': '2026-01-' + day if day else None}
            for case, values in CASES.items() for npi, day, _ in values]
    rows.append(dict(rows[0]))
    return inlined('int_medscape__metrics', variables={'debug': debug}, fixtures={
        'stg_medscape__global': source_values('stg_medscape__global', rows),
        'nppes_taxonomy': association_fixture(), 'taxonomy_dictionary': dictionary_fixture()})


def check_dated(rows):
    expected = {(case, npi): flag for case, values in CASES.items() for npi, _, flag in values}
    assert len(rows) == len(expected), (len(rows), len(expected))
    assert len({r['metric_row_id'] for r in rows}) == len(rows)
    for row in rows:
        key = (row['email'].split('@')[0], row['npi'])
        assert row['conflicting_npis_share_specialty'] is expected[key], (key, row['conflicting_npis_share_specialty'])
        if row['npi'] == '1':
            assert row['specialty_code_values'] == ['207Q00000X', '207R00000X']
        assert bool(row['conflicting_npi_specialty_comparisons']) == (row['has_conflict_linkage'] is True)


class ConflictingSpecialtyTests(unittest.TestCase):
    def test_dated_records(self):
        check_dated(execute(dated_fixture()))

    def test_undated_drdb_feeds(self):
        rows = execute(inlined('int_drdb__metrics', fixtures={
            'stg_drdb__npi': source_values('stg_drdb__npi', [
                {'emailaddress': 'team@example.test', 'npi': '1'},
                {'emailaddress': 'team@example.test', 'npi': '1'}]),
            'stg_drdb__enrich': source_values('stg_drdb__enrich', [
                {'email': 'team@example.test', 'npi': '2'}]),
            'nppes_taxonomy': association_fixture(), 'taxonomy_dictionary': dictionary_fixture()}))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['conflicting_npis_share_specialty'] is True for r in rows))
        self.assertTrue(all(r['conflict_days'] == [] for r in rows))

    def test_provider_lookup_unique_and_clean(self):
        sql = p.render_sql("{{ specialty_npi_lookup() }}", source_overrides={
            ('iceberg__npi', 'nppes_npidata_latest'): association_fixture(),
            ('iceberg__npi', 'npi_taxonomy'): dictionary_fixture()})
        rows = execute(sql)
        self.assertEqual(len(rows), 3)
        self.assertEqual(next(r for r in rows if r['npi'] == '1')['specialty_code_values'],
                         ['207Q00000X', '207R00000X'])
        self.assertFalse(any(r['npi'] in ('4', '5') for r in rows))

    def test_all_sources_have_identical_schema(self):
        fields = None
        for source in p.SOURCES:
            rows = execute(inlined(f'int_{source}__metrics'))
            schema = list(rows[0])
            if fields is not None:
                self.assertEqual(schema, fields, source)
            fields = schema
            self.assertTrue(all(r['specialty_code_values'] == [] for r in rows))
            self.assertTrue(all(r['conflicting_npis_share_specialty'] is None for r in rows))

    def test_independent_check_and_corruption(self):
        sql = dated_fixture()
        template = (p.ROOT / 'tests/conflicting_specialties.sql').read_text()
        def check(query):
            return execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + query + ')'}))
        self.assertEqual(check(sql), [])
        fields = list(execute(sql)[0])
        projection = ', '.join('false AS ' + c if c == 'conflicting_npis_share_specialty' else c for c in fields)
        self.assertTrue(check(f'SELECT {projection} FROM ({sql})'))

    def test_debug_preserves_specialty_fields(self):
        rows = {r['metric_row_id']: r for r in execute(dated_fixture())}
        for row in execute(dated_fixture(debug=True)):
            for field in ('specialty_code_values', 'conflicting_npis_share_specialty',
                          'conflicting_npi_specialty_comparisons', 'specialty_definition_version'):
                self.assertEqual(row[field], rows[row['metric_row_id']][field])


if __name__ == '__main__':
    unittest.main()
