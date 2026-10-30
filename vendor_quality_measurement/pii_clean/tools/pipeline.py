#!/usr/bin/env python3
"""Build source metrics and the unscored final UNION ALL table."""
import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT
SCHEMA = 'iceberg.jteixeira_ipa'
FINAL_MODEL = 'pii_clean'
SOURCES = ('healthlink', 'quantummedica', 'medscape', 'endato', 'rocketreach', 'drdb', 'haymarket')
NAME_CONSISTENCY_METRICS = ('email_name_count', 'email_npi_has_name_conflict')
CONFLICTING_NAME_METRIC = 'conflicting_npis_share_name'
LINKAGE_METRICS = ('email_npi_count', 'email_has_multiple_npis', 'has_been_reassigned', 'has_conflict_linkage')
NAME_METRICS = ('email_matches_source_name', 'email_matches_registry_name', 'vendor_name_matches_registry_name')
# Reduce plan stages; larger unions still fall back to vendor batches.
EVIDENCE_SESSION_PROPERTIES = {'distinct_aggregations_strategy': 'single_step'}
SCRIPTS = Path.home() / '.codex/skills/pulsepoint-trino/scripts'
sys.path.insert(0, str(SCRIPTS))
from ppconfig import bootstrap


def model_paths():
    files = list((PROJECT / 'models').rglob('*.sql')) + list((PROJECT / 'seeds').glob('*.csv'))
    paths = {p.stem: p for p in files}
    if len(paths) != len(files):
        raise ValueError('Model names must be unique')
    return paths


def relation(name):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,120}', name):
        raise ValueError('Invalid model name')
    return f'{SCHEMA}.{name}' if name == FINAL_MODEL else f'{SCHEMA}.pii__{name}'


def render_sql(text, variables=None, ref_overrides=None, dependencies=None, source_overrides=None):
    paths = model_paths()
    declared = yaml.safe_load((PROJECT / 'models/sources.yml').read_text())['sources']
    sources = {s['name']: s for s in declared}
    variables, overrides = variables or {}, ref_overrides or {}

    def source(name, table):
        definition = sources[name]
        if table not in {entry['name'] for entry in definition['tables']}:
            raise ValueError(f'Undeclared source: {name}.{table}')
        return (source_overrides or {}).get((name, table), f"{definition['schema']}.{table}")

    def ref(name):
        if name not in paths:
            raise ValueError(f'Unknown model: {name}')
        if dependencies is not None:
            dependencies.append(name)
        return overrides.get(name, relation(name))

    def var(name, default=None):
        if name in variables:
            return variables[name]
        if default is not None:
            return default
        raise ValueError(f'Missing variable: {name}')

    def record_schema(name):
        return json.loads((PROJECT / 'models/record_schemas.json').read_text())[name]

    def record_payload(name, alias):
        parts = []
        for field in record_schema(name)['columns']:
            if field['name'] == 'day':
                continue
            identifier = alias + '."' + field['name'].replace('"', '""') + '"'
            if field['type'].startswith(('timestamp', 'date', 'decimal')):
                identifier = f'cast({identifier} AS varchar)'
            key = json.dumps(field['name'], ensure_ascii=False).replace("'", "''")
            parts.append("'" + key + ":' || coalesce(json_format(cast(" + identifier + " AS json)), 'null')")
        return "'{' || array_join(ARRAY[" + ', '.join(parts) + "], ',') || '}'"

    macros = '\n'.join(p.read_text() for p in sorted((PROJECT / 'macros').glob('*.sql')))
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=True)
    env.globals.update(source=source, ref=ref, var=var, record_schema=record_schema, record_payload=record_payload)
    return env.from_string(macros + '\n' + text).render().strip()


