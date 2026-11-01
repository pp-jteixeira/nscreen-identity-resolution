#!/usr/bin/env python3
"""Add stored name evidence to existing core/final records without rebuilding history.

Run with --publish to write the two existing sandbox tables and refresh views.
Default is read-only validation. Existing fields, including cookies and timestamps,
are preserved and checked. Partial publication can resume from the upgraded core.
Results and checkpoints stay on stdout.
"""
import argparse
import json
import re
import time

import pipeline as p

FIELDS = ('name_match_evidence', 'vendor_registry_match_classes',
          'name_match_evaluated_at', 'name_match_definition_version')
COMPARISONS = (*p.NAME_METRICS, 'source_name_usable', 'registry_name_usable',
               'registry_npi_present', 'source_name_values')
HEX = '0123456789ABCDEF'
PARTIAL = 'pii_clean: name evidence batches'


def bucket_sql():
    return 'substr(to_hex(sha256(to_utf8(email))),1,1)'


def batch_relation(table, batch):
    if batch not in HEX or len(batch) != 1:
        raise ValueError('Expected one uppercase hexadecimal batch')
    return '(SELECT * FROM ' + table + ' WHERE ' + bucket_sql() + "='" + batch + "')"


def partial_pins(ddl):
    match = re.search(re.escape(PARTIAL) + r' core=(\d+) final=(\d+)', ddl)
    if PARTIAL in ddl and not match:
        raise ValueError('Unrecognized partial-publication marker')
    return match.groups() if match else None


def name_sql(core, registry_snapshot):
    variants = '(' + p.read_model('int_name__variants', ref_overrides={
        'nicknames': '(' + p.read_model('nicknames') + ')'}) + ')'
    reference = '(' + p.read_model('stg_npi__reference', source_overrides={
        ('iceberg__npi', 'npi_reference'): 'iceberg.npi.npi_reference FOR VERSION AS OF '
        + str(int(registry_snapshot))}) + ')'
    registry = '(' + p.read_model('int_npi__names', ref_overrides={
        'stg_npi__reference': reference, 'int_name__variants': variants}) + ')'
    names_type = p.render_sql('{{ source_name_array_type() }}')
    fallback = ('CAST(ARRAY[ROW(CAST(NULL AS varchar), CAST(NULL AS varchar), '
                'CAST(ARRAY[] AS array(varchar)))] AS ' + names_type + ')')
    inputs = ('(SELECT CAST(ROW(m.source,m.metric_row_id) AS row(source varchar, row_id varchar)) '
              'AS metric_row_id, m.email, m.npi, s.first_name, s.last_name FROM ' + core
              + ' m CROSS JOIN UNNEST(CASE WHEN cardinality(m.source_name_values)>0 '
              'THEN m.source_name_values ELSE ' + fallback
              + ' END) AS s(first_name,last_name,first_variants))')
    return p.render_sql("{{ link_name_metrics(none, input_relation=var('inputs'), "
                        "record_grain=true, include_source_names=true) }}",
                        variables={'inputs': inputs}, ref_overrides={
                            'int_name__variants': variants, 'int_npi__names': registry})


def comparison_sql(core, names):
    checks = ', '.join('count_if(m.' + f + ' IS DISTINCT FROM n.' + f + ') AS ' + f
                       for f in COMPARISONS)
    return ('WITH names AS (' + names + ') SELECT m.source, count(*) AS records, '
            'count_if(n.metric_row_id IS NULL) AS missing_evidence, ' + checks
            + ' FROM ' + core + ' m LEFT JOIN names n '
            'ON n.metric_row_id = CAST(ROW(m.source,m.metric_row_id) AS row(source varchar,row_id varchar)) GROUP BY m.source ORDER BY m.source')


def core_select(core, names, columns):
    projection = ', '.join(('n.' if c in FIELDS else 'm.') + c for c in columns)
    return ('WITH names AS (' + names + ') SELECT ' + projection + ' FROM ' + core
            + ' m LEFT JOIN names n ON n.metric_row_id = CAST(ROW(m.source,m.metric_row_id) AS row(source varchar,row_id varchar))')


