#!/usr/bin/env python3
"""Execute synthetic model fixtures locally with DuckDB after Trino SQL translation.

This checks model behavior while Trino is unavailable; it does not replace live Trino tests.
"""
import argparse
import json
import unittest

import duckdb
import pipeline
import sqlglot

CASES = [
    ('ordinary', 'alex@example.test', True),
    ('plus', 'alex+work@example.test', True),
    ('apostrophe', "o'neil@example.test", False),
    ('international', 'josé@example.test', False),
    ('quoted', '"alex smith"@example.test', False),
    ('ip_literal', 'alex@[192.0.2.1]', False),
    ('double_dot_local', 'alex..smith@example.test', True),
    ('double_dot_domain', 'alex@example..test', True),
    ('leading_dot', '.alex@example.test', True),
    ('leading_hyphen_domain', 'alex@-example.test', True),
    ('missing_at', 'alex.example.test', False),
    ('missing_domain', 'alex@', False),
    ('one_letter_suffix', 'alex@b.c', False),
    ('one_character_domain', 'alex@b.test', True),
    ('uppercase', 'Alex@EXAMPLE.TEST', False),
    ('internal_space', 'alex smith@example.test', False),
    ('role_account', 'info@example.test', True),
    ('test_prefix', 'testqaa@example.test', True),
    ('missing', None, None),
    ('empty', '', False),
]

class SQL(str):
    pass


def literal(value):
    if isinstance(value, SQL):
        return str(value)
    if value is None:
        return 'CAST(NULL AS varchar)'
    return "'" + str(value).replace("'", "''") + "'"


TABLE_COLUMNS = {
    'stg_npi__reference': 'npi first_name last_name',
    'stg_healthlink__email': 'npi hld_email day emailrank bestemail',
    'stg_healthlink__hcp': 'npi day firstname lastname state phone',
    'stg_quantummedica__hcpdata': 'npi day email first_name last_name state',
    'stg_quantummedica__hcpmeta': 'npi day profession primary_specialty',
    'stg_medscape__global': 'npi day email_address guid first_name last_name state source',
    'stg_medscape__meta': 'npi day guid profession',
    'stg_medscape__optout': 'npi day optout_day',
    'stg_endato__pii': 'npi email_1_address email_2_address email_3_address email_4_address email_5_address name_first name_last email',
    'stg_rocketreach__lookup': 'npi name region emails recommended_email recommended_personal_email recommended_professional_email current_work_email current_personal_email',
    'stg_drdb__npi': 'npi emailaddress firstname lastname state',
    'stg_drdb__enrich': 'npi email name state',
    'stg_haymarket__npi': 'npi_number day email first_name last_name',
}


