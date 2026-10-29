#!/usr/bin/env python3
"""Synthetic name comparisons and join invariants, runnable locally and on Trino."""
import unittest
import pipeline
from test_models import execute, literal

# Email, vendor first/last, registry first/last, expected three comparisons.
CASES = [
 ('john.smith@example.test','John','Smith','JOHN','SMITH',(True,True,True)),
 ('jsmith@example.test','John','Smith','Jane','Smith',(True,True,False)),
 ('smithj@example.test','John','Smith','John','Smith',(True,True,True)),
 ('bobsmith@example.test','Robert','Smith','Bob','Smith',(True,True,True)),
 ('robertsmith@example.test','Bob','Smith','Robert','Smith',(True,True,True)),
 ('johnsmit@example.test','John','Smith','John','Smith',(True,True,True)),
 ('random@example.test','John','Smith','John','Smith',(False,False,True)),
 ('johnsmith@example.test','Jane','Jones','John','Smith',(False,True,False)),
 ('johnsmith@example.test','John','Smith','Jane','Jones',(True,False,False)),
 ('johnsmith@example.test','John','Smith','John','Jones',(True,False,False)),
 ('joseobrien@example.test','José',"O’Brien",'Jose',"O'Brien",(True,True,True)),
 ('johnsmith@example.test','John','Smith-Jones','John','Smith',(False,True,True)),
 ('johnsmith@example.test','John','Smith','John Paul','Smith',(True,True,True)),
 ('kathleenjones@example.test','Kathleen','Jones','Kath','Jones',(True,True,True)),
 ('johnjohnson@example.test','John','Johnston','John','Johnson',(True,True,True)),
 ('johnsmith@example.test',None,None,'John','Smith',(None,True,None)),
 ('johnsmith@example.test','John','Smith',None,None,(True,None,None)),
 ('johnsmith@example.test',None,None,None,None,(None,None,None)),
 ('johnsmith@example.test','NULL','Smith','John','Smith',(None,True,None)),
 ('johnsmith@example.test','John','S','John','Smith',(None,True,None)),
 ('johnsmith@example.test',"'",'Smith','John','Smith',(None,True,None)),
 ('johnsmith.example.test','John','Smith','John','Smith',(False,False,True)),
 ('123456@example.test','John','Smith','John','Smith',(False,False,True)),
]


def rows_sql(rows, columns):
    values = ',\n'.join('(' + ', '.join(literal(v) for v in row) + ')' for row in rows)
    return 'SELECT * FROM (VALUES\n' + values + ') AS f(' + ', '.join(columns) + ')'


def fixture_sql():
    source_rows=[(e,str(i),f,l) for i,(e,f,l,rf,rl,expected) in enumerate(CASES)]
    registry_rows=[(str(i),rf,rl) for i,(e,f,l,rf,rl,expected) in enumerate(CASES)]
    return comparison_sql(source_rows, registry_rows)


def comparison_sql(source_rows, registry_rows, detail=False):
    variants=pipeline.read_model('int_name__variants', ref_overrides={'nicknames':'('+pipeline.read_model('nicknames')+')'})
    registry=pipeline.read_model('int_npi__names', ref_overrides={
        'stg_npi__reference':'('+rows_sql(registry_rows,['npi_clean','first_name','last_name'])+')',
        'int_name__variants':'('+variants+')'})
    inputs=pipeline.render_sql("SELECT DISTINCT email, npi, {{ norm_name('first_name') }} AS first_name, {{ norm_name('last_name') }} AS last_name FROM ("+rows_sql(source_rows,['email','npi','first_name','last_name'])+')')
    template = "{{ link_name_metrics(none, input_relation=var('inputs'), detail=" + ('true' if detail else 'false') + ') }}'
    return pipeline.render_sql(template, variables={'inputs':'('+inputs+')'}, ref_overrides={
        'int_name__variants':'('+variants+')',
        'int_npi__names':'('+registry+')'})


class NameMatchingTests(unittest.TestCase):
    def test_matching_boundaries(self):
        rows=execute(fixture_sql())
        self.assertEqual(len(rows),len(CASES))
        for row in rows:
            i=int(row['npi'])
            actual=tuple(row[k] for k in ('email_matches_source_name','email_matches_registry_name','vendor_name_matches_registry_name'))
            self.assertEqual(actual,CASES[i][-1],(i,CASES[i]))

    def test_duplicate_reference_names_and_unknowns_preserve_link_grain(self):
        sources=[('jsmith@example.test','1','Jane','Smith'),
                 ('jsmith@example.test','1','Jane','Smith'),
                 ('jsmith@example.test','1',None,None),
                 ('unknown@example.test','missing',None,None)]
        registry=[('1','John','Smith'),('1','John','Smith'),('1','Jane','Smith'),('1',None,None)]
        rows={r['npi']:r for r in execute(comparison_sql(sources,registry))}
        self.assertEqual(set(rows),{'1','missing'})
        self.assertTrue(rows['1']['vendor_name_matches_registry_name'])
        self.assertTrue(rows['1']['email_matches_registry_name'])
        self.assertFalse(rows['missing']['registry_npi_present'])
        self.assertIsNone(rows['missing']['vendor_name_matches_registry_name'])

    def test_never_combine_names_across_records(self):
        sources=[('random@example.test','1','John','Jones'),('random@example.test','1','Jane','Smith')]
        row=execute(comparison_sql(sources,[('1','John','Smith')]))[0]
        self.assertFalse(row['vendor_name_matches_registry_name'])

    def test_nickname_lookup_is_unique(self):
        sql=pipeline.read_model('int_name__variants',ref_overrides={'nicknames':'('+pipeline.read_model('nicknames')+')'})
        rows=execute(sql)
        self.assertEqual(len(rows),len({r['first_name'] for r in rows}))
        values={r['first_name']:r['variants'] for r in rows}
        self.assertIn('ROBERT',values['BOB'])
        self.assertIn('BOB',values['ROBERT'])

    def test_debug_details_preserve_partial_and_unknown_comparisons(self):
        sources=[('jsmith@example.test','1','Jane','Smith'),
                 ('unknown@example.test','missing',None,None)]
        registry=[('1','John','Smith'),('1','Jane','Smith')]
        details=execute(comparison_sql(sources,registry,detail=True))
        self.assertEqual(len(details),3)
        known=[r for r in details if r['npi']=='1']
        self.assertEqual({r['vendor_registry_match_class'] for r in known}, {'exact','last_only'})
        self.assertEqual({r['comparison_vendor_name_matches_registry_name'] for r in known}, {True,False})
        unknown=next(r for r in details if r['npi']=='missing')
        self.assertEqual(unknown['vendor_registry_match_class'],'unknown')
        self.assertIsNone(unknown['comparison_vendor_name_matches_registry_name'])
        aggregate={r['npi']:r for r in execute(comparison_sql(sources,registry))}
        for npi,row in aggregate.items():
            for metric in pipeline.NAME_METRICS:
                values=[r['comparison_'+metric] for r in details if r['npi']==npi
                        and r['comparison_'+metric] is not None]
                self.assertEqual(any(values) if values else None,row[metric])


if __name__=='__main__':
    unittest.main()
