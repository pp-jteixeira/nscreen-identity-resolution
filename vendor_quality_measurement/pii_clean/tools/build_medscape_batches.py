#!/usr/bin/env python3
"""Resume Medscape core writes by email hash, preserving every email's history.

The core table must already exist with the 124-field vendor contract. Expected
record keys and observation histories are recomputed from pinned raw snapshots.
Each Iceberg INSERT is atomic. A batch is skipped only when its stored key/history
checksum matches its complete expected population. Results stay on stdout.
"""
import argparse
from datetime import datetime
import json
import re
import time
import uuid
from zoneinfo import ZoneInfo

import pipeline as p

PROPERTIES = {**p.HISTORY_SESSION_PROPERTIES, 'max_writer_task_count': 8,
              'task_max_writer_count': 1, 'task_scale_writers_enabled': False,
              'iceberg.target_max_file_size': '64MB', 'query_max_run_time': '30m'}
HEX = '0123456789ABCDEF'
HISTORY_FIELDS = ('metric_row_id', 'record_id', 'record_payload', 'email', 'npi',
                  'observed_days', 'first_seen_day', 'last_seen_day',
                  'observed_day_count', 'observation_count',
                  'undated_observation_count', 'invalid_day_observation_count')


def bucket_sql(email='email'):
    return f'substr(to_hex(sha256(to_utf8({email}))), 1, 1)'


def history_check_sql(select):
    return ('SELECT ' + bucket_sql() + ' AS batch, count(*) AS records, '
            'count(*) - count(DISTINCT metric_row_id) AS duplicate_keys, '
            'to_hex(checksum(ROW(' + ', '.join(HISTORY_FIELDS) + '))) AS checksum '
            'FROM (' + select + ') GROUP BY 1 ORDER BY 1')


def versioned_records_sql(stage, optout):
    return p.render_sql("WITH versions AS ({{ record_versions('stg_medscape__global', "
                        "exclude_npis_model='stg_medscape__optout') }}) "
                        "SELECT * FROM versions WHERE email_clean IS NOT NULL AND email_clean <> '' "
                        "AND npi_clean IS NOT NULL AND npi_clean <> ''",
                        ref_overrides={'stg_medscape__global': '(' + stage + ')',
                                       'stg_medscape__optout': '(' + optout + ')'})


def records_from_versions(relation):
    return ("SELECT to_hex(sha256(to_utf8(record_id || chr(0) || '1'))) AS metric_row_id, "
            'email_clean AS email, npi_clean AS npi, ' +
            ', '.join(c for c in HISTORY_FIELDS if c not in ('metric_row_id', 'email', 'npi')) +
            ' FROM ' + relation)


def expected_records_sql(stage, optout):
    return records_from_versions('(' + versioned_records_sql(stage, optout) + ')')


def batch_select(stage, optout, meta, batch, latest_day, evaluation_day, versions_table=None):
    if batch not in HEX or len(batch) != 1:
        raise ValueError('Expected one uppercase hexadecimal batch identifier')
    # Filter raw input before exact-record grouping. Every record/day for one
    # normalized email goes to the same batch, including all registration GUIDs.
    # Staging aliases are not visible to its own WHERE, so use an outer relation.
    filtered = '(SELECT * FROM (' + stage + ') WHERE ' + bucket_sql('email_clean') + " = '" + batch + "')"
    variables = {name: evaluation_day for name in ('sequence_as_of_day', 'registry_status_as_of_day',
                 'npi_identity_as_of_day', 'link_freshness_as_of_day', 'location_evidence_day')}
    variables['source_latest_observed_day'] = latest_day
    if versions_table is not None:
        if not re.fullmatch(re.escape(p.SCHEMA) + r'\.[a-z][a-z0-9_]*', versions_table):
            raise ValueError('Versioned input must be a table in the build schema')
        variables['medscape_versioned_records'] = ('(SELECT * FROM ' + versions_table +
            ' WHERE ' + bucket_sql('email_clean') + " = '" + batch + "')")
    return p.read_model('int_medscape__metrics', variables=variables,
                        ref_overrides={'stg_medscape__global': filtered,
                                       'stg_medscape__optout': '(' + optout + ')',
                                       'stg_medscape__meta': '(' + meta + ')'})


