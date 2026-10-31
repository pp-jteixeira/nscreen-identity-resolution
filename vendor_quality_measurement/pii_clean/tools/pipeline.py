#!/usr/bin/env python3
"""Build stored source metrics, then publish actual cookie-enriched records."""
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
from zoneinfo import ZoneInfo

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT
SCHEMA = 'iceberg.jteixeira_ipa'
FINAL_MODEL = 'pii_clean'
CORE_MODEL = 'int_pii__metrics'
PENDING_BATCH_COMMENT = 'pii_clean: incomplete Medscape email batches'
SOURCES = ('healthlink', 'quantummedica', 'medscape', 'endato', 'rocketreach', 'drdb', 'haymarket')
NAME_CONSISTENCY_METRICS = ('email_name_count', 'email_npi_has_name_conflict')
CONFLICTING_NAME_METRIC = 'conflicting_npis_share_name'
LINKAGE_METRICS = ('email_npi_count', 'email_has_multiple_npis', 'has_been_reassigned', 'has_conflict_linkage')
NAME_METRICS = ('email_matches_source_name', 'email_matches_registry_name', 'vendor_name_matches_registry_name')
# Reduce plan stages and bound concurrent HDFS writers. Larger unions still
# fall back to vendor batches. Upstream computation remains distributed.
EVIDENCE_SESSION_PROPERTIES = {'distinct_aggregations_strategy': 'single_step',
    'max_writer_task_count': 8, 'task_max_writer_count': 1,
    'task_scale_writers_enabled': False, 'iceberg.target_max_file_size': '64MB'}
# A retained input contains one source. Exact partitioning prevents the planner
# from using that constant source key for every email history on a single task.
HISTORY_SESSION_PROPERTIES = {**EVIDENCE_SESSION_PROPERTIES, 'use_exact_partitioning': True}
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


def cookie_column_types():
    model = yaml.safe_load((PROJECT / 'models/final/schema.yml').read_text())['models'][0]
    return {c['name']: c['data_type'] for c in model['columns'] if c['name'].startswith('cookie_')}


def publication_schema(vendor_schema):
    fields = dict(vendor_schema)
    if any(c.startswith('cookie_') for c in fields):
        raise ValueError('Vendor metric views still contain cookie fields. Rebuild their definitions first')
    fields.update(cookie_column_types())
    model = yaml.safe_load((PROJECT / 'models/final/schema.yml').read_text())['models'][0]
    declared = {c['name'] for c in model['columns']}
    if set(fields) != declared:
        raise ValueError('Vendor fields differ from the declared publication contract')
    return [(c['name'], fields[c['name']]) for c in model['columns']]


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

    def metric_columns(include_cookie=False):
        # The final contract is shared by all seven vendor outputs. Use it when
        # a window enrichment must discard helper columns without rereading input.
        schema = yaml.safe_load((PROJECT / 'models/final/schema.yml').read_text())
        model = next(m for m in schema['models'] if m['name'] == FINAL_MODEL)
        return [c['name'] for c in model['columns'] if include_cookie or not c['name'].startswith('cookie_')]

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
    env.globals.update(source=source, ref=ref, var=var, record_schema=record_schema, record_payload=record_payload,
                       metric_columns=metric_columns, cookie_column_types=cookie_column_types)
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


def require_completed_batches(db):
    ddl = query(db, 'SHOW CREATE TABLE ' + relation(CORE_MODEL))
    if any(PENDING_BATCH_COMMENT in str(value) for row in ddl for value in row.values()):
        raise ValueError('Medscape email batches are incomplete. Resume build_medscape_batches.py first')


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


def evidence_snapshot_sql(table, columns, include_computed_at=False):
    # computed_at is query time in views; all substantive fields must agree.
    fields = ', '.join(c for c in columns if include_computed_at or c != 'computed_at')
    return f'''SELECT source, count(*) AS metric_rows,
       count(*) - count(DISTINCT ROW(source, metric_row_id)) AS duplicate_keys,
       to_hex(checksum(ROW({fields}))) AS evidence_checksum
FROM {table} GROUP BY source ORDER BY source'''


