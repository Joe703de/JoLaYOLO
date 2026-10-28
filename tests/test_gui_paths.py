import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


@unittest.skipUnless(importlib.util.find_spec('PyQt6'), 'PyQt6 required for GUI checks')
class GuiPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_config_statuses_and_windows_launcher(self):
        from PIL import Image
        from PyQt6 import QtWidgets
        import jolayolo
        with tempfile.TemporaryDirectory(prefix='Jo Lä & ') as tmp:
            root = Path(tmp) / 'dataset'
            images = root / 'images' / 'all'
            images.mkdir(parents=True)
            for i, status in enumerate(['manual', 'verified', 'pseudo', None]):
                Image.new('RGB', (32, 32), 'white').save(images / f'{i}.jpg')
                if status:
                    folder = root / 'labels' / status
                    folder.mkdir(parents=True)
                    (folder / f'{i}.txt').write_text('0 0.5 0.5 0.4 0.4\n')
            window = jolayolo.MainWindow(root, ['egg'])
            self.assertTrue((root / 'jolayolo.json').exists())
            for i, status in enumerate(['manual', 'verified', 'pseudo', 'unlabeled']):
                window.load_image(i)
                window.save_labels()
                self.assertEqual(window.image_status(images / f'{i}.jpg'), status)
            # Exercise actual GUI training wiring without launching a training job.
            with patch.object(jolayolo.sys, 'platform', 'win32'), \
                 patch.object(jolayolo.subprocess, 'CREATE_NEW_CONSOLE', 16, create=True), \
                 patch.object(jolayolo.subprocess, 'Popen') as popen, \
                 patch.object(QtWidgets.QInputDialog, 'getInt', return_value=(8, True)), \
                 patch.object(QtWidgets.QMessageBox, 'question', return_value=QtWidgets.QMessageBox.StandardButton.Yes), \
                 patch.object(QtWidgets.QMessageBox, 'information'):
                window.run_training()
                args, kwargs = popen.call_args
                self.assertEqual(kwargs, {'cwd': str(root), 'creationflags': 16})
                self.assertEqual(args[0][args[0].index('--dataset') + 1], str(root))
            window.close()

    def test_new_dataset_created_before_first_config_write(self):
        from PyQt6 import QtWidgets
        import jolayolo
        with tempfile.TemporaryDirectory() as tmp, patch.object(QtWidgets.QMessageBox, 'warning'):
            root = Path(tmp) / 'new' / 'dataset'
            window = jolayolo.MainWindow(root)
            self.assertTrue((root / 'jolayolo.json').exists())
            self.assertTrue((root / 'images' / 'all').is_dir())
            window.close()