def read_model(name, **kwargs):
    paths = model_paths()
    if name not in paths:
        raise ValueError(f'Unknown model: {name}')
    if paths[name].suffix == '.csv':
        with paths[name].open(newline='') as handle:
            rows = list(csv.reader(handle))
        columns = rows[0]
        if not all(re.fullmatch(r'[a-z][a-z0-9_]*', col) for col in columns):
            raise ValueError('Invalid seed column')
        if len(rows) < 2 or any(len(row) != len(columns) for row in rows[1:]):
            raise ValueError('Seed must contain rectangular data')
        values = ',\n'.join('(' + ', '.join("'" + value.replace("'", "''") + "'" for value in row) + ')'
                            for row in rows[1:])
        return 'SELECT * FROM (VALUES\n' + values + '\n) AS seed(' + ', '.join(columns) + ')'
    return render_sql(paths[name].read_text(), **kwargs)


def source_plan(source):
    if source not in SOURCES:
        raise ValueError('Unknown source')
    paths = model_paths()
    staging = sorted(n for n in paths if n.startswith(f'stg_{source}__'))
    target = f'int_{source}__metrics'
    ordered, active, visited = [], set(), set()

    def visit(name):
        if name in active:
            raise ValueError(f'Cyclic model dependency: {name}')
        if name in visited:
            return
        active.add(name)
        dependencies = []
        read_model(name, dependencies=dependencies)
        for dep in dependencies:
            visit(dep)
        active.remove(name)
        visited.add(name)
        ordered.append(name)

    for name in staging + [target]:
        visit(name)
    return ordered


def run_write(sql, session_properties=None):
    if session_properties:
        # ppquery has no session-property option. Use the same credential bootstrap
        # and drain the cursor so a submitted write cannot be mistaken for completion.
        db, _ = bootstrap()
        connection = db.get_trino_connection(session_properties=session_properties)
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            cursor.fetchall()
        finally:
            cursor.close()
            connection.close()
        return
    directory = ROOT / 'target'
    directory.mkdir(exist_ok=True)
    # Independent builds must not overwrite each other's submitted statement.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', prefix='pipeline_', dir=directory) as handle:
        handle.write(sql + '\n')
        handle.flush()
        subprocess.run([sys.executable, str(SCRIPTS / 'ppquery.py'), '--file', handle.name, '--allow-writes'], check=True)


def query(db, sql):
    return json.loads(db.query2df(sql).to_json(orient='records', date_format='iso', double_precision=12))


def create_source(source):
    for name in source_plan(source):
        print(f'Creating view {relation(name)}', flush=True)
        run_write(f'CREATE OR REPLACE VIEW {relation(name)} AS\n{read_model(name)}')


def validate_record_schemas(db, sources=SOURCES):
    """Refuse to silently omit new raw columns from exact-record identity."""
    schemas = json.loads((PROJECT / 'models/record_schemas.json').read_text())
    for name, definition in schemas.items():
        if not any(name.startswith(f'stg_{s}__') for s in sources):
            continue
        actual = sorted((r['Column'], r['Type']) for r in query(db, 'DESCRIBE ' + definition['table']))
        expected = sorted((r['name'], r['type']) for r in definition['columns'])
        if actual != expected:
            raise ValueError(f'{name}: raw schema changed; update record_schemas.json before building')


def build_views():
    """Build all source dependencies once, in dependency order."""
    created = set()
    for source in SOURCES:
        for name in source_plan(source):
            if name not in created:
                print(f'Creating view {relation(name)}', flush=True)
                run_write(f'CREATE OR REPLACE VIEW {relation(name)} AS\n{read_model(name)}')
                created.add(name)


def evidence_snapshot_sql(table, columns):
    # computed_at is query time in views; all substantive fields must agree.
    fields = ', '.join(c for c in columns if c != 'computed_at')
    return f'''SELECT source, count(*) AS metric_rows,
       count(*) - count(DISTINCT ROW(source, metric_row_id)) AS duplicate_keys,
       to_hex(checksum(ROW({fields}))) AS evidence_checksum
FROM {table} GROUP BY source ORDER BY source'''