def final_select(final, core, columns):
    projection = ', '.join(('c.' if c in FIELDS else 'f.') + c for c in columns)
    return ('SELECT ' + projection + ' FROM ' + final + ' f LEFT JOIN ' + core
            + ' c ON c.source=f.source AND c.metric_row_id=f.metric_row_id')


def snapshot_sql(table, groups, batches=False):
    checks = ', '.join('to_hex(checksum(ROW(' + ', '.join(columns) + '))) AS ' + label
                       for label, columns in groups.items())
    batch = bucket_sql() + ' AS batch, ' if batches else ''
    grouping = 'source,2' if batches else 'source'
    return ('SELECT source, ' + batch + 'count(*) AS records, count(*)-count(DISTINCT ROW(source, metric_row_id)) '
            'AS duplicate_keys, ' + checks + ' FROM ' + table + ' GROUP BY ' + grouping + ' ORDER BY ' + grouping)


def require_population(rows):
    if ({r['source'] for r in rows} != set(p.SOURCES)
            or any(r['records'] < 1 or r['duplicate_keys'] for r in rows)):
        raise ValueError('Expected all seven sources with nonempty, unique record populations')


def require_same(before, after, field):
    project = lambda rows: sorted((r['source'], r.get('batch', ''), r['records'], r['duplicate_keys'], r[field]) for r in rows)
    if project(before) != project(after):
        raise ValueError('Stored values, keys or counts changed: ' + field)


def emit(phase, **values):
    print(json.dumps({'phase': phase, **values}, default=str), flush=True)


