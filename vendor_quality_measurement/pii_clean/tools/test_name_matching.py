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


    def test_stored_classes_retain_scoring_distinctions(self):
        cases = [
            ('exact', 'JOHN', 'SMITH', 'JOHN', 'SMITH', True),
            ('nickname', 'BOB', 'SMITH', 'ROBERT', 'SMITH', True),
            ('token', 'JOHN PAUL', 'SMITH', 'JOHN', 'SMITH', True),
            ('edit', 'JOHN', 'JOHNSTON', 'JOHN', 'JOHNSON', True),
            ('first_only', 'JOHN', 'SMITH', 'JOHN', 'JONES', False),
            ('last_only', 'JANE', 'SMITH', 'JOHN', 'SMITH', False),
            ('none', 'JANE', 'JONES', 'JOHN', 'SMITH', False),
            ('unknown', None, None, 'JOHN', 'SMITH', None),
        ]
        sources = [('jsmith@example.test', label, first, last) for label, first, last, _, _, _ in cases]
        registry = [(label, first, last) for label, _, _, first, last, _ in cases]
        rows = {r['npi']: r for r in execute(comparison_sql(sources, registry))}
        for label, _, _, _, _, expected in cases:
            row = rows[label]
            self.assertEqual(row['vendor_registry_match_classes'], [label])
            self.assertEqual(len(row['name_match_evidence']), 1)
            item = row['name_match_evidence'][0]
            self.assertEqual(item['match_class'], label)
            self.assertIs(item['vendor_name_matches_registry_name'], expected)
            self.assertIs(row['vendor_name_matches_registry_name'], expected)
            self.assertEqual(row['name_match_definition_version'], 'stored_name_comparisons_v1')
            self.assertIsNotNone(row['name_match_evaluated_at'])

    def test_all_reference_outcomes_are_retained_without_duplicate_votes(self):
        sources = [('jsmith@example.test', '1', 'JANE', 'SMITH')]
        registry = [('1', 'JANE', 'SMITH'), ('1', 'JANE', 'SMITH'),
                    ('1', 'JOHN', 'SMITH'), ('1', None, None)]
        row = execute(comparison_sql(sources, registry))[0]
        self.assertEqual(row['vendor_registry_match_classes'], ['exact', 'last_only', 'unknown'])
        self.assertEqual(len(row['name_match_evidence']), 3)
        self.assertTrue(row['vendor_name_matches_registry_name'])
        self.assertEqual({r['vendor_name_matches_registry_name'] for r in row['name_match_evidence']},
                         {True, False, None})
        # Unknown references do not erase a known disagreement in bool_or.
        row = execute(comparison_sql(sources, registry[2:]))[0]
        self.assertFalse(row['vendor_name_matches_registry_name'])
        self.assertEqual(row['vendor_registry_match_classes'], ['last_only', 'unknown'])

    def test_unusable_vendor_names_have_one_unknown_fallback(self):
        registry = [('1', 'JOHN', 'SMITH')]
        sources = [('jsmith@example.test', '1', None, 'SMITH'),
                   ('jsmith@example.test', '1', 'JOHN', None)]
        row = execute(comparison_sql(sources, registry))[0]
        self.assertEqual(len(row['name_match_evidence']), 1)
        self.assertEqual(row['vendor_registry_match_classes'], ['unknown'])
        self.assertIsNone(row['name_match_evidence'][0]['source_first_name'])
        row = execute(comparison_sql(sources + [('jsmith@example.test', '1', 'JOHN', 'SMITH')], registry))[0]
        self.assertEqual(row['vendor_registry_match_classes'], ['exact'])
        self.assertEqual(len(row['name_match_evidence']), 1)

    def test_stored_evidence_integrity_rejects_corruption(self):
        query = "SELECT 'fixture' AS source, npi AS link_id, * FROM (" + fixture_sql() + ')'
        template = (pipeline.ROOT / 'tests/name_match_evidence.sql').read_text()
        def check(sql):
            return execute(pipeline.render_sql(template, {'metric_model': pipeline.CORE_MODEL},
                                                {pipeline.CORE_MODEL: '(' + sql + ')'}))
        self.assertEqual(check(query), [])
        fields = list(execute(query)[0])
        for field, replacement in [
            ('vendor_registry_match_classes', "ARRAY['invented']"),
            ('vendor_name_matches_registry_name', 'NOT vendor_name_matches_registry_name'),
            ('name_match_evidence', "slice(name_match_evidence, 1, 0)"),
        ]:
            corrupted = 'SELECT ' + ', '.join(replacement + ' AS ' + name if name == field else name for name in fields) + ' FROM (' + query + ')'
            self.assertTrue(check(corrupted), field)


if __name__=='__main__':
    unittest.main()