def explain_fragments(db, sql):
    connection = db.get_trino_connection(session_properties=EVIDENCE_SESSION_PROPERTIES)
    cursor = connection.cursor()
    try:
        cursor.execute('EXPLAIN (TYPE DISTRIBUTED) ' + sql)
        plan = '\n'.join(str(row[0]) for row in cursor.fetchall())
    finally:
        cursor.close()
        connection.close()
    return len(re.findall(r'Fragment \d+', plan))


def build_final(db, preservation=None):
    """Materialize vendor outputs once, validate the candidate, then publish it."""
    directory = ROOT / 'results'
    directory.mkdir(exist_ok=True)
    manifest = {'started_at_utc': datetime.now(timezone.utc).isoformat(),
                'table': relation(FINAL_MODEL), 'sources': {}, 'verified': False,
                'session_properties': EVIDENCE_SESSION_PROPERTIES}
    path = directory / 'final_build.json'

    def save():
        path.write_text(json.dumps(manifest, indent=2) + '\n')

    # Every path validates stored rows before touching the canonical table.
    # Retain the candidate for audit/recovery; cleanup is an explicit operation.
    candidate = f'{SCHEMA}.pii_clean_candidate_{uuid.uuid4().hex[:16]}'
    candidate_sql = f"CREATE TABLE {candidate} WITH (format = 'PARQUET') AS\n{read_model(FINAL_MODEL)}"
    sql = f"CREATE OR REPLACE TABLE {relation(FINAL_MODEL)} WITH (format = 'PARQUET') AS\nSELECT * FROM {candidate}"
    manifest.update(create_sql=sql, candidate_table=candidate, candidate_writes=[],
                    publication_mode='union_candidate')
    save()
    # Validate the distributed union with the same settings as the write. Syntax
    # validation alone misses the stage limit. EXPLAIN does not execute sources.
    batched = False
    try:
        manifest['candidate_plan_fragments'] = explain_fragments(db, candidate_sql)
    except Exception as exc:
        if 'QUERY_HAS_TOO_MANY_STAGES' not in str(exc):
            raise
        batched = True
        manifest.update(publication_mode='vendor_batches', union_plan_error=str(exc))
        print('Union exceeds stage limit; building a validated candidate by vendor', flush=True)
    save()
    columns = None
    expected_schema = None
    for source in SOURCES:
        table = relation(f'int_{source}__metrics')
        schema = [(r['Column'], r['Type']) for r in query(db, 'DESCRIBE ' + table)]
        if expected_schema is not None and schema != expected_schema:
            raise ValueError(f'{source}: incompatible metric schema')
        expected_schema = schema
        columns = [c for c, _ in schema]
        if not all(re.fullmatch(r'[a-z][a-z0-9_]*', c) for c in columns):
            raise ValueError('Unexpected column identifier')
        manifest['sources'][source] = {'view': table}
        save()
    manifest['schema'] = expected_schema
    save()
    validation_table = candidate
    if batched:
        for index, source in enumerate(SOURCES):
            select = f'SELECT * FROM {relation(f"int_{source}__metrics")}'
            statement = (f"CREATE TABLE {candidate} WITH (format = 'PARQUET') AS\n" if index == 0
                         else f'INSERT INTO {candidate}\n') + select
            entry = {'source': source, 'sql': statement, 'completed': False,
                     'plan_fragments': explain_fragments(db, statement)}
            manifest['candidate_writes'].append(entry)
            save()
            run_write(statement, session_properties=EVIDENCE_SESSION_PROPERTIES)
            entry['completed'] = True
            save()
            print(f'Candidate appended {source}', flush=True)
    else:
        entry = {'sources': list(SOURCES), 'sql': candidate_sql, 'completed': False,
                 'plan_fragments': manifest['candidate_plan_fragments']}
        manifest['candidate_writes'].append(entry)
        save()
        run_write(candidate_sql, session_properties=EVIDENCE_SESSION_PROPERTIES)
        entry['completed'] = True
        save()
    final_schema = [(r['Column'], r['Type']) for r in query(db, 'DESCRIBE ' + validation_table)]
    if final_schema != expected_schema:
        raise ValueError('Final columns or types differ from the vendor outputs')
    check_sql = evidence_snapshot_sql(validation_table, columns)
    actual = query(db, check_sql)
    manifest.update(validation_sql=check_sql, validation=actual)
    save()
    if (len(actual) != len(SOURCES) or {r['source'] for r in actual} != set(SOURCES)
            or any(r['metric_rows'] < 1 or r['duplicate_keys'] for r in actual)):
        raise ValueError('Candidate source coverage or grain check failed; inspect final_build.json')
    for row in actual:
        manifest['sources'][row['source']]['materialized'] = row
        print(f"Checked {row['source']}: {row['metric_rows']:,} metric_rows", flush=True)
    save()
    if preservation is not None:
        old_sql = evidence_snapshot_sql(validation_table, preservation['columns'])
        old_rows = query(db, old_sql)
        manifest['previous_column_validation'] = {'sql': old_sql, 'rows': old_rows}
        save()
        if old_rows != preservation['rows']:
            raise ValueError('Existing record attributes changed; inspect previous-column checksums before publication')
    overrides = {FINAL_MODEL: validation_table}
    integrity_sql = render_sql((ROOT / 'tests/source_integrity.sql').read_text(), {'metric_model': FINAL_MODEL}, overrides)
    failures = query(db, integrity_sql)
    manifest.update(integrity_sql=integrity_sql, integrity_failures=failures)
    save()
    if failures:
        raise ValueError(f'Evidence integrity checks failed: {failures}')
    manifest['linkage_checks'] = {}
    for name in ('email_npi_multiplicity.sql', 'email_linkage_history.sql', 'name_consistency.sql', 'conflicting_names.sql', 'conflicting_states.sql', 'conflicting_facilities.sql', 'conflicting_specialties.sql', 'registry_status.sql', 'vendor_facility_state.sql', 'cookie_location.sql', 'link_freshness.sql', 'link_stability.sql'):
        test_sql = render_sql((ROOT / 'tests' / name).read_text(), {'metric_model': FINAL_MODEL}, overrides)
        failures = query(db, test_sql)
        manifest['linkage_checks'][name] = {'sql': test_sql, 'failures': failures}
        save()
        if failures:
            raise ValueError(f'Evidence {name} failed: {failures}')
    manifest['plan_fragments'] = explain_fragments(db, sql)
    save()
    run_write(sql, session_properties=EVIDENCE_SESSION_PROPERTIES)
    manifest['published_at_utc'] = datetime.now(timezone.utc).isoformat()
    save()
    published_schema = [(r['Column'], r['Type']) for r in query(db, 'DESCRIBE ' + relation(FINAL_MODEL))]
    published_sql = evidence_snapshot_sql(relation(FINAL_MODEL), columns)
    published = query(db, published_sql)
    manifest.update(published_validation_sql=published_sql, published_validation=published)
    save()
    if published_schema != expected_schema or published != actual:
        raise ValueError('Published table differs from the validated candidate')
    manifest.update(verified=True, completed_at_utc=datetime.now(timezone.utc).isoformat())
    save()
    print(f"PASS {relation(FINAL_MODEL)}: {sum(r['metric_rows'] for r in actual):,} metric_rows", flush=True)


