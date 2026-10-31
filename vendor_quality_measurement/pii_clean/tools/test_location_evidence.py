#!/usr/bin/env python3
"""Facility comparison and bounded-window UID evidence with synthetic identifiers only."""
import unittest

import pipeline as p
from test_models import execute, inlined, literal


def values(columns, rows):
    return '(SELECT * FROM (VALUES ' + ', '.join('(' + ', '.join(literal(v) for v in row) + ')'
                                               for row in rows) + ') AS t(' + ', '.join(columns) + '))'


def fixture_sql(context=False, window_days=7, evaluation_day='2026-10-29'):
    cases = [('agree', '1', ['NY']), ('disagree', '1', ['CA']), ('mixed', '1', ['NY', 'CA']),
             ('nostate', '1', []), ('unmapped', '1', ['NY']), ('tied', '1', ['NY']),
             ('majority', '1', ['NY']), ('offday', '1', ['NY']), ('unknown', '1', ['NY']),
             ('nogeo', '1', ['NY']), ('invalidtokens', '1', ['NY']), ('unknownzip', '1', ['NY']),
             ('ambiguousfacility', '3', ['NY']), ('missingstate', '4', ['NY']),
             ('missinglocation', '5', ['NY']), ('norank1', '6', ['NY']), ('padding', '1', ['NY'])]
    records = ', '.join('(' + ', '.join([literal(name + '@example.test'), literal(npi), literal(name),
                                       'cast(ARRAY[' + ', '.join(literal(s) for s in states) + '] AS array(varchar))']) + ')'
                        for name, npi, states in cases)
    records += ", ('agree@example.test', '1', 'second-position', ARRAY['NY'])"
    records = '(SELECT *, \'preserved\' AS raw_attribute FROM (VALUES ' + records + ') AS t(email,npi,metric_row_id,source_state_values))'
    facility = values(['npi_facility_provider_npi', 'state_code', 'location', 'npi_facility_rank'], [
        ('1', 'New York', 'POINT(1 1)', '1'), ('1', 'NY', 'POINT(1 1)', '1'),
        ('3', 'NY', 'POINT(1 1)', '1'), ('3', 'CA', 'POINT(1 1)', '1'),
        ('4', None, 'POINT(1 1)', '1'), ('5', 'NY', None, '1'), ('6', 'NY', 'POINT(1 1)', '2')])
    # Rank is bigint in production. This VALUES helper builds varchar fixtures.
    facility = '(SELECT npi_facility_provider_npi, state_code, location, cast(npi_facility_rank AS bigint) AS npi_facility_rank FROM ' + facility + ')'
    mappings = []
    for name in ['agree', 'disagree', 'mixed', 'nostate', 'ambiguousfacility', 'missingstate', 'missinglocation', 'norank1']:
        mappings.append(('2026-10-22', name + '@example.test', 'web:u_agree|web:u_agree|mobile:u_agree'))
    mappings += [('2026-10-22', 'tied@example.test', 'web:u_tied'), ('2026-10-23', 'tied@example.test', 'web:u_tied'),
                 ('2026-10-22', 'majority@example.test', 'web:u_majority'), ('2026-10-23', 'majority@example.test', 'web:u_majority'),
                 ('2026-10-24', 'majority@example.test', 'web:u_majority'), ('2026-10-22', 'offday@example.test', 'web:u_offday'),
                 ('2026-10-22', 'unknown@example.test', 'web:u_unknown'), ('2026-10-22', 'nogeo@example.test', 'web:u_nogeo'),
                 ('2026-10-22', 'invalidtokens@example.test', 'bad|:missing|web:|bad:too:many'),
                 ('2026-10-22', 'unknownzip@example.test', 'web:u_unknownzip'),
                 ('2026-10-22', 'padding@example.test', 'web:u_padding'),
                 ('2026-10-29', 'agree@example.test', 'web:u_today'), ('2026-10-21', 'agree@example.test', 'web:u_old')]
    mapping_values = values(['day', 'email', 'uids'], mappings)
    mapping_values = '(SELECT day, ' + p.render_sql("{{ cookie_hash('email') }}") + ' AS hashedemail_sha256, uids FROM ' + mapping_values + ')'
    geo = values(['day', 'uid', 'geo'], [
        ('2026-10-22', 'u_agree', '100'), ('2026-10-22', 'u_agree', '100'),
        ('2026-10-22', 'u_tied', '100'), ('2026-10-23', 'u_tied', '900'),
        ('2026-10-22', 'u_majority', '100'), ('2026-10-23', 'u_majority', '100'), ('2026-10-24', 'u_majority', '900'),
        ('2026-10-23', 'u_offday', '100'), ('2026-10-22', 'u_unknown', 'bad'),
        ('2026-10-22', 'u_unknownzip', '999'), ('2026-10-22', 'u_padding', '7'),
        ('2026-10-29', 'u_agree', '900'), ('2026-10-21', 'u_agree', '900')])
    zip_map = values(['zip3', 'state'], [('100', 'NY'), ('100', 'New York'), ('900', 'CA'),
                                       ('999', 'NY'), ('999', 'CA'), ('007', 'NY')])
    variables = {'location_evidence_day': evaluation_day, 'location_metadata_from_rows': True, 'cookie_window_days': window_days}
    overrides = {('bq_bi__analytics_prod', 'npi_facility_locations_with_ids'): facility,
                 ('iceberg__thirdparty', 'liveintent_idsync'): mapping_values,
                 ('iceberg__crossscreen', 'nscreen_geo_daily_ua'): geo,
                 ('iceberg__jteixeira_ipa', 'tmp_zip3_to_state'): zip_map}
    if context:
        return records, variables, overrides
    return p.render_sql("WITH records AS (SELECT 'fixture' AS source, x.* FROM " + records + " x), "
                        "facility AS ({{ vendor_facility_records('records') }}), "
                        "measured AS ({{ cookie_location_records('facility') }}) SELECT * FROM measured",
                        variables, source_overrides=overrides)


