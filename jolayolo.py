#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JoLaYOLO — Tool zum Labeln und Trainieren von YOLO-Datasets.

Workflow:
    Bilder liegen unter images/all/.
    Labels landen je nach Status in labels/manual/, labels/pseudo/ oder labels/verified/.
    Vor dem Training werden labels/train/ und labels/val/ neu aufgebaut.

Tastenkürzel:
    1-9             Klasse wählen
    Leertaste       Nächstes Bild (speichert automatisch)
    ← / →           Vorheriges / Nächstes Bild
    Entf            Ausgewählte Box löschen
    q / Esc         Beenden
    r               Bild neu laden (ungepeicherte Änderungen gehen verloren)
    c               Klassen bearbeiten
    v               Aktuelles Bild als verified markieren (Pseudo -> verified)

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
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PyQt6 import QtCore, QtGui, QtWidgets
    from PyQt6.QtCore import Qt
except ImportError:
    print("PyQt6 ist nicht installiert. Bitte ausführen: pip install -r requirements.txt")
    sys.exit(1)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

STATUS_UNLABELED = "unlabeled"
STATUS_MANUAL = "manual"
STATUS_PSEUDO = "pseudo"
STATUS_VERIFIED = "verified"

STATUS_COLORS = {
    STATUS_UNLABELED: "#808080",   # Grau
    STATUS_MANUAL:    "#87CEEB",   # Hellblau
    STATUS_PSEUDO:    "#FFA500",   # Orange
    STATUS_VERIFIED:  "#90EE90",   # Hellgrün
}

STATUS_NAMES = {
    STATUS_UNLABELED: "Ungelabelt",
    STATUS_MANUAL:    "Manuell",
    STATUS_PSEUDO:    "Pseudo",
    STATUS_VERIFIED:  "Verifiziert",
}