def stage_input(name):
    text = model_paths()[name].read_text()
    refs = re.findall(r"source\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)", text)
    if len(refs) != 1:
        raise ValueError(f'{name}: staging must read exactly one declared input table')
    return refs[0]


def test_source(db, source):
    for name in source_plan(source):
        if not name.startswith('stg_'):
            continue
        namespace, table = stage_input(name)
        variables = {'staging_model': name, 'source_namespace': namespace, 'source_table': table}
        sql = render_sql((PROJECT / 'tests/staging_row_count.sql').read_text(), variables)
        failures = query(db, sql)
        if failures:
            raise ValueError(f'{name} dropped or multiplied rows: {failures}')
        print(f'PASS {name}: input row count preserved', flush=True)
    schemas = json.loads((PROJECT / 'models/record_schemas.json').read_text())
    for stage, definition in schemas.items():
        if not stage.startswith(f'stg_{source}__'):
            continue
        versions_sql = render_sql("{{ record_versions('" + stage + "') }}")
        sql = f'''SELECT
            (SELECT count(*) FROM {definition['table']}) AS raw_rows,
            coalesce(sum(observation_count), 0) AS represented_rows,
            count(*) - count(DISTINCT record_id) AS duplicate_record_ids
            FROM ({versions_sql})'''
        checked = query(db, sql)[0]
        if checked['raw_rows'] != checked['represented_rows'] or checked['duplicate_record_ids']:
            raise ValueError(f'{stage}: exact-record preservation failed: {checked}')
        print(f'PASS {stage}: raw copies preserved; record IDs unique', flush=True)
    variables = {'metric_model': f'int_{source}__metrics'}
    for name in ('source_integrity.sql', 'email_npi_multiplicity.sql', 'email_linkage_history.sql', 'name_consistency.sql', 'conflicting_names.sql', 'conflicting_states.sql', 'conflicting_facilities.sql', 'conflicting_specialties.sql', 'registry_status.sql', 'vendor_facility_state.sql', 'cookie_location.sql', 'link_freshness.sql', 'link_stability.sql'):
        failures = query(db, render_sql((PROJECT / 'tests' / name).read_text(), variables))
        if failures:
            raise ValueError(f'{name} failed: {failures}')
        print(f'PASS {source}: {name}', flush=True)