def fixture(name):
    columns = TABLE_COLUMNS[name].split()
    values = {c: ' Alice ' for c in columns}
    npi = 'npi_number' if name == 'stg_haymarket__npi' else 'npi'
    values[npi] = ' 123 '
    if 'day' in values:
        values['day'] = '2020-01-01'
    for c in ('hld_email', 'email_address', 'emailaddress', 'email'):
        if c in values:
            values[c] = ' Alex@Example.test '
    if name == 'stg_quantummedica__hcpdata':
        values['email'] = ' Alex@Example.test | alex@example.test | Second@Example.test '
    if name == 'stg_endato__pii':
        values.update(email='provider@example.test', email_1_address=' Alex@Example.test ',
                      email_2_address='alex@example.test', email_3_address='second@example.test',
                      email_4_address=None, email_5_address=None)
    if name == 'stg_rocketreach__lookup':
        values['emails'] = SQL("ARRAY[CAST(ROW(' Alex@Example.test ') AS ROW(email varchar)), CAST(ROW('second@example.test') AS ROW(email varchar))]")
        for c in columns:
            if 'email' in c and c != 'emails':
                values[c] = None
        values['recommended_email'] = 'alex@example.test'
    values.update({c: ' NY ' for c in ('state', 'region') if c in values})
    if 'source' in values:
        values['source'] = 'MEDSCAPE REGISTRATION'
    if 'emailrank' in values:
        values['emailrank'] = '1'
        values['bestemail'] = '1'
    if 'optout_day' in values:
        values['optout_day'] = '2020-01-02'
    schema_path = pipeline.ROOT / 'models/record_schemas.json'
    schema = json.loads(schema_path.read_text()).get(name)
    if schema:
        for field in schema['columns']:
            if field['name'] not in values:
                values[field['name']] = SQL('CAST(NULL AS ' + field['type'] + ')')
        columns = [field['name'] for field in schema['columns']]
        if name == 'stg_rocketreach__lookup':
            values['emails'] = SQL("ARRAY[CAST(ROW(' Alex@Example.test ', NULL, NULL, NULL, NULL) AS ROW(email varchar, smtp_valid varchar, type varchar, last_validation_check varchar, grade varchar)), CAST(ROW('second@example.test', NULL, NULL, NULL, NULL) AS ROW(email varchar, smtp_valid varchar, type varchar, last_validation_check varchar, grade varchar))]")
    rows = []
    for index in range(4):
        row = dict(values)
        if index in (1, 2) and 'day' in row:
            row['day'] = '2026-10-28'
        if index == 2:
            row[npi] = '456'
        if index == 3:
            row[npi] = ' '
            if 'day' in row:
                row['day'] = 'bad-date'
            for c in columns:
                if 'email' in c:
                    row[c] = SQL('CAST(NULL AS ' + next(f['type'] for f in schema['columns'] if f['name'] == c) + ')') if schema else None
        rows.append('(' + ', '.join(literal(row[c]) for c in columns) + ')')
    return '(SELECT * FROM (VALUES\n' + ',\n'.join(rows) + '\n) AS input(' + ', '.join(columns) + '))'


