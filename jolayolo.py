# -*- coding: utf-8 -*-
"""
JoLaYOLO — ein einfaches Tool zum Labeln von Bildern im YOLO-Format.

Tastenkürzel:
    1-9             Klasse wählen
    Leertaste       Nächstes Bild (speichert automatisch)
    ← / →           Vorheriges / Nächstes Bild
    Entf / d        Ausgewählte Box löschen
    q / Esc         Beenden
    r               Bild neu laden (ungepeicherte Änderungen gehen verloren)
    c               Klassen bearbeiten

Mausbefehle:
    Linker Klick + Ziehen       Box zeichnen
    Linker Klick auf Box        Box auswählen / verschieben
    Rechter Klick auf Box       Box auswählen
    Mausrad                     Zoomen (bezogen auf Mausposition)
    Mittlere Maustaste + Ziehen  Bild verschieben (Pan)
    Anfasser ziehen             Box in der Größe ändern
"""

import argparse
import json
import sys
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt


class ResizableRect(QtWidgets.QGraphicsRectItem):
    HANDLE_SIZE = 10

    def __init__(self, x, y, w, h, class_id, class_name, color, parent=None):
        super().__init__(x, y, w, h, parent)
        self.class_id = class_id
        self.class_name = class_name
        self.color = color
        self.setPen(QtGui.QPen(QtGui.QColor(color), 3))
        self.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.handles = []
        self.label_item = None
        self._create_label()
        self._create_handles()
        self._update_handles()
        self._selected = False

    def _create_label(self):
        self.label_item = QtWidgets.QGraphicsTextItem(self.class_name, self)
        self.label_item.setDefaultTextColor(QtGui.QColor(self.color))
        font = QtGui.QFont("Segoe UI", 10)
        font.setBold(True)
        self.label_item.setFont(font)
        self.label_item.setPos(self.rect().x() + 2, self.rect().y() - 18)

    def _create_handles(self):
        for _ in range(8):
            handle = QtWidgets.QGraphicsRectItem(0, 0, self.HANDLE_SIZE, self.HANDLE_SIZE, self)
            handle.setBrush(QtGui.QBrush(QtGui.QColor(self.color)))
            handle.setPen(QtGui.QPen(QtGui.QColor("white"), 1))
            handle.setFlag(QtWidgets.QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False)
            handle.setVisible(False)
            self.handles.append(handle)

    def _update_handles(self):
        r = self.rect()
        cx = r.x() + r.width() / 2
        cy = r.y() + r.height() / 2
        positions = [
            (r.x(), r.y()),
            (cx, r.y()),
            (r.x() + r.width(), r.y()),
            (r.x() + r.width(), cy),
            (r.x() + r.width(), r.y() + r.height()),
            (cx, r.y() + r.height()),
            (r.x(), r.y() + r.height()),
            (r.x(), cy),
        ]
        hs = self.HANDLE_SIZE / 2
        for handle, (px, py) in zip(self.handles, positions):
            handle.setRect(px - hs, py - hs, self.HANDLE_SIZE, self.HANDLE_SIZE)

    def set_selected(self, selected):
        self._selected = selected
        if selected:
            self.setPen(QtGui.QPen(QtGui.QColor("white"), 3, Qt.PenStyle.DashLine))
        else:
            self.setPen(QtGui.QPen(QtGui.QColor(self.color), 3))
        for handle in self.handles:
            handle.setVisible(selected)
        self._update_handles()

    def update_geometry(self):
        self._update_handles()
        if self.label_item:
            self.label_item.setPos(self.rect().x() + 2, self.rect().y() - 18)

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            self._update_handles()
            self.label_item.setPos(self.rect().x() + value.x() + 2, self.rect().y() + value.y() - 18)
        return super().itemChange(change, value)


