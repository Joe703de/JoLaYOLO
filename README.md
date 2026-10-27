# Joachim Labelt YOLO (JoLaYOLO)

Ein einfaches, lokal lauffähiges Tool zum Labeln von Bildern im **YOLO-Format**.

## Features

- Bilder aus einem Ordner laden und anzeigen
- Bounding Boxen per Maus zeichnen
- Klassen per Tastenkürzel oder Bearbeiten-Dialog wählen
- Navigation zwischen Bildern mit automatischem Speichern
- Letzte Position merken (Resume)
- Negative-Beispiele durch leere Label-Dateien
- Linke Datei-Liste mit Suchfeld und Markierung gelabelter Bilder
- Smoothes Zoomen mit dem Mausrad (bezogen auf Mausposition)
- Panning mit mittlerer Maustaste
- Boxen verschieben und in der Größe ändern
- Export im YOLO-Textformat: `<class_id> <x_center> <y_center> <width> <height>`

## Installation

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

## Start

```bash
python jolayolo.py -i /pfad/zu/bildern
```

Mit eigenen Klassen:

```bash
python jolayolo.py -i /pfad/zu/bildern -c egg,kein_ei
```

Labels werden standardmäßig im gleichen Ordner wie die Bilder abgelegt. Ein eigener Ausgabeordner ist möglich:

```bash
python jolayolo.py -i /pfad/zu/bildern -o /pfad/zu/labels
```

## Tastenkürzel

| Taste | Aktion |
|-------|--------|
| `1` – `9` | Klasse auswählen |
| `Leertaste` / `→` | Nächstes Bild (automatisch speichern) |
| `←` | Vorheriges Bild |
| `Entf` | Ausgewählte Box löschen |
| `r` | Aktuelles Bild neu laden |
| `c` | Klassen bearbeiten |
| `q` / `Esc` | Beenden und speichern |

## Mausbedienung

| Aktion | Bedeutung |
|--------|-----------|
| Linker Klick + Ziehen auf freiem Bereich | Neue Box zeichnen |
| Linker Klick auf Box | Box auswählen / verschieben |
| Rechter Klick auf Box | Box auswählen |
| Mausrad | Zoomen zur Mausposition |
| Mittlere Maustaste + Ziehen | Bild verschieben (Pan) |
| Anfasser an ausgewählter Box ziehen | Größe ändern |

## Dateien

- `jolayolo.py` — Hauptanwendung
- `requirements.txt` — Python-Abhängigkeiten
- `jolayolo.json` — Wird im Bilderordner angelegt und speichert Klassen sowie letzte Position