def render_profile(filename, source=None):
    """Render a profile over published rows, optionally scoped to one vendor."""
    if source is not None and source not in SOURCES:
        raise ValueError('Unknown source')
    sql = (ROOT / 'sql' / filename).read_text()
    evaluated = f'SELECT * FROM {relation(FINAL_MODEL)}'
    if source is not None:
        evaluated += f" WHERE source = '{source}'"
    for marker in ('/* EVALUATED_SQL */', '/* EVIDENCE_SQL */'):
        sql = sql.replace(marker, evaluated)
    return render_sql(sql)


def report(db, source):
    table = relation(FINAL_MODEL)
    sql = render_profile('email_format_profile.sql', source)
    rows = query(db, sql)
    data = {'relation': table, 'source': source, 'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    name = f'{source}_intermediate_metrics'
    directory = ROOT / 'results'
    directory.mkdir(exist_ok=True)
    (directory / f'{name}.json').write_text(json.dumps(data, indent=2) + '\n')
    lines = [f"| {r['source']} | {r['metric_rows']:,} | {r['invalid_metric_rows']:,} ({r['invalid_pct']:.5f}%) | {r['unknown_metric_rows']:,} ({r['unknown_pct']:.5f}%) |" for r in rows]
    md = f'''# {source}: email-format metric

**Relation:** `{table}`. **Measured:** {data['measured_at_utc']}.
One row per `source`, `metric_row_id`: an exact source record and email position. Input: `email`; indicator: `email_format_valid`.

The indicator checks `email` against `^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{{2,}}$`. For example, `alex+work@example.com` passes; `o'neil@example.com` fails. This does not establish deliverability or ownership. Counts are exact; percentages use this source's metric rows with nonempty email and NPI. Missing-key input records remain in staging but do not enter these metric-row counts.

| Source | Metric rows | False, n (%) | Unknown, n (%) |
|---|---:|---:|---:|
{chr(10).join(lines)}

[Metric documentation](../docs/metrics/02_email_format_valid.md) · Query results (local-only: `{name}.json`)
'''
    (directory / f'{name}.md').write_text(md)
    print(json.dumps(rows, indent=2))
    print(f'Saved {directory / (name + ".md")}')


def report_role(db, source):
    table = relation(FINAL_MODEL)
    sql = render_profile('email_role_profile.sql', source)
    rows = query(db, sql)
    data = {'relation': table, 'source': source, 'metric': 'email_role_account',
            'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    path = ROOT / f'results/{source}_email_role_account.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(rows, indent=2), flush=True)
    print(f'Saved {path}', flush=True)


def report_domain(db, source):
    table = relation(FINAL_MODEL)
    sql = render_profile('email_domain_profile.sql', source)
    rows = query(db, sql)
    if any(r['mismatched_values'] for r in rows):
        raise ValueError(f'{source}: stored domain classes differ from the rule')
    data = {'relation': table, 'source': source, 'metric': 'email_domain_class',
            'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    path = ROOT / f'results/{source}_email_domain_class.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(rows, indent=2), flush=True)
    print(f'Saved {path}', flush=True)
    return data


def report_names(db, source, metric=None):
    table = relation(FINAL_MODEL)
    sql = render_profile('name_match_profile.sql', source)
    rows = query(db, sql)
    for row in rows:
        if row['duplicate_keys'] or row['coverage_failures']:
            raise ValueError(f'{source}: name-metric uniqueness or coverage check failed')
        if row['matched_metric_rows'] + row['unmatched_metric_rows'] + row['unknown_metric_rows'] != row['metric_rows']:
            raise ValueError(f'{source}: name outcomes do not partition metric_rows')
    data = {'relation': table, 'source': source, 'measured_at_utc': datetime.now(timezone.utc).isoformat(),
            'sql': sql, 'rows': rows}
    path = ROOT / f'results/{source}_name_matching.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps([r for r in rows if metric is None or r['metric'] == metric], indent=2), flush=True)
    print(f'Saved {path}', flush=True)
    return data


def report_linkage(db, source, metric='email_npi_count'):
    table = relation(FINAL_MODEL)
    profile = 'email_linkage_profile.sql' if metric in ('has_been_reassigned', 'has_conflict_linkage') else 'email_npi_profile.sql'
    sql = render_profile(profile, source)
    rows = query(db, sql)
    if any(r.get('mismatched_emails', 0) for r in rows):
        raise ValueError(f'{source}: stored linkage metrics differ from the rule')
    data = {'relation': table, 'source': source, 'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    path = ROOT / f'results/{source}_{profile.removesuffix(".sql")}.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(rows, indent=2), flush=True)
    return data


def report_name_consistency(db, source):
    table = relation(FINAL_MODEL)
    sql = render_profile('name_consistency_profile.sql', source)
    rows = query(db, sql)
    if any(r['mismatched_emails'] for r in rows):
        raise ValueError(f'{source}: inconsistent name-history outcomes')
    data = {'relation': table, 'source': source, 'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    path = ROOT / f'results/{source}_name_consistency.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(rows, indent=2), flush=True)
    return data


def report_conflicting_names(db, source, state=False, facility=False, specialty=False):
    table = relation(FINAL_MODEL)
    filename = 'conflicting_specialties' if specialty else ('conflicting_facilities' if facility else ('conflicting_states' if state else 'conflicting_names'))
    sql = render_profile(f'{filename}_profile.sql', source)
    rows = query(db, sql)
    data = {'relation': table, 'source': source, 'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    path = ROOT / f'results/{source}_{filename}.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(rows, indent=2), flush=True)
    return data


def report_registry_status(db, source):
    table = relation(FINAL_MODEL)
    sql = render_profile('registry_status_profile.sql', source)
    rows = query(db, sql)
    path = ROOT / f'results/{source}_registry_status.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'relation': table, 'source': source, 'measured_at_utc': datetime.now(timezone.utc).isoformat(),
                               'sql': sql, 'rows': rows}, indent=2) + '\n')
    print(json.dumps(rows, indent=2), flush=True)
    return rows