class ResizableRect(QtWidgets.QGraphicsRectItem):
    HANDLE_SIZE = 10

    def __init__(self, x, y, w, h, class_id, class_name, color, source="manual", confidence=None, parent=None):
        super().__init__(x, y, w, h, parent)
        self.class_id = class_id
        self.class_name = class_name
        self.color = color
        self.source = source
        self.confidence = confidence
        self.setPen(QtGui.QPen(QtGui.QColor(color), 3))
        self.setBrush(QtGui.QBrush(Qt.BrushStyle.NoBrush))
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.handles = []
        self.label_item = None
        self._selected = False
        self._create_label()
        self._create_handles()
        self._update_handles()

    def _create_label(self):
        text = self.class_name
        if self.confidence is not None:
            text += f" {self.confidence:.2f}"
        self.label_item = QtWidgets.QGraphicsTextItem(text, self)
        self.label_item.setDefaultTextColor(QtGui.QColor(self.color))
        font = QtGui.QFont("Segoe UI", 10)
        font.setBold(True)
        self.label_item.setFont(font)
        self._update_label_pos()

    def _create_handles(self):
        for _ in range(8):
            handle = QtWidgets.QGraphicsRectItem(0, 0, self.HANDLE_SIZE, self.HANDLE_SIZE, self)
            handle.setBrush(QtGui.QBrush(QtGui.QColor(self.color)))
            handle.setPen(QtGui.QPen(QtGui.QColor("white"), 1))
            handle.setFlag(QtWidgets.QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False)
            handle.setVisible(False)
            self.handles.append(handle)

    def _update_label_pos(self):
        self.label_item.setPos(self.rect().x() + 2, self.rect().y() - 18)

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

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            self._update_handles()
            self._update_label_pos()
        return super().itemChange(change, value)

    def update_after_resize(self):
        self._update_handles()
        self._update_label_pos()

    def update_appearance(self):
        self.label_item.setPlainText(self.class_name + (f" {self.confidence:.2f}" if self.confidence is not None else ""))
        self.label_item.setDefaultTextColor(QtGui.QColor(self.color))
        self.setPen(QtGui.QPen(QtGui.QColor("white" if self._selected else self.color), 3))
        for handle in self.handles:
            handle.setBrush(QtGui.QBrush(QtGui.QColor(self.color)))
        self._update_handles()


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

            self._drawing = True
            self._draw_start = scene_pos
            self._temp_rect = QtWidgets.QGraphicsRectItem()
            self._temp_rect.setPen(QtGui.QPen(QtGui.QColor(self._parent.current_color()), 2))
            self._temp_rect.setBrush(QtGui.QBrush(Qt.BrushStyle.NoBrush))
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
    def __init__(self, dataset_dir, classes=None, config_file=None):
        super().__init__()
        self.dataset_dir = Path(dataset_dir)
        self.images_dir = self.dataset_dir / "images" / "all"
        self.labels_dir = self.dataset_dir / "labels"
        self.config_file = Path(config_file) if config_file else self.dataset_dir / "jolayolo.json"

        self.config = self.load_config()
        if classes:
            self.config["classes"] = classes
        if not self.config.get("classes"):
            self.config["classes"] = ["egg"]
            self.save_config()

        self.class_colors = self.generate_colors(len(self.config["classes"]))
        self.current_class_index = 0

        self.image_files = sorted([
            p for p in self.images_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        ]) if self.images_dir.exists() else []

        if not self.image_files:
            QtWidgets.QMessageBox.warning(self, "Hinweis",
                f"Keine Bilder in {self.images_dir} gefunden.\n"
                "Bitte lege deine Bilder unter images/all/ ab.")

        self.index = self.config.get("last_index", 0)
        if self.image_files:
            self.index = max(0, min(self.index, len(self.image_files) - 1))

        self.pixmap_item = None
        self.selected_rect = None
        self.rect_items = []

        self._verified_override = False

        self._ensure_dirs()
        self.init_ui()
        if self.image_files:
            self.load_image(self.index)

    # --- Ordnerstruktur -----------------------------------------------------

    def _ensure_dirs(self):
        for sub in ["manual", "pseudo", "verified", "train", "val"]:
            (self.labels_dir / sub).mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def _status_dirs(self):
        return {
            STATUS_MANUAL: self.labels_dir / "manual",
            STATUS_PSEUDO: self.labels_dir / "pseudo",
            STATUS_VERIFIED: self.labels_dir / "verified",
        }

    def label_path_for_status(self, image_path, status):
        if status == STATUS_UNLABELED:
            return None
        return self._status_dirs()[status] / f"{image_path.stem}.txt"

    def image_status(self, image_path):
        for status in [STATUS_VERIFIED, STATUS_MANUAL, STATUS_PSEUDO]:
            if self.label_path_for_status(image_path, status).exists():
                return status
        return STATUS_UNLABELED

    def _label_count_for_image(self, image_path, status):
        if status == STATUS_UNLABELED:
            return 0
        label_file = self.label_path_for_status(image_path, status)
        if not label_file.exists():
            return 0
        try:
            return sum(1 for line in label_file.read_text(encoding="utf-8").splitlines() if line.strip())
        except Exception:
            return 0

    def current_status(self):
        if not hasattr(self, "current_image_path"):
            return STATUS_UNLABELED
        return self.image_status(self.current_image_path)

    def current_color(self):
        return self.class_colors[self.current_class_index % len(self.class_colors)]

    # --- Config -------------------------------------------------------------

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

    # --- UI -----------------------------------------------------------------

    def init_ui(self):
        self.setWindowTitle("JoLaYOLO")
        self.resize(1500, 950)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Linke Leiste
        self.left_panel = QtWidgets.QWidget()
        self.left_panel.setFixedWidth(320)
        self.left_panel.setStyleSheet("background-color: #222;")
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)

        title = QtWidgets.QLabel("JoLaYOLO")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        left_layout.addWidget(title)

        # Statistik / Fortschritt
        self.stats_label = QtWidgets.QLabel()
        self.stats_label.setStyleSheet("color: #ccc; font-size: 12px;")
        left_layout.addWidget(self.stats_label)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #333; border-radius: 4px; }
            QProgressBar::chunk { border-radius: 4px; }
        """)
        self.progress_bar.setFixedHeight(20)
        left_layout.addWidget(self.progress_bar)

        # Workflow-Buttons
        left_layout.addSpacing(10)

        self.train_btn = QtWidgets.QPushButton("1. YOLO Training starten")
        self.train_btn.setStyleSheet("background-color: #87CEEB; color: black; font-weight: bold; padding: 8px;")
        self.train_btn.clicked.connect(self.run_training)
        left_layout.addWidget(self.train_btn)

        self.auto_label_btn = QtWidgets.QPushButton("2. Auto-Label mit best.pt")
        self.auto_label_btn.setStyleSheet("background-color: #FFA500; color: black; font-weight: bold; padding: 8px;")
        self.auto_label_btn.clicked.connect(self.run_auto_label)
        left_layout.addWidget(self.auto_label_btn)

        self.next_pseudo_btn = QtWidgets.QPushButton("3. Nächstes Pseudo-Bild")
        self.next_pseudo_btn.setStyleSheet("background-color: #FFB84D; color: black; font-weight: bold; padding: 8px;")
        self.next_pseudo_btn.clicked.connect(self.goto_next_pseudo)
        left_layout.addWidget(self.next_pseudo_btn)

        self.export_btn = QtWidgets.QPushButton("4. TFLite exportieren")
        self.export_btn.setStyleSheet("background-color: #90EE90; color: black; font-weight: bold; padding: 8px;")
        self.export_btn.clicked.connect(self.run_export)
        left_layout.addWidget(self.export_btn)

        self.verify_btn = QtWidgets.QPushButton("Aktuelles Bild verifizieren (v)")
        self.verify_btn.setStyleSheet("background-color: #666; color: white; padding: 6px;")
        self.verify_btn.clicked.connect(self.verify_current_image)
        left_layout.addWidget(self.verify_btn)

        left_layout.addSpacing(10)

        # Suchfeld
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Suchen oder Filter: @pseudo @manual @verified @unlabeled")
        self.search_edit.setStyleSheet("background-color: #333; color: white; padding: 6px;")
        self.search_edit.textChanged.connect(self.refresh_file_list)
        left_layout.addWidget(self.search_edit)

        # Dateiliste
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setStyleSheet(
            "QListWidget { background-color: #222; color: #ccc; border: none; }"
            "QListWidget::item { padding: 4px; border-radius: 3px; }"
            "QListWidget::item:selected { background-color: #444; color: white; }"
        )
        self.file_list.itemClicked.connect(self.on_file_clicked)
        left_layout.addWidget(self.file_list)

        # Status-Legende
        legend = QtWidgets.QLabel(
            "<span style='color:#808080'>&#9679;</span> Ungelabelt  "
            "<span style='color:#FFA500'>&#9679;</span> Pseudo  "
            "<span style='color:#87CEEB'>&#9679;</span> Manuell  "
            "<span style='color:#90EE90'>&#9679;</span> Verified"
        )
        legend.setStyleSheet("color: #aaa; font-size: 11px;")
        left_layout.addWidget(legend)

        layout.addWidget(self.left_panel)

        # Hauptbereich
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QtWidgets.QGraphicsScene()
        self.view = GraphicsView(self)
        self.view.setScene(self.scene)
        main_layout.addWidget(self.view)

        self.info_label = QtWidgets.QLabel()
        self.info_label.setStyleSheet("background-color: #222; color: white; padding: 8px;")
        main_layout.addWidget(self.info_label)

        layout.addWidget(main_widget, 1)

    # --- Dateiliste ---------------------------------------------------------

    def refresh_file_list(self):
        self.file_list.clear()
        raw_search = self.search_edit.text().strip().lower()
        status_filter = None
        status_tokens = {
            "@unlabeled": STATUS_UNLABELED,
            "@manual": STATUS_MANUAL,
            "@pseudo": STATUS_PSEUDO,
            "@verified": STATUS_VERIFIED,
        }
        for token, st in status_tokens.items():
            if token in raw_search:
                status_filter = st
                break
        text_search = raw_search
        for token in status_tokens:
            text_search = text_search.replace(token, "").strip()

        self.filtered_indices = []
        for i, path in enumerate(self.image_files):
            status = self.image_status(path)
            if status_filter and status != status_filter:
                continue
            if text_search and text_search not in path.name.lower():
                continue
            self.filtered_indices.append(i)

            pixmap = QtGui.QPixmap(12, 12)
            pixmap.fill(QtGui.QColor(STATUS_COLORS[status]))
            icon = QtGui.QIcon(pixmap)

            label_count = self._label_count_for_image(path, status)
            suffix = f"  ({label_count})"
            item = QtWidgets.QListWidgetItem(icon, path.name + suffix)
            item.setData(Qt.ItemDataRole.UserRole, i)
            if i == self.index:
                item.setSelected(True)
                self.file_list.setCurrentItem(item)
            self.file_list.addItem(item)
        self.update_stats()

    def on_file_clicked(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx != self.index:
            self.load_image(idx)

    def update_stats(self):
        counts = {s: 0 for s in [STATUS_UNLABELED, STATUS_MANUAL, STATUS_PSEUDO, STATUS_VERIFIED]}
        for path in self.image_files:
            counts[self.image_status(path)] += 1
        total = len(self.image_files)
        labeled = total - counts[STATUS_UNLABELED]
        percent = (labeled / total * 100) if total else 0

        self.stats_label.setText(
            f"Gesamt: {total} | Ungelabelt: {counts[STATUS_UNLABELED]} | "
            f"Manuell: {counts[STATUS_MANUAL]} | Pseudo: {counts[STATUS_PSEUDO]} | "
            f"Verified: {counts[STATUS_VERIFIED]}"
        )
        self.progress_bar.setValue(int(percent))

        if counts[STATUS_VERIFIED] > 0:
            self.progress_bar.setStyleSheet("""
                QProgressBar { background-color: #333; border-radius: 4px; }
                QProgressBar::chunk { background-color: #90EE90; border-radius: 4px; }
            """)
        elif counts[STATUS_MANUAL] > 0 or counts[STATUS_PSEUDO] > 0:
            self.progress_bar.setStyleSheet("""
                QProgressBar { background-color: #333; border-radius: 4px; }
                QProgressBar::chunk { background-color: #87CEEB; border-radius: 4px; }
            """)

    # --- Bild laden / speichern ---------------------------------------------

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

    def read_labels(self, image_path):
        status = self.image_status(image_path)
        if status == STATUS_UNLABELED:
            return

        label_file = self.label_path_for_status(image_path, status)
        if not label_file.exists():
            return

        img_w = self.pixmap.width()
        img_h = self.pixmap.height()
        source = status
        for line in label_file.read_text(encoding="utf-8").strip().splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            try:
                class_id = int(parts[0])
                cx, cy, w, h = map(float, parts[1:5])
                conf = None
                if len(parts) >= 6:
                    conf = float(parts[5])
                x1 = (cx - w / 2) * img_w
                y1 = (cy - h / 2) * img_h
                self.add_box(x1, y1, w * img_w, h * img_h, class_id=class_id, source=source, confidence=conf)
            except ValueError:
                continue

    def save_labels(self):
        if not hasattr(self, "current_image_path") or self.pixmap is None:
            return

        # Alte Label-Dateien für dieses Bild löschen
        for status in [STATUS_MANUAL, STATUS_PSEUDO, STATUS_VERIFIED]:
            lp = self.label_path_for_status(self.current_image_path, status)
            if lp.exists():
                lp.unlink()

        img_w = self.pixmap.width()
        img_h = self.pixmap.height()
        lines = []
        for rect in self.rect_items:
            r = rect.rect()
            cx = (r.x() + r.width() / 2) / img_w
            cy = (r.y() + r.height() / 2) / img_h
            w = abs(r.width()) / img_w
            h = abs(r.height()) / img_h
            line = f"{rect.class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
            if rect.confidence is not None:
                line += f" {rect.confidence:.6f}"
            lines.append(line)

        target_status = STATUS_MANUAL
        current = self.current_status()
        if current == STATUS_PSEUDO and not getattr(self, "_verified_override", False):
            target_status = STATUS_PSEUDO
        if self._verified_override:
            target_status = STATUS_VERIFIED
            self._verified_override = False

        target_dir = self._status_dirs()[target_status]
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{self.current_image_path.stem}.txt"
        target_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

    # --- Boxen -------------------------------------------------------------

    def add_box(self, x, y, w, h, class_id=None, source="manual", confidence=None):
        if class_id is None:
            class_id = self.current_class_index
        color = self.class_colors[class_id % len(self.class_colors)]
        class_name = self.config["classes"][class_id % len(self.config["classes"])]
        rect = ResizableRect(x, y, w, h, class_id, class_name, color, source=source, confidence=confidence)
        self.scene.addItem(rect)
        self.rect_items.append(rect)
        self.select_box(rect)
        # Bei manueller Änderung am Pseudo-Bild: automatisch verified setzen
        if self.current_status() == STATUS_PSEUDO:
            self._verified_override = True
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
        rect.update_after_resize()

    def on_box_changed(self):
        if self.selected_rect:
            self.selected_rect.update_after_resize()
        self.update_info()

    def set_class(self, class_index):
        if 0 <= class_index < len(self.config["classes"]):
            self.current_class_index = class_index
            if self.selected_rect:
                self.selected_rect.class_id = class_index
                self.selected_rect.class_name = self.config["classes"][class_index]
                self.selected_rect.color = self.class_colors[class_index % len(self.class_colors)]
                self.selected_rect.update_appearance()
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

    def verify_current_image(self):
        if not hasattr(self, "current_image_path"):
            return
        self._verified_override = True
        self.save_labels()
        self.load_image(self.index)

    def goto_next_pseudo(self):
        if not self.image_files:
            return
        n = len(self.image_files)
        for offset in range(1, n + 1):
            idx = (self.index + offset) % n
            if self.image_status(self.image_files[idx]) == STATUS_PSEUDO:
                self.load_image(idx)
                return
        QtWidgets.QMessageBox.information(self, "Fertig", "Keine weiteren Pseudo-Bilder vorhanden.")

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

        elif key == Qt.Key.Key_V:
            self.verify_current_image()

        elif Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            class_index = key - Qt.Key.Key_1
            self.set_class(class_index)

    def update_info(self):
        if not self.image_files:
            self.info_label.setText("Keine Bilder geladen.")
            return
        img_name = self.image_files[self.index].name
        current_class = self.config["classes"][self.current_class_index]
        status = self.image_status(self.image_files[self.index])
        selected_text = ""
        if self.selected_rect:
            selected_text = f" | Ausgewählt: {self.selected_rect.class_name}"
        self.info_label.setText(
            f"Bild {self.index + 1}/{len(self.image_files)}: {img_name}  |  "
            f"Status: {STATUS_NAMES[status]}  |  "
            f"Klasse: [{self.current_class_index + 1}] {current_class}  |  "
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

    # --- Workflow-Actions ---------------------------------------------------

    def run_auto_label(self):
        if not self.image_files:
            QtWidgets.QMessageBox.warning(self, "Fehler", "Keine Bilder geladen.")
            return

        model_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "YOLO-Modell wählen", "", "PyTorch Modelle (*.pt)"
        )
        if not model_path:
            return

        try:
            from ultralytics import YOLO
        except ImportError:
            QtWidgets.QMessageBox.critical(self, "Fehler",
                "ultralytics ist nicht installiert.\n"
                "Bitte ausführen: pip install ultralytics")
            return

        conf, ok = QtWidgets.QInputDialog.getDouble(
            self, "Confidence", "Minimale Confidence:", value=0.5, min=0.01, max=1.0, decimals=2
        )
        if not ok:
            return

        self.save_labels()
        model = YOLO(model_path)

        progress = QtWidgets.QProgressDialog("Erzeuge Pseudo-Labels...", "Abbrechen", 0, len(self.image_files), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        unlabeled_images = [p for p in self.image_files if self.image_status(p) == STATUS_UNLABELED]
        progress.setMaximum(len(unlabeled_images))

        pseudo_dir = self.labels_dir / "pseudo"
        pseudo_dir.mkdir(parents=True, exist_ok=True)

        for i, path in enumerate(unlabeled_images):
            progress.setValue(i)
            if progress.wasCanceled():
                break
            results = model.predict(source=str(path), conf=conf, verbose=False)
            result = results[0]
            lines = []
            for box in result.boxes:
                cls = int(box.cls[0])
                conf_val = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                img_w = result.orig_shape[1]
                img_h = result.orig_shape[0]
                cx = ((x1 + x2) / 2) / img_w
                cy = ((y1 + y2) / 2) / img_h
                w = abs(x2 - x1) / img_w
                h = abs(y2 - y1) / img_h
                lines.append(f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f} {conf_val:.6f}")

            label_file = pseudo_dir / f"{path.stem}.txt"
            label_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

        progress.setValue(len(unlabeled_images))
        self.refresh_file_list()
        QtWidgets.QMessageBox.information(self, "Fertig",
            f"Pseudo-Labels für {len(unlabeled_images)} Bilder erzeugt.")

    def _prepare_train_val(self, val_ratio=0.2, seed=None):
        if seed is None:
            seed = random.randint(0, 100000)
        random.seed(seed)

        train_dir = self.labels_dir / "train"
        val_dir = self.labels_dir / "val"

        for d in [train_dir, val_dir]:
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)

        usable_images = []
        for path in self.image_files:
            status = self.image_status(path)
            if status in (STATUS_MANUAL, STATUS_VERIFIED):
                usable_images.append(path)

        if not usable_images:
            return None, None, "Keine gelabelten Bilder vorhanden."

        random.shuffle(usable_images)
        split_idx = max(1, int(len(usable_images) * (1 - val_ratio)))
        train_images = usable_images[:split_idx]
        val_images = usable_images[split_idx:] or [usable_images[0]]

        train_lines = []
        val_lines = []

        for img_path in train_images:
            src = self.label_path_for_status(img_path, self.image_status(img_path))
            dst = train_dir / f"{img_path.stem}.txt"
            shutil.copy2(src, dst)
            train_lines.append(str(img_path.relative_to(self.dataset_dir)))

        for img_path in val_images:
            src = self.label_path_for_status(img_path, self.image_status(img_path))
            dst = val_dir / f"{img_path.stem}.txt"
            shutil.copy2(src, dst)
            val_lines.append(str(img_path.relative_to(self.dataset_dir)))

        (self.dataset_dir / "train.txt").write_text("\n".join(train_lines) + "\n", encoding="utf-8")
        (self.dataset_dir / "val.txt").write_text("\n".join(val_lines) + "\n", encoding="utf-8")

        nc = len(self.config["classes"])
        names = self.config["classes"]
        data_yaml = (
            f"path: .\n"
            f"train: train.txt\n"
            f"val: val.txt\n"
            f"nc: {nc}\n"
            f"names: {names}\n"
        )
        (self.dataset_dir / "data.yaml").write_text(data_yaml, encoding="utf-8")

        return train_images, val_images, None

    def run_training(self):
        self.save_labels()
        train_images, val_images, error = self._prepare_train_val()
        if error:
            QtWidgets.QMessageBox.warning(self, "Fehler", error)
            return

        base_model = "yolov8n.pt"

        epochs, ok = QtWidgets.QInputDialog.getInt(self, "Epochs", "Anzahl Epochen:", value=100, min=1, max=1000)
        if not ok:
            return
        imgsz, ok = QtWidgets.QInputDialog.getInt(self, "Bildgröße", "imgsz:", value=640, min=32, max=1280)
        if not ok:
            return
        batch, ok = QtWidgets.QInputDialog.getInt(self, "Batch", "batch:", value=8, min=1, max=64)
        if not ok:
            return

        cmd = [
            "yolo", "detect", "train",
            f"data={self.dataset_dir / 'data.yaml'}",
            f"model={base_model}",
            f"epochs={epochs}",
            f"imgsz={imgsz}",
            f"batch={batch}",
        ]

        reply = QtWidgets.QMessageBox.question(
            self, "Training starten",
            f"Training mit {len(train_images)} Train- und {len(val_images)} Val-Bildern starten?\n\n"
            f"{' '.join(cmd)}",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        try:
            if sys.platform == "win32":
                # Neues CMD-Fenster öffnen, Training darin laufen lassen
                subprocess.Popen(
                    ["cmd", "/k", "cd", str(self.dataset_dir), "&&"] + cmd,
                    shell=False,
                )
            else:
                subprocess.Popen(cmd, cwd=str(self.dataset_dir))
            QtWidgets.QMessageBox.information(self, "Gestartet",
                "Training wurde in einem neuen Terminal-Fenster gestartet.\n"
                f"Ergebnis liegt später unter {self.dataset_dir / 'runs' / 'detect'}.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"Training konnte nicht gestartet werden:\n{e}")

    def run_export(self):
        QtWidgets.QMessageBox.information(self, "TFLite Export",
            "TFLite-Export funktioniert unter Windows nicht direkt.\n\n"
            "Workflow:\n"
            "1. Kopiere best.pt aus dem Trainings-Run.\n"
            "2. Schiebe es ins GitHub-Repo unter upload/best.pt.\n"
            "3. Sag mir Bescheid — ich exportiere es auf dem Linux-Host nach "
            "app/src/main/assets/yolo_eggs.tflite und pushe es zurück.")


def main():
    parser = argparse.ArgumentParser(description="JoLaYOLO — Bilder labeln und YOLO trainieren")
    parser.add_argument("--dataset", "-d", required=True, help="Dataset-Ordner (z. B. egg_dataset)")
    parser.add_argument("--classes", "-c", help="Kommaseparierte Klassennamen, z. B. 'egg'")
    args = parser.parse_args()

    classes = [c.strip() for c in args.classes.split(",") if c.strip()] if args.classes else None

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(args.dataset, classes)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
