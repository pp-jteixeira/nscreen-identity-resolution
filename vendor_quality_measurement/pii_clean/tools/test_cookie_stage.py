"""Cookie metrics are computed downstream of stored core attribution."""
import unittest
import pipeline as p
from test_models import execute,inlined
from test_record_grain import source_values
from test_location_evidence import fixture_sql


class CookieStageTests(unittest.TestCase):
    def test_vendor_models_have_no_cookie_dependencies(self):
        for source in p.SOURCES:
            sql=p.read_model('int_'+source+'__metrics')
            self.assertNotIn('liveintent_idsync',sql)
            self.assertNotIn('nscreen_geo_daily_ua',sql)
        rows=execute(inlined('int_medscape__metrics'))
        self.assertEqual(len(rows[0]),124)
        self.assertFalse(any(c.startswith('cookie_') for c in rows[0]))

    def test_downstream_model_computes_real_values_and_preserves_core(self):
        data=[{'email_address':'agree@example.test','npi':'1','day':'2026-10-22','state':'NY','first_name':'JOHN','last_name':'SMITH'},
              {'email_address':'agree@example.test','npi':'1','day':'2026-10-23','state':'NY','first_name':'JOHN','last_name':'JONES'},
              {'email_address':'disagree@example.test','npi':'1','day':'2026-10-22','state':'CA','first_name':'JANE','last_name':'SMITH'}]
        _,variables,overrides=fixture_sql(context=True,window_days=3,evaluation_day='2026-10-25')
        base=inlined('int_medscape__metrics',fixtures={
            'stg_medscape__global':source_values('stg_medscape__global',data),
            'facility_locations':overrides[('bq_bi__analytics_prod','npi_facility_locations_with_ids')]},variables=variables)
        original={r['metric_row_id']:r for r in execute(base)}
        sql=p.read_model('int_cookie__metrics',variables=variables,
                         ref_overrides={p.CORE_MODEL:'('+base+')'},source_overrides=overrides)
        rows=execute(sql)
        self.assertEqual(len(rows),3)
        for row in rows:
            self.assertEqual(len(row),154)
            self.assertEqual(row['cookie_count'],1)
            self.assertEqual(row['cookie_location_status'],'observed')
            self.assertEqual(row['cookie_location_window_days'],3)
            self.assertEqual(row['cookie_facility_state_evidence'],'corroborated')
            self.assertEqual(row['cookie_vendor_state_evidence'],'corroborated' if row['email']=='agree@example.test' else 'not_observed')
            self.assertEqual({k:v for k,v in row.items() if not k.startswith('cookie_') and k!='computed_at'},
                             {k:v for k,v in original[row['metric_row_id']].items() if k!='computed_at'})
        self.assertNotIn('not_evaluated',sql)

    def test_model_dependencies_follow_core_cookie_final_order(self):
        dependencies=[];p.read_model('int_cookie__metrics',dependencies=dependencies)
        self.assertEqual(set(dependencies),{p.CORE_MODEL})
        dependencies=[];p.read_model(p.FINAL_MODEL,dependencies=dependencies)
        self.assertEqual(set(dependencies),{'int_cookie__metrics'})
        self.assertNotIn('int_cookie__metrics',p.source_plan('medscape'))
        fields=[(k,'varchar') for k in p.render_sql('{{ metric_columns() | join(",") }}').split(',')]
        self.assertEqual(len(p.publication_schema(fields)),154)
        for bad in [fields[:-1],fields+[('unexpected','varchar')]]:
            with self.assertRaises(ValueError):p.publication_schema(bad)


if __name__=='__main__':unittest.main()
