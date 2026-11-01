"""Evidence-only publication preserves old values and uses exact record keys."""
import unittest
from unittest.mock import Mock, patch
import publish_name_evidence as b
from test_models import execute


class NameEvidencePublicationTests(unittest.TestCase):
    def test_retries_reduce_writer_pressure_within_configured_limit(self):
        self.assertEqual([b.batch_writer_count(4, attempt) for attempt in range(6)], [4, 4, 2, 2, 1, 1])
        self.assertEqual([b.batch_writer_count(1, attempt) for attempt in range(6)], [1] * 6)

    def test_final_projection_preserves_cookies_dates_and_duplicate_email_records(self):
        old = "(SELECT * FROM (VALUES ('a','1','same@test','2020-01-01',7), ('a','2','same@test','2021-02-03',9), ('b','1','same@test','2022-04-05',11)) AS t(source,metric_row_id,email,computed_at,cookie_count))"
        new = "(SELECT *, ARRAY[metric_row_id] AS name_match_evidence, ARRAY[source] AS vendor_registry_match_classes, '2026-10-31' AS name_match_evaluated_at, 'v1' AS name_match_definition_version FROM " + old + ')'
        columns = ['source','metric_row_id','email','computed_at','cookie_count',*b.FIELDS]
        rows = execute(b.final_select(old, new, columns))
        before = {(r['source'],r['metric_row_id']): r for r in execute('SELECT * FROM ' + old)}
        self.assertEqual(len(rows),3)
        for row in rows:
            self.assertEqual({c:row[c] for c in columns if c not in b.FIELDS},before[(row['source'],row['metric_row_id'])])
            self.assertEqual(row['vendor_registry_match_classes'],[row['source']])
            self.assertEqual(row['name_match_evidence'],[row['metric_row_id']])

    def test_core_projection_keeps_original_booleans(self):
        old = "(SELECT 'a' AS source, '1' AS metric_row_id, false AS vendor_name_matches_registry_name)"
        names = "SELECT CAST(ROW('a','1') AS row(source varchar,row_id varchar)) AS metric_row_id, true AS vendor_name_matches_registry_name, ARRAY['first_only'] AS vendor_registry_match_classes"
        row = execute(b.core_select(old,names,['source','metric_row_id','vendor_name_matches_registry_name','vendor_registry_match_classes']))[0]
        self.assertFalse(row['vendor_name_matches_registry_name'])
        self.assertEqual(row['vendor_registry_match_classes'],['first_only'])

    def test_preservation_rejects_changed_values_or_keys(self):
        rows = [{'source':s,'records':1,'duplicate_keys':0,'checksum':s} for s in sorted(b.p.SOURCES)]
        b.require_population(rows)
        b.require_same(rows,rows,'checksum')
        for change in ({'records':2},{'duplicate_keys':1},{'checksum':'changed'}):
            changed=[{**r,**change} if i==0 else r for i,r in enumerate(rows)]
            with self.assertRaises(ValueError):b.require_same(rows,changed,'checksum')
        with self.assertRaises(ValueError):b.require_population(rows[:-1])

    def test_email_batches_are_disjoint_and_keep_all_email_records(self):
        old = "(SELECT * FROM (VALUES ('a','1','same@test',7), ('a','2','same@test',9), ('b','1','else@test',11)) AS t(source,metric_row_id,email,cookie_count))"
        new = "(SELECT *, ARRAY[metric_row_id] AS name_match_evidence FROM " + old + ')'
        columns = ['source','metric_row_id','email','cookie_count','name_match_evidence']
        expected = execute(b.final_select(old,new,columns))
        collected = []
        locations = {}
        for batch in b.HEX:
            rows = execute(b.final_select(b.batch_relation(old,batch),b.batch_relation(new,batch),columns))
            collected.extend(rows)
            for row in rows:
                locations.setdefault(row['email'],set()).add(batch)
        keyed = lambda rows: sorted(rows,key=lambda r:(r['source'],r['metric_row_id']))
        self.assertEqual(keyed(collected),keyed(expected))
        self.assertTrue(all(len(v)==1 for v in locations.values()))
        with self.assertRaises(ValueError):b.batch_relation(old,"A'")

    def test_resume_requires_complete_matching_bucket_checksums(self):
        final = [{'source':'healthlink','batch':batch,'records':2,'duplicate_keys':0,'old_final':'f'+batch} for batch in '01']
        core = [{**r,'full_core':'c'+r['batch']} for r in final]
        self.assertEqual(b.verified_batches(core[:1],final,core),{'0'})
        for change in ({'records':1},{'duplicate_keys':1},{'old_final':'changed'},{'full_core':'changed'},{'batch':'F'}):
            with self.assertRaises(ValueError):
                b.verified_batches([{**core[0],**change}],final,core)

    def test_partial_marker_keeps_original_input_snapshots(self):
        self.assertEqual(b.partial_pins("COMMENT '"+b.PARTIAL+" core=3003 final=881'"),('3003','881'))
        self.assertIsNone(b.partial_pins("COMMENT 'pii_clean: stored name evidence verified complete'"))
        with self.assertRaises(ValueError):b.partial_pins(b.PARTIAL+' core=broken final=881')

    def run_recovery(self, outcomes):
        columns = ['source', 'metric_row_id', *b.FIELDS]
        baseline = [{'source':'healthlink', 'batch':'0', 'records':2,
                     'duplicate_keys':0, 'old_final':'f0', 'full_core':'c0'}]
        state = {'head':'old', 'rows':[], 'started':False}
        calls = []
        def query(db, sql):
            if sql.startswith('DESCRIBE '):
                return [{'Column':c} for c in (columns if state['started'] else columns[:2])]
            return state['rows']
        def write(sql, phase):
            calls.append(sql)
            outcome = outcomes[len(calls)-1]
            if outcome in ('committed', 'committed_error', 'corrupt'):
                state.update(head='new', started=True, rows=[dict(baseline[0])])
            if outcome == 'corrupt':
                state['rows'][0]['records'] = 1
            if outcome in ('empty_error', 'committed_error'):
                raise RuntimeError('HIVE_WRITER_CLOSE_ERROR')
        guard = Mock()
        with patch.object(b, 'HEX', '0'), patch.object(b.p, 'query', side_effect=query), \
                patch.object(b.p, 'current_snapshot', side_effect=lambda *_:state['head']), \
                patch.object(b, 'emit'), patch.object(b.time, 'sleep') as sleep:
            result = b.publish_batches(None, 'final', 'old_final', 'new_core', columns,
                columns, columns[:2], baseline, baseline, False,
                b.PARTIAL+' core=1 final=2', write, guard)
        return result, calls, sleep.call_count

    def test_commit_with_lost_acknowledgement_is_not_written_twice(self):
        snapshot, calls, sleeps = self.run_recovery(['committed_error'])
        self.assertEqual(snapshot, 'new')
        self.assertEqual(len(calls), 1)
        self.assertIn("COMMENT '"+b.PARTIAL+' core=1 final=2', calls[0])
        self.assertEqual(sleeps, 0)

    def test_uncommitted_retry_preserves_atomic_input_marker(self):
        snapshot, calls, sleeps = self.run_recovery(['empty_error', 'committed'])
        self.assertEqual(snapshot, 'new')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(sleeps, 1)

    def test_partial_committed_batch_stops_instead_of_retrying(self):
        with self.assertRaisesRegex(ValueError, 'Stored values, keys or counts changed'):
            self.run_recovery(['corrupt'])


if __name__ == '__main__':
    unittest.main()
