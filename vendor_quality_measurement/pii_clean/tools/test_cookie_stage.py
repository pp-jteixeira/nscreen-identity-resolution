"""Cookie metrics are computed downstream of stored core attribution."""
import unittest
import yaml
import pipeline as p
from test_models import execute,inlined
from test_record_grain import source_values
from test_location_evidence import fixture_sql


class CookieStageTests(unittest.TestCase):
    def test_declared_core_and_cookie_schemas_match_contract(self):
        declared=yaml.safe_load((p.ROOT/'models/intermediate/schema.yml').read_text())['models']
        core=p.render_sql('{{ metric_columns() | join(",") }}').split(',')
        final=p.render_sql('{{ metric_columns(include_cookie=true) | join(",") }}').split(',')
        for model in declared:
            if model['name'].endswith('__metrics'):
                expected=final if model['name']=='int_cookie__metrics' else core
                self.assertEqual([c['name'] for c in model['columns']],expected,model['name'])

    def test_vendor_models_have_no_cookie_dependencies(self):
        for source in p.SOURCES:
            sql=p.read_model('int_'+source+'__metrics')
            self.assertNotIn('liveintent_idsync',sql)
            self.assertNotIn('nscreen_geo_daily_ua',sql)
        rows=execute(inlined('int_medscape__metrics'))
        self.assertEqual(len(rows[0]),134)
        self.assertFalse(any(c.startswith('cookie_') for c in rows[0]))

    def test_downstream_model_computes_real_values_and_preserves_core(self):
        data=[{'email_address':'agree@example.test','npi':'1','day':'2026-10-22','state':'NY','first_name':'JOHN','last_name':'SMITH'},
              {'email_address':'agree@example.test','npi':'1','day':'2026-10-23','state':'NY','first_name':'JOHN','last_name':'JONES'},
              {'email_address':'disagree@example.test','npi':'1','day':'2026-10-22','state':'CA','first_name':'JANE','last_name':'SMITH'}]
        _,variables,overrides=fixture_sql(context=True,window_days=3,evaluation_day='2026-10-25')
        base=inlined('int_medscape__metrics',fixtures={
            'stg_medscape__global':source_values('stg_medscape__global',data),
            'facility_locations':overrides[('bq_bi__analytics_prod','npi_facility_locations_with_ids')]},variables=variables)
        original={r['link_id']:r for r in execute(base)}
        sql=p.read_model('int_cookie__metrics',variables=variables,
                         ref_overrides={p.CORE_MODEL:'('+base+')'},source_overrides=overrides)
        rows=execute(sql)
        # The two agree@ name versions share one link.
        self.assertEqual(len(rows),2)
        for row in rows:
            self.assertEqual(len(row),165)
            self.assertEqual(row['cookie_count'],1)
            self.assertEqual(row['cookie_location_status'],'observed')
            self.assertEqual(row['cookie_location_window_days'],3)
            self.assertEqual(row['cookie_facility_state_evidence'],'corroborated')
            self.assertEqual(row['cookie_vendor_state_evidence'],'corroborated' if row['email']=='agree@example.test' else 'not_observed')
            self.assertEqual({k:v for k,v in row.items() if not k.startswith('cookie_') and k!='computed_at'},
                             {k:v for k,v in original[row['link_id']].items() if k!='computed_at'})
        self.assertNotIn('not_evaluated',sql)

    def test_model_dependencies_follow_core_cookie_final_order(self):
        dependencies=[];p.read_model('int_cookie__metrics',dependencies=dependencies)
        self.assertEqual(set(dependencies),{p.CORE_MODEL})
        dependencies=[];p.read_model(p.FINAL_MODEL,dependencies=dependencies)
        self.assertEqual(set(dependencies),{'int_cookie__metrics'})
        self.assertNotIn('int_cookie__metrics',p.source_plan('medscape'))
        fields=[(k,'varchar') for k in p.render_sql('{{ metric_columns() | join(",") }}').split(',')]
        self.assertEqual(len(p.publication_schema(fields)),165)
        for bad in [fields[:-1],fields+[('unexpected','varchar')]]:
            with self.assertRaises(ValueError):p.publication_schema(bad)

    def test_separate_sources_preserve_shared_email_evidence_and_own_state(self):
        data=[{'email_address':'agree@example.test','npi':'1','day':'2026-10-22',
               'state':'NY','first_name':'JOHN','last_name':'SMITH'}]
        _,variables,overrides=fixture_sql(context=True,window_days=3,evaluation_day='2026-10-25')
        base=inlined('int_medscape__metrics',fixtures={
            'stg_medscape__global':source_values('stg_medscape__global',data),
            'facility_locations':overrides[('bq_bi__analytics_prod','npi_facility_locations_with_ids')]},variables=variables)
        columns=list(execute(base)[0])
        base='SELECT '+', '.join("TIMESTAMP '2026-10-25 12:00:00 UTC' AS computed_at" if name=='computed_at'
                                  else name for name in columns)+' FROM ('+base+')'
        second=', '.join("'healthlink' AS source" if name=='source' else
                        "ARRAY['CA'] AS source_state_values" if name=='source_state_values' else name for name in columns)
        core='('+base+' UNION ALL SELECT '+second+' FROM ('+base+'))'
        combined=p.render_sql("{{ cookie_location_records(var('input')) }}",
                              {**variables,'input':core},source_overrides=overrides)
        scoped=[]
        for source in ('medscape','healthlink'):
            sql=p.read_model('int_cookie__metrics',variables={**variables,'cookie_sources':[source]},
                             ref_overrides={p.CORE_MODEL:core},source_overrides=overrides)
            scoped.extend(execute(sql))
        keyed=lambda rows:{(r['source'],r['link_id']):r for r in rows}
        self.assertEqual(keyed(scoped),keyed(execute(combined)))
        self.assertEqual(len(scoped),2)
        self.assertEqual({r['cookie_count'] for r in scoped},{1})
        self.assertEqual({r['source']:r['cookie_vendor_state_evidence'] for r in scoped},
                         {'medscape':'corroborated','healthlink':'not_observed'})


if __name__=='__main__':unittest.main()