def explain_fragments(db, sql, session_properties=None):
    connection = db.get_trino_connection(session_properties=session_properties or EVIDENCE_SESSION_PROPERTIES)
    cursor = connection.cursor()
    try:
        cursor.execute('EXPLAIN (TYPE DISTRIBUTED) ' + sql)
        plan = '\n'.join(str(row[0]) for row in cursor.fetchall())
    finally:
        cursor.close()
        connection.close()
    return len(re.findall(r'Fragment \d+', plan))


def quality_from_stored_records(table, source):
    """Attach quality enrichments to stored location metrics using exact keys."""
    if source not in SOURCES:
        raise ValueError('Unknown source')
    return render_sql("WITH stored_records AS (SELECT * FROM " + table + "), freshness AS ("
                      "{{ link_freshness_records('stored_records', 'stored_records') }}), stability AS ("
                      "{{ link_stability_records('freshness', 'stored_records') }}), identity AS ("
                      "{{ npi_identity_records('stability', 'stored_records') }}), professional AS ("
                      "{{ vendor_professional_records('identity', '" + source + "', 'stored_records') }}) SELECT * FROM professional")


def history_from_stored_records(table, source):
    """Attach history to stored base metrics without rerunning their enrichments."""
    if source not in SOURCES:
        raise ValueError('Unknown source')
    return render_sql("WITH history_records AS (SELECT * FROM " + table + "), sequence_metrics AS ("
                      "{{ sequential_history_records('history_records', 'history_records', '" + source
                      + "', undated_flag='m.link_stability_has_undated_observations') }}) "
                      "{{ registration_supersession_records('sequence_metrics', '" + source
                      + "', 'history_records', inline=true) }}")


