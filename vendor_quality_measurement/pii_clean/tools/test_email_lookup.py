"""Complete lookup preserves stored context and computes all unpublished groups."""
import hashlib
import unittest

import pipeline as p
from render_email_lookup import base_columns, render_lookup
from test_location_evidence import values
from test_models import execute, inlined
from test_record_grain import source_values


def fixture():
    vendor = source_values('stg_endato__pii', [
        {'npi': '1000000001', 'email_1_address': 'team@example.test', 'email_2_address': 'team@example.test',
         'name_first': 'ALICE', 'name_last': 'SMITH', 'address_state': 'NY'},
        {'npi': '1000000002', 'email_1_address': 'team@example.test',
         'name_first': 'BOB', 'name_last': 'JONES', 'address_state': 'CA'},
        {'npi': '1000000003', 'email_1_address': 'other@example.test', 'address_state': 'NY'}])
    stored = 'SELECT ' + ', '.join(base_columns()) + ' FROM (' + inlined('int_endato__metrics', fixtures={'stg_endato__pii': vendor}) + ')'
    nppes = values(['npi', 'npi_deactivation_date', 'npi_reactivation_date', 'replacement_npi', 'npi_deactivation_reason_code',
                     'healthcare_provider_taxonomy_code_1'], [
        ('1000000001', None, None, None, None, '207Q00000X'),
        ('1000000002', '2020-01-01', None, None, None, '207Q00000X')])
    nppes = '(SELECT *, ' + ', '.join(f'cast(NULL AS varchar) AS healthcare_provider_taxonomy_code_{i}' for i in range(2, 16)) + ' FROM ' + nppes + ')'
    facilities = "(SELECT * FROM (VALUES ('1000000001',ARRAY['1888888888']),('1000000002',ARRAY['1888888888'])) AS t(provider_npi,facility_npis))"
    locations = values(['npi_facility_provider_npi', 'state_code', 'location'], [
        ('1000000001', 'NY', 'POINT(1 1)'), ('1000000002', 'CA', 'POINT(1 1)')])
    locations = '(SELECT *, cast(1 AS bigint) AS npi_facility_rank FROM ' + locations + ')'
    mappings = values(['day', 'hashedemail_sha256', 'uids'], [
        ('2026-10-22', hashlib.sha256(b'team@example.test').hexdigest(), 'web:synthetic_uid')])
    overrides = {
        ('bq_bi__analytics_prod', 'npi_facility_association'): facilities,
        ('iceberg__npi', 'nppes_npidata_latest'): nppes,
        ('iceberg__npi', 'npi_taxonomy'): "(SELECT '207Q00000X' AS code)",
        ('bq_bi__analytics_prod', 'npi_facility_locations_with_ids'): locations,
        ('iceberg__thirdparty', 'liveintent_idsync'): mappings,
        ('iceberg__crossscreen', 'nscreen_geo_daily_ua'): values(['day', 'uid', 'geo'], [('2026-10-22', 'synthetic_uid', '100')]),
        ('iceberg__jteixeira_ipa', 'tmp_zip3_to_state'): values(['zip3', 'state'], [('100', 'NY')])}
    sql = render_lookup(' TEAM@EXAMPLE.TEST ', '2026-10-29', {p.FINAL_MODEL: '(' + stored + ')'}, overrides,
                        {'location_metadata_from_rows': True})
    return stored, sql


def check_rows(rows):
    assert len(rows) == 3 and len({r['metric_row_id'] for r in rows}) == 3
    for row in rows:
        assert row['email'] == 'team@example.test'
        assert row['email_npi_count'] == 2 and row['has_conflict_linkage'] is True
        assert row['conflicting_npis_share_facility'] is True
        assert row['conflicting_npis_share_specialty'] is True
        assert row['vendor_state_evidence'] == 'corroborated'
        assert row['cookie_location_status'] == 'observed'
        assert row['cookie_state_values'] == ['NY']
        assert row['npi_registry_status'] == ('active_as_reported' if row['npi'] == '1000000001' else 'deactivated')
        assert row['cookie_vendor_state_evidence'] == ('corroborated' if row['npi'] == '1000000001' else 'not_observed')


class EmailLookupTests(unittest.TestCase):
    def test_hash_matches_independent_sha256(self):
        rows = execute(p.render_sql("SELECT {{ cookie_hash(\"'team@example.test'\") }} AS hash"))
        self.assertEqual(rows[0]['hash'], hashlib.sha256(b'team@example.test').hexdigest())

    def test_complete_lookup_and_preservation(self):
        stored, sql = fixture()
        rows = execute(sql)
        check_rows(rows)
        before = {r['metric_row_id']: r for r in execute(stored) if r['email'] == 'team@example.test'}
        for row in rows:
            for name in base_columns():
                if name != 'computed_at':
                    self.assertEqual(row[name], before[row['metric_row_id']][name], name)
        self.assertEqual(len(rows[0]), 109)

    def test_email_literal_escaping_and_single_edit(self):
        sql = render_lookup("o'neil@example.test")
        self.assertEqual(sql.count("o''neil@example.test"), 1)
        self.assertNotIn('CREATE ', sql)


if __name__ == '__main__':
    unittest.main()
