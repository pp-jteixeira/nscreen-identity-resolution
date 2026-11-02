"""Publish source-scoped cookie enrichment with snapshot-pinned, resumable batches."""
import json
import re
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

PREFIX = 'pii_clean: incomplete cookie source batches '
INPUTS = {
    ('iceberg__thirdparty', 'liveintent_idsync'): 'iceberg.thirdparty.liveintent_idsync',
    ('iceberg__crossscreen', 'nscreen_geo_daily_ua'): 'iceberg.crossscreen.nscreen_geo_daily_ua',
    ('iceberg__jteixeira_ipa', 'tmp_zip3_to_state'): 'iceberg.jteixeira_ipa.tmp_zip3_to_state',
}
COVERAGE_COUNTS = ('cookie_location_window_days', 'cookie_mapping_available_days',
                   'cookie_location_available_days')
COVERAGE_DAYS = ('cookie_mapping_missing_days', 'cookie_location_missing_days')


def coverage_sql(coverage):
    """Freeze global date coverage so source batches share one evidence window."""
    expected = {*COVERAGE_COUNTS, *COVERAGE_DAYS, 'cookie_location_window_status'}
    if set(coverage) != expected:
        raise ValueError('Unexpected cookie coverage fields')
    expressions = []
    for name in COVERAGE_COUNTS:
        value = coverage[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError('Invalid cookie coverage count')
        expressions.append(f'CAST({value} AS bigint) AS {name}')
    for name in COVERAGE_DAYS:
        values = [date.fromisoformat(str(value)[:10]).isoformat() for value in coverage[name]]
        literals = ', '.join("DATE '" + value + "'" for value in values)
        expressions.append(f'CAST(ARRAY[{literals}] AS array(date)) AS {name}')
    status = coverage['cookie_location_window_status']
    if status not in ('all_source_days_present', 'missing_source_days'):
        raise ValueError('Invalid cookie coverage status')
    expressions.append("'" + status + "' AS cookie_location_window_status")
    return 'SELECT ' + ', '.join(expressions)


def checkpoint(ddl):
    if PREFIX not in ddl:
        return None
    match = re.search("COMMENT '([^']*)'", ddl)
    if not match or not match[1].startswith(PREFIX):
        raise ValueError('Invalid cookie batch marker')
    state = json.loads(match[1][len(PREFIX):])
    if set(state) != {'core_snapshot', 'evaluation_day', 'input_snapshots', 'coverage'}:
        raise ValueError('Invalid cookie batch checkpoint')
    if set(state['input_snapshots']) != set(INPUTS.values()):
        raise ValueError('Unexpected cookie input tables')
    if not all(str(value).isdigit() for value in [state['core_snapshot'], *state['input_snapshots'].values()]):
        raise ValueError('Invalid cookie snapshot pin')
    date.fromisoformat(state['evaluation_day'])
    coverage_sql(state['coverage'])
    return state


def require_population(rows, sources):
    if ({r['source'] for r in rows} != set(sources)
            or len(rows) != len(set(sources))
            or any(r['metric_rows'] < 1 or r['duplicate_keys'] for r in rows)):
        raise ValueError('Expected complete sources with unique record keys')


def require_preserved(actual, baseline):
    order = lambda rows: sorted(rows, key=lambda row: row['source'])
    if order(actual) != order(baseline):
        raise ValueError('Cookie publication changed core values, keys or counts')


def build_by_source(db, p):
    p.require_completed_batches(db)
    core, target = p.relation(p.CORE_MODEL), p.relation(p.FINAL_MODEL)
    schema = lambda table: [(r['Column'], r['Type']) for r in p.query(db, 'DESCRIBE ' + table)]
    core_schema = schema(core)
    expected = p.publication_schema(core_schema)
    columns = [name for name, _ in core_schema]
    try:
        ddl = p.query(db, 'SHOW CREATE TABLE ' + target)[0]['Create Table']
    except Exception as exc:
        if 'TABLE_NOT_FOUND' not in str(exc):
            raise
        ddl = None
    state = checkpoint(ddl) if ddl else None
    head = p.current_snapshot(db, target) if ddl else None
    current_core = p.current_snapshot(db, core)
    resumed = state is not None
    if resumed and str(state['core_snapshot']) != current_core:
        raise ValueError('Core changed since the interrupted cookie publication')
    if not resumed:
        day = datetime.now(ZoneInfo('Europe/Paris')).date().isoformat()
        pins = {table:p.current_snapshot(db, table) for table in INPUTS.values()}
        coverage = p.query(db, p.render_sql('{{ cookie_source_coverage() }}', {'location_evidence_day':day}))[0]
        if any(p.current_snapshot(db, table) != pin for table, pin in pins.items()):
            raise ValueError('Cookie inputs changed while capturing date coverage')
        state = {'core_snapshot':current_core, 'evaluation_day':day, 'input_snapshots':pins, 'coverage':coverage}
    pinned = core + ' FOR VERSION AS OF ' + str(state['core_snapshot'])
    baseline = p.query(db, p.evidence_snapshot_sql(pinned, columns, include_computed_at=True))
    require_population(baseline, p.SOURCES)
    variables = {'location_evidence_day':state['evaluation_day'],
                 'cookie_window_days':state['coverage']['cookie_location_window_days'],
                 'cookie_coverage_relation':'(' + coverage_sql(state['coverage']) + ')'}
    overrides = {key:table + ' FOR VERSION AS OF ' + str(state['input_snapshots'][table])
                 for key, table in INPUTS.items()}
    def select(sources):
        if not sources or any(source not in p.SOURCES for source in sources):
            raise ValueError('Invalid cookie source selection')
        return p.read_model('int_cookie__metrics', variables={**variables, 'cookie_sources':list(sources)},
                            ref_overrides={p.CORE_MODEL:pinned}, source_overrides=overrides)
    def actual(sources=None):
        relation = target
        if sources is not None:
            relation = '(SELECT * FROM ' + target + " WHERE source IN ('" + "','".join(sources) + "'))"
        return p.query(db, p.evidence_snapshot_sql(relation, columns, include_computed_at=True))
    def integrity(sources=None):
        relation = target if sources is None else '(SELECT * FROM ' + target + " WHERE source IN ('" + "','".join(sources) + "'))"
        failures = p.query(db, p.render_sql((p.ROOT/'tests/cookie_location.sql').read_text(),
                            {'metric_model':p.FINAL_MODEL}, {p.FINAL_MODEL:relation}))
        if failures:
            raise ValueError('Cookie metrics failed integrity checks')
    def guard():
        if p.current_snapshot(db, core) != current_core:
            raise ValueError('Core snapshot changed during cookie publication')
        if head is not None and p.current_snapshot(db, target) != head:
            raise ValueError('Final snapshot changed during cookie publication')
    completed = set()
    if resumed:
        if schema(target) != expected:
            raise ValueError('Incomplete cookie table has an unexpected schema')
        found = actual()
        completed = {r['source'] for r in found}
        require_population(found, completed)
        require_preserved(found, [r for r in baseline if r['source'] in completed])
        integrity()
    marker = PREFIX + json.dumps(state, separators=(',', ':'), sort_keys=True)
    properties = {**p.HISTORY_SESSION_PROPERTIES, 'scale_writers':False,
                  'max_writer_task_count':4, 'iceberg.target_max_file_size':'32MB'}
    print(json.dumps({'phase':'cookie_sources_start', **state, 'completed_sources':sorted(completed)}), flush=True)
    for source in p.SOURCES:
        if source in completed:
            continue
        guard()
        prefix = ('INSERT INTO ' + target if completed else 'CREATE OR REPLACE TABLE ' + target
                  + " COMMENT '" + marker + "' WITH (format='PARQUET') AS")
        sql = prefix + '\n' + select([source])
        for attempt in range(6):
            guard()
            attempt_properties = {**properties, 'max_writer_task_count':max(1, 4 // (2 ** (attempt // 2)))}
            fragments = p.explain_fragments(db, sql, session_properties=attempt_properties)
            print(json.dumps({'phase':'cookie_source_start', 'source':source, 'plan_fragments':fragments,
                              'writer_tasks':attempt_properties['max_writer_task_count']}), flush=True)
            error = None
            try:
                p.run_write(sql, session_properties=attempt_properties)
            except Exception as exc:
                error = exc
            # Inspect commit state before retrying an INSERT, including a lost acknowledgement.
            next_head = p.current_snapshot(db, target)
            if next_head == head:
                if not error:
                    raise ValueError('Cookie source write did not commit')
                retryable = any(code in str(error) for code in ('HIVE_WRITER_CLOSE_ERROR', 'HIVE_WRITER_DATA_ERROR',
                    'ICEBERG_COMMIT_ERROR', 'PAGE_TRANSPORT_TIMEOUT', 'REMOTE_TASK_ERROR', 'REMOTE_HOST_GONE'))
                if not retryable or attempt == 5:
                    raise error
                delay = min(10 * 2 ** attempt, 45)
                print(json.dumps({'phase':'cookie_source_retry', 'source':source, 'attempt':attempt+1,
                                  'wait_seconds':delay, 'error':str(error).split('\n')[0]}), flush=True)
                time.sleep(delay)
                continue
            if schema(target) != expected:
                raise ValueError('Cookie output schema differs from the publication contract')
            require_preserved(actual([source]), [r for r in baseline if r['source'] == source])
            integrity([source])
            head = next_head
            completed.add(source)
            print(json.dumps({'phase':'cookie_source_verified', 'source':source, 'snapshot':head}), flush=True)
            break
    require_preserved(actual(), baseline)
    integrity()
    guard()
    p.run_write('CREATE OR REPLACE VIEW ' + p.relation('int_cookie__metrics') + ' AS ' + select(p.SOURCES),
                session_properties=p.EVIDENCE_SESSION_PROPERTIES)
    p.run_write("COMMENT ON TABLE " + target + " IS 'pii_clean: cookie source batches verified complete'",
                session_properties=p.EVIDENCE_SESSION_PROPERTIES)
    guard()
    print(json.dumps({'phase':'cookie_sources_complete', 'core_snapshot':current_core, 'final_snapshot':head,
                      'evaluation_day':state['evaluation_day'], 'sources':list(p.SOURCES),
                      'records':sum(r['metric_rows'] for r in baseline), 'verified':True}), flush=True)