def build_core(db, preservation=None, vendor_batches=False, history_inputs=None, candidate_table=None, direct=False, resume_direct=False):
    """Build vendors once and validate the candidate or direct development target."""
    manifest = {'started_at_utc': datetime.now(timezone.utc).isoformat(),
                'table': relation(CORE_MODEL), 'sources': {}, 'verified': False,
                'session_properties': EVIDENCE_SESSION_PROPERTIES}
    def save():
        print(json.dumps(manifest, indent=2), flush=True)

    # Candidate mode validates before replacement. Direct mode validates the
    # completed target after all batches. Retain staged inputs for audit/recovery.
    history_inputs = history_inputs or {}
    if resume_direct and not direct:
        raise ValueError('Resuming the development target requires direct mode')
    if direct and candidate_table is not None:
        raise ValueError('Direct builds do not use a candidate table')
    for source, table in history_inputs.items():
        if source not in SOURCES or not re.fullmatch(re.escape(SCHEMA) + r'\.[a-z][a-z0-9_]*', table):
            raise ValueError('History inputs must name a known source and a table in the build schema')
    if candidate_table is not None:
        if not re.fullmatch(re.escape(SCHEMA) + r'\.pii_clean_candidate_[a-z0-9_]+', candidate_table):
            raise ValueError('Candidate must be a pii_clean_candidate table in the build schema')
        catalog, schema, name = candidate_table.split('.')
        if query(db, f"SELECT table_name FROM {catalog}.information_schema.tables WHERE table_schema = '{schema}' AND table_name = '{name}'"):
            raise ValueError('The supplied candidate already exists. Inspect it before resuming')
    candidate = relation(CORE_MODEL) if direct else candidate_table or f'{SCHEMA}.pii_clean_candidate_{uuid.uuid4().hex[:16]}'
    first_write = 'CREATE OR REPLACE TABLE' if direct else 'CREATE TABLE'
    candidate_sql = f"{first_write} {candidate} WITH (format = 'PARQUET') AS\n{read_model(CORE_MODEL)}"
    sql = f"CREATE OR REPLACE TABLE {relation(CORE_MODEL)} WITH (format = 'PARQUET') AS\nSELECT * FROM {candidate}"
    writes_key = 'vendor_writes' if direct else 'candidate_writes'
    manifest.update(create_sql=candidate_sql if direct else sql,
                    publication_mode='direct_vendor_batches' if direct else 'union_candidate')
    manifest[writes_key] = []
    manifest['build_table' if direct else 'candidate_table'] = candidate
    save()
    # Validate the distributed union with the same settings as the write. Syntax
    # validation alone misses the stage limit. EXPLAIN does not execute sources.
    batched = direct or vendor_batches or bool(history_inputs)
    if batched:
        manifest.update(publication_mode='direct_vendor_batches' if direct else 'vendor_batches',
                        union_plan_skipped='direct vendor batching' if direct else 'retained history inputs' if history_inputs else 'explicit vendor batching')
    else:
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
    vendor_schema = expected_schema
    manifest['schema'] = expected_schema
    save()
    existing_sources = {}
    if resume_direct:
        require_completed_batches(db)
        target_schema = [(r['Column'], r['Type']) for r in query(db, 'DESCRIBE ' + candidate)]
        if target_schema != expected_schema:
            raise ValueError('Resume target differs from the current metric contract')
        existing = query(db, f'''SELECT source, count(*) AS metric_rows,
            count(*) - count(DISTINCT ROW(source, metric_row_id)) AS duplicate_keys
            FROM {candidate} GROUP BY source ORDER BY source''')
        if any(r['source'] not in SOURCES or r['metric_rows'] < 1 or r['duplicate_keys'] for r in existing):
            raise ValueError('Resume target contains invalid source coverage or duplicate keys')
        existing_sources = {r['source']: r for r in existing}
        manifest['resumed_sources'] = existing
        save()
    validation_table = candidate
    if batched:
        for index, source in enumerate(SOURCES):
            if source in existing_sources:
                manifest[writes_key].append({'source': source, 'completed': True,
                                             'retained_metric_rows': existing_sources[source]['metric_rows']})
                save()
                continue
            entry_properties = HISTORY_SESSION_PROPERTIES
            if source in history_inputs:
                base_table = history_inputs[source]
                expected_base = [(name, kind) for name, kind in vendor_schema
                                 if not name.startswith(('sequence_', 'registration_'))
                                 and name not in ('n_versions_observed', 'n_npis_window', 'n_npi_changes',
                                                  'n_swaps', 'n_flipbacks', 'stability_history_sufficient')]
                base_schema = [(r['Column'], r['Type']) for r in query(db, 'DESCRIBE ' + base_table)]
                if base_schema != expected_base:
                    raise ValueError(f'{source}: retained history-input schema differs from the base contract')
                coverage = query(db, f'SELECT source, count(*) AS metric_rows FROM {base_table} GROUP BY source')
                if len(coverage) != 1 or coverage[0]['source'] != source or coverage[0]['metric_rows'] < 1:
                    raise ValueError(f'{source}: retained history input is empty or contains another source')
                manifest.setdefault('reused_history_inputs', {})[source] = {'table': base_table, 'coverage': coverage}
                select = history_from_stored_records(base_table, source)
                save()
            else:
                select = f'SELECT * FROM {relation(f"int_{source}__metrics")}'
            statement = (f"{first_write} {candidate} WITH (format = 'PARQUET') AS\n" if index == 0 and not resume_direct
                         else f'INSERT INTO {candidate}\n') + select
            entry = {'source': source, 'sql': statement, 'completed': False, 'session_properties': entry_properties}
            if source in history_inputs:
                entry['history_input'] = history_inputs[source]
            try:
                entry['plan_fragments'] = explain_fragments(db, statement, session_properties=entry_properties)
            except Exception as exc:
                if 'QUERY_HAS_TOO_MANY_STAGES' not in str(exc):
                    raise
                # Keep the logical vendor model intact. Materialize its base once
                # when writing its full history would exceed the engine's stage cap.
                base_table = (f'{SCHEMA}.pii_clean_history_input_{source}_{uuid.uuid4().hex[:12]}' if direct
                              else candidate + '_' + source + '_history_input')
                base_sql = (f"CREATE TABLE {base_table} WITH (format = 'PARQUET') AS\n"
                            + read_model(f'int_{source}__metrics', variables={'defer_sequential_history': True}))
                # Exact keys avoid concentrating a single vendor on one worker.
                # If that plan exceeds the stage cap, store the 73-field location input first.
                try:
                    base_fragments = explain_fragments(db, base_sql, session_properties=HISTORY_SESSION_PROPERTIES)
                except Exception as base_error:
                    if 'QUERY_HAS_TOO_MANY_STAGES' not in str(base_error):
                        raise
                    core_table = base_table + '_core'
                    core_sql = (f"CREATE TABLE {core_table} WITH (format = 'PARQUET') AS\n"
                                + read_model(f'int_{source}__metrics', variables={'defer_quality_enrichments': True}))
                    core_entry = {'source': source, 'table': core_table, 'sql': core_sql, 'completed': False,
                                  'plan_fragments': explain_fragments(db, core_sql, session_properties=HISTORY_SESSION_PROPERTIES)}
                    manifest.setdefault('quality_input_writes', []).append(core_entry)
                    save()
                    run_write(core_sql, session_properties=HISTORY_SESSION_PROPERTIES)
                    core_entry['completed'] = True
                    save()
                    base_sql = (f"CREATE TABLE {base_table} WITH (format = 'PARQUET') AS\n"
                                + quality_from_stored_records(core_table, source))
                    base_fragments = explain_fragments(db, base_sql, session_properties=HISTORY_SESSION_PROPERTIES)
                base_entry = {'source': source, 'table': base_table, 'sql': base_sql, 'completed': False,
                              'plan_fragments': base_fragments, 'session_properties': HISTORY_SESSION_PROPERTIES}
                manifest.setdefault('history_input_writes', []).append(base_entry)
                save()
                run_write(base_sql, session_properties=HISTORY_SESSION_PROPERTIES)
                base_entry['completed'] = True
                save()
                select = history_from_stored_records(base_table, source)
                statement = (f"{first_write} {candidate} WITH (format = 'PARQUET') AS\n" if index == 0 and not resume_direct
                             else f'INSERT INTO {candidate}\n') + select
                entry_properties = HISTORY_SESSION_PROPERTIES
                entry.update(sql=statement, history_input=base_table, session_properties=entry_properties,
                             plan_fragments=explain_fragments(db, statement, session_properties=entry_properties))
            manifest[writes_key].append(entry)
            save()
            run_write(statement, session_properties=entry_properties)
            entry['completed'] = True
            save()
            print(f"{'Direct table' if direct else 'Candidate'} appended {source}", flush=True)
    else:
        entry = {'sources': list(SOURCES), 'sql': candidate_sql, 'completed': False,
                 'plan_fragments': manifest['candidate_plan_fragments']}
        manifest[writes_key].append(entry)
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
        raise ValueError('Build source coverage or grain check failed; inspect stdout checkpoint')
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
    overrides = {CORE_MODEL: validation_table}
    integrity_sql = render_sql((ROOT / 'tests/source_integrity.sql').read_text(), {'metric_model': CORE_MODEL}, overrides)
    failures = query(db, integrity_sql)
    manifest.update(integrity_sql=integrity_sql, integrity_failures=failures)
    save()
    if failures:
        raise ValueError(f'Evidence integrity checks failed: {failures}')
    manifest['linkage_checks'] = {}
    for name in ('email_npi_multiplicity.sql', 'email_linkage_history.sql', 'name_consistency.sql', 'conflicting_names.sql', 'conflicting_states.sql', 'conflicting_facilities.sql', 'conflicting_specialties.sql', 'registry_status.sql', 'vendor_facility_state.sql', 'link_freshness.sql', 'link_stability.sql', 'npi_identity.sql', 'vendor_professional.sql', 'medscape_optout.sql', 'sequential_history.sql'):
        test_sql = render_sql((ROOT / 'tests' / name).read_text(), {'metric_model': CORE_MODEL}, overrides)
        failures = query(db, test_sql)
        manifest['linkage_checks'][name] = {'sql': test_sql, 'failures': failures}
        save()
        if failures:
            raise ValueError(f'Evidence {name} failed: {failures}')
    if not direct:
        manifest['plan_fragments'] = explain_fragments(db, sql)
        save()
        run_write(sql, session_properties=EVIDENCE_SESSION_PROPERTIES)
    manifest['published_at_utc'] = datetime.now(timezone.utc).isoformat()
    save()
    published_schema = [(r['Column'], r['Type']) for r in query(db, 'DESCRIBE ' + relation(CORE_MODEL))]
    published_sql = evidence_snapshot_sql(relation(CORE_MODEL), columns)
    published = query(db, published_sql)
    manifest.update(published_validation_sql=published_sql, published_validation=published)
    save()
    if published_schema != expected_schema or published != actual:
        raise ValueError('Published table differs from the validated candidate')
    manifest.update(verified=True, completed_at_utc=datetime.now(timezone.utc).isoformat())
    save()
    print(f"PASS {relation(CORE_MODEL)}: {sum(r['metric_rows'] for r in actual):,} metric_rows", flush=True)