def execute(sql):
    def translate_match(node):
        # Trino SHA256 returns bytes; DuckDB SHA256 returns hex text already.
        # Avoid hex-encoding that text a second time in local fixture execution.
        if isinstance(node, sqlglot.exp.Hex) and isinstance(node.this, sqlglot.exp.SHA2):
            if isinstance(node, sqlglot.exp.LowerHex):
                return node.this.copy()
            return sqlglot.exp.Upper(this=node.this.copy())
        if isinstance(node, sqlglot.exp.Cast) and node.args['to'].is_type(sqlglot.exp.DataType.Type.JSON):
            return sqlglot.exp.Anonymous(this='to_json', expressions=[node.this.copy()])
        if isinstance(node, sqlglot.exp.Anonymous) and node.name.lower() == 'any_match':
            args = ', '.join(arg.copy().transform(translate_match).sql(dialect='trino') for arg in node.expressions)
            return sqlglot.parse_one('trino_any_match(transform(' + args + '))', read='trino')
        return node
    translated = sqlglot.parse_one(sql, read='trino').transform(translate_match).sql(dialect='duckdb')
    with duckdb.connect() as db:
        # sqlglot leaves this Trino function untranslated. Preserve SQL null semantics.
        db.execute('''CREATE MACRO arrays_overlap(a, b) AS CASE
            WHEN a IS NULL OR b IS NULL THEN NULL
            WHEN list_has_any(a, b) THEN TRUE
            WHEN len(a) > 0 AND len(b) > 0
                 AND (list_position(a, NULL) IS NOT NULL OR list_position(b, NULL) IS NOT NULL) THEN NULL
            ELSE FALSE END''')
        db.execute('''CREATE MACRO trino_any_match(matches) AS CASE
            WHEN matches IS NULL THEN NULL
            WHEN list_contains(matches, TRUE) THEN TRUE
            WHEN list_position(matches, NULL) IS NOT NULL THEN NULL
            ELSE FALSE END''')
        db.execute('CREATE MACRO levenshtein_distance(a, b) AS levenshtein(a, b)')
        cursor = db.execute(translated)
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def inlined(name, cache=None, fixtures=None, variables=None):
    variables = {'location_metadata_from_rows': True, 'location_evidence_day': '2026-10-29', **(variables or {})}
    cache = cache if cache is not None else {}
    key = (name, json.dumps(variables, sort_keys=True))
    if key in cache:
        return cache[key]
    dependencies = []
    pipeline.read_model(name, dependencies=dependencies, variables=variables)
    overrides = {dep: '(' + inlined(dep, cache, fixtures) + ')' for dep in dependencies}
    source_overrides = {('bq_bi__analytics_prod', 'npi_facility_association'): (fixtures or {}).get('facility_association', "(SELECT CAST(NULL AS varchar) AS provider_npi, CAST(ARRAY[] AS array(varchar)) AS facility_npis WHERE false)")}
    source_overrides.update({
        ('iceberg__npi', 'npi_taxonomy'): (fixtures or {}).get('taxonomy_dictionary', "(SELECT CAST(NULL AS varchar) AS code WHERE false)"),
        ('iceberg__npi', 'nppes_npidata_latest'): (fixtures or {}).get('nppes_taxonomy',
            "(SELECT CAST(NULL AS bigint) AS npi, CAST(NULL AS varchar) AS npi_deactivation_date, CAST(NULL AS varchar) AS npi_reactivation_date, CAST(NULL AS bigint) AS replacement_npi, CAST(NULL AS varchar) AS npi_deactivation_reason_code, " + ', '.join(f'CAST(NULL AS varchar) AS healthcare_provider_taxonomy_code_{i}' for i in range(1, 16)) + " WHERE false)")})
    if (fixtures or {}).get('nppes_taxonomy') and not (fixtures or {}).get('nppes_has_lifecycle'):
        source_overrides[('iceberg__npi', 'nppes_npidata_latest')] = (
            '(SELECT *, CAST(NULL AS varchar) AS npi_deactivation_date, CAST(NULL AS varchar) AS npi_reactivation_date, '
            'CAST(NULL AS bigint) AS replacement_npi, CAST(NULL AS varchar) AS npi_deactivation_reason_code FROM '
            + fixtures['nppes_taxonomy'] + ')')
    nppes_key = ('iceberg__npi', 'nppes_npidata_latest')
    if not (fixtures or {}).get('nppes_has_entity_type'):
        source_overrides[nppes_key] = '(SELECT *, CAST(NULL AS varchar) AS entity_type_code FROM ' + source_overrides[nppes_key] + ')'
    source_overrides.update({
        ('bq_bi__analytics_prod', 'npi_facility_locations_with_ids'): (fixtures or {}).get('facility_locations',
            "(SELECT CAST(NULL AS varchar) AS npi_facility_provider_npi, CAST(NULL AS varchar) AS state_code, CAST(NULL AS varchar) AS location, CAST(NULL AS bigint) AS npi_facility_rank WHERE false)"),
        ('iceberg__thirdparty', 'liveintent_idsync'): (fixtures or {}).get('cookie_mappings',
            "(SELECT CAST(NULL AS varchar) AS day, CAST(NULL AS varchar) AS hashedemail_sha256, CAST(NULL AS varchar) AS uids WHERE false)"),
        ('iceberg__crossscreen', 'nscreen_geo_daily_ua'): (fixtures or {}).get('cookie_geo',
            "(SELECT CAST(NULL AS varchar) AS day, CAST(NULL AS varchar) AS uid, CAST(NULL AS varchar) AS geo WHERE false)"),
        ('iceberg__jteixeira_ipa', 'tmp_zip3_to_state'): (fixtures or {}).get('cookie_zip',
            "(SELECT CAST(NULL AS varchar) AS zip3, CAST(NULL AS varchar) AS state WHERE false)")})
    if name.startswith('stg_'):
        source_overrides[pipeline.stage_input(name)] = (fixtures or {}).get(name) or fixture(name)
    sql = pipeline.read_model(name, ref_overrides=overrides, source_overrides=source_overrides, variables=variables)
    cache[key] = sql
    return sql


