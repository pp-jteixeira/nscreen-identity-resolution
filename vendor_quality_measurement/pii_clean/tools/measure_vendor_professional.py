#!/usr/bin/env python3
"""Read-only Trino checks and vendor populations. SQL/results stay on stdout."""
import argparse
from datetime import datetime, timezone
import json

import pipeline as p
from test_vendor_professional import check_same_day, same_day_fixture


def measurement_sql(source):
    # Existing stored attribution context avoids recomputing unrelated metrics.
    records = (f"SELECT source, email, npi, metric_row_id, record_payload, observed_days, conflict_days, has_conflict_linkage, source_tables "
               f"FROM {p.relation(p.FINAL_MODEL)} WHERE source = '{source}'")
    evaluated = p.render_sql("WITH professional_input AS (" + records + "), professional_output AS ("
                            + "{{ vendor_professional_records('professional_input', '" + source
                            + "', 'professional_input') }}) SELECT * FROM professional_output")
    template = (p.ROOT / 'sql/vendor_professional_profile.sql').read_text()
    return p.render_sql(template.replace('/* EVALUATED_SQL */', evaluated))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measure', action='store_true', help='Also measure all rows per selected vendor')
    parser.add_argument('--source', choices=(*p.SOURCES, 'all'), default='all')
    parser.add_argument('--show-sql', action='store_true', help='Print executed SQL as well as results')
    args = parser.parse_args()
    db, _ = p.bootstrap()

    def query(label, sql):
        started = {'check': label, 'started_at_utc': datetime.now(timezone.utc).isoformat()}
        if args.show_sql:
            started['sql'] = sql
        print(json.dumps(started), flush=True)
        rows = db.query2df(sql).to_dict('records')
        print(json.dumps({'check': label, 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                          'rows': rows}, default=str), flush=True)
        return rows

    fixture = same_day_fixture()
    check_same_day(query('native_same_day_guid_preservation', fixture))
    test = p.render_sql((p.ROOT / 'tests/vendor_professional.sql').read_text(),
                        {'metric_model': p.FINAL_MODEL}, {p.FINAL_MODEL: '(' + fixture + ')'})
    if query('native_independent_integrity', test):
        raise ValueError('Synthetic native integrity check failed')
    for source in p.SOURCES if args.source == 'all' else [args.source]:
        query(source + '_model_validation', 'EXPLAIN (TYPE VALIDATE) ' + p.read_model('int_' + source + '__metrics'))
        print(json.dumps({'check': source + '_distributed_plan',
                          'fragments': p.explain_fragments(db, p.read_model('int_' + source + '__metrics'))}), flush=True)
        if args.measure:
            sql = measurement_sql(source)
            query(source + '_measurement_validation', 'EXPLAIN (TYPE VALIDATE) ' + sql)
            rows = query(source + '_population', sql)
            if len(rows) != 2:
                raise ValueError(f'{source}: missing metric dimensions')
            for row in rows:
                if row['shared_rows'] + row['disjoint_rows'] + row['unknown_conflict_rows'] != row['conflict_rows']:
                    raise ValueError(f'{source}: conflict denominator mismatch')


if __name__ == '__main__':
    main()
