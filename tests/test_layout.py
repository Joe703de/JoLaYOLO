import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from PyQt6 import QtWidgets, QtGui
import jolayolo


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_status_pixels_cover_full_width_without_gaps(self):
        bar = jolayolo.DatasetStatusBar()
        for counts in ({'manual': 3, 'verified': 7},
                       {'manual': 1, 'verified': 2, 'pseudo': 3, 'unlabeled': 4},
                       {'verified': 1}, {}):
            bar.set_counts(counts)
            for width in (137, 300, 511):
                bar.resize(width, 20)
                bar.show()
                self.app.processEvents()
                image = bar.grab().toImage()
                expected = []
                left = cumulative = 0
                total = sum(counts.values())
                for status in bar.order:
                    cumulative += counts.get(status, 0)
                    right = round(width * cumulative / total) if total else width
                    expected.extend([jolayolo.STATUS_COLORS[status]] * (right - left))
                    left = right
                    if not total:
                        expected = [jolayolo.STATUS_COLORS['unlabeled']] * width
                        break
                for y in (0, 10, 19):
                    self.assertEqual([image.pixelColor(x, y).name().lower() for x in range(width)],
                                     [color.lower() for color in expected])
        bar.close()

    def test_file_rows_use_content_height_and_touch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = root / 'images/all'
            images.mkdir(parents=True)
            image = QtGui.QImage(32, 32, QtGui.QImage.Format.Format_RGB32)
            image.fill(0xffffff)
            for i in range(12):
                image.save(str(images / f'PXL_20261028_123456789_{i:02}.jpg'))
                status = 'manual' if i < 6 else 'verified'
                labels = root / 'labels' / status
                labels.mkdir(parents=True, exist_ok=True)
                (labels / f'PXL_20261028_123456789_{i:02}.txt').write_text('0 0.5 0.5 0.4 0.4\n')
            window = jolayolo.MainWindow(root)
            window.show()
            self.app.processEvents()
            listing = window.file_list
            # Test both the default font and larger fonts (DPI/accessibility).
            for point_size in (10, 14):
                font = listing.font()
                font.setPointSize(point_size)
                listing.setFont(font)
                listing.doItemsLayout()
                self.app.processEvents()
                expected = max(listing.fontMetrics().height(), listing.iconSize().height()) + 2
                rects = [listing.visualItemRect(listing.item(i)) for i in range(4)]
                self.assertEqual([r.height() for r in rects], [expected] * 4)
                for first, second in zip(rects, rects[1:]):
                    self.assertEqual(first.bottom() + 1, second.top())
                self.assertEqual(listing.iconSize().width(), 10)
            window.grab().save('/tmp/jolayolo-layout-after.png')
            window.close()
