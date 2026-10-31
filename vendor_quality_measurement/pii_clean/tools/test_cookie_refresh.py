"""Final publication consumes real cookie output and preserves core records."""
import contextlib
import io
import unittest
from unittest.mock import Mock,patch
import pipeline as p


class CookiePublicationTests(unittest.TestCase):
    def run_publication(self,failure=None):
        writes=[];checks=0
        baseline=[{'source':s,'metric_rows':1,'duplicate_keys':0,'evidence_checksum':s} for s in p.SOURCES]
        def query(db,sql):
            nonlocal checks
            if sql.startswith('SHOW CREATE TABLE'):
                return [{'Create Table': p.PENDING_BATCH_COMMENT if failure == 'pending_batches' else 'core'}]
            if sql.startswith('DESCRIBE'):return [{'Column':'source','Type':'varchar'},{'Column':'computed_at','Type':'timestamp'}]
            if 'evidence_checksum' in sql:
                checks+=1;result=[dict(r) for r in baseline]
                if failure=='missing' and checks==1:return result[:-1]
                if failure=='changed' and checks>1:result[0]['evidence_checksum']='changed'
                return result
            if sql=='CHECK':return [{'failures':1}] if failure=='cookies' else []
            raise AssertionError(sql)
        heads = ['100', '101'] if failure == 'concurrent_before' else ['100', '100', '101'] if failure == 'concurrent_after' else ['100'] * 3
        with patch.object(p,'query',query),patch.object(p,'publication_schema',side_effect=lambda x:x), \
             patch.object(p,'current_snapshot',side_effect=heads), \
             patch.object(p,'read_model',return_value='SELECT actual_cookie_metrics'), \
             patch.object(p,'render_sql',return_value='CHECK'),patch.object(p,'explain_fragments',return_value=10), \
             patch.object(p,'run_write',side_effect=lambda sql,**kw:writes.append(sql)),contextlib.redirect_stdout(io.StringIO()):
            if failure:
                with self.assertRaises(ValueError):p.build_final(Mock())
            else:p.build_final(Mock())
        return writes

    def test_real_enrichment_publishes_after_core_validation(self):
        writes=self.run_publication()
        self.assertEqual(len(writes),2)
        self.assertTrue(writes[0].startswith('CREATE OR REPLACE VIEW'))
        self.assertTrue(writes[1].startswith('CREATE OR REPLACE TABLE'))
        self.assertFalse(any('MERGE' in sql or 'CAST(NULL' in sql for sql in writes))

    def test_missing_core_aborts_and_changed_values_are_detected(self):
        self.assertEqual(self.run_publication('missing'),[])
        self.assertEqual(self.run_publication('pending_batches'),[])
        self.assertEqual(self.run_publication('concurrent_before'),[])
        self.assertEqual(len(self.run_publication('concurrent_after')),2)
        self.assertEqual(len(self.run_publication('changed')),2)
        self.assertEqual(len(self.run_publication('cookies')),2)


if __name__=='__main__':unittest.main()
