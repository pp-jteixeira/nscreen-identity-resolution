#!/usr/bin/env python3
"""Read-only native validation and facility-overlap measurements on saved records.

Does not recreate views or publish the final table. Outputs record the executed SQL.
"""
import argparse
import json
from datetime import datetime, timezone

import pipeline as p
from test_conflicting_facilities import check_dated, dated_fixture


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('native', 'measure'))
    args = parser.parse_args()
    db, _ = p.bootstrap()
    result = {'started_at_utc': now(), 'mode': 'read_only', 'published': False}
    path = p.ROOT / f'results/conflicting_facilities_{args.phase}.json'

    def run(name, sql):
        if not sql.lstrip().lower().startswith(('select', 'with', '--')):
            raise ValueError('Read-only SQL required')
        result[name] = {'sql': sql, 'started_at_utc': now()}
        save(path, result)
        print(f'Running {name}', flush=True)
        rows = p.query(db, sql)
        result[name].update(rows=rows, completed_at_utc=now())
        save(path, result)
        print(f'Completed {name}: {len(rows)} result rows', flush=True)
        return rows

    if args.phase == 'native':
        sql = dated_fixture()
        rows = run('dated_facilities', sql)
        check_dated(rows)
        template = (p.ROOT / 'tests/conflicting_facilities.sql').read_text()
        checks = run('independent_check', p.render_sql(template, {'metric_model': p.FINAL_MODEL},
                    {p.FINAL_MODEL: '(' + sql + ')'}))
        if checks:
            raise ValueError(f'Independent check failed: {checks}')
    else:
        run('snapshot', 'SELECT snapshot_id, committed_at FROM iceberg.jteixeira_ipa."pii_clean$snapshots" ORDER BY committed_at DESC LIMIT 1')
        lookup = p.render_sql('{{ facility_npi_lookup() }}')
        run('reference', f'''WITH facility_reference AS ({lookup})
SELECT count(*) AS provider_npis,
       count_if(cardinality(facility_npi_values) > 0) AS providers_with_facility_ids,
       count_if(cardinality(facility_npi_values) = 0) AS providers_without_facility_ids,
       max(cardinality(facility_npi_values)) AS max_facilities_per_provider
FROM facility_reference''')
        run('coverage', f'''WITH facility_reference AS ({lookup})
SELECT m.source, count(*) AS metric_rows, count(DISTINCT m.email) AS distinct_emails,
       count(DISTINCT ROW(m.email, m.npi)) AS distinct_links,
       count_if(cardinality(f.facility_npi_values) > 0) AS usable_facility_rows,
       count_if(m.has_conflict_linkage) AS conflict_rows,
       count_if(m.has_conflict_linkage = false) AS not_applicable_rows,
       count_if(m.has_conflict_linkage IS NULL) AS unknown_timing_rows,
       count(DISTINCT IF(m.has_conflict_linkage, m.email, NULL)) AS conflict_emails
FROM {p.relation(p.FINAL_MODEL)} m LEFT JOIN facility_reference f ON m.npi = f.npi
GROUP BY m.source ORDER BY m.source''')
        run('link_coverage', f'''WITH facility_reference AS ({lookup})
SELECT m.source, count(DISTINCT ROW(m.email, m.npi)) AS distinct_links,
       count(DISTINCT IF(cardinality(f.facility_npi_values) > 0, ROW(m.email, m.npi), NULL)) AS usable_facility_links
FROM {p.relation(p.FINAL_MODEL)} m LEFT JOIN facility_reference f ON m.npi = f.npi
GROUP BY m.source ORDER BY m.source''')
        # No-conflict records cannot have an applicable outcome. Evaluate windows
        # only for the established conflict subset; preserve its exact record grain.
        metrics = p.render_sql("{{ facility_consistency_metrics('saved_records') }}")
        candidate = f'''WITH saved_records AS (
    SELECT * FROM {p.relation(p.FINAL_MODEL)} WHERE has_conflict_linkage
), evaluated AS ({metrics}) SELECT * FROM evaluated'''
        run('outcomes', f'''WITH measured AS ({candidate})
SELECT source, count(*) AS conflict_rows, count(DISTINCT metric_row_id) AS distinct_record_keys,
       count_if(conflicting_npis_share_facility) AS shared_facility_rows,
       count_if(conflicting_npis_share_facility = false) AS different_facility_rows,
       count_if(conflicting_npis_share_facility IS NULL) AS unknown_facility_rows,
       count(DISTINCT ROW(email, npi)) AS conflict_links,
       count(DISTINCT IF(conflicting_npis_share_facility, ROW(email, npi), NULL)) AS shared_facility_links,
       count(DISTINCT IF(conflicting_npis_share_facility = false, ROW(email, npi), NULL)) AS different_facility_links,
       count(DISTINCT IF(conflicting_npis_share_facility IS NULL, ROW(email, npi), NULL)) AS unknown_facility_links
FROM measured GROUP BY source ORDER BY source''')
        template = (p.ROOT / 'tests/conflicting_facilities.sql').read_text()
        failures = run('independent_check', p.render_sql(template, {'metric_model': p.FINAL_MODEL},
                       {p.FINAL_MODEL: '(' + candidate + ')'}))
        if failures:
            raise ValueError(f'Population check failed: {failures}')
        run('examples', f'''WITH measured AS ({candidate}), ranked AS (
    SELECT source, metric_row_id, email, npi, observed_days, conflict_days,
           facility_npi_values, conflicting_npis_share_facility, conflicting_npi_facility_comparisons,
           row_number() OVER (PARTITION BY source, conflicting_npis_share_facility ORDER BY metric_row_id) AS sample_rank
    FROM measured
)
SELECT * FROM ranked WHERE sample_rank <= 2 ORDER BY source, conflicting_npis_share_facility, sample_rank''')
        expected = {r['source']: r for r in result['coverage']['rows']}
        for row in result['outcomes']['rows']:
            if row['conflict_rows'] != expected[row['source']]['conflict_rows'] or row['distinct_record_keys'] != row['conflict_rows']:
                raise ValueError('Facility enrichment changed conflict-row grain')
            if sum(row[k] for k in ('shared_facility_rows', 'different_facility_rows', 'unknown_facility_rows')) != row['conflict_rows']:
                raise ValueError('Outcomes do not partition conflict rows')
    result.update(verified=True, completed_at_utc=now())
    save(path, result)
    print(f'Saved {path}', flush=True)


if __name__ == '__main__':
    main()