def batch_writer_count(maximum, attempt):
    return max(1, maximum // (2 ** (attempt // 2)))


def verified_batches(actual, final_before, core_after):
    completed = set()
    for batch in sorted({r['batch'] for r in actual}):
        found = [r for r in actual if r['batch'] == batch]
        require_same([r for r in final_before if r['batch'] == batch], found, 'old_final')
        require_same([r for r in core_after if r['batch'] == batch], found, 'full_core')
        completed.add(batch)
    return completed


def publish_batches(db, final, pinned_final, pinned_core, columns, core_columns,
                    old_columns, final_before, core_after, started, marker, write, guard):
    groups = {'old_final': old_columns, 'full_core': core_columns}
    head = p.current_snapshot(db, final)
    actual = p.query(db, snapshot_sql(final + ' FOR VERSION AS OF ' + head, groups, True)) if started else []
    completed = verified_batches(actual, final_before, core_after)
    emit('final_batches_checked', completed=sorted(completed))
    for batch in HEX:
        if batch in completed:
            continue
        guard(final, head)
        select = final_select(batch_relation(pinned_final, batch),
                              batch_relation(pinned_core, batch), columns)
        prefix = ('INSERT INTO ' + final if started else 'CREATE OR REPLACE TABLE ' + final
                  + " COMMENT '" + marker + "' WITH (format='PARQUET')")
        sql = prefix + (' AS ' if not started else ' ') + select
        for attempt in range(6):
            error = None
            try:
                write(sql, 'final_batch_' + batch)
            except Exception as exc:
                error = exc
            # Check commit state even after an error. An INSERT must not be repeated blindly.
            current_columns = [r['Column'] for r in p.query(db, 'DESCRIBE ' + final)]
            head_after = p.current_snapshot(db, final)
            found = (p.query(db, snapshot_sql(batch_relation(final + ' FOR VERSION AS OF ' + head_after, batch), groups, True))
                     if current_columns == columns else [])
            if found:
                verified_batches(found, final_before, core_after)
                head = head_after
                started = True
                emit('final_batch_verified', batch=batch, snapshot=head, records=sum(r['records'] for r in found))
                break
            if error is None:
                raise ValueError('Write returned without committing the expected batch')
            if head_after != head:
                raise ValueError('Final snapshot changed without the expected batch') from error
            retryable = any(code in str(error) for code in ('HIVE_WRITER_CLOSE_ERROR', 'HIVE_WRITER_DATA_ERROR',
                'ICEBERG_COMMIT_ERROR', 'PAGE_TRANSPORT_TIMEOUT', 'REMOTE_TASK_ERROR', 'REMOTE_HOST_GONE'))
            if not retryable or attempt == 5:
                raise error
            delay = min(10 * 2 ** attempt, 45)
            emit('final_batch_retry', batch=batch, attempt=attempt+1, wait_seconds=delay,
                 error=str(error).split('\n')[0])
            time.sleep(delay)
    return head


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='Publish after all preflight checks pass')
    parser.add_argument('--final-batches', action='store_true',
                        help='Recover final publication in 16 resumable email batches. Final is partial until completion')
    parser.add_argument('--batch-writers', type=int, choices=(1, 2, 4, 8), default=4,
                        help='Maximum writer tasks per batch, reduced after repeated failures (default: 4)')
    args = parser.parse_args()
    db, _ = p.bootstrap()
    core, final = p.relation(p.CORE_MODEL), p.relation(p.FINAL_MODEL)
    expected_core = p.render_sql('{{ metric_columns() | join(",") }}').split(',')
    expected_final = p.render_sql('{{ metric_columns(include_cookie=true) | join(",") }}').split(',')
    old_core = [c for c in expected_core if c not in FIELDS]
    old_final = [c for c in expected_final if c not in FIELDS]
    schema = lambda table: [(r['Column'], r['Type']) for r in p.query(db, 'DESCRIBE ' + table)]
    core_schema, final_schema = schema(core), schema(final)
    core_columns, final_columns = ([n for n, _ in s] for s in (core_schema, final_schema))
    if core_columns not in (old_core, expected_core) or final_columns not in (old_final, expected_final):
        raise ValueError('Unexpected schema. This tool only adds the four stored name fields')
    if final_columns == expected_final and core_columns != expected_core:
        raise ValueError('Final is ahead of core. Inspect the publication before resuming')
    if args.final_batches and core_columns != expected_core:
        raise ValueError('Final batches require the completed 128-field core')
    p.require_completed_batches(db)
    cp, final_head = p.current_snapshot(db, core), p.current_snapshot(db, final)
    pins = partial_pins(str(p.query(db, 'SHOW CREATE TABLE ' + final)))
    if pins and (not args.final_batches or pins[0] != cp):
        raise ValueError('Final batches are incomplete. Resume --final-batches with the same core snapshot')
    fp = pins[1] if pins else final_head
    pinned_core, pinned_final = core + ' FOR VERSION AS OF ' + cp, final + ' FOR VERSION AS OF ' + fp
    rp = p.current_snapshot(db, 'iceberg.npi.npi_reference') if core_columns == old_core else None
    emit('pinned', core_snapshot=cp, final_snapshot=fp, registry_snapshot=rp)
    core_groups = {'old_core': old_core}
    if core_columns == expected_core:
        core_groups['full_core'] = expected_core
    core_before = p.query(db, snapshot_sql(pinned_core, core_groups, args.final_batches))
    final_before = p.query(db, snapshot_sql(pinned_final, {'old_core': old_core, 'old_final': old_final}, args.final_batches))
    require_population(core_before)
    require_population(final_before)
    require_same(core_before, final_before, 'old_core')
    if core_columns == old_core:
        names = name_sql(pinned_core, rp)
        comparisons = p.query(db, comparison_sql(pinned_core, names))
        if ([(r['source'], r['records']) for r in comparisons]
                != [(r['source'], r['records']) for r in core_before]
                or any(r['missing_evidence'] or any(r[f] for f in COMPARISONS) for r in comparisons)):
            emit('comparison_mismatch', comparisons=comparisons)
            raise ValueError('Current name reference/variants do not reproduce stored indicators')
        emit('comparisons_verified', records=sum(r['records'] for r in comparisons))
    if not args.publish:
        emit('preflight_complete', published=False)
        return

    def unchanged(table, expected):
        if p.current_snapshot(db, table) != expected:
            raise ValueError('Concurrent change to ' + table)

    write_attempts = {}

    def write(sql, phase):
        attempt = write_attempts.get(phase, 0)
        write_attempts[phase] = attempt + 1
        properties = {**p.HISTORY_SESSION_PROPERTIES}
        if phase.startswith('final'):
            properties['iceberg.target_max_file_size'] = '32MB'
        if phase.startswith('final_batch'):
            properties['max_writer_task_count'] = batch_writer_count(args.batch_writers, attempt)
            properties['scale_writers'] = False
        fragments = p.explain_fragments(db, sql, session_properties=properties)
        emit(phase + '_start', plan_fragments=fragments, target_file_size=properties['iceberg.target_max_file_size'],
             writer_tasks=properties['max_writer_task_count'])
        connection = db.get_trino_connection(session_properties=properties)
        cursor = connection.cursor()
        started = time.monotonic()
        try:
            cursor.execute(sql)
            cursor.fetchall()
            emit(phase + '_done', query_id=cursor.query_id, seconds=round(time.monotonic()-started, 2))
        finally:
            cursor.close()
            connection.close()

    unchanged(core, cp)
    unchanged(final, final_head)
    if core_columns == old_core:
        write('CREATE OR REPLACE TABLE ' + core + " WITH (format='PARQUET') AS "
              + core_select(pinned_core, names, expected_core), 'core_write')
        cp = p.current_snapshot(db, core)
        pinned_core = core + ' FOR VERSION AS OF ' + cp
    core_after = (core_before if core_columns == expected_core else
                  p.query(db, snapshot_sql(pinned_core, {'old_core': old_core, 'full_core': expected_core})))
    require_population(core_after)
    require_same(core_before, core_after, 'old_core')
    core_schema = schema(core)
    if [n for n, _ in core_schema] != expected_core:
        raise ValueError('Published core schema differs from the local contract')
    check = (p.ROOT / 'tests/name_match_evidence.sql').read_text()
    failures = p.query(db, 'SELECT * FROM (' + p.render_sql(check, {'metric_model': p.CORE_MODEL},
                        {p.CORE_MODEL: pinned_core}) + ') LIMIT 20')
    if failures:
        emit('evidence_failures', failures=failures[:20])
        raise ValueError('Stored name evidence failed integrity')
    emit('core_verified', snapshot=cp, records=sum(r['records'] for r in core_after))
    unchanged(core, cp)
    unchanged(final, final_head)
    if args.final_batches:
        marker = PARTIAL + ' core=' + cp + ' final=' + fp
        fp = publish_batches(db, final, pinned_final, pinned_core, expected_final, expected_core, old_final,
                             final_before, core_after, final_columns == expected_final, marker, write, unchanged)
        pinned_final = final + ' FOR VERSION AS OF ' + fp
    elif final_columns == old_final:
        write('CREATE OR REPLACE TABLE ' + final + " WITH (format='PARQUET') AS "
              + final_select(pinned_final, pinned_core, expected_final), 'final_write')
        fp = p.current_snapshot(db, final)
        pinned_final = final + ' FOR VERSION AS OF ' + fp
    if schema(final) != p.publication_schema(core_schema):
        raise ValueError('Final schema differs from the publication contract')
    final_after = p.query(db, snapshot_sql(pinned_final, {'old_final': old_final, 'full_core': expected_core}, args.final_batches))
    require_population(final_after)
    require_same(final_before, final_after, 'old_final')
    require_same(core_after, final_after, 'full_core')
    if args.final_batches:
        keys = p.query(db, 'SELECT source,count(*) AS records,count(*)-count(DISTINCT metric_row_id) AS duplicate_keys '
                       'FROM ' + pinned_final + ' GROUP BY source ORDER BY source')
        require_population(keys)
    unchanged(core, cp)
    unchanged(final, fp)
    if args.final_batches:
        p.run_write("COMMENT ON TABLE " + final + " IS 'pii_clean: stored name evidence verified complete'",
                    session_properties=p.EVIDENCE_SESSION_PROPERTIES)
    for model in [*(f'int_{s}__metrics' for s in p.SOURCES), 'int_cookie__metrics']:
        p.run_write('CREATE OR REPLACE VIEW ' + p.relation(model) + ' AS ' + p.read_model(model),
                    session_properties=p.EVIDENCE_SESSION_PROPERTIES)
        emit('view_refreshed', model=model)
    unchanged(core, cp)
    unchanged(final, fp)
    emit('published', core_snapshot=cp, final_snapshot=fp, registry_snapshot=rp,
         records=sum(r['records'] for r in final_after), original_fields_preserved=len(old_final),
         core_fields=len(expected_core), final_fields=len(expected_final))


if __name__ == '__main__':
    main()
