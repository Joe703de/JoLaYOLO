# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
JoLaYOLO — ein einfaches Tool zum Labeln von Bildern im YOLO-Format.

Tastenkürzel:
    1-9             Klasse wählen
    Leertaste       Nächstes Bild (speichert automatisch)
    ← / →           Vorheriges / Nächstes Bild
    Entf / d        Ausgewählte Box löschen
    q / Esc         Beenden
    + / -           Zoomen
    r               Bild neu laden (ungepeicherte Änderungen gehen verloren)

Mausbefehle:
    Linker Klick + Ziehen     Box zeichnen
    Rechter Klick auf Box     Box auswählen / löschen (siehe Taste d)
"""

import argparse
import json
import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog

from PIL import Image, ImageTk


class YoloLabeler:
    def __init__(self, image_dir, output_dir=None, classes=None, config_file=None):
        self.image_dir = Path(image_dir)
        self.output_dir = Path(output_dir) if output_dir else self.image_dir
        self.config_file = Path(config_file) if config_file else self.image_dir / "jolayolo.json"

        # Konfiguration laden oder Standard verwenden
        self.config = self.load_config()
        if classes:
            self.config["classes"] = classes
        if not self.config.get("classes"):
            self.config["classes"] = ["egg"]
            self.save_config()

        self.class_colors = self.generate_colors(len(self.config["classes"]))
        self.current_class = 0

        # Bilder sammeln
        self.image_files = sorted([
            p for p in self.image_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        ])
        if not self.image_files:
            print(f"Keine Bilder in {self.image_dir} gefunden.")
            sys.exit(1)

        self.index = self.config.get("last_index", 0)
        self.index = max(0, min(self.index, len(self.image_files) - 1))

        # GUI
        self.root = tk.Tk()
        self.root.title("JoLaYOLO")
        self.root.geometry("1200x800")
        self.root.configure(bg="#222")

        self.canvas = tk.Canvas(self.root, bg="#111", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.info_label = tk.Label(
            self.root,
            text="",
            bg="#222",
            fg="#fff",
            font=("Segoe UI", 12),
            anchor="w",
        )
        self.info_label.pack(fill=tk.X, side=tk.BOTTOM)

        self.bind_events()

        # Zustand
        self.photo = None
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.boxes = []  # Liste von (class_id, x1, y1, x2, y2) in Bildkoordinaten
        self.selected_box = None
        self.start_x = None
        self.start_y = None
        self.temp_rect = None

        self.load_image(self.index)
        self.root.mainloop()

    # --- Konfiguration -----------------------------------------------------

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

    # --- Bilder laden ------------------------------------------------------

    def load_image(self, index):
        self.save_labels()
        self.index = index
        self.config["last_index"] = self.index
        self.save_config()

        path = self.image_files[self.index]
        self.original = Image.open(path).convert("RGB")
        self.boxes = self.read_labels(path)
        self.selected_box = None

        self.fit_image()
        self.draw()
        self.update_info()

    def fit_image(self):
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w < 100 or canvas_h < 100:
            canvas_w, canvas_h = 1000, 700

        img_w, img_h = self.original.size
        scale_x = canvas_w / img_w
        scale_y = canvas_h / img_h
        self.scale = min(scale_x, scale_y, 1.0)

        self.offset_x = (canvas_w - img_w * self.scale) / 2
        self.offset_y = (canvas_h - img_h * self.scale) / 2

    # --- Label lesen / schreiben --------------------------------------------

    def label_path(self, image_path):
        stem = image_path.stem
        return self.output_dir / f"{stem}.txt"

    def read_labels(self, image_path):
        label_file = self.label_path(image_path)
        boxes = []
        if not label_file.exists():
            return boxes

        img_w, img_h = self.original.size
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
                boxes.append((class_id, x1, y1, x2, y2))
            except ValueError:
                continue
        return boxes

    def save_labels(self):
        if not hasattr(self, "original") or self.original is None:
            return

        img_w, img_h = self.original.size
        label_file = self.label_path(self.image_files[self.index])
        lines = []
        for class_id, x1, y1, x2, y2 in self.boxes:
            cx = ((x1 + x2) / 2) / img_w
            cy = ((y1 + y2) / 2) / img_h
            w = abs(x2 - x1) / img_w
            h = abs(y2 - y1) / img_h
            lines.append(f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        if lines:
            label_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            if label_file.exists():
                label_file.write_text("", encoding="utf-8")

    # --- Zeichnen ----------------------------------------------------------

    def draw(self):
        self.canvas.delete("all")

        img_w, img_h = self.original.size
        resized = self.original.resize(
            (int(img_w * self.scale), int(img_h * self.scale)), Image.Resampling.LANCZOS
        )
        self.photo = ImageTk.PhotoImage(resized)
        self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.photo)

        for i, (class_id, x1, y1, x2, y2) in enumerate(self.boxes):
            sx1 = x1 * self.scale + self.offset_x
            sy1 = y1 * self.scale + self.offset_y
            sx2 = x2 * self.scale + self.offset_x
            sy2 = y2 * self.scale + self.offset_y
            color = self.class_colors[class_id % len(self.class_colors)]
            rect = self.canvas.create_rectangle(
                sx1, sy1, sx2, sy2, outline=color, width=3, tags=f"box_{i}"
            )
            label_text = self.config["classes"][class_id % len(self.config["classes"])]
            self.canvas.create_text(
                sx1 + 2, sy1 - 8, text=label_text, anchor=tk.SW,
                fill=color, font=("Segoe UI", 10, "bold"),
            )
            if self.selected_box == i:
                self.canvas.itemconfig(rect, outline="#fff")
                self.canvas.create_rectangle(
                    sx1 - 2, sy1 - 2, sx2 + 2, sy2 + 2, outline="#fff", width=1,
                    dash=(4, 2),
                )

    def update_info(self):
        img_name = self.image_files[self.index].name
        current_class = self.config["classes"][self.current_class]
        self.info_label.config(
            text=f"Bild {self.index + 1}/{len(self.image_files)}: {img_name}  |  "
                 f"Aktuelle Klasse: [{self.current_class + 1}] {current_class}  |  "
                 f"Boxen: {len(self.boxes)}"
        )
        self.root.title(f"JoLaYOLO — {img_name} ({self.index + 1}/{len(self.image_files)})")

    # --- Events ------------------------------------------------------------

    def bind_events(self):
        self.root.bind("<Key>", self.on_key)
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        if self.original:
            self.fit_image()
            self.draw()

    def on_mouse_down(self, event):
        x = (event.x - self.offset_x) / self.scale
        y = (event.y - self.offset_y) / self.scale
        self.start_x = x
        self.start_y = y

        # Prüfen, ob auf eine bestehende Box geklickt wurde
        clicked = self.box_at(x, y)
        if clicked is not None:
            self.selected_box = clicked
            self.draw()
            self.update_info()
            self.start_x = None
            self.start_y = None
            return

        self.temp_rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline=self.class_colors[self.current_class], width=2
        )

    def on_mouse_move(self, event):
        if self.temp_rect and self.start_x is not None:
            self.canvas.coords(self.temp_rect, self.to_canvas(self.start_x, self.start_y) + (event.x, event.y))

    def on_mouse_up(self, event):
        if self.temp_rect is None or self.start_x is None:
            return

        x = (event.x - self.offset_x) / self.scale
        y = (event.y - self.offset_y) / self.scale

        x1, x2 = sorted([self.start_x, x])
        y1, y2 = sorted([self.start_y, y])

        if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
            self.boxes.append((self.current_class, x1, y1, x2, y2))

        self.canvas.delete(self.temp_rect)
        self.temp_rect = None
        self.start_x = None
        self.start_y = None
        self.draw()
        self.update_info()

    def on_right_click(self, event):
        x = (event.x - self.offset_x) / self.scale
        y = (event.y - self.offset_y) / self.scale
        clicked = self.box_at(x, y)
        if clicked is not None:
            self.selected_box = clicked
            self.draw()
            self.update_info()

    def box_at(self, x, y):
        for i in range(len(self.boxes) - 1, -1, -1):
            class_id, x1, y1, x2, y2 = self.boxes[i]
            if x1 <= x <= x2 and y1 <= y <= y2:
                return i
        return None

    def to_canvas(self, x, y):
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    # --- Tastatur ----------------------------------------------------------

    def on_key(self, event):
        key = event.keysym

        if key in ("q", "Escape"):
            self.save_labels()
            self.root.destroy()

        elif key in ("Right", "space"):
            self.next_image()

        elif key == "Left":
            self.prev_image()

        elif key in ("Delete", "d"):
            if self.selected_box is not None:
                del self.boxes[self.selected_box]
                self.selected_box = None
                self.draw()
                self.update_info()

        elif key == "r":
            self.load_image(self.index)

        elif key == "plus" or key == "KP_Add":
            self.scale *= 1.2
            self.draw()

        elif key == "minus" or key == "KP_Subtract":
            self.scale /= 1.2
            self.draw()

        elif key.isdigit():
            num = int(key)
            if 1 <= num <= len(self.config["classes"]):
                self.current_class = num - 1
                if self.selected_box is not None:
                    old = self.boxes[self.selected_box]
                    self.boxes[self.selected_box] = (self.current_class, old[1], old[2], old[3], old[4])
                    self.draw()
                self.update_info()

        elif key == "c":
            self.edit_classes()

    def next_image(self):
        if self.index < len(self.image_files) - 1:
            self.load_image(self.index + 1)

    def prev_image(self):
        if self.index > 0:
            self.load_image(self.index - 1)

    def edit_classes(self):
        text = simpledialog.askstring(
            "Klassen bearbeiten",
            "Kommaseparierte Klassennamen:",
            initialvalue=",".join(self.config["classes"]),
        )
        if text:
            self.config["classes"] = [c.strip() for c in text.split(",") if c.strip()]
            self.class_colors = self.generate_colors(len(self.config["classes"]))
            self.current_class = min(self.current_class, len(self.config["classes"]) - 1)
            self.save_config()
            self.draw()
            self.update_info()

    # --- Hilfsmethoden -----------------------------------------------------

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

    YoloLabeler(args.images, args.output, classes)


if __name__ == "__main__":
    main()
