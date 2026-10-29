#!/usr/bin/env python3
"""Render complete, standalone, read-only email-lookup SQL without publishing views."""
import argparse
from pathlib import Path

import pipeline as p
import yaml

NAME_HISTORY = ['email_name_count', 'email_npi_has_name_conflict', 'conflicting_npis_share_name',
                'conflicting_npi_name_comparisons', 'conflicting_npis_share_state', 'conflicting_npi_state_comparisons']


def base_columns():
    return [x.strip() for x in p.render_sql('{{ consistency_base_columns() }}').split(',')] + NAME_HISTORY


def render_lookup(email='person@example.com', day=None, ref_overrides=None, source_overrides=None, variables=None):
    schema = yaml.safe_load((p.ROOT / 'models/final/schema.yml').read_text())
    model = next(m for m in schema['models'] if m['name'] == p.FINAL_MODEL)
    declared = [c['name'] for c in model['columns']]
    base = base_columns()
    output = ['email', 'source', 'npi']
    output += [c for c in base + declared if c not in output and c not in ['email', 'source', 'npi']]
    output = list(dict.fromkeys(output))
    expressions = []
    for name in output:
        expressions.append('    r.' + name)
        if name == 'npi':
            expressions += ["    array_join(transform(r.source_name_values, n -> trim(concat_ws(' ', n.first_name, n.last_name))), '; ') AS name",
                            "    array_join(r.source_state_values, '; ') AS state"]
    expressions += ['    cardinality(r.conflicting_npi_name_comparisons) AS name_comparison_count']
    for flag, alias in [('false', 'name_mismatch_count'), ('true', 'shared_name_count'), ('NULL', 'unknown_name_match_count')]:
        condition = 'x.shares_name IS NULL' if flag == 'NULL' else 'x.shares_name = ' + flag
        expressions.append(f'    cardinality(filter(r.conflicting_npi_name_comparisons, x -> {condition})) AS {alias}')
    variables = {**(variables or {}), 'lookup_email_literal': "'" + email.replace("'", "''") + "'",
                 'lookup_base_projection': ', '.join('t.' + c for c in base),
                 'lookup_output_projection': ',\n'.join(expressions)}
    if day:
        variables.update(location_evidence_day=day, registry_status_as_of_day=day)
    return p.render_sql((p.ROOT / 'sql/email_lookup_full.sql.j2').read_text(), variables,
                        ref_overrides=ref_overrides, source_overrides=source_overrides)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', default='person@example.com')
    parser.add_argument('--day', help='Fixed evaluation date; default Europe/Paris current day')
    parser.add_argument('--output', type=Path, default=p.ROOT / 'sql/email_lookup_full.sql')
    args = parser.parse_args()
    if args.day:
        from datetime import date
        date.fromisoformat(args.day)
    args.output.write_text(render_lookup(args.email, args.day) + '\n')
    print(f'Saved {args.output}')


if __name__ == '__main__':
    main()