class ModelFixtures(unittest.TestCase):
    source = None

    def test_common_email_format_rule(self):
        values = ', '.join('(' + literal(name) + ', ' + literal(email) + ')' for name, email, _ in CASES)
        sql = pipeline.render_sql("SELECT name, {{ email_format_valid('email') }} AS result FROM (VALUES " + values + ") AS t(name, email)")
        rows = execute(sql)
        expected = {name: value for name, _, value in CASES}
        self.assertEqual(len(rows), len(CASES))
        for row in rows:
            self.assertIs(row['result'], expected[row['name']], row['name'])

    def test_role_accounts_match_v2_exact_list(self):
        names = ('admin', 'info', 'office', 'contact', 'frontdesk', 'billing',
                 'reception', 'appointments', 'scheduling', 'support', 'noreply')
        cases = [(name + '@example.test', True) for name in names]
        cases += [('info@', True)]  # Prefix rule is independent of format validity.
        cases += [(email, False) for email in (
            'jane@example.test', 'billing.team@example.test', 'billing+work@example.test',
            'noreply-team@example.test', 'INFO@example.test', 'info', '@example.test', '', None)]
        values = ', '.join('(' + str(i) + ', ' + literal(email) + ')' for i, (email, _) in enumerate(cases))
        sql = pipeline.render_sql("SELECT i, {{ email_role_account('email') }} AS result FROM (VALUES " + values + ") AS t(i, email)")
        rows = execute(sql)
        self.assertEqual(len(rows), len(cases))
        for row in rows:
            self.assertIs(row['result'], cases[row['i']][1])
        # Staging lowercases and trims before evaluating this case.
        sql = pipeline.render_sql("SELECT {{ email_role_account('email') }} AS result FROM (SELECT {{ clean_email('raw') }} AS email FROM (VALUES (' INFO@example.test ')) AS t(raw))")
        self.assertTrue(execute(sql)[0]['result'])

    def test_staging_preserves_rows_and_original_columns(self):
        for name in TABLE_COLUMNS:
            if self.source and not name.startswith(f'stg_{self.source}__'):
                continue
            with self.subTest(model=name):
                rows = execute(inlined(name))
                self.assertEqual(len(rows), 4)
                raw_npi = 'npi_number' if name == 'stg_haymarket__npi' else 'npi'
                self.assertEqual(rows[0][raw_npi], ' 123 ')
                self.assertEqual(rows[0]['npi_clean'], '123')
                self.assertEqual(rows[3][raw_npi], ' ')
                self.assertIsNone(rows[3]['npi_clean'])

    def test_intermediate_preserves_positions_and_historical_attributions(self):
        sources = [self.source] if self.source else pipeline.SOURCES
        for source in sources:
            with self.subTest(source=source):
                rows = execute(inlined(f'int_{source}__metrics'))
                self.assertTrue(all(r['email'] and r['npi'] for r in rows))
                self.assertEqual(len({r['metric_row_id'] for r in rows}), len(rows))
                expected_links = 6 if source in ('quantummedica', 'endato', 'rocketreach') else (4 if source == 'drdb' else 2)
                self.assertEqual(len(rows), expected_links)
                row = next(r for r in rows if r['email'] == 'alex@example.test' and r['npi'] == '123')
                self.assertEqual(row['observation_count'], 2)
                self.assertTrue(row['email_format_valid'])
                self.assertFalse(row['email_role_account'])
                self.assertEqual(row['email_domain_class'], 'custom')
                if source in ('healthlink', 'quantummedica', 'medscape', 'haymarket'):
                    self.assertEqual(str(row['first_seen_day']), '2020-01-01')
                    self.assertEqual(str(row['last_seen_day']), '2026-10-28')
                    self.assertEqual(row['observed_day_count'], 2)
                else:
                    self.assertIsNone(row['first_seen_day'])
                    self.assertIsNone(row['observed_day_count'])
                self.assertTrue(any(r['npi'] == '456' for r in rows))
                self.assertFalse(any(r['email'] == 'provider@example.test' for r in rows))
                self.assertTrue(all(r['email_npi_count'] == 2 and r['email_has_multiple_npis'] for r in rows))
                self.assertTrue(all(r['has_conflict_linkage'] is True for r in rows))
                if source in ('endato', 'rocketreach', 'drdb'):
                    self.assertTrue(all(r['has_been_reassigned'] is None and r['conflict_days'] == [] for r in rows))
                else:
                    self.assertTrue(all(r['has_been_reassigned'] is True for r in rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=pipeline.SOURCES)
    args = parser.parse_args()
    ModelFixtures.source = args.source
    unittest.main(argv=[__file__])
