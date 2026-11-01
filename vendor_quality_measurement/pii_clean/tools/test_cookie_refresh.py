"""Source cookie batches preserve records, freeze inputs and resume safely."""
import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch

import cookie_publication as c
import pipeline as p

COVERAGE = {'cookie_location_window_days':3, 'cookie_mapping_available_days':2,
            'cookie_location_available_days':2, 'cookie_mapping_missing_days':['2026-10-30'],
            'cookie_location_missing_days':['2026-10-30'], 'cookie_location_window_status':'missing_source_days'}


def state():
    return {'core_snapshot':'100', 'evaluation_day':'2026-10-31',
            'input_snapshots':{table:'200' for table in c.INPUTS.values()}, 'coverage':dict(COVERAGE)}


class CookiePublicationTests(unittest.TestCase):
    def run_publication(self, failure=None, resume=False, replace_name_backfill=False):
        writes = []
        rendered = []
        baseline = [{'source':s, 'metric_rows':1, 'duplicate_keys':0, 'evidence_checksum':s} for s in p.SOURCES]
        stored = [dict(baseline[0])] if resume else []
        head = '500'
        committed = 0
        def query(db, sql):
            if sql.startswith('SHOW CREATE TABLE'):
                if p.relation(p.CORE_MODEL) in sql:
                    return [{'Create Table':p.PENDING_BATCH_COMMENT if failure == 'pending_core' else 'core'}]
                comment = ('pii_clean: name evidence batches core=100 final=500' if failure == 'pending_names'
                           else c.PREFIX+json.dumps(state()) if resume else 'complete')
                return [{'Create Table':"COMMENT '"+comment+"'"}]
            if sql.startswith('DESCRIBE'):
                return [{'Column':'source','Type':'varchar'}, {'Column':'computed_at','Type':'timestamp'}]
            if 'evidence_checksum' in sql:
                if p.relation(p.CORE_MODEL) in sql:
                    return baseline[:-1] if failure == 'missing_core' else baseline
                rows = [dict(row) for row in stored]
                if "WHERE source IN ('" in sql:
                    source = sql.split("WHERE source IN ('")[1].split("'")[0]
                    rows = [r for r in rows if r['source'] == source]
                if failure == 'corrupt' and rows:
                    rows[0]['evidence_checksum'] = 'changed'
                return rows
            if sql == 'COVERAGE':return [dict(COVERAGE)]
            if sql == 'CHECK':return [{'failure':1}] if failure == 'cookie_integrity' else []
            raise AssertionError(sql)
        def snapshot(db, table):
            if table == p.relation(p.FINAL_MODEL):return head
            if table == p.relation(p.CORE_MODEL):
                return '101' if failure == 'concurrent_core' and committed else '100'
            return '200'
        def write(sql, **kwargs):
            nonlocal head, committed, stored
            writes.append(sql)
            if sql.startswith(('CREATE OR REPLACE TABLE', 'INSERT INTO')):
                if failure == 'uncommitted':raise RuntimeError('HIVE_WRITER_CLOSE_ERROR')
                source = sql.rsplit('COOKIE ', 1)[1]
                if sql.startswith('CREATE OR REPLACE TABLE'):stored = []
                stored.append(next(dict(r) for r in baseline if r['source'] == source))
                committed += 1
                head = str(500+committed)
                if failure == 'lost_ack':raise RuntimeError('HIVE_WRITER_CLOSE_ERROR')
        def render_model(name, **kwargs):
            rendered.append(kwargs)
            return 'COOKIE ' + ','.join(kwargs['variables']['cookie_sources'])
        with patch.object(p, 'query', query), patch.object(p, 'publication_schema', side_effect=lambda x:x), \
             patch.object(p, 'current_snapshot', snapshot), patch.object(p, 'read_model', side_effect=render_model), \
             patch.object(p, 'render_sql', side_effect=lambda sql,*a,**k:'COVERAGE' if sql=='{{ cookie_source_coverage() }}' else 'CHECK'), \
             patch.object(p, 'explain_fragments', return_value=25), patch.object(p, 'run_write', side_effect=write), \
             patch.object(c.time, 'sleep'), \
             contextlib.redirect_stdout(io.StringIO()):
            if failure and failure != 'lost_ack' and not (failure == 'pending_names' and replace_name_backfill):
                with self.assertRaises((ValueError, RuntimeError)):p.build_final(Mock(), replace_name_backfill=replace_name_backfill)
            else:p.build_final(Mock(), replace_name_backfill=replace_name_backfill)
        return writes, rendered, stored

    def test_enriches_each_source_before_combining_final_rows(self):
        writes, rendered, stored = self.run_publication()
        self.assertEqual(len(writes), 9)
        self.assertTrue(writes[0].startswith('CREATE OR REPLACE TABLE'))
        self.assertIn(c.PREFIX, writes[0])
        self.assertTrue(all(sql.startswith('INSERT INTO') for sql in writes[1:7]))
        self.assertTrue(writes[7].startswith('CREATE OR REPLACE VIEW'))
        self.assertIn('verified complete', writes[8])
        self.assertEqual([r['variables']['cookie_sources'] for r in rendered[:-1]], [[s] for s in p.SOURCES])
        self.assertEqual(len(stored), 7)
        for kwargs in rendered:
            self.assertEqual(set(kwargs['source_overrides'].values()), {table+' FOR VERSION AS OF 200' for table in c.INPUTS.values()})
            self.assertEqual(kwargs['ref_overrides'][p.CORE_MODEL], p.relation(p.CORE_MODEL)+' FOR VERSION AS OF 100')
            self.assertIn("DATE '2026-10-30'", kwargs['variables']['cookie_coverage_relation'])

    def test_resume_keeps_only_verified_complete_sources(self):
        writes, rendered, stored = self.run_publication(resume=True)
        self.assertEqual(len(writes), 8)
        self.assertTrue(all(sql.startswith('INSERT INTO') for sql in writes[:6]))
        self.assertNotIn([p.SOURCES[0]], [r['variables']['cookie_sources'] for r in rendered[:-1]])
        self.assertEqual(len(stored), 7)
        self.assertEqual(self.run_publication('corrupt', resume=True)[0], [])
        self.assertEqual(self.run_publication('cookie_integrity', resume=True)[0], [])

    def test_lost_acknowledgement_does_not_duplicate_records(self):
        writes, _, stored = self.run_publication('lost_ack')
        self.assertEqual(len(stored), 7)
        self.assertEqual(len(writes), 9)

    def test_rejects_incomplete_inputs_and_detects_bad_publication(self):
        for failure in ('missing_core', 'pending_core', 'pending_names'):
            self.assertEqual(self.run_publication(failure)[0], [], failure)
        for failure in ('uncommitted', 'corrupt', 'cookie_integrity', 'concurrent_core'):
            writes, _, _ = self.run_publication(failure)
            self.assertEqual(len(writes), 6 if failure == 'uncommitted' else 1, failure)
            self.assertFalse(any('verified complete' in sql for sql in writes))

    def test_explicit_switch_replaces_name_backfill_atomically(self):
        writes, _, stored = self.run_publication('pending_names', replace_name_backfill=True)
        self.assertEqual(len(stored), 7)
        self.assertIn(c.PREFIX, writes[0])
        self.assertFalse(any(sql.startswith('COMMENT') for sql in writes[:-1]))

    def test_checkpoint_preserves_inputs_and_rejects_bad_metadata(self):
        expected = state()
        self.assertEqual(c.checkpoint("COMMENT '"+c.PREFIX+json.dumps(expected)+"'"), expected)
        self.assertIsNone(c.checkpoint("COMMENT 'verified complete'"))
        for changed in ({**expected, 'core_snapshot':'bad'}, {**expected, 'input_snapshots':{}},
                        {**expected, 'evaluation_day':'bad'}):
            with self.assertRaises(ValueError):c.checkpoint("COMMENT '"+c.PREFIX+json.dumps(changed)+"'")
        with self.assertRaises(ValueError):c.coverage_sql({**COVERAGE, 'cookie_location_window_status':"bad'"})


if __name__ == '__main__':unittest.main()
