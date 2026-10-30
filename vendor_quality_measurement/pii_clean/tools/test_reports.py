"""Published reports preserve vendor scope without executing metric views."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import sqlglot
from sqlglot import exp

import pipeline as p
from test_models import execute


class PublishedReportTests(unittest.TestCase):
    def test_profiles_read_published_rows_and_preserve_source_scope(self):
        profiles = sorted((p.ROOT / 'sql').glob('*profile.sql'))
        self.assertEqual(len(profiles), 16)
        for path in profiles:
            for source in (None, 'endato'):
                with self.subTest(profile=path.name, source=source):
                    sql = p.render_profile(path.name, source)
                    self.assertNotIn('EVALUATED_SQL', sql)
                    self.assertNotIn('EVIDENCE_SQL', sql)
                    self.assertNotIn('{{', sql)
                    tables = sqlglot.parse_one(sql, read='trino').find_all(exp.Table)
                    physical = {'.'.join(part.name for part in t.parts) for t in tables if t.catalog}
                    self.assertEqual(physical, {p.relation(p.FINAL_MODEL)})
        fixture = """(SELECT *, DATE '2020-01-01' AS first_seen_day, DATE '2020-01-02' AS last_seen_day FROM (VALUES
            ('endato', 'alice@example.test', true),
            ('endato', 'alice@example.test', true),
            ('healthlink', 'bad-email', false)
        ) AS records(source, email, email_format_valid))"""
        sql = p.render_profile('email_format_profile.sql', 'endato').replace(p.relation(p.FINAL_MODEL), fixture)
        rows = execute(sql)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source'], 'endato')
        self.assertEqual(rows[0]['metric_rows'], 2)
        self.assertEqual(rows[0]['distinct_emails'], 1)
        self.assertEqual(rows[0]['invalid_metric_rows'], 0)
        with self.assertRaisesRegex(ValueError, 'Unknown source'):
            p.render_profile('profile.sql', "endato' OR true")

    def test_all_report_handlers_use_published_relation_and_record_vendor(self):
        calls = [
            (p.report, {}), (p.report_role, {}), (p.report_domain, {}), (p.report_names, {}),
            (p.report_linkage, {}), (p.report_linkage, {'metric': 'has_conflict_linkage'}),
            (p.report_name_consistency, {}), (p.report_conflicting_names, {}),
            (p.report_conflicting_names, {'state': True}),
            (p.report_conflicting_names, {'facility': True}),
            (p.report_conflicting_names, {'specialty': True}), (p.report_registry_status, {}),
            (p.report_location, {'metric': 'vendor_state_evidence'}),
            (p.report_location, {'metric': 'cookie_location_status'}),
            (p.report_location, {'metric': 'link_freshness'}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sql').symlink_to(p.ROOT / 'sql', target_is_directory=True)
            with patch.object(p, 'ROOT', root), patch.object(p, 'query', return_value=[]) as query, \
                    contextlib.redirect_stdout(io.StringIO()):
                for source in p.SOURCES:
                    for report, kwargs in calls:
                        with self.subTest(source=source, report=report.__name__, kwargs=kwargs):
                            report(Mock(), source, **kwargs)
                            sql = query.call_args.args[1]
                            self.assertIn(f"FROM {p.relation(p.FINAL_MODEL)} WHERE source = '{source}'", sql)
                            self.assertNotIn('pii__int_', sql)
                self.assertEqual(query.call_count, len(calls) * len(p.SOURCES))
            artifacts = list((root / 'results').glob('*.json'))
            self.assertEqual(len(artifacts), len(calls) * len(p.SOURCES))
            for path in artifacts:
                data = json.loads(path.read_text())
                self.assertEqual(data['relation'], p.relation(p.FINAL_MODEL))
                self.assertIn(data['source'], p.SOURCES)


if __name__ == '__main__':
    unittest.main()