def check_fixture(rows):
    assert len(rows) == 18 and len({r['metric_row_id'] for r in rows}) == 18
    keyed = {r['metric_row_id']: r for r in rows}
    for r in rows:
        assert r['raw_attribute'] == 'preserved'
        assert r['cookie_mapping_available_days'] == 3 and r['cookie_location_available_days'] == 3
        assert len(r['cookie_mapping_missing_days']) == 4
    a = keyed['agree']
    assert a['facility_rank1_rows'] == 2 and a['vendor_state_evidence'] == 'corroborated'
    assert a['cookie_count'] == a['cookie_mapped_uid_days'] == a['cookie_eligible_uid_days'] == 1
    assert a['cookie_state_values'] == ['NY'] and a['cookie_uid_types'] == ['mobile', 'web']
    assert a['cookie_vendor_state_evidence'] == a['cookie_facility_state_evidence'] == 'corroborated'
    for field in a:
        if field != 'metric_row_id':
            assert a[field] == keyed['second-position'][field], field
    assert keyed['disagree']['vendor_state_evidence'] == 'not_corroborated'
    assert keyed['disagree']['cookie_vendor_state_evidence'] == 'not_observed'
    assert keyed['disagree']['cookie_facility_state_evidence'] == 'corroborated'
    assert keyed['mixed']['vendor_state_evidence'] == 'mixed_vendor_states'
    assert keyed['mixed']['vendor_state_corroborated'] is None
    assert keyed['nostate']['vendor_state_evidence'] == 'unknown_vendor_state'
    for name in ['unmapped', 'invalidtokens']:
        assert keyed[name]['cookie_location_status'] == 'no_mapping'
    assert keyed['tied']['cookie_primary_state_tied_count'] == 1
    assert keyed['tied']['cookie_location_status'] == 'ambiguous_primary_state'
    assert keyed['tied']['cookie_state_values'] == [] and keyed['tied']['cookie_eligible_uid_days'] == 0
    assert keyed['majority']['cookie_observed_uid_days'] == 3
    assert keyed['majority']['cookie_eligible_uid_days'] == 2
    assert keyed['majority']['cookie_primary_state_multistate_count'] == 1
    assert keyed['majority']['cookie_state_values'] == ['NY']
    for name in ['offday', 'nogeo']:
        assert keyed[name]['cookie_location_status'] == 'no_state_observation'
    for name in ['unknown', 'unknownzip']:
        assert keyed[name]['cookie_location_status'] == 'unknown_state'
    for name, expected in [('ambiguousfacility', 'ambiguous_state'), ('missingstate', 'missing_state'),
                           ('missinglocation', 'missing_location'), ('norank1', 'no_rank1_association')]:
        assert keyed[name]['facility_reference_status'] == expected
        assert keyed[name]['vendor_state_evidence'] == 'unknown_facility'
        assert keyed[name]['cookie_facility_state_evidence'] == 'unknown_reference_state'
    assert keyed['padding']['cookie_state_values'] == ['NY']


class LocationEvidenceTests(unittest.TestCase):
    def test_semantic_cases(self):
        check_fixture(execute(fixture_sql()))

    def test_invariant_checks_and_corruption(self):
        records = fixture_sql()
        for name in ['vendor_facility_state', 'cookie_location']:
            template = (p.ROOT / f'tests/{name}.sql').read_text()
            failures = execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + records + ')'}))
            self.assertEqual(failures, [])
        columns = list(execute(records)[0])
        projection = ', '.join('999 AS cookie_state_count' if c == 'cookie_state_count' else c for c in columns)
        bad = 'SELECT ' + projection + ' FROM (' + records + ')'
        template = (p.ROOT / 'tests/cookie_location.sql').read_text()
        self.assertTrue(execute(p.render_sql(template, {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + bad + ')'})))

    def test_three_completed_days_exclude_today_and_older_observations(self):
        sql = fixture_sql(window_days=3, evaluation_day='2026-10-25').replace("'2026-10-29'", "'2026-10-25'")
        rows = execute(sql)
        for row in rows:
            self.assertEqual(row['cookie_location_window_days'],3)
            self.assertEqual(str(row['cookie_location_window_start']),'2026-10-22')
            self.assertEqual(str(row['cookie_location_window_end']),'2026-10-24')
            self.assertEqual(row['cookie_mapping_available_days'],3)
            self.assertEqual(row['cookie_location_available_days'],3)
            self.assertEqual(row['cookie_mapping_missing_days'],[])
        agree=next(r for r in rows if r['metric_row_id']=='agree')
        self.assertEqual(agree['cookie_count'],1)
        default = execute(p.render_sql("SELECT {{ cookie_window_start() }} AS start_day, {{ cookie_window_end() }} AS end_day, {{ cookie_window_days() }} AS days",{'location_evidence_day':'2026-10-25'}))[0]
        self.assertEqual(default['days'],3)
        self.assertEqual(str(default['start_day']),'2026-10-22')

    def test_all_vendor_models_have_matching_schemas_and_preserve_rows(self):
        fields = None
        for source in p.SOURCES:
            rows = execute(inlined(f'int_{source}__metrics'))
            self.assertEqual(len(rows), len({r['metric_row_id'] for r in rows}))
            if fields is not None:
                self.assertEqual(list(rows[0]), fields)
            fields = list(rows[0])
            self.assertTrue(all(not any(c.startswith('cookie_') for c in r) for r in rows))


if __name__ == '__main__':
    unittest.main()
