import argparse
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, Mock

import export_worker


class LocalExport(unittest.TestCase):
    def test_local_export_preserves_source_and_uses_exact_result(self):
        with tempfile.TemporaryDirectory(prefix='Jo Lä & ') as tmp:
            root = Path(tmp)
            model = root / 'best.pt'
            model.write_bytes(b'original')
            output = root / 'result.tflite'
            output.write_bytes(b'old output')
            def convert(**kw):
                self.assertEqual(kw['format'], 'tflite')
                self.assertFalse(kw['nms'])
                self.assertEqual(kw['device'], 'cpu')
                result = root / 'exported.tflite'
                result.write_bytes(b'converted')
                return str(result)
            yolo = Mock()
            yolo.return_value.export.side_effect = convert
            args = argparse.Namespace(model=str(model), output=str(output), imgsz=320)
            with patch.object(export_worker.sys, 'platform', 'linux'), patch.dict(
                    sys.modules, {'ultralytics': types.SimpleNamespace(YOLO=yolo)}):
                self.assertEqual(export_worker.run(args), str(output))
            self.assertEqual(model.read_bytes(), b'original')
            self.assertEqual(output.read_bytes(), b'converted')
            self.assertNotEqual(yolo.call_args.args[0], str(model))

    def test_failed_conversion_keeps_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / 'best.pt'
            model.write_bytes(b'original')
            output = root / 'result.tflite'
            output.write_bytes(b'previous valid model')
            yolo = Mock()
            yolo.return_value.export.side_effect = RuntimeError('converter failed')
            args = argparse.Namespace(model=str(model), output=str(output), imgsz=320)
            with patch.object(export_worker.sys, 'platform', 'linux'), patch.dict(
                    sys.modules, {'ultralytics': types.SimpleNamespace(YOLO=yolo)}):
                with self.assertRaisesRegex(RuntimeError, 'converter failed'):
                    export_worker.run(args)
            self.assertEqual(output.read_bytes(), b'previous valid model')
            self.assertEqual(model.read_bytes(), b'original')

    def test_windows_wsl_arguments_and_output_check(self):
        with tempfile.TemporaryDirectory(prefix='Jo Lä & ') as tmp:
            root = Path(tmp)
            model = root / 'best.pt'
            model.touch()
            output = root / 'out.tflite'
            args = argparse.Namespace(model=str(model), output=str(output), imgsz=640)
            with patch.object(export_worker.sys, 'platform', 'win32'), patch.object(
                    export_worker, 'wsl_path', side_effect=['/mnt/c/Jo Lä &/export_worker.py', '/mnt/c/best.pt', '/mnt/c/out.tflite']), patch.object(
                    export_worker.subprocess, 'check_output', return_value='/home/joe\n'), patch.object(
                    export_worker.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'fehlt'):
                    export_worker.run(args)
                cmd = run.call_args.args[0]
                self.assertEqual(cmd[:5], ['wsl.exe', '-d', 'Ubuntu', '--exec', '/home/joe/.venvs/jolayolo-export/bin/python'])
                self.assertEqual(cmd[5], '/mnt/c/Jo Lä &/export_worker.py')
                self.assertEqual(run.call_args.kwargs, {'check': True})

    def test_failure_writes_report_and_log_without_replacing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'out.tflite'
            output.write_bytes(b'keep')
            report = root / 'result.json'
            argv = ['export_worker', '--model', str(root / 'missing.pt'), '--output', str(output), '--result-file', str(report)]
            with patch.object(sys, 'argv', argv), patch.object(sys, 'platform', 'linux'):
                self.assertEqual(export_worker.main(), 1)
            self.assertFalse(json.loads(report.read_text())['success'])
            self.assertIn('FileNotFoundError', (root / 'export_error.log').read_text())
            self.assertEqual(output.read_bytes(), b'keep')