def report_location(db, source, metric):
    table = relation(FINAL_MODEL)
    profile = {'vendor_state_evidence': 'vendor_facility_state_profile.sql',
               'cookie_location_status': 'cookie_location_profile.sql',
               'link_freshness': 'link_freshness_profile.sql',
               'link_stability': 'link_stability_profile.sql'}[metric]
    sql = render_profile(profile, source)
    rows = query(db, sql)
    path = ROOT / f'results/{source}_{metric}.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'relation': table, 'source': source, 'sql': sql, 'rows': rows}, indent=2) + '\n')
    print(json.dumps(rows, indent=2), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('render', 'source', 'test', 'report', 'build', 'final'))
    parser.add_argument('--metric', choices=('email_format_valid', 'email_role_account', 'email_domain_class', *NAME_METRICS, *LINKAGE_METRICS, *NAME_CONSISTENCY_METRICS, CONFLICTING_NAME_METRIC, 'conflicting_npis_share_state', 'conflicting_npis_share_facility', 'conflicting_npis_share_specialty', 'npi_registry_status', 'vendor_state_evidence', 'cookie_location_status', 'link_freshness', 'link_stability'),
                        default='email_format_valid', help='Metric for the report command')
    parser.add_argument('--model', help='Model to render without a warehouse connection')
    parser.add_argument('--source', choices=(*SOURCES, 'all'))
    args = parser.parse_args()
    if args.command == 'render':
        if not args.model or args.source:
            parser.error('render requires --model and does not use --source')
        print(read_model(args.model))
        return
    if args.command in ('build', 'final'):
        if args.model or args.source:
            parser.error('build and final always include every source; omit --source and --model')
        db, _ = bootstrap()
        if args.command == 'build':
            validate_record_schemas(db)
            build_views()
        build_final(db)
        return
    if not args.source or args.model:
        parser.error('source, test and report require --source and do not use --model')
    sources = SOURCES if args.source == 'all' else (args.source,)
    if args.command == 'source':
        db, _ = bootstrap()
        validate_record_schemas(db, sources)
        for source in sources:
            create_source(source)
        return
    if args.command == 'test':
        subprocess.run([sys.executable, str(ROOT / 'tools/test_pipeline.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_reports.py')], check=True)
        command = [sys.executable, str(ROOT / 'tools/test_models.py')]
        if args.source != 'all':
            command += ['--source', args.source]
        subprocess.run(command, check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_domain_class.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_name_matching.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_record_grain.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_email_linkage.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_name_consistency.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_conflicting_names.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_conflicting_states.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_conflicting_facilities.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_conflicting_specialties.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_registry_status.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_location_evidence.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_link_freshness.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_link_stability.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_email_lookup.py')], check=True)
    db, _ = bootstrap()
    for source in sources:
        if args.command == 'test':
            test_source(db, source)
        else:
            if args.metric == 'email_role_account':
                report_role(db, source)
            elif args.metric == 'email_domain_class':
                report_domain(db, source)
            elif args.metric in LINKAGE_METRICS:
                report_linkage(db, source, args.metric)
            elif args.metric in ('vendor_state_evidence', 'cookie_location_status', 'link_freshness', 'link_stability'):
                report_location(db, source, args.metric)
            elif args.metric == 'npi_registry_status':
                report_registry_status(db, source)
            elif args.metric == 'conflicting_npis_share_specialty':
                report_conflicting_names(db, source, specialty=True)
            elif args.metric == 'conflicting_npis_share_facility':
                report_conflicting_names(db, source, facility=True)
            elif args.metric == 'conflicting_npis_share_state':
                report_conflicting_names(db, source, state=True)
            elif args.metric == CONFLICTING_NAME_METRIC:
                report_conflicting_names(db, source)
            elif args.metric in NAME_CONSISTENCY_METRICS:
                report_name_consistency(db, source)
            elif args.metric in NAME_METRICS:
                report_names(db, source, args.metric)
            else:
                report(db, source)


if __name__ == '__main__':
    main()
