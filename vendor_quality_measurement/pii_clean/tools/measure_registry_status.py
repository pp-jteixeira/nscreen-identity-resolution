#!/usr/bin/env python3
"""Read-only lifecycle validation, population measurement and query planning."""
import argparse
import json
from datetime import datetime, timezone

import pipeline as p
from test_registry_status import check_fixture, fixture_sql


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('native', 'measure', 'plans'))
    args = parser.parse_args()
    db, _ = p.bootstrap()
    path = p.ROOT / f'results/registry_status_{args.phase}.json'
    result = {'started_at_utc': now(), 'mode': 'read_only', 'published': False}

    def save():
        print(json.dumps(result, indent=2), flush=True)

    def run(name, sql):
        if not sql.lstrip().lower().startswith(('with', 'select', 'explain', '--')):
            raise ValueError('Only read-only queries are permitted')
        result[name] = {'sql': sql, 'started_at_utc': now()}
        save()
        print('Running ' + name, flush=True)
        rows = p.query(db, sql)
        result[name].update(rows=rows, completed_at_utc=now())
        save()
        print(f'Completed {name}: {len(rows)} result rows', flush=True)
        return rows

    if args.phase == 'native':
        sql = fixture_sql()
        check_fixture(run('fixtures', sql))
        sql = "SELECT 'fixture' AS source, x.* FROM (" + sql + ') x'
        failures = run('invariants', p.render_sql((p.ROOT / 'tests/registry_status.sql').read_text(),
                       {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + sql + ')'}))
        if failures:
            raise ValueError(f'Native invariant failures: {failures}')
    elif args.phase == 'plans':
        result['sources'] = {}
        for source in p.SOURCES:
            sql = 'SELECT * FROM (' + p.read_model(f'int_{source}__metrics') + ')'
            fragments = p.explain_fragments(db, sql)
            result['sources'][source] = {'sql': sql, 'plan_fragments': fragments}
            save()
            print(f'{source}: {fragments} fragments', flush=True)
        lookup_sql = (p.ROOT / 'sql/email_lookup_full.sql').read_text().strip().rstrip(';')
        run('email_lookup', 'EXPLAIN (TYPE VALIDATE) ' + lookup_sql)
    else:
        snapshot_sql = 'SELECT snapshot_id, committed_at FROM iceberg.jteixeira_ipa."pii_clean$snapshots" ORDER BY committed_at DESC LIMIT 1'
        before = run('snapshot', snapshot_sql)
        run('reference_profile', '''SELECT count(*) AS reference_rows, count(DISTINCT npi) AS distinct_npis,
    count_if(npi_deactivation_date IS NOT NULL) AS deactivation_values,
    count_if(npi_reactivation_date IS NOT NULL) AS reactivation_values,
    count_if(replacement_npi IS NOT NULL) AS replacement_values,
    count_if(npi_deactivation_reason_code IS NOT NULL) AS reason_values,
    count_if(nullif(trim(npi_deactivation_date), '') IS NOT NULL AND try_cast(npi_deactivation_date AS date) IS NULL) AS invalid_deactivation_dates,
    count_if(nullif(trim(npi_reactivation_date), '') IS NOT NULL AND try_cast(npi_reactivation_date AS date) IS NULL) AS invalid_reactivation_dates
FROM iceberg.npi.nppes_npidata_latest''')
        lookup = p.render_sql('{{ registry_status_lookup() }}')
        run('reference_outcomes', f'''WITH statuses AS ({lookup})
SELECT npi_registry_status, npi_registry_status_reason, count(*) AS npis
FROM statuses GROUP BY npi_registry_status, npi_registry_status_reason ORDER BY 1, 2''')
        totals = run('totals', f'''SELECT source, count(*) AS metric_rows,
       count(DISTINCT ROW(email, npi)) AS distinct_links, count(DISTINCT npi) AS distinct_npis
FROM {p.relation(p.FINAL_MODEL)} GROUP BY source ORDER BY source''')
        metrics = p.render_sql("{{ registry_status_records('saved_records') }}")
        candidate = f'WITH saved_records AS (SELECT * FROM {p.relation(p.FINAL_MODEL)}), evaluated AS ({metrics}) SELECT * FROM evaluated'
        profile = (p.ROOT / 'sql/registry_status_profile.sql').read_text().replace('/* EVALUATED_SQL */', candidate)
        outcomes = run('outcomes', profile)
        failures = run('invariants', p.render_sql((p.ROOT / 'tests/registry_status.sql').read_text(),
                       {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + candidate + ')'}))
        if failures:
            raise ValueError(f'Population invariant failures: {failures}')
        run('examples', f'''WITH measured AS ({candidate}), ranked AS (
    SELECT source, metric_row_id, npi, npi_registry_status, npi_registry_status_reason,
           npi_registry_replacement_npi, npi_registry_deactivation_date, npi_registry_reactivation_date,
           npi_registry_reference_row_count, npi_registry_variant_count, npi_registry_lifecycle_evidence,
           npi_registry_status_as_of_day,
           row_number() OVER (PARTITION BY source, npi_registry_status ORDER BY metric_row_id) AS sample_rank
    FROM measured
)
SELECT * FROM ranked WHERE sample_rank <= 2 ORDER BY source, npi_registry_status, sample_rank''')
        for total in totals:
            rows = [r for r in outcomes if r['source'] == total['source']]
            if sum(r['metric_rows'] for r in rows) != total['metric_rows']:
                raise ValueError('Status enrichment changed metric-row population')
            if sum(r['distinct_links'] for r in rows) != total['distinct_links']:
                raise ValueError('Statuses do not partition distinct links')
            if any(r['unique_metric_rows'] != r['metric_rows'] for r in rows):
                raise ValueError('Status enrichment duplicated metric-row keys')
        after = run('snapshot_after', snapshot_sql)
        if before != after:
            raise ValueError('Published input changed during measurement')
    result.update(verified=True, completed_at_utc=now())
    save()
    print('Results displayed on stdout', flush=True)


if __name__ == '__main__':
    main()
