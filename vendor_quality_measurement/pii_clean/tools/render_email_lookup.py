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


def published_columns():
    schema = yaml.safe_load((p.ROOT / 'models/final/schema.yml').read_text())
    model = next(m for m in schema['models'] if m['name'] == p.FINAL_MODEL)
    declared = [c['name'] for c in model['columns']]
    return declared


def render_lookup(email='person@example.com', ref_overrides=None):
    declared = published_columns()
    # Preserve the existing display order while selecting every published field.
    base = base_columns()
    output = ['email', 'source', 'npi']
    output += [c for c in base + declared if c not in output and c not in ['email', 'source', 'npi']]
    output = list(dict.fromkeys(output))
    expressions = []
    for name in output:
        expressions.append('    r.' + name)
        if name == 'npi':
            expressions += ["    array_join(transform(r.source_name_values, n -> trim(concat_ws(' ', n.first_name, n.last_name))), concat(chr(59), ' ')) AS name",
                            "    array_join(r.source_state_values, concat(chr(59), ' ')) AS state"]
    expressions += ['    coalesce(cardinality(r.conflicting_npi_name_comparisons), 0) AS name_comparison_count']
    for flag, alias in [('false', 'name_mismatch_count'), ('true', 'shared_name_count'), ('NULL', 'unknown_name_match_count')]:
        condition = 'x.shares_name IS NULL' if flag == 'NULL' else 'x.shares_name = ' + flag
        expressions.append(f'    coalesce(cardinality(filter(r.conflicting_npi_name_comparisons, x -> {condition})), 0) AS {alias}')
    # SQLTools splits even quoted semicolons, so encode them as characters.
    email_literal = "'" + email.replace("'", "''").replace(';', "' || chr(59) || '") + "'"
    variables = {'lookup_email_literal': email_literal,
                 'lookup_output_projection': ',\n'.join(expressions)}
    sql = p.render_sql((p.ROOT / 'sql/email_lookup_full.sql.j2').read_text(), variables,
                       ref_overrides=ref_overrides)
    return '\n'.join(line for line in sql.splitlines() if line.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', default='person@example.com')
    parser.add_argument('--output', type=Path, default=p.ROOT / 'sql/email_lookup_full.sql')
    args = parser.parse_args()
    args.output.write_text(render_lookup(args.email) + '\n')
    print(f'Saved {args.output}')


if __name__ == '__main__':
    main()