class GraphicsView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        self.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing | QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#111")))
        self._panning = False
        self._last_mouse_pos = None
        self._drawing = False
        self._draw_start = None
        self._temp_rect = None
        self._resizing = False
        self._resize_handle = None
        self._resize_item = None
        self._resize_start_rect = None
        self._resize_start_pos = None

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 0.87
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        scene_pos = self.mapToScene(event.pos())
        item = self.scene().itemAt(scene_pos, self.transform())

        if event.button() == Qt.MouseButton.RightButton:
            if isinstance(item, ResizableRect):
                self._parent.select_box(item)
            else:
                self._parent.deselect_all()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # Prüfe Anfasser
            handle_info = self._parent.handle_at(scene_pos)
            if handle_info:
                rect, handle_name = handle_info
                self._resizing = True
                self._resize_handle = handle_name
                self._resize_item = rect
                self._resize_start_rect = QtCore.QRectF(rect.rect())
                self._resize_start_pos = scene_pos
                self._parent.select_box(rect)
                return

            if isinstance(item, ResizableRect):
                self._parent.select_box(item)
                super().mousePressEvent(event)
                return

            # Neue Box zeichnen
            self._drawing = True
            self._draw_start = scene_pos
            self._temp_rect = QtWidgets.QGraphicsRectItem()
            self._temp_rect.setPen(QtGui.QPen(QtGui.QColor(self._parent.current_color()), 2))
            self._temp_rect.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
            self._temp_rect.setRect(QtCore.QRectF(scene_pos, scene_pos))
            self.scene().addItem(self._temp_rect)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return

        scene_pos = self.mapToScene(event.pos())

        if self._resizing and self._resize_item:
            self._parent.resize_box(self._resize_item, self._resize_handle,
                                    self._resize_start_rect, self._resize_start_pos, scene_pos)
            return

        if self._drawing and self._temp_rect:
            r = QtCore.QRectF(self._draw_start, scene_pos).normalized()
            self._temp_rect.setRect(r)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if self._resizing:
            self._resizing = False
            self._resize_handle = None
            self._resize_item = None
            self._resize_start_rect = None
            self._resize_start_pos = None
            self._parent.on_box_changed()
            return

        if self._drawing and self._temp_rect:
            r = self._temp_rect.rect().normalized()
            if r.width() > 5 and r.height() > 5:
                self._parent.add_box(r.x(), r.y(), r.width(), r.height())
            self.scene().removeItem(self._temp_rect)
            self._temp_rect = None
            self._drawing = False
            return

        super().mouseReleaseEvent(event)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, image_dir, output_dir=None, classes=None, config_file=None):
        super().__init__()
        self.image_dir = Path(image_dir)
        self.output_dir = Path(output_dir) if output_dir else self.image_dir
        self.config_file = Path(config_file) if config_file else self.image_dir / "jolayolo.json"

        self.config = self.load_config()
        if classes:
            self.config["classes"] = classes
        if not self.config.get("classes"):
            self.config["classes"] = ["egg"]
            self.save_config()

        self.class_colors = self.generate_colors(len(self.config["classes"]))
        self.current_class_index = 0

        self.image_files = sorted([
            p for p in self.image_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        ])
        if not self.image_files:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"Keine Bilder in {self.image_dir} gefunden.")
            sys.exit(1)

        self.index = self.config.get("last_index", 0)
        self.index = max(0, min(self.index, len(self.image_files) - 1))

        self.pixmap_item = None
        self.selected_rect = None
        self.rect_items = []

        self.init_ui()
        self.load_image(self.index)

    def init_ui(self):
        self.setWindowTitle("JoLaYOLO")
        self.resize(1400, 900)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Linke Leiste
        self.file_dock = QtWidgets.QWidget()
        self.file_dock.setFixedWidth(280)
        self.file_dock.setStyleSheet("background-color: #222;")
        file_layout = QtWidgets.QVBoxLayout(self.file_dock)
        file_layout.setContentsMargins(8, 8, 8, 8)

        label = QtWidgets.QLabel("Bilder")
        label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        file_layout.addWidget(label)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Suchen...")
        self.search_edit.setStyleSheet("background-color: #333; color: white;")
        self.search_edit.textChanged.connect(self.refresh_file_list)
        file_layout.addWidget(self.search_edit)

        self.file_list = QtWidgets.QListWidget()
        self.file_list.setStyleSheet(
            "QListWidget { background-color: #222; color: #ccc; border: none; }"
            "QListWidget::item:selected { background-color: #444; color: white; }"
        )
        self.file_list.itemClicked.connect(self.on_file_clicked)
        file_layout.addWidget(self.file_list)

        layout.addWidget(self.file_dock)

        # Hauptbereich
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QtWidgets.QGraphicsScene()
        self.view = GraphicsView(self)
        self.view.setScene(self.scene)
        main_layout.addWidget(self.view)

        self.info_label = QtWidgets.QLabel()
        self.info_label.setStyleSheet("background-color: #222; color: white; padding: 6px;")
        main_layout.addWidget(self.info_label)

        layout.addWidget(main_widget, 1)

    def current_color(self):
        return self.class_colors[self.current_class_index % len(self.class_colors)]

    def load_config(self):
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Konfiguration konnte nicht geladen werden: {e}")
        return {"classes": []}

    def save_config(self):
        try:
            self.config_file.write_text(
                json.dumps(self.config, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"Konfiguration konnte nicht gespeichert werden: {e}")

    def refresh_file_list(self):
        self.file_list.clear()
        search = self.search_edit.text().lower()
        self.filtered_indices = []
        for i, path in enumerate(self.image_files):
            if search and search not in path.name.lower():
                continue
            self.filtered_indices.append(i)
            item = QtWidgets.QListWidgetItem(self.file_list_label(path))
            item.setData(Qt.ItemDataRole.UserRole, i)
            if i == self.index:
                item.setSelected(True)
                self.file_list.setCurrentItem(item)
            self.file_list.addItem(item)

    def file_list_label(self, path):
        has_label = self.label_path(path).exists()
        marker = "● " if has_label else "○ "
        return marker + path.name

    def on_file_clicked(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx != self.index:
            self.load_image(idx)

    def load_image(self, index):
        self.save_labels()
        self.index = index
        self.config["last_index"] = self.index
        self.save_config()

        self.scene.clear()
        self.rect_items.clear()
        self.selected_rect = None
        self.pixmap_item = None

        path = self.image_files[self.index]
        self.current_image_path = path
        self.pixmap = QtGui.QPixmap(str(path))
        self.pixmap_item = QtWidgets.QGraphicsPixmapItem(self.pixmap)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())

        self.read_labels(path)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.refresh_file_list()
        self.update_info()

    def label_path(self, image_path):
        return self.output_dir / f"{image_path.stem}.txt"

    def read_labels(self, image_path):
        label_file = self.label_path(image_path)
        if not label_file.exists():
            return

        img_w = self.pixmap.width()
        img_h = self.pixmap.height()
        for line in label_file.read_text(encoding="utf-8").strip().splitlines():
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            try:
                class_id = int(parts[0])
                cx, cy, w, h = map(float, parts[1:])
                x1 = (cx - w / 2) * img_w
                y1 = (cy - h / 2) * img_h
                x2 = (cx + w / 2) * img_w
                y2 = (cy + h / 2) * img_h
                self.add_box(x1, y1, x2 - x1, y2 - y1, class_id)
            except ValueError:
                continue

    def save_labels(self):
        if not hasattr(self, "current_image_path") or self.pixmap is None:
            return

        img_w = self.pixmap.width()
        img_h = self.pixmap.height()
        lines = []
        for rect in self.rect_items:
            r = rect.rect()
            cx = (r.x() + r.width() / 2) / img_w
            cy = (r.y() + r.height() / 2) / img_h
            w = abs(r.width()) / img_w
            h = abs(r.height()) / img_h
            lines.append(f"{rect.class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.label_path(self.current_image_path).write_text(
            "\n".join(lines) + "\n" if lines else "", encoding="utf-8"
        )

    def add_box(self, x, y, w, h, class_id=None):
        if class_id is None:
            class_id = self.current_class_index
        color = self.class_colors[class_id % len(self.class_colors)]
        class_name = self.config["classes"][class_id % len(self.config["classes"])]
        rect = ResizableRect(x, y, w, h, class_id, class_name, color)
        self.scene.addItem(rect)
        self.rect_items.append(rect)
        self.select_box(rect)
        return rect

    def select_box(self, rect):
        if self.selected_rect:
            self.selected_rect.set_selected(False)
        self.selected_rect = rect
        rect.set_selected(True)
        self.update_info()

    def deselect_all(self):
        if self.selected_rect:
            self.selected_rect.set_selected(False)
        self.selected_rect = None
        self.update_info()

    def delete_selected(self):
        if self.selected_rect and self.selected_rect in self.rect_items:
            self.scene.removeItem(self.selected_rect)
            self.rect_items.remove(self.selected_rect)
            self.selected_rect = None
            self.update_info()

    def handle_at(self, scene_pos):
        if self.selected_rect is None:
            return None
        hs = ResizableRect.HANDLE_SIZE / 2 / self.view.transform().m11()
        r = self.selected_rect.rect()
        cx = r.x() + r.width() / 2
        cy = r.y() + r.height() / 2
        positions = {
            "nw": (r.x(), r.y()),
            "n": (cx, r.y()),
            "ne": (r.x() + r.width(), r.y()),
            "e": (r.x() + r.width(), cy),
            "se": (r.x() + r.width(), r.y() + r.height()),
            "s": (cx, r.y() + r.height()),
            "sw": (r.x(), r.y() + r.height()),
            "w": (r.x(), cy),
        }
        for name, (px, py) in positions.items():
            if abs(scene_pos.x() - px) <= hs and abs(scene_pos.y() - py) <= hs:
                return self.selected_rect, name
        return None

    def resize_box(self, rect, handle, start_rect, start_pos, current_pos):
        dx = current_pos.x() - start_pos.x()
        dy = current_pos.y() - start_pos.y()
        x1, y1, x2, y2 = start_rect.x(), start_rect.y(), start_rect.x() + start_rect.width(), start_rect.y() + start_rect.height()

        if "w" in handle:
            x1 += dx
        if "e" in handle:
            x2 += dx
        if "n" in handle:
            y1 += dy
        if "s" in handle:
            y2 += dy

        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])
        rect.setRect(x1, y1, x2 - x1, y2 - y1)
        rect.update_geometry()

    def on_box_changed(self):
        if self.selected_rect:
            self.selected_rect.update_geometry()
        self.update_info()

    def set_class(self, class_index):
        if 0 <= class_index < len(self.config["classes"]):
            self.current_class_index = class_index
            if self.selected_rect:
                self.selected_rect.class_id = class_index
                self.selected_rect.class_name = self.config["classes"][class_index]
                self.selected_rect.color = self.class_colors[class_index % len(self.class_colors)]
                self.selected_rect.setPen(QtGui.QPen(QtGui.QColor("white" if self.selected_rect._selected else self.selected_rect.color), 3))
                self.selected_rect._create_label()
                self.selected_rect._update_handles()
            self.update_info()

    def edit_classes(self):
        text, ok = QtWidgets.QInputDialog.getText(
            self, "Klassen bearbeiten", "Kommaseparierte Klassennamen:",
            text=",".join(self.config["classes"])
        )
        if ok and text:
            self.config["classes"] = [c.strip() for c in text.split(",") if c.strip()]
            self.class_colors = self.generate_colors(len(self.config["classes"]))
            self.current_class_index = min(self.current_class_index, len(self.config["classes"]) - 1)
            self.save_config()
            self.load_image(self.index)

    def next_image(self):
        if self.index < len(self.image_files) - 1:
            self.load_image(self.index + 1)

    def prev_image(self):
        if self.index > 0:
            self.load_image(self.index - 1)

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key.Key_Q or key == Qt.Key.Key_Escape:
            self.save_labels()
            self.close()

        elif key == Qt.Key.Key_Space or key == Qt.Key.Key_Right:
            self.next_image()

        elif key == Qt.Key.Key_Left:
            self.prev_image()

        elif key == Qt.Key.Key_Delete:
            self.delete_selected()

        elif key == Qt.Key.Key_R:
            self.load_image(self.index)

        elif key == Qt.Key.Key_C:
            self.edit_classes()

        elif Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            class_index = key - Qt.Key.Key_1
            self.set_class(class_index)

    def update_info(self):
        img_name = self.image_files[self.index].name
        current_class = self.config["classes"][self.current_class_index]
        selected_text = ""
        if self.selected_rect:
            selected_text = f" | Ausgewählt: {self.selected_rect.class_name}"
        self.info_label.setText(
            f"Bild {self.index + 1}/{len(self.image_files)}: {img_name}  |  "
            f"Aktuelle Klasse: [{self.current_class_index + 1}] {current_class}  |  "
            f"Boxen: {len(self.rect_items)}{selected_text}"
        )
        self.setWindowTitle(f"JoLaYOLO — {img_name} ({self.index + 1}/{len(self.image_files)})")

    @staticmethod
    def generate_colors(n):
        palette = [
            "#ff595e", "#ffca3a", "#8ac926", "#1982c4", "#6a4c93",
            "#f3722c", "#43aa8b", "#577590", "#f94144", "#90be6d",
        ]
        return palette * ((n // len(palette)) + 1)


def main():
    parser = argparse.ArgumentParser(description="JoLaYOLO — Bilder im YOLO-Format labeln")
    parser.add_argument("--images", "-i", required=True, help="Ordner mit Bildern")
    parser.add_argument("--output", "-o", help="Ordner für Label-Dateien (Standard: gleicher Ordner wie Bilder)")
    parser.add_argument("--classes", "-c", help="Kommaseparierte Klassennamen, z. B. 'egg,kein_ei'")
    args = parser.parse_args()

    classes = [c.strip() for c in args.classes.split(",")] if args.classes else None

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(args.images, args.output, classes)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
