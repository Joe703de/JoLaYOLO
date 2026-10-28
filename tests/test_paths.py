import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from dataset_workflow import prepare_split, training_command


class PathTests(unittest.TestCase):
    def test_real_ultralytics_loader_and_rebuild(self):
        from ultralytics.data.utils import check_det_dataset, img2label_paths
        from ultralytics.data.dataset import YOLODataset
        with tempfile.TemporaryDirectory(prefix="Jo Lä & (dataset) ") as tmp:
            root = Path(tmp) / "egg dataset"
            images = root / "images" / "all"
            labels = root / "labels" / "verified"
            images.mkdir(parents=True)
            labels.mkdir(parents=True)
            files = []
            for i in range(5):
                image = images / f"Bild ä {i}.jpg"
                Image.new("RGB", (32, 32), "white").save(image)
                (labels / f"{image.stem}.txt").write_text("0 0.5 0.5 0.4 0.4 0.98\n", encoding="utf-8")
                files.append(image)
            lookup = lambda p: labels / f"{p.stem}.txt"
            for seed in (1, 2):
                train, val = prepare_split(root, files, lookup, ["Ei: 'weiß'"], seed=seed)
                self.assertFalse(set(train) & set(val))
                self.assertEqual(len(train) + len(val), 5)
                data = check_det_dataset(str(root / "data.yaml"), autodownload=False)
                for split in ("train", "val"):
                    dataset = YOLODataset(img_path=data[split], data=data, imgsz=32, augment=False)
                    self.assertEqual(len(dataset), 4 if split == "train" else 1)
                    for entry in dataset.labels:
                        self.assertEqual(len(entry["cls"]), 1)
                    for label in img2label_paths(dataset.im_files):
                        self.assertTrue(Path(label).exists())
                        self.assertEqual(len(Path(label).read_text().split()), 5)
            self.assertTrue(all(p.exists() for p in files))
            self.assertTrue(all(len(lookup(p).read_text().split()) == 6 for p in files))

    def test_small_dataset_and_duplicate_stems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            label = root / 'a.txt'
            label.write_text('0 0.5 0.5 0.4 0.4')
            with self.assertRaisesRegex(ValueError, 'zwei'):
                prepare_split(root, [root / 'a.jpg'], lambda p: label, ['egg'])
            with self.assertRaisesRegex(ValueError, 'eindeutig'):
                prepare_split(root, [root / 'A.jpg', root / 'a.png'], lambda p: label, ['egg'])

    def test_process_argv_not_shell(self):
        with tempfile.TemporaryDirectory(prefix='Pfad ä & space ') as tmp:
            command = training_command(tmp, 3, 640, 8)
            self.assertEqual(command[0], sys.executable)
            self.assertEqual(command[command.index('--dataset') + 1], str(Path(tmp).resolve()))
            result = subprocess.run(command[:2] + ['--help'], capture_output=True)
            self.assertEqual(result.returncode, 0)
        # Windows serialization keeps an entire path as one argument; no cmd /k.
        command = ['C:\\User Name\\venv\\Scripts\\python.exe', 'C:\\My App\\train_worker.py', '--dataset', 'D:\\Bilder ä & Eier']
        self.assertIn('"D:\\Bilder ä & Eier"', subprocess.list2cmdline(command))


if __name__ == '__main__':
    unittest.main()