def current_snapshot(db, table):
    catalog, namespace, name = table.split('.')
    return str(query(db, f'SELECT snapshot_id FROM {catalog}.{namespace}."{name}$history" '
                     'ORDER BY made_current_at DESC LIMIT 1')[0]['snapshot_id'])


def build_final(db):
    """Publish actual cookie-enriched output after stored core metrics."""
    require_completed_batches(db)
    core = relation(CORE_MODEL)
    target = relation(FINAL_MODEL)
    core_schema = [(r['Column'], r['Type']) for r in query(db, 'DESCRIBE ' + core)]
    expected = publication_schema(core_schema)
    columns = [name for name, _ in core_schema]
    snapshot = current_snapshot(db, core)
    pinned = core + ' FOR VERSION AS OF ' + snapshot
    baseline = query(db, evidence_snapshot_sql(pinned, columns, include_computed_at=True))
    if ({r['source'] for r in baseline} != set(SOURCES)
            or any(r['metric_rows'] < 1 or r['duplicate_keys'] for r in baseline)):
        raise ValueError('Core metrics must contain all seven sources with unique record keys')
    day = datetime.now(ZoneInfo('Europe/Paris')).date().isoformat()
    select = read_model('int_cookie__metrics', variables={'location_evidence_day': day},
                        ref_overrides={CORE_MODEL: pinned})
    sql = f"CREATE OR REPLACE TABLE {target} WITH (format = 'PARQUET') AS\n{select}"
    manifest = {'phase': 'cookie_enrichment', 'core_table': core, 'core_snapshot': snapshot,
                'evaluation_day': day, 'target': target,
                'plan_fragments': explain_fragments(db, sql, session_properties=HISTORY_SESSION_PROPERTIES),
                'verified': False}
    print(json.dumps(manifest, indent=2), flush=True)
    # Resolve the downstream view only after the core table exists. A view alone
    # would not create an execution boundary between attribution and cookie work.
    model = 'int_cookie__metrics'
    if current_snapshot(db, core) != snapshot:
        raise ValueError('Core snapshot changed before cookie publication')
    run_write(f'CREATE OR REPLACE VIEW {relation(model)} AS {select}',
              session_properties=EVIDENCE_SESSION_PROPERTIES)
    run_write(sql, session_properties=HISTORY_SESSION_PROPERTIES)
    actual_schema = [(r['Column'], r['Type']) for r in query(db, 'DESCRIBE ' + target)]
    actual = query(db, evidence_snapshot_sql(target, columns, include_computed_at=True))
    if actual_schema != expected or actual != baseline:
        raise ValueError('Enriched publication changed core values, schema, keys or counts')
    failures = query(db, render_sql((ROOT / 'tests/cookie_location.sql').read_text(),
                                   {'metric_model': FINAL_MODEL}))
    if failures:
        raise ValueError(f'Published cookie metrics failed integrity checks: {failures}')
    if current_snapshot(db, core) != snapshot:
        raise ValueError('Core snapshot changed during cookie publication')
    manifest.update(verified=True, preserved_core=actual)
    print(json.dumps(manifest, indent=2), flush=True)


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
    for name in ('source_integrity.sql', 'email_npi_multiplicity.sql', 'email_linkage_history.sql', 'name_consistency.sql', 'conflicting_names.sql', 'conflicting_states.sql', 'conflicting_facilities.sql', 'conflicting_specialties.sql', 'registry_status.sql', 'vendor_facility_state.sql', 'link_freshness.sql', 'link_stability.sql', 'npi_identity.sql', 'vendor_professional.sql', 'medscape_optout.sql', 'sequential_history.sql'):
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
    lines = [f"| {r['source']} | {r['metric_rows']:,} | {r['invalid_metric_rows']:,} ({r['invalid_pct']:.5f}%) | {r['unknown_metric_rows']:,} ({r['unknown_pct']:.5f}%) |" for r in rows]
    md = f'''# {source}: email-format metric

**Relation:** `{table}`. **Measured:** {data['measured_at_utc']}.
One row per `source`, `metric_row_id`: an exact source record and email position. Input: `email`; indicator: `email_format_valid`.

The indicator checks `email` against `^[a-z0-9._%+-]+@[a-z0-9.-]+[.][a-z]{{2,}}$`. For example, `alex+work@example.com` passes; `o'neil@example.com` fails. This does not establish deliverability or ownership. Counts are exact; percentages use this source's metric rows with nonempty email and NPI. Missing-key input records remain in staging but do not enter these metric-row counts.

| Source | Metric rows | False, n (%) | Unknown, n (%) |
|---|---:|---:|---:|
{chr(10).join(lines)}

[Metric documentation](../docs/metrics/02_email_format_valid.md)
'''
    print(md)
    print(json.dumps(rows, indent=2))


