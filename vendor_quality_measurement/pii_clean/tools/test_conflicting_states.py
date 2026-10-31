#!/usr/bin/env python3
"""State normalization, observation timing, unknowns and final UNION ALL fidelity."""
import json
import unittest
import pipeline as p
from test_models import execute, inlined, literal
from test_record_grain import source_values

CASES = {
 'same': [('1','01','NY',True),('2','01',' New York ',True)],
 'different': [('1','01','NY',False),('2','01','CA',False)],
 'missing': [('1','01','NY',None),('2','01',None,None)],
 'invalid': [('1','01','XX',None),('2','01','XX',None)],
 'reassigned': [('1','01','NY',None),('2','02','NY',None)],
 'gap': [('1','01','NY',None),('1','03','NY',None),('2','02','NY',None)],
 'changed': [('1','01','NY',False),('1','02','CA',True),('2','01','CA',True),('2','02','CA',True)],
 'match_missing': [('1','01','NY',True),('2','01','NY',True),('3','01',None,None)],
 'mismatch_missing': [('1','01','NY',None),('2','01','CA',None),('3','01',None,None)],
 'unknown_date': [('1',None,'NY',None),('2',None,'NY',None)],
}

def dated_fixture(debug=False):
 rows=[{'email_address':case+'@example.test','npi':npi,'day':'2026-01-'+day if day else None,
        'state':state,'country':'US'} for case,values in CASES.items() for npi,day,state,_ in values]
 rows.append(dict(rows[0]))
 rows += [{'email_address':'foreign@example.test','npi':npi,'day':'2026-01-01','state':'CA','country':country}
          for npi,country in [('1','US'),('2','Canada')]]
 return inlined('int_medscape__metrics',variables={'debug':debug},fixtures={
     'stg_medscape__global':source_values('stg_medscape__global',rows)})

def check_dated(rows):
 expected={(case,npi,state):flag for case,vs in CASES.items() for npi,day,state,flag in vs}
 expected.update({('foreign','1','CA'):None,('foreign','2','CA'):None})
 assert len(rows)==len(expected)
 assert len({r['metric_row_id'] for r in rows})==len(rows)
 for r in rows:
  raw=json.loads(r['record_payload']);key=(r['email'].split('@')[0],r['npi'],raw['state'])
  assert r['conflicting_npis_share_state'] is expected[key],(key,r['conflicting_npis_share_state'])
  assert bool(r['conflicting_npi_state_comparisons']) == (r['has_conflict_linkage'] is True)
  if key==('foreign','2','CA'):assert r['source_state_values']==[]

def undated_fixture():
 return inlined('int_endato__metrics',fixtures={'stg_endato__pii':source_values('stg_endato__pii',[
  {'email_1_address':'same@example.test','npi':'1','address_state':'ny','provider_business_practice_location_address_state_name':'CA'},
  {'email_1_address':'same@example.test','npi':'2','address_state':'NEW YORK'},
  {'email_1_address':'missing@example.test','npi':'1','address_state':None,'provider_business_practice_location_address_state_name':'CA'},
  {'email_1_address':'missing@example.test','npi':'2','address_state':'CA'}])})

def check_undated(rows):
 assert len(rows)==4
 for r in rows:
  assert r['conflicting_npis_share_state'] is (True if r['email']=='same@example.test' else None)
  assert r['conflict_days']==[]
  if r['email']=='missing@example.test' and r['npi']=='1':assert r['source_state_values']==[]

def healthlink_fixture():
 return inlined('int_healthlink__metrics',fixtures={
  'stg_healthlink__email':source_values('stg_healthlink__email',[
   {'npi':npi,'day':'2026-01-01','hld_email':'same@example.test'} for npi in ['1','2']]),
  'stg_healthlink__hcp':"(SELECT *, CAST(NULL AS varchar) AS day, CAST(NULL AS varchar) AS phone, CAST(NULL AS varchar) AS specialty FROM (VALUES ('1','JOHN','SMITH','NY'),('1','JOHN','SMITH','CA'),('1','JOHN','SMITH','NY'),('2','JANE','JONES','New York')) AS t(npi,firstname,lastname,state))"})

def check_healthlink(rows):
 assert len(rows)==2
 assert all(r['conflicting_npis_share_state'] is True for r in rows)
 assert next(r for r in rows if r['npi']=='1')['source_state_values']==['CA','NY']

FIXTURES={'dated_states':(dated_fixture,check_dated),'undated_states':(undated_fixture,check_undated),
          'healthlink_states':(healthlink_fixture,check_healthlink)}

class ConflictingStateTests(unittest.TestCase):
 def test_fixtures(self):
  for name,(make,check) in FIXTURES.items():
   with self.subTest(name=name):check(execute(make()))
 def test_normalization(self):
  cases=[(' new   york ','NY'),('ny','NY'),('California','CA'),('PR','PR'),('Ontario',None),('XX',None),('',None),(None,None)]
  sql=p.render_sql("SELECT i, {{ normalized_state('value') }} AS state FROM (VALUES "+','.join(f'({i},{literal(x)})' for i,(x,_) in enumerate(cases))+') AS t(i,value)')
  for row in execute(sql):self.assertEqual(row['state'],cases[row['i']][1])
 def test_country_context(self):
  for payload,expected in [({'region':'CA','country_code':'US','country':'Canada'},[]),
                           ({'region':'CA','country':'Canada'},[]),
                           ({'region':'California','country':'United States'},['CA']),
                           ({'region':'CA'},['CA'])]:
   sql=p.render_sql("SELECT {{ state_values_from_payload('rocketreach', 'payload') }} AS states FROM (VALUES ("+literal(json.dumps(payload))+")) AS t(payload)")
   self.assertEqual(execute(sql)[0]['states'],expected)
 def test_population_check_and_debug(self):
  sql=dated_fixture();rows=execute(sql);fields=list(rows[0])
  template=(p.ROOT/'tests/conflicting_states.sql').read_text()
  def check(q):return execute(p.render_sql(template,{'metric_model':p.FINAL_MODEL},{p.FINAL_MODEL:'('+q+')'}))
  self.assertEqual(check(sql),[])
  projection=', '.join('false AS '+c if c=='conflicting_npis_share_state' else c for c in fields)
  self.assertTrue(check(f'SELECT {projection} FROM ({sql})'))
  expected={r['metric_row_id']:r for r in rows}
  for row in execute(dated_fixture(debug=True)):
   for c in ['source_state_values','conflicting_npis_share_state','conflicting_npi_state_comparisons']:
    self.assertEqual(row[c],expected[row['metric_row_id']][c])
 def test_final_is_exact_union_including_extra_attributes_and_duplicates(self):
  inputs={f'int_{s}__metrics':f"(SELECT '{s}' AS source, 'same' AS email, '1' AS npi, 'raw-{s}' AS vendor_attribute, true AS custom_metric FROM (VALUES (1),(1)) AS copies(x))" for s in p.SOURCES}
  rows=execute(p.read_model(p.CORE_MODEL,ref_overrides=inputs))
  self.assertEqual(len(rows),14)
  self.assertTrue(all(r['vendor_attribute']=='raw-'+r['source'] and r['custom_metric'] is True for r in rows))
  self.assertEqual(p.relation(p.FINAL_MODEL),'iceberg.jteixeira_ipa.pii_clean')

if __name__=='__main__':unittest.main()