def emit(event, **values):
    print(json.dumps({'event': event, **values}, default=str), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batches', default=HEX, help='Hexadecimal batches to build, default all 16')
    parser.add_argument('--day', default=datetime.now(ZoneInfo('Europe/Paris')).date().isoformat())
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--versioned-input', help='Reuse validated stored exact-record versions in the build schema')
    inputs.add_argument('--materialize-records', action='store_true', help='Group eligible raw records once before metric batches')
    args = parser.parse_args()
    if not re.fullmatch('[0-9A-F]+', args.batches) or len(set(args.batches)) != len(args.batches):
        parser.error('Use unique uppercase hexadecimal batch identifiers')
    datetime.strptime(args.day, '%Y-%m-%d')
    db, _ = p.bootstrap()
    def run(sql):
        connection = db.get_trino_connection(session_properties=PROPERTIES)
        cursor = connection.cursor()
        start = time.monotonic()
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            emit('query_done', query_id=cursor.query_id, seconds=round(time.monotonic() - start, 2))
            return [dict(zip([d[0] for d in cursor.description], row)) for row in rows]
        except Exception as exc:
            emit('query_failed', query_id=getattr(exc, 'query_id', None), error=str(exc).split('\n')[0])
            raise
        finally:
            cursor.close()
            connection.close()
    target = p.relation(p.CORE_MODEL)
    expected_schema = run('DESCRIBE ' + p.relation('int_medscape__metrics'))
    assert run('DESCRIBE ' + target) == expected_schema, 'Core table has incompatible schema'
    stages = {}
    for model, raw in [('stg_medscape__global', 'medscape_pii_global'),
                       ('stg_medscape__meta', 'medscape_pii_meta_global'),
                       ('stg_medscape__optout', 'medscape_npi_optout')]:
        table = 'iceberg.thirdparty.' + raw
        snap = run('SELECT snapshot_id FROM iceberg.thirdparty."' + raw +
                   '$history" ORDER BY made_current_at DESC LIMIT 1')[0]['snapshot_id']
        stages[model] = p.read_model(model, source_overrides={('iceberg__thirdparty', raw):
                                      table + ' FOR VERSION AS OF ' + str(snap)})
        emit('pinned_source', table=table, snapshot_id=snap)
    stage, optout, meta = (stages['stg_medscape__' + n] for n in ('global', 'optout', 'meta'))
    expected_select = expected_records_sql(stage, optout)
    expected = {r['batch']: r for r in run(history_check_sql(expected_select))}
    assert expected and not any(r['duplicate_keys'] for r in expected.values()), 'Invalid expected keys'
    if args.materialize_records:
        args.versioned_input = p.SCHEMA + '.pii_medscape_versions_' + uuid.uuid4().hex[:12]
        emit('versioned_input_start', table=args.versioned_input)
        run('CREATE TABLE ' + args.versioned_input + " WITH (format='PARQUET') AS " +
            versioned_records_sql(stage, optout))
    if args.versioned_input:
        if not re.fullmatch(re.escape(p.SCHEMA) + r'\.[a-z][a-z0-9_]*', args.versioned_input):
            raise ValueError('Versioned input must be a table in the build schema')
        cached = records_from_versions(args.versioned_input)
        stored_expected = {r['batch']: r for r in run(history_check_sql(cached))}
        if stored_expected != expected:
            raise ValueError('Versioned input differs from current pinned eligible source histories')
        emit('versioned_input_verified', table=args.versioned_input)
    latest = run('SELECT max(last_seen_day) AS latest FROM (' + expected_select + ')')[0]['latest']
    assert latest is not None, 'Cannot fix full-source freshness date without dated observations'
    emit('expected_population', records=sum(r['records'] for r in expected.values()),
         latest_day=latest, evaluation_day=args.day, batches=expected)
    stored_select = 'SELECT * FROM ' + target + " WHERE source = 'medscape'"
    actual = {r['batch']: r for r in run(history_check_sql(stored_select))}
    if any(batch not in expected or row != expected[batch] for batch, row in actual.items()):
        raise ValueError('Existing Medscape batch is incomplete or differs from pinned source history')
    run('COMMENT ON TABLE ' + target + " IS '" + p.PENDING_BATCH_COMMENT + "'")
    for batch in args.batches:
        if batch not in expected:
            continue
        if batch in actual:
            emit('batch_retained', **actual[batch])
            continue
        select = batch_select(stage, optout, meta, batch, str(latest), args.day, args.versioned_input)
        sql = 'INSERT INTO ' + target + '\n' + select
        emit('batch_start', batch=batch, expected=expected[batch],
             fragments=p.explain_fragments(db, sql, session_properties=PROPERTIES))
        for attempt in range(3):
            try:
                run(sql)
            except Exception as exc:
                retryable = any(name in str(exc) for name in ('HIVE_WRITER_DATA_ERROR',
                    'HIVE_WRITER_CLOSE_ERROR', 'ICEBERG_COMMIT_ERROR', 'PAGE_TRANSPORT_TIMEOUT',
                    'REMOTE_TASK_ERROR', 'REMOTE_HOST_GONE', 'TOO_MANY_REQUESTS_FAILED'))
                # Check commit state even after errors. Never blindly repeat an INSERT.
                found = run(history_check_sql(stored_select + ' AND ' + bucket_sql() + " = '" + batch + "'"))
                if found == [expected[batch]]:
                    break
                if found or not retryable or attempt == 2:
                    raise
                emit('retry_empty_batch', batch=batch, attempt=attempt + 1)
                time.sleep(10)
            else:
                found = run(history_check_sql(stored_select + ' AND ' + bucket_sql() + " = '" + batch + "'"))
                if found != [expected[batch]]:
                    raise ValueError('Committed batch does not match source key/history checksum')
                break
        emit('batch_verified', **expected[batch])
    actual = {r['batch']: r for r in run(history_check_sql(stored_select))}
    if actual == expected:
        run('COMMENT ON TABLE ' + target + " IS 'pii_clean: Medscape email batches verified complete'")
    emit('medscape_complete' if actual == expected else 'medscape_partial',
         records=sum(r['records'] for r in actual.values()), completed_batches=sorted(actual))


if __name__ == '__main__':
    main()
