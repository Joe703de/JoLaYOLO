import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6 import QtWidgets
import jolayolo


class ExportGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_cancel_start_success_failure_and_retry(self):
        from PIL import Image
        with tempfile.TemporaryDirectory(prefix='Jo Lä & ') as tmp:
            root = Path(tmp)
            images = root / 'images' / 'all'
            images.mkdir(parents=True)
            Image.new('RGB', (32, 32)).save(images / '1.jpg')
            window = jolayolo.MainWindow(root, ['object'])
            with patch.object(QtWidgets.QFileDialog, 'getOpenFileName', return_value=('', '')), patch.object(jolayolo.subprocess, 'Popen') as popen:
                window.run_export()
                popen.assert_not_called()
            with patch.object(QtWidgets.QFileDialog, 'getOpenFileName', return_value=(str(root / 'best.pt'), '')), patch.object(
                    QtWidgets.QFileDialog, 'getSaveFileName', return_value=(str(root / 'out.tflite'), '')), patch.object(
                    QtWidgets.QInputDialog, 'getInt', return_value=(320, True)), patch.object(
                    jolayolo.sys, 'platform', 'win32'), patch.object(
                    jolayolo.subprocess, 'CREATE_NEW_CONSOLE', 16, create=True), patch.object(
                    jolayolo.subprocess, 'Popen') as popen:
                window.run_export()
                self.assertFalse(window.export_btn.isEnabled())
                self.assertEqual(popen.call_args.kwargs, {'cwd': str(root), 'creationflags': 16})
                self.assertIn(str(root / 'best.pt'), popen.call_args.args[0])
                popen.return_value.poll.return_value = None
                with patch.object(QtWidgets.QMessageBox, 'information') as info:
                    window._check_export()
                    info.assert_not_called()
                    report = window.export_result_file
                    report.write_text(json.dumps({'success': True, 'output': str(root / 'out.tflite')}))
                    window._check_export()
                    self.assertIn(str(root / 'out.tflite'), info.call_args.args[2])
                    self.assertFalse(report.exists())
                    self.assertTrue(window.export_btn.isEnabled())
                window.run_export()
                popen.return_value.poll.return_value = 2
                with patch.object(QtWidgets.QMessageBox, 'critical') as error:
                    window._check_export()
                    self.assertIn('Exit-Code 2', error.call_args.args[2])
                    self.assertTrue(window.export_btn.isEnabled())
            window.close()
