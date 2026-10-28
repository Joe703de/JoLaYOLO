import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import train_worker


class WorkerCompletion(unittest.TestCase):
    def test_success_closes_and_failure_reports_before_wait(self):
        with tempfile.TemporaryDirectory(prefix="Jo Lä & ") as tmp:
            result = Path(tmp) / "result.json"
            argv = ['train_worker.py', '--dataset', tmp, '--epochs', '1',
                    '--imgsz', '32', '--batch', '1', '--result-file', str(result)]
            with patch.object(train_worker.sys, 'argv', argv), \
                 patch.object(train_worker.sys, 'platform', 'win32'), \
                 patch.object(train_worker, 'run', return_value={'success': True, 'save_dir': tmp}), \
                 patch('builtins.input') as wait:
                self.assertEqual(train_worker.main(), 0)
                wait.assert_not_called()
                self.assertTrue(json.loads(result.read_text())['success'])
            def on_wait(*args):
                self.assertEqual(json.loads(result.read_text())['error'], 'failure')
            with patch.object(train_worker.sys, 'argv', argv), \
                 patch.object(train_worker.sys, 'platform', 'win32'), \
                 patch.object(train_worker.sys.stdin, 'isatty', return_value=True), \
                 patch.object(train_worker, 'run', side_effect=RuntimeError('failure')), \
                 patch.object(train_worker.traceback, 'print_exc'), \
                 patch('builtins.input', side_effect=on_wait) as wait:
                self.assertEqual(train_worker.main(), 1)
                wait.assert_called_once()
