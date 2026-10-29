#!/usr/bin/env python3
"""Exercise domain categories, precedence and malformed-input boundaries."""
import unittest

import jinja2

import pipeline
from test_models import execute, literal


CASES = [
    (None, 'unknown'), ('', 'unknown'), ('NULL', 'unknown'),
    ('alice.example.test', 'unknown'),
    ('alice@example.edu', 'institutional'),
    ('alice@example.gov', 'institutional'),
    ('alice@example.mil', 'institutional'),
    ('alice@example.ac.uk', 'institutional'),
    ('alice@example.edu.au', 'institutional'),
    ('alice@EXAMPLE.EDU', 'institutional'),
    ('alice@clinic.example', 'institutional'),
    ('alice@university.example', 'institutional'),
    ('alice@gmail.com', 'free'), ('alice@proton.me', 'free'),
    ('alice@gmail.example', 'free'),  # Prefix matching, not domain verification.
    ('alice@mail.example', 'free'),
    ('alice@gmail.clinic.example', 'institutional'),  # First rule wins.
    ('alice@sub.gmail.com', 'custom'),
    ('alice@notgmail.com', 'custom'),
    ('alice@example.org', 'custom'),
    ('alice@example.edu.example', 'custom'),
    ('alice@example.ac.toolong', 'custom'),
    ('alice@', 'custom'), ('@', 'custom'),
    ('@example.edu', 'institutional'),
    ('alice@@gmail.com', 'custom'),
    ('alice@@clinic.example', 'institutional'),
    ('alice@unhealthy.example', 'institutional'),  # Substring false positive.
]


def fixture_sql():
    values = ',\n'.join(f'({i}, {literal(email)}, {literal(expected)})'
                        for i, (email, expected) in enumerate(CASES))
    return pipeline.render_sql(
        "SELECT i, expected, {{ email_domain_class('email') }} AS actual "
        'FROM (VALUES\n' + values + ') AS fixtures(i, email, expected) ORDER BY i')


class DomainClassTests(unittest.TestCase):
    def test_category_and_boundary_cases(self):
        rows = execute(fixture_sql())
        self.assertEqual(len(rows), len(CASES))
        for row in rows:
            self.assertEqual(row['actual'], row['expected'], CASES[row['i']])

    def test_exact_v2_macro_parity(self):
        path = pipeline.ROOT.parent / 'pii_clean_v2/macros/name_match.sql'
        legacy = jinja2.Environment().from_string(path.read_text()).module
        current = jinja2.Environment().from_string(
            (pipeline.ROOT / 'macros/email_domain_class.sql').read_text()).module
        self.assertEqual(current.email_domain_class('email'), legacy.email_domain_class('email'))

    def test_staging_normalization_before_classification(self):
        sql = pipeline.render_sql(
            "SELECT {{ email_domain_class('email') }} AS actual "
            "FROM (SELECT {{ clean_email('raw') }} AS email "
            "FROM (VALUES (' Alice@EXAMPLE.EDU ')) AS t(raw))")
        self.assertEqual(execute(sql)[0]['actual'], 'institutional')

    def test_report_uses_separate_link_and_email_denominators(self):
        evaluated = """SELECT * FROM (VALUES
            ('fixture', 'alice@gmail.com', true, 'free'),
            ('fixture', 'alice@gmail.com', true, 'free'),
            ('fixture', 'bob@example.test', true, 'custom'),
            ('fixture', 'missing-at', false, 'unknown')
        ) AS t(source, email, email_format_valid, email_domain_class)"""
        sql = pipeline.render_sql(
            (pipeline.ROOT / 'sql/email_domain_profile.sql').read_text()
        ).replace('/* EVALUATED_SQL */', evaluated)
        rows = {r['email_domain_class']: r for r in execute(sql)}
        self.assertEqual(set(rows), {'institutional', 'free', 'custom', 'unknown'})
        self.assertEqual(rows['free']['metric_rows'], 4)
        self.assertEqual(rows['free']['distinct_emails'], 3)
        self.assertEqual(rows['free']['class_metric_rows'], 2)
        self.assertEqual(rows['free']['class_distinct_emails'], 1)
        self.assertEqual(rows['free']['class_metric_rows_pct'], 50)
        self.assertAlmostEqual(rows['free']['class_distinct_emails_pct'], 100 / 3)
        self.assertEqual(rows['institutional']['class_metric_rows'], 0)
        self.assertEqual(rows['unknown']['format_invalid_metric_rows'], 1)
        self.assertTrue(all(r['mismatched_values'] == 0 for r in rows.values()))


if __name__ == '__main__':
    unittest.main()
