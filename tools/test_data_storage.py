"""Storage policy rejects dumps and embedded outputs, while preserving code inputs."""
import json
import unittest

from check_data_storage import problem


class StoragePolicyTests(unittest.TestCase):
    def test_exports_and_compressed_temporary_files_are_rejected(self):
        for path in ('sample.csv', 'sample.csv.gz', 'dump.parquet.tmp', 'state.partial.duckdb',
                     'run.duckdb.wal', 'result.jsonl', 'outputs/measurement.json', 'results/debug.txt'):
            self.assertIsNotNone(problem(path), path)

    def test_reference_code_and_configuration_are_preserved(self):
        for path in ('models/record_schemas.json', 'seeds/nicknames.csv', 'sql/examples/07.sql',
                     'docs/metrics/07.md', 'profiles/vendor.json'):
            self.assertIsNone(problem(path), path)

    def test_notebook_checks_embedded_results_and_execution_state(self):
        clean = {'cells': [{'cell_type': 'code', 'outputs': [], 'execution_count': None}]}
        self.assertIsNone(problem('analysis.ipynb', json.dumps(clean)))
        for field, value in [('outputs', [{'output_type': 'stream', 'text': ['synthetic']}]),
                             ('execution_count', 1), ('attachments', {'fixture': {}})]:
            cell = {**clean['cells'][0], field: value}
            self.assertIsNotNone(problem('analysis.ipynb', json.dumps({'cells': [cell]})))

    def test_staged_notebook_uses_index_content(self):
        from unittest.mock import patch
        from check_data_storage import check_staged
        output = json.dumps({'cells': [{'outputs': [{'text': ['synthetic']}]}]}).encode()
        with patch('check_data_storage.subprocess.check_output', side_effect=[b'analysis.ipynb\0', output]) as read:
            self.assertEqual(list(check_staged()), [('analysis.ipynb',
                             'notebook output, attachment, widget state, or execution count')])
            self.assertEqual(read.call_args.args[0], ['git', 'show', ':analysis.ipynb'])

    def test_replay_refuses_storage_before_creating_run_directory(self):
        import sys
        from pathlib import Path
        from unittest.mock import patch
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nscreen-replay'))
        from replay.runner import Replay
        with patch.object(Path, 'mkdir') as mkdir:
            with self.assertRaisesRegex(ValueError, 'Explicit allow_local_results=True'):
                Replay('synthetic', '/unused', warehouse=object())
            mkdir.assert_not_called()


if __name__ == '__main__':
    unittest.main()
