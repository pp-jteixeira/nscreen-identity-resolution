#!/usr/bin/env python3
"""Read-only facility/cookie measurement; live outputs contain aggregates only."""
import argparse
import json
from datetime import datetime, timezone

import pipeline as p
from test_location_evidence import check_fixture, fixture_sql

VARIABLES = {'location_evidence_day': '2026-10-29'}


def now():
    return datetime.now(timezone.utc).isoformat()


def invariant(name):
    sql = (p.ROOT / f'tests/{name}.sql').read_text()
    return sql.split('WHERE', 1)[1].rsplit('GROUP BY', 1)[0].strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('native', 'facility', 'cookie', 'plans'))
    args = parser.parse_args()
    db, _ = p.bootstrap()
    path = p.ROOT / f'results/location_evidence_{args.phase}.json'
    data = {'mode': 'read_only', 'published': False, 'verified': False, 'started_at_utc': now(), 'variables': VARIABLES}

    def save():
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + '\n')

    def run(name, sql):
        if not sql.lstrip().lower().startswith(('select', 'with', 'explain', '--')):
            raise ValueError('Read-only SQL required')
        data[name] = {'sql': sql, 'started_at_utc': now()}
        save()
        print('Running ' + name, flush=True)
        try:
            rows = p.query(db, sql)
        except Exception as exc:
            data[name]['error'] = {'type': type(exc).__name__, 'message': str(exc)}
            save()
            raise
        data[name].update(rows=rows, completed_at_utc=now())
        save()
        print(f'Completed {name}: {len(rows)} rows', flush=True)
        return rows

    if args.phase == 'native':
        sql = fixture_sql()
        check_fixture(run('synthetic_records', sql))
        for name in ['vendor_facility_state', 'cookie_location']:
            query = p.render_sql((p.ROOT / f'tests/{name}.sql').read_text(),
                                 {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + sql + ')'})
            if run(name, query):
                raise ValueError('Native integrity failure')
    elif args.phase == 'plans':
        data['sources'] = {}
        for source in p.SOURCES:
            sql = p.read_model(f'int_{source}__metrics', variables=VARIABLES)
            fragments = p.explain_fragments(db, 'SELECT * FROM (' + sql + ')')
            data['sources'][source] = {'sql': sql, 'plan_fragments': fragments}
            save()
            print(f'{source}: {fragments} fragments', flush=True)
        lookup = (p.ROOT / 'sql/email_lookup_full.sql').read_text().strip().rstrip(';')
        run('email_lookup', 'EXPLAIN (TYPE VALIDATE) ' + lookup)
    else:
        snapshot = 'SELECT snapshot_id, committed_at FROM iceberg.jteixeira_ipa."pii_clean$snapshots" ORDER BY committed_at DESC LIMIT 1'
        before = run('snapshot', snapshot)
        if args.phase == 'facility':
            metrics = p.render_sql("{{ vendor_facility_records('saved_records') }}", VARIABLES)
            candidate = f'WITH saved_records AS (SELECT * FROM {p.relation(p.FINAL_MODEL)}), evaluated AS ({metrics}) SELECT * FROM evaluated'
            query = f'''WITH measured AS ({candidate})
SELECT source, vendor_state_evidence, facility_reference_status,
       count(*) AS metric_rows, count(DISTINCT metric_row_id) AS unique_metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links,
       count_if({invariant('vendor_facility_state')}) AS invariant_failures
FROM measured GROUP BY source, vendor_state_evidence, facility_reference_status ORDER BY 1, 2, 3'''
            outcomes = run('outcomes', query)
        else:
            run('coverage', p.render_sql('{{ cookie_source_coverage() }}', VARIABLES))
            facility = p.render_sql("{{ vendor_facility_records('saved_records') }}", VARIABLES)
            cookie = p.render_sql("{{ cookie_location_records('facility_records') }}", VARIABLES)
            candidate = f'''WITH saved_records AS (SELECT * FROM {p.relation(p.FINAL_MODEL)}),
facility_records AS ({facility}), evaluated AS ({cookie}) SELECT * FROM evaluated'''
            # One scan emits all population measures and invariants. No real
            # hashed emails, UIDs, record IDs or email rows leave the warehouse.
            query = f'''WITH measured AS ({candidate})
SELECT source,
       CASE WHEN grouping(cookie_location_status) = 0 THEN 'location_status'
            WHEN grouping(cookie_vendor_state_evidence) = 0 THEN 'vendor_state'
            WHEN grouping(cookie_facility_state_evidence) = 0 THEN 'facility_state'
            ELSE 'totals' END AS section,
       cookie_location_status, cookie_vendor_state_evidence, cookie_facility_state_evidence,
       count(*) AS metric_rows, count(DISTINCT metric_row_id) AS unique_metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links, count(DISTINCT email) AS distinct_emails,
       count_if({invariant('cookie_location')}) AS invariant_failures,
       count(DISTINCT IF(cookie_primary_state_tied_count > 0, email, NULL)) AS emails_with_tied_uids,
       count(DISTINCT IF(cookie_primary_state_multistate_count > 0, email, NULL)) AS emails_with_multistate_uids
FROM measured GROUP BY GROUPING SETS ((source), (source,cookie_location_status),
    (source,cookie_vendor_state_evidence), (source,cookie_facility_state_evidence))
ORDER BY source, section, cookie_location_status, cookie_vendor_state_evidence, cookie_facility_state_evidence'''
            data['distributed_plan_fragments'] = p.explain_fragments(db, query)
            save()
            outcomes = run('outcomes', query)
        if any(r['invariant_failures'] or r['metric_rows'] != r['unique_metric_rows'] for r in outcomes):
            raise ValueError('Measurement integrity failure')
        totals = run('totals', f'''SELECT source, count(*) AS metric_rows,
count(DISTINCT ROW(email,npi)) AS distinct_links FROM {p.relation(p.FINAL_MODEL)} GROUP BY source ORDER BY source''')
        for total in totals:
            rows = [r for r in outcomes if r['source'] == total['source'] and
                    (args.phase == 'facility' or r['section'] == 'location_status')]
            if sum(r['metric_rows'] for r in rows) != total['metric_rows']:
                raise ValueError('Record population changed')
            if args.phase == 'cookie' and sum(r['distinct_links'] for r in rows) != total['distinct_links']:
                raise ValueError('Location statuses failed link partitioning')
        if before != run('snapshot_after', snapshot):
            raise ValueError('Published input changed during measurement')
        if args.phase == 'cookie':
            after_coverage = run('coverage_after', p.render_sql('{{ cookie_source_coverage() }}', VARIABLES))
            data['source_date_coverage_unchanged'] = after_coverage == data['coverage']['rows']
            save()
            if not data['source_date_coverage_unchanged']:
                raise ValueError('Source-date coverage changed during measurement')
    data.update(verified=True, completed_at_utc=now())
    save()
    print(f'Saved {path}', flush=True)


if __name__ == '__main__':
    main()
