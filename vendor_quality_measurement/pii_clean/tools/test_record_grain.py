#!/usr/bin/env python3
"""Exact-record history and per-record indicators; also supplies native Trino fixtures."""
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
    base={'npi':'123','name':'JOHN SMITH','updated_at':SQL("TIMESTAMP '2026-01-01 12:00:00.123456'")}
    stage = 'stg_rocketreach__lookup'
    staged = inlined(stage, fixtures={stage: source_values(stage,
        [base, base, dict(base, updated_at=SQL("TIMESTAMP '2026-01-02 12:00:00.123456'"))])})
    return p.render_sql("{{ record_versions('stg_rocketreach__lookup') }}",
                        ref_overrides={stage: '(' + staged + ')'})


def check_medscape(rows):
    assert len(rows)==6, len(rows)
    assert len({r['record_id'] for r in rows})==6
    assert len({r['metric_row_id'] for r in rows})==6
    assert len({(r['email'],r['npi']) for r in rows})==1
    repeated=next(r for r in rows if r['observation_count']==3)
    assert str(repeated['first_seen_day'])[:10]=='2026-01-01'
    assert str(repeated['last_seen_day'])[:10]=='2026-01-02'
    assert repeated['observed_day_count']==2
    changed=next(r for r in rows if json.loads(r['record_payload'])['first_name']=='JANE')
    assert changed['email_matches_source_name'] is False
    assert changed['vendor_name_matches_registry_name'] is False
    assert all(r['email_matches_source_name'] is True for r in rows if r is not changed)
    assert all('day' not in json.loads(r['record_payload']) for r in rows)


def check_quantum(rows):
    assert len(rows)==2
    assert len({r['record_id'] for r in rows})==1
    assert len({r['metric_row_id'] for r in rows})==2
    assert {r['email_ordinal'] for r in rows}=={1,2}
    assert all(r['observation_count']==2 for r in rows)


def check_rocket(rows):
    assert len(rows)==2
    assert sorted(r['observation_count'] for r in rows)==[1,2]
    assert len({json.loads(r['record_payload'])['updated_at'] for r in rows})==2


FIXTURES={'changed_records':(medscape_fixture,check_medscape),
          'repeated_email_slots':(quantum_fixture,check_quantum),
          'non_delivery_timestamps':(rocket_fixture,check_rocket)}

class RecordGrainTests(unittest.TestCase):
    def test_record_identity_and_metrics(self):
        for name,(sql,check) in FIXTURES.items():
            with self.subTest(case=name):check(execute(sql()))

    def test_debug_comparisons_keep_changed_records_separate(self):
        metrics = medscape_fixture()
        sql = medscape_fixture(debug=True)
        rows = execute(sql)
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({r['debug_comparison_id'] for r in rows}), 6)
        self.assertEqual(sum(r['comparison_vendor_name_matches_registry_name'] for r in rows), 5)
        expected = {row['metric_row_id']: row for row in execute(metrics)}
        for row in rows:
            for metric in p.NAME_METRICS:
                self.assertEqual(row['comparison_' + metric], expected[row['metric_row_id']][metric])

if __name__=='__main__':unittest.main()
