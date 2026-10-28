# Joachim Labelt YOLO (JoLaYOLO)

Ein lokales Label- und Trainings-Tool für **YOLOv8**, gebaut mit **PyQt6**.

## Workflow

JoLaYOLO organisiert ein Dataset nach dem YOLO-Standard:

```
egg_dataset/
├── images/
│   └── all/                    # alle Bilder
├── labels/
│   ├── manual/                 # von Hand gelabelt
│   ├── pseudo/                 # automatisch gelabelt, noch ungeprüft
│   ├── verified/               # Pseudo-Labels korrigiert / geprüft
│   ├── train/                  # vor Training neu generiert
│   └── val/                    # vor Training neu generiert
├── train.txt                   # vor Training neu generiert
├── val.txt                     # vor Training neu generiert
├── data.yaml                   # vor Training neu generiert
└── jolayolo.json               # Einstellungen
```

### Status-Farben

| Farbe | Status | Bedeutung |
|-------|--------|-----------|
| Grau | `unlabeled` | noch keine `.txt` |
| Orange | `pseudo` | automatisch gelabelt, muss geprüft werden |
| Hellblau | `manual` | von Hand gelabelt |
| Hellgrün | `verified` | Pseudo-Labels korrigiert / geprüft |

### Ablauf

1. **Bilder** in `egg_dataset/images/all/` ablegen.
2. **Auto-Label**: JoLaYOLO lädt ein `.pt`-Modell und erzeugt Pseudo-Labels in `labels/pseudo/`.
3. **Korrigieren**: Boxen anpassen, Status mit `v` auf `verified` setzen oder manuell labeln.
4. **Trainieren**: JoLaYOLO baut `train/` und `val/` neu auf und startet `yolo detect train`.
5. **Exportieren**: `.pt`-Modell an den Assistenten senden, der auf Linux nach `.tflite` exportiert.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

## Start

```bash
python jolayolo.py -d /pfad/zu/egg_dataset
```

Mit eigenen Klassen:

```bash
python jolayolo.py -d /pfad/zu/egg_dataset -c egg
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
| `v` | Aktuelles Pseudo-Bild als `verified` markieren |
| `q` / `Esc` | Beenden und speichern |

## Mausbedienung

| Aktion | Bedeutung |
|--------|-----------|
| Linker Klick + Ziehen | Neue Box zeichnen |
| Linker Klick auf Box | Box auswählen / verschieben |
| Rechter Klick auf Box | Box auswählen |
| Mausrad | Zoomen (zur Mausposition) |
| Mittlere Maustaste + Ziehen | Pan |
| Anfasser ziehen | Box in der Größe ändern |

## Dateien

- `jolayolo.py` — Hauptanwendung
- `requirements.txt` — Python-Abhängigkeiten
- `jolayolo.json` — Einstellungen im Dataset-Ordner
- `data.yaml` — Wird vor dem Training neu generiert

## Hinweise

- **TFLite-Export** funktioniert unter Windows nicht direkt. Schiebe `best.pt` ins GitHub-Repo unter `upload/best.pt` und sag dem Assistenten Bescheid.
- Vor jedem Training werden `labels/train/` und `labels/val/` automatisch geleert und neu aufgebaut.
- Negative Beispiele brauchen keine leeren `.txt`-Dateien — Bilder ohne Label-Datei gelten automatisch als Hintergrund.