def report_role(db, source):
    table = relation(FINAL_MODEL)
    sql = render_profile('email_role_profile.sql', source)
    rows = query(db, sql)
    data = {'relation': table, 'source': source, 'metric': 'email_role_account',
            'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    print(json.dumps(rows, indent=2), flush=True)


def report_domain(db, source):
    table = relation(FINAL_MODEL)
    sql = render_profile('email_domain_profile.sql', source)
    rows = query(db, sql)
    if any(r['mismatched_values'] for r in rows):
        raise ValueError(f'{source}: stored domain classes differ from the rule')
    data = {'relation': table, 'source': source, 'metric': 'email_domain_class',
            'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    print(json.dumps(rows, indent=2), flush=True)
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
    print(json.dumps([r for r in rows if metric is None or r['metric'] == metric], indent=2), flush=True)
    return data


def report_linkage(db, source, metric='email_npi_count'):
    table = relation(FINAL_MODEL)
    profile = 'email_linkage_profile.sql' if metric in ('has_been_reassigned', 'has_conflict_linkage') else 'email_npi_profile.sql'
    sql = render_profile(profile, source)
    rows = query(db, sql)
    if any(r.get('mismatched_emails', 0) for r in rows):
        raise ValueError(f'{source}: stored linkage metrics differ from the rule')
    data = {'relation': table, 'source': source, 'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    print(json.dumps(rows, indent=2), flush=True)
    return data


def report_name_consistency(db, source):
    table = relation(FINAL_MODEL)
    sql = render_profile('name_consistency_profile.sql', source)
    rows = query(db, sql)
    if any(r['mismatched_emails'] for r in rows):
        raise ValueError(f'{source}: inconsistent name-history outcomes')
    data = {'relation': table, 'source': source, 'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    print(json.dumps(rows, indent=2), flush=True)
    return data


def report_conflicting_names(db, source, state=False, facility=False, specialty=False):
    table = relation(FINAL_MODEL)
    filename = 'conflicting_specialties' if specialty else ('conflicting_facilities' if facility else ('conflicting_states' if state else 'conflicting_names'))
    sql = render_profile(f'{filename}_profile.sql', source)
    rows = query(db, sql)
    data = {'relation': table, 'source': source, 'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'sql': sql, 'rows': rows}
    print(json.dumps(rows, indent=2), flush=True)
    return data


def report_registry_status(db, source):
    table = relation(FINAL_MODEL)
    sql = render_profile('registry_status_profile.sql', source)
    rows = query(db, sql)
    print(json.dumps(rows, indent=2), flush=True)
    return rows


def report_location(db, source, metric):
    table = relation(FINAL_MODEL)
    profile = {'vendor_state_evidence': 'vendor_facility_state_profile.sql',
               'cookie_location_status': 'cookie_location_profile.sql',
               'link_freshness': 'link_freshness_profile.sql',
               'link_stability': 'link_stability_profile.sql',
               'npi_identity': 'npi_identity_profile.sql',
               'sequential_history': 'sequential_history_profile.sql',
               'registration_supersession': 'registration_supersession_profile.sql',
               'conflicting_npis_share_vendor_specialty': 'vendor_professional_profile.sql',
               'conflicting_npis_share_vendor_profession': 'vendor_professional_profile.sql'}[metric]
    sql = render_profile(profile, source)
    if metric.startswith('conflicting_npis_share_vendor_'):
        dimension = 'profession' if metric.endswith('_profession') else 'specialty'
        sql = f"SELECT * FROM ({sql}) AS vendor_professional_report WHERE metric = '{dimension}'"
    rows = query(db, sql)
    print(json.dumps(rows, indent=2), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('render', 'source', 'test', 'report', 'build', 'core', 'final', 'cookies'))
    parser.add_argument('--metric', choices=('email_format_valid', 'email_role_account', 'email_domain_class', *NAME_METRICS, *LINKAGE_METRICS, *NAME_CONSISTENCY_METRICS, CONFLICTING_NAME_METRIC, 'conflicting_npis_share_state', 'conflicting_npis_share_facility', 'conflicting_npis_share_nppes_specialty', 'npi_registry_status', 'vendor_state_evidence', 'cookie_location_status', 'link_freshness', 'link_stability', 'npi_identity', 'sequential_history', 'registration_supersession', 'conflicting_npis_share_vendor_specialty', 'conflicting_npis_share_vendor_profession'),
                        default='email_format_valid', help='Metric for the report command')
    parser.add_argument('--model', help='Model to render without a warehouse connection')
    parser.add_argument('--source', choices=(*SOURCES, 'all'))
    parser.add_argument('--vendor-batches', action='store_true', help='Skip the combined core plan and validate vendor batches')
    parser.add_argument('--direct', action='store_true', help='Rebuild the development table directly by vendor, then validate all rows')
    parser.add_argument('--resume', action='store_true', help='With --direct, retain completed source batches after validating their schema and unique keys')
    args = parser.parse_args()
    if args.vendor_batches and args.command not in ('build', 'core'):
        parser.error('--vendor-batches is only available for build and core')
    if args.direct and args.command not in ('build', 'core'):
        parser.error('--direct is only available for build and core')
    if args.resume and not args.direct:
        parser.error('--resume requires --direct')
    if args.command == 'render':
        if not args.model or args.source:
            parser.error('render requires --model and does not use --source')
        print(read_model(args.model))
        return
    if args.command in ('build', 'core', 'final', 'cookies'):
        if args.model or args.source:
            parser.error('build, core and final operate on all sources. Omit --source and --model')
        db, _ = bootstrap()
        if args.command == 'build':
            validate_record_schemas(db)
            build_views()
        if args.command in ('build', 'core'):
            build_core(db, vendor_batches=args.vendor_batches, direct=args.direct, resume_direct=args.resume)
        if args.command in ('build', 'final', 'cookies'):
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
        subprocess.run([sys.executable, str(ROOT / 'tools/test_npi_identity.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_vendor_professional.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_medscape_optout.py')], check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/test_sequential_history.py')], check=True)
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
            elif args.metric in ('vendor_state_evidence', 'cookie_location_status', 'link_freshness', 'link_stability', 'npi_identity', 'sequential_history', 'registration_supersession', 'conflicting_npis_share_vendor_specialty', 'conflicting_npis_share_vendor_profession'):
                report_location(db, source, args.metric)
            elif args.metric == 'npi_registry_status':
                report_registry_status(db, source)
            elif args.metric == 'conflicting_npis_share_nppes_specialty':
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
