"""Vendor labels: exact-day joins, registration keys, nullable peers and preserved rows."""
import json
import unittest

import pipeline as p
from test_models import execute, inlined, literal


def records_sql(rows, source):
    values = []
    for row in rows:
        values.append('(' + ', '.join([
            literal(source), literal(row.get('email', 'team@example.test')),
            literal(row['npi']), literal(row['id']),
            literal(json.dumps(row.get('payload', {'guid': row['id']}))),
            'cast(ARRAY[' + ', '.join("DATE '" + day + "'" for day in row.get('days', [])) + '] AS array(date))',
            'cast(ARRAY[' + ', '.join("DATE '" + day + "'" for day in row.get('conflicts', row.get('days', []))) + '] AS array(date))',
            str(row.get('conflict', True)).lower(), "'preserved'",
            "ARRAY['" + ('iceberg.thirdparty.drdb_npi' if 'emailaddress' in row.get('payload', {})
                         else 'iceberg.thirdparty.npi_enrich_emails_hashlower') + "']"
        ]) + ')')
    return '(SELECT * FROM (VALUES ' + ', '.join(values) + ') AS t(source,email,npi,metric_row_id,record_payload,observed_days,conflict_days,has_conflict_linkage,stored_attribute,source_tables))'


def metadata_sql(rows, source):
    columns = ['npi_clean', 'vendor_day', 'guid', 'primary_specialty', 'secondary_specialty',
               'tertiary_specialty', 'profession', 'specialty']
    values = []
    for row in rows or [{}]:
        values.append('(' + ', '.join([
            literal(row.get('npi')), "cast(" + literal(row.get('day')) + ' AS date)',
            literal(row.get('guid')), literal(row.get('specialty')),
            literal(row.get('secondary')), literal(row.get('tertiary')),
            literal(row.get('profession')), literal(row.get('specialty'))
        ]) + ')')
    return '(SELECT * FROM (VALUES ' + ', '.join(values) + ') AS t(' + ','.join(columns) + '))'


def fixture_sql(source='medscape', rows=None, metadata=None):
    rows = rows or [{'npi': '1', 'id': 'a', 'days': ['2026-01-01']},
                    {'npi': '2', 'id': 'b', 'days': ['2026-01-01']}]
    overrides = {name: metadata_sql(metadata or [], source) for name in
                 ['stg_medscape__meta', 'stg_quantummedica__hcpmeta', 'stg_healthlink__hcp']}
    return p.render_sql("WITH records AS (" + records_sql(rows, source) + "), evaluated AS ("
                        + "{{ vendor_professional_records('records', '" + source + "', 'records') }}"
                        + ") SELECT * FROM evaluated", ref_overrides=overrides)


def same_day_fixture():
    days = ['2026-01-01', '2026-01-02']
    rows = [{'npi': '1', 'id': 'a', 'days': days}, {'npi': '2', 'id': 'b', 'days': days}]
    metadata = [
        {'npi': '1', 'guid': 'a', 'day': days[0], 'specialty': ' Cardiology ', 'profession': ' Physician '},
        {'npi': '1', 'guid': 'a', 'day': days[1], 'specialty': 'Neurology', 'profession': 'Nurse'},
        {'npi': '2', 'guid': 'b', 'day': days[0], 'specialty': 'Neurology', 'profession': 'Nurse'},
        {'npi': '2', 'guid': 'b', 'day': days[1], 'specialty': 'Cardiology', 'profession': 'Physician'},
        {'npi': '2', 'guid': 'wrong-registration', 'day': days[0], 'specialty': 'Cardiology', 'profession': 'Physician'},
        {'npi': '2', 'guid': 'b', 'day': '2026-01-03', 'specialty': 'Cardiology', 'profession': 'Physician'},
    ]
    metadata.append(dict(metadata[0]))
    return fixture_sql(rows=rows, metadata=metadata)


def check_same_day(rows):
    assert len(rows) == 2
    assert {r['metric_row_id'] for r in rows} == {'a', 'b'}
    for row in rows:
        assert row['stored_attribute'] == 'preserved'
        assert row['source_vendor_specialty_values'] == ['CARDIOLOGY', 'NEUROLOGY']
        assert row['source_vendor_profession_values'] == ['NURSE', 'PHYSICIAN']
        assert row['conflicting_npis_share_vendor_specialty'] is False
        assert row['conflicting_npis_share_vendor_profession'] is False
        assert len(row['vendor_professional_evidence']) == 2
        assert len(row['conflicting_npi_vendor_specialty_comparisons']) == 2


