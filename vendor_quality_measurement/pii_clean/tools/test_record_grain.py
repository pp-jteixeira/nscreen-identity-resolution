#!/usr/bin/env python3
"""Version merging, link history and all-version vs latest indicators; also supplies native Trino fixtures."""
import json
import unittest
import pipeline as p
from test_models import SQL, execute, inlined, literal


def source_values(stage, rows):
    columns=json.loads((p.ROOT/'models/record_schemas.json').read_text())[stage]['columns']
    values=[]
    for row in rows:
        values.append('('+', '.join(literal(row[c['name']]) if c['name'] in row
                     else 'CAST(NULL AS '+c['type']+')' for c in columns)+')')
    return '(SELECT * FROM (VALUES '+',\n'.join(values)+') AS s('+', '.join('"'+c['name']+'"' for c in columns)+'))'


def medscape_fixture(debug=False):
    base={'day':'2026-01-01','npi':'123','email_address':'jsmith@example.test','first_name':'JOHN','last_name':'SMITH','source':'feed_a','guid':'person_1','street_address_1':'1 Main St'}
    rows=[dict(base),dict(base),dict(base,day='2026-01-02'),
          dict(base,day='2026-01-03',first_name='JANE',last_name='JONES'),
          dict(base,day='2026-01-04',street_address_1='2 Main St'),
          dict(base,day='2026-01-05',email_address='JSMITH@example.test'),
          dict(base,day='2026-01-06',source='feed_b'),
          dict(base,day='2026-01-07',guid='person_2')]
    return inlined('int_medscape__metrics',variables={'debug':debug},fixtures={
        'stg_medscape__global':source_values('stg_medscape__global',rows),
        'stg_npi__reference':"(SELECT '123' AS npi, 'JOHN' AS first_name, 'SMITH' AS last_name)"})


def quantum_fixture():
    base={'day':'2026-01-01','npi':'123','email':'jsmith@example.test|jsmith@example.test','first_name':'JOHN','last_name':'SMITH'}
    return inlined('int_quantummedica__metrics',fixtures={
        'stg_quantummedica__hcpdata':source_values('stg_quantummedica__hcpdata',[base,dict(base,day='2026-01-02')])})


def rocket_fixture():
    base={'npi':'123','name':'JOHN SMITH','recommended_email':'jsmith@example.test',
          'updated_at':SQL("TIMESTAMP '2026-01-01 12:00:00.123456'")}
    stage = 'stg_rocketreach__lookup'
    return inlined('int_rocketreach__metrics', fixtures={stage: source_values(stage,
        [base, base, dict(base, updated_at=SQL("TIMESTAMP '2026-01-02 12:00:00.123456'"))])})


def check_medscape(rows):
    # All fixture rows share one email and NPI: one link holding four versions.
    # Email case and source label are volatile and merge into the base version.
    assert len(rows)==1, len(rows)
    link=rows[0]
    assert link['record_count']==4 and len(link['record_ids'])==4
    versions=link['attribute_versions']
    assert [v['record_id'] for v in versions]==sorted(link['record_ids'], key=lambda r: next(
        (str(v['first_seen_day']), str(v['last_seen_day']), v['record_id']) for v in versions if v['record_id']==r))
    assert link['observation_count']==8 and link['observed_day_count']==7
    assert str(link['first_seen_day'])[:10]=='2026-01-01' and str(link['last_seen_day'])[:10]=='2026-01-07'
    base=next(v for v in versions if v['observation_count']==5)
    assert str(base['first_seen_day'])[:10]=='2026-01-01' and str(base['last_seen_day'])[:10]=='2026-01-06'
    merged=json.loads(base['record_payload'])
    assert merged['source']==['feed_a','feed_b']
    assert merged['email_address']==['JSMITH@example.test','jsmith@example.test']
    assert link['source_feeds']==['feed_a','feed_b']
    assert all('day' not in json.loads(v['record_payload']) for v in versions)
    # The GUID person_2 version is the only one seen on the last day.
    latest=next(v for v in versions if v['record_id']==link['latest_record_id'])
    assert json.loads(latest['record_payload'])['guid']=='person_2'
    assert link['email_matches_source_name'] is True and link['email_matches_source_name_latest'] is True
    assert link['vendor_name_matches_registry_name'] is True and link['vendor_name_matches_registry_name_latest'] is True
    assert {n['first_name'] for n in link['source_name_values']}=={'JOHN','JANE'}


def check_quantum(rows):
    # The same email in two positions of one record is one link and one version.
    assert len(rows)==1
    assert rows[0]['record_count']==1
    assert rows[0]['email_origins']==['email_token_1','email_token_2']
    assert rows[0]['observation_count']==2


def check_rocket(rows):
    # Undated versions: two records merge into one link without a single latest version.
    assert len(rows)==1
    link=rows[0]
    assert link['record_count']==2 and link['observation_count']==3
    assert sorted(v['observation_count'] for v in link['attribute_versions'])==[1,2]
    assert len({json.loads(v['record_payload'])['updated_at'] for v in link['attribute_versions']})==2
    assert link['latest_record_id'] is None and link['source_state_values_latest'] is None


FIXTURES={'changed_records':(medscape_fixture,check_medscape),
          'repeated_email_slots':(quantum_fixture,check_quantum),
          'non_delivery_timestamps':(rocket_fixture,check_rocket)}

class RecordGrainTests(unittest.TestCase):
    def test_record_identity_and_metrics(self):
        for name,(sql,check) in FIXTURES.items():
            with self.subTest(case=name):check(execute(sql()))

    def test_debug_comparisons_cover_every_link_name(self):
        metrics = {r['link_id']: r for r in execute(medscape_fixture())}
        rows = execute(medscape_fixture(debug=True))
        # One debug row per distinct vendor name of the link.
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['debug_comparison_id'] for r in rows}), 2)
        self.assertEqual(sum(r['comparison_vendor_name_matches_registry_name'] for r in rows), 1)
        for metric in p.NAME_METRICS:
            for link_id, link in metrics.items():
                values = [r['comparison_' + metric] for r in rows if r['link_id'] == link_id]
                expected = True if True in values else (False if False in values else None)
                self.assertEqual(link[metric], expected, metric)


if __name__=='__main__':unittest.main()
