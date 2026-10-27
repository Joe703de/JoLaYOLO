# Joachim Labelt YOLO

1. Ordner Ansicht / Bild laden und anzeigen
- Einfache GUI, z. B. mit Python / tkinter
- Zoom, Pan
2. Bounding Boxen zeichnen
- Klick + Drag
- Boxen verschieben/vergrößern
- Boxen löschen
3. Klassen automatisch zuweisen
- Auswahl über Dropdown Menü (default für nächste Bounding Box bzw für aufgewählte Bounding Box)
- Space / Backspace
4. Export ins richtige Format
- YOLO: <class_id> <x_center> <y_center> <width> <height>
- COCO: JSON mit images, annotations, categories
5. zusätzlich
- für nächstes/voriges Bild
- Auto-Save bei Wechsel
- Last-Image-Resume
- Bilder in Ordner laden
- Negative-Beispiele markieren (leere Label-Datei)