class VendorProfessionalTests(unittest.TestCase):
    def test_same_day_and_guid_joins_do_not_cross_history_or_multiply_records(self):
        check_same_day(execute(same_day_fixture()))

    def test_normalization_placeholders_and_exact_label_matching(self):
        values = [' family   medicine ', 'FAMILY MEDICINE', 'N/A', '\\N', 'Other', '', None,
                  'Internal Medicine/Cardiology', 'Cardiology', 'profession', 'primary_specialty']
        sql = p.render_sql("SELECT {{ vendor_labels('raw') }} AS labels FROM (SELECT ARRAY["
                           + ','.join(literal(v) for v in values) + '] AS raw)')
        self.assertEqual(execute(sql)[0]['labels'],
                         ['CARDIOLOGY', 'FAMILY MEDICINE', 'INTERNAL MEDICINE/CARDIOLOGY'])

    def test_nullable_peer_aggregation_and_missing_delivery_day(self):
        day = '2026-01-01'
        rows = [{'npi': npi, 'id': key, 'days': [day]} for npi, key in [('1', 'a'), ('2', 'b'), ('3', 'c')]]
        metadata = [{'npi': '1', 'guid': 'a', 'day': day, 'specialty': 'Cardiology', 'profession': 'Physician'},
                    {'npi': '2', 'guid': 'b', 'day': day, 'specialty': ' cardiology ', 'profession': ' physician '},
                    {'npi': '3', 'guid': 'c', 'day': '2026-01-02', 'specialty': 'Cardiology', 'profession': 'Physician'}]
        result = {r['metric_row_id']: r for r in execute(fixture_sql(rows=rows, metadata=metadata))}
        for key in ('a', 'b'):
            self.assertTrue(result[key]['conflicting_npis_share_vendor_specialty'])
            self.assertTrue(result[key]['conflicting_npis_share_vendor_profession'])
        self.assertIsNone(result['c']['conflicting_npis_share_vendor_specialty'])
        metadata[1]['specialty'] = 'Neurology'
        metadata[1]['profession'] = 'Nurse'
        result = execute(fixture_sql(rows=rows, metadata=metadata))
        self.assertTrue(all(r['conflicting_npis_share_vendor_specialty'] is None for r in result))
        self.assertTrue(all(r['conflicting_npis_share_vendor_profession'] is None for r in result))

    def test_nonoverlapping_days_and_no_conflict_are_inapplicable(self):
        rows = [{'npi': '1', 'id': 'a', 'days': ['2026-01-01'], 'conflict': False},
                {'npi': '2', 'id': 'b', 'days': ['2026-01-02'], 'conflict': False}]
        for row in execute(fixture_sql(rows=rows)):
            self.assertIsNone(row['conflicting_npis_share_vendor_specialty'])
            self.assertEqual(row['conflicting_npi_vendor_specialty_comparisons'], [])

    def test_quantummedica_and_healthlink_reference_inputs(self):
        day = '2026-01-01'
        metadata = [{'npi': npi, 'day': day, 'specialty': 'Cardiology',
                     'secondary': 'Internal Medicine', 'tertiary': 'Family Medicine',
                     'profession': 'Physician'} for npi in ('1', '2')]
        for source in ('quantummedica', 'healthlink'):
            rows = execute(fixture_sql(source, metadata=metadata))
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertTrue(row['conflicting_npis_share_vendor_specialty'])
                self.assertIs(row['conflicting_npis_share_vendor_profession'], True if source == 'quantummedica' else None)
                self.assertEqual(len(row['source_vendor_specialty_values']), 3 if source == 'quantummedica' else 1)

    def test_undated_drdb_exact_records_and_unsupported_vendors(self):
        rows = [{'npi': '1', 'id': 'a', 'payload': {'specialty': 'Cardiology', 'emailaddress': 'team@example.test'}},
                {'npi': '2', 'id': 'b', 'payload': {'specialty': ' cardiology ', 'email': 'team@example.test'}}]
        result = execute(fixture_sql('drdb', rows))
        self.assertEqual(len(result), 2)
        for row in result:
            self.assertTrue(row['conflicting_npis_share_vendor_specialty'])
            self.assertIsNone(row['conflicting_npis_share_vendor_profession'])
        for source in ('endato', 'rocketreach', 'haymarket'):
            for row in execute(fixture_sql(source, rows)):
                self.assertEqual(row['source_vendor_specialty_values'], [])
                self.assertEqual(row['source_vendor_profession_values'], [])
                self.assertIsNone(row['conflicting_npis_share_vendor_specialty'])
                self.assertIsNone(row['conflicting_npis_share_vendor_profession'])

    def test_every_vendor_schema_and_old_field_preservation(self):
        import yaml
        declared = yaml.safe_load((p.ROOT / 'models/final/schema.yml').read_text())['models'][0]['columns']
        fields = [c['name'] for c in declared if not c['name'].startswith('cookie_')]
        self.assertEqual(len(fields), 124)
        order = None
        for source in p.SOURCES:
            model = 'int_' + source + '__metrics'
            sql = inlined(model)
            rows = execute(sql)
            self.assertTrue(rows)
            self.assertEqual(set(rows[0]), set(fields))
            integrity = p.render_sql((p.ROOT / 'tests/vendor_professional.sql').read_text(),
                                     {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + sql + ')'})
            self.assertEqual(execute(integrity), [], source)
            if order is not None:
                self.assertEqual(list(rows[0]), order)
            order = list(rows[0])
            # Remove only the new wrapping CTE to compare every preexisting field.
            text = p.model_paths()[model].read_text()
            before = text.replace("{{ vendor_professional_records('identity_metrics', '" + source + "', 'metric_records', derive_conflicts=true) }}", 'SELECT * FROM identity_metrics')
            # The baseline intentionally lacks the new vendor fields. Use the
            # generic registration wrapper rather than its full-schema projection.
            before = before.replace(', inline=true)', ')')
            from unittest.mock import patch
            original = p.read_model
            def read(name, **kwargs):
                return p.render_sql(before, **kwargs) if name == model else original(name, **kwargs)
            with patch.object(p, 'read_model', side_effect=read):
                old_rows = execute(inlined(model))
            by_id = {r['metric_row_id']: r for r in old_rows}
            self.assertEqual(len(by_id), len(rows))
            for row in rows:
                for name, value in by_id[row['metric_row_id']].items():
                    if name != 'computed_at':
                        self.assertEqual(row[name], value, (source, name))

    def test_independent_integrity_and_population_denominators(self):
        sql = same_day_fixture()
        template = (p.ROOT / 'tests/vendor_professional.sql').read_text()
        def check(query):
            return execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL},
                                        {p.FINAL_MODEL: '(' + query + ')'}))
        self.assertEqual(check(sql), [])
        fields = list(execute(sql)[0])
        for name in ('conflicting_npis_share_vendor_specialty', 'conflicting_npis_share_vendor_profession'):
            projection = ', '.join('true AS ' + field if field == name else field for field in fields)
            self.assertTrue(check('SELECT ' + projection + ' FROM (' + sql + ')'))
        profile = p.render_profile('vendor_professional_profile.sql').replace(p.relation(p.FINAL_MODEL), '(' + sql + ')')
        for row in execute(profile):
            self.assertEqual(row['metric_rows'], 2)
            self.assertEqual(row['conflict_rows'], 2)
            self.assertEqual(row['disjoint_rows'], 2)
            self.assertEqual(row['shared_rows'] + row['disjoint_rows'] + row['unknown_conflict_rows'], row['conflict_rows'])
            self.assertEqual(row['disjoint_conflict_row_pct'], 100)

    def test_pipeline_narrow_inputs_preserve_dated_and_unknown_conflict_contexts(self):
        from test_record_grain import source_values
        rows = [{'npi': npi, 'guid': guid, 'day': day, 'email_address': 'team@example.test'}
                for npi, guid in [('1', 'a'), ('2', 'b')]
                for day in ['2026-01-01', '2026-01-02']]
        rows += [{'npi': npi, 'guid': npi, 'email_address': 'undated@example.test'} for npi in ('3', '4')]
        metadata = [{'npi': npi, 'guid': guid, 'day': day,
                     'specialty': specialty, 'profession': profession}
                    for npi, guid, day, specialty, profession in [
                        ('1', 'a', '2026-01-01', 'Cardiology', 'Physician'),
                        ('1', 'a', '2026-01-02', 'Neurology', 'Nurse'),
                        ('2', 'b', '2026-01-01', 'Neurology', 'Nurse'),
                        ('2', 'b', '2026-01-02', 'Cardiology', 'Physician')]]
        meta = ('(SELECT npi_clean AS npi, cast(vendor_day AS varchar) AS day, guid, primary_specialty, '
                'secondary_specialty, tertiary_specialty, profession FROM ' + metadata_sql(metadata, 'medscape') + ')')
        result = execute(inlined('int_medscape__metrics', fixtures={
            'stg_medscape__global': source_values('stg_medscape__global', rows), 'stg_medscape__meta': meta}))
        self.assertEqual(len(result), 4)
        for row in result:
            if row['email'] == 'undated@example.test':
                self.assertIsNone(row['has_conflict_linkage'])
                self.assertIsNone(row['conflicting_npis_share_vendor_specialty'])
                self.assertEqual(row['conflicting_npi_vendor_specialty_comparisons'], [])
            else:
                self.assertTrue(row['has_conflict_linkage'])
                self.assertFalse(row['conflicting_npis_share_vendor_specialty'])
                self.assertFalse(row['conflicting_npis_share_vendor_profession'])
                self.assertEqual(len(row['conflicting_npi_vendor_specialty_comparisons']), 2)


if __name__ == '__main__':
    unittest.main()
