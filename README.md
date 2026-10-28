# Joachim Labelt YOLO (JoLaYOLO)

Ein lokales Label- und Trainings-Tool für **YOLOv8**, gebaut mit **PyQt6**.

## Workflow

JoLaYOLO organisiert ein Dataset nach dem YOLO-Standard:

```
egg_dataset/
├── images/
│   ├── all/                    # Originalbilder (bleiben unverändert)
│   ├── train/                  # vor Training generiert
│   └── val/                    # vor Training generiert
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

1. **Bilder** in `./egg_dataset/images/all/` ablegen.
2. **Auto-Label**: JoLaYOLO lädt ein `.pt`-Modell und erzeugt Pseudo-Labels in `labels/pseudo/`.
3. **Korrigieren**: Boxen anpassen, Status mit `v` auf `verified` setzen oder manuell labeln.
4. **Trainieren**: JoLaYOLO baut `train/` und `val/` neu auf und startet Ultralytics mit dem Python der aktiven Umgebung.
   Als Basismodell wird immer `yolov8n.pt` verwendet (Ultralytics lädt es beim ersten Mal herunter).
5. **Exportieren**: `.pt`-Modell an den Assistenten senden, der auf Linux nach `.tflite` exportiert.

## Auschecken

```bash
git clone https://github.com/Joe703de/JoLaYOLO.git
cd JoLaYOLO
```

## Installation

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force ".\egg_dataset\images\all"
.\venv\Scripts\python.exe jolayolo.py -d ".\egg_dataset"
```

Eine Aktivierung oder Änderung der PowerShell-ExecutionPolicy ist dafür nicht nötig.

## Start

```bash
python jolayolo.py -d ./egg_dataset
```

Mit eigenen Klassen:

```bash
python jolayolo.py -d ./egg_dataset -c egg
```

Auch ein anderer Name ist möglich, z. B. `my_dataset`:

```bash
python jolayolo.py -d ./my_dataset -c egg
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
- `dataset_workflow.py` — Split-Erzeugung und portable Prozessargumente
- `train_worker.py` — Training in einem separaten Python-Prozess
- `requirements.txt` — Python-Abhängigkeiten
- `jolayolo.json` — Einstellungen im Dataset-Ordner
- `data.yaml` — Wird vor dem Training neu generiert

## Hinweise

- **TFLite-Export** funktioniert unter Windows nicht direkt. Schiebe `best.pt` ins GitHub-Repo unter `upload/best.pt` und sag dem Assistenten Bescheid.
- Vor jedem Training werden ausschließlich die generierten Ordner `images/train`, `images/val`, `labels/train`, `labels/val`, deren Label-Caches sowie `train.txt`, `val.txt` und `data.yaml` ersetzt. Originalbilder und Status-Labels bleiben erhalten. Bilder werden per Hardlink bereitgestellt, ersatzweise kopiert (keine Windows-Symlink-Rechte nötig).
- Ultralytics ordnet `images/train/<name>` genau `labels/train/<name>.txt` zu, entsprechend für `val`. Die Listen enthalten `./images/train/...` bzw. `./images/val/...`; `data.yaml` enthält einen absoluten, sicher maskierten Dataset-Pfad. Nach Verschieben des Datasets vor dem Training neu erzeugen lassen.
- Relative `-d`-Pfade beziehen sich auf das aktuelle Arbeitsverzeichnis, nicht auf das Skriptverzeichnis. Absolute Pfade und Pfade mit Leerzeichen/Umlauten sind ebenfalls erlaubt; in der Shell immer in Anführungszeichen setzen.
- Mindestens zwei manuell gelabelte oder verifizierte Bilder werden benötigt. Train und Val überlappen nicht. Ungeprüfte Pseudo-Labels werden nicht verwendet; Confidence-Werte werden aus den Trainingskopien entfernt.
- Bildnamen müssen ohne Endung eindeutig sein, auch bei unterschiedlicher Groß-/Kleinschreibung (z. B. nicht `Foto.jpg` und `foto.png`). Bilder liegen direkt in `images/all`, nicht in Unterordnern.
- Trainingsausgabe: `<Dataset>/runs/detect/train*/weights/best.pt`. Auto-Label öffnet die Modellauswahl im Dataset-Run-Ordner. Das Basismodell liegt unter `<Dataset>/yolov8n.pt` und wird bei Bedarf heruntergeladen.
- Ein Einstellungsdialog enthält Epochen, Bildgröße und Batchgröße; die zuletzt verwendeten Werte werden gespeichert. Nach „Training starten“ folgen keine weiteren Bestätigungen. Ein zweiter Trainingsstart ist während des Trainings gesperrt.
- JoLaYOLO meldet Erfolg (mit tatsächlichem Modellpfad) oder Fehler, solange die Anwendung geöffnet bleibt. Beim Schließen läuft der unabhängige Trainingsprozess weiter, aber die Abschlussmeldung in der Oberfläche entfällt.
- Unter Windows startet ein eigenes Konsolenfenster: Bei Erfolg schließt es automatisch; bei Fehlern bleibt es bis Enter offen. Linux/macOS nutzt das bestehende Terminal. Kein `cmd /k`, `shell=True` oder `yolo.exe` aus einer fremden Umgebung.
- Für bewusst geprüfte Hintergrundbilder ein leeres Bild mit `v` verifizieren. Bilder ohne Status-Label werden nicht ins Training aufgenommen.

## Pfad-Regressionstests

```bash
python -m unittest discover -s tests -v
```

Die Tests laden erzeugte Splits mit dem echten Ultralytics-Datasetloader, einschließlich Leerzeichen/Umlauten, Confidence-Konvertierung und erneutem Split-Aufbau. Ein nativer Windows-Test muss zusätzlich auf Windows erfolgen.
