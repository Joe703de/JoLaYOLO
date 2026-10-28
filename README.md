# Joachim Labelt YOLO (JoLaYOLO)

Ein lokales Label- und Trainings-Tool für **YOLOv8**, gebaut mit **PyQt6**.

## Workflow

JoLaYOLO organisiert ein Dataset nach dem YOLO-Standard:

```
my_dataset/
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
5. **Exportieren**: Mit „4. TFLite exportieren“ das lokale `.pt`-Modell auswählen, Zielpfad und Bildgröße festlegen. Unter Windows läuft die Konvertierung lokal in Ubuntu/WSL2.

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
New-Item -ItemType Directory -Force ".\my_dataset\images\all"
.\venv\Scripts\python.exe jolayolo.py -d ".\my_dataset"
```

Eine Aktivierung oder Änderung der PowerShell-ExecutionPolicy ist dafür nicht nötig.

## Start

```bash
python jolayolo.py -d ./my_dataset
```

Ohne `--classes` ist die Klassenliste leer; Klassen können jederzeit in der GUI mit `c` bearbeitet werden.

### Klassen direkt übergeben

Eine Klasse:

```bash
python jolayolo.py -d ./my_dataset -c egg
```

Mehrere Klassen kommasepariert:

```bash
python jolayolo.py -d ./my_dataset -c "egg,broken_egg,dirt"
```

## Lokaler TFLite-Export unter Windows

JoLaYOLO bleibt eine Windows-Anwendung. Nur die Konvertierung läuft in **Ubuntu unter WSL2 auf demselben PC**, auf CPU; eine GPU ist nicht erforderlich. Die Dateien bleiben auf deinen Laufwerken. Es wird nichts zu GitHub oder zum Assistenten hochgeladen. Für Installation und gegebenenfalls automatische Paketdownloads wird Internet benötigt.

### Einmalige Einrichtung

1. In **PowerShell als Administrator** Ubuntu installieren:

   ```powershell
   wsl --install -d Ubuntu
   ```

   Falls Windows dazu auffordert, neu starten. Ubuntu einmal öffnen und Linux-Benutzername/Passwort anlegen. `wsl --list --verbose` sollte für `Ubuntu` Version `2` zeigen; andernfalls `wsl --set-version Ubuntu 2` ausführen.

2. Im **Ubuntu-Terminal** die separate Export-Umgebung anlegen (Ubuntu 24.04 mit Python 3.12 empfohlen):

   ```bash
   sudo apt update
   sudo apt install -y python3-venv libgl1 libglib2.0-0
   python3 -m venv ~/.venvs/jolayolo-export
   ~/.venvs/jolayolo-export/bin/python -m pip install --upgrade pip
   ```

3. Zum Windows-Checkout wechseln und Export-Pakete installieren. Beispiel: `C:\Users\Joe\JoLaYOLO` entspricht `/mnt/c/Users/Joe/JoLaYOLO`. Den Pfad an deinen Checkout anpassen, bei Leerzeichen in Anführungszeichen setzen:

   ```bash
   cd "/mnt/c/Users/Joe/JoLaYOLO"
   ~/.venvs/jolayolo-export/bin/python -m pip install -r requirements-export.txt
   ```

   Die separate Umgebung hält die Export-Pakete von deinem Windows-Training getrennt. Die Export-Version ist bewusst auf Ultralytics 8.3.203 festgelegt, das den klassischen YOLOv8-TFLite-Export unterstützt. Nicht unabhängig aktualisieren: Neuere Versionen können den Exportpfad ändern. Der hier unterstützte Modelltyp ist YOLOv8.

Der Button verwendet ausdrücklich die Distribution **Ubuntu**, deren Standardbenutzer und `~/.venvs/jolayolo-export/bin/python`. Repository, Modell und Ziel müssen für WSL erreichbar sein (normale lokale Windows-Laufwerke; keine UNC-Netzwerkpfade). JoLaYOLO muss nicht in WSL installiert oder gestartet werden.

### Exportieren

1. In JoLaYOLO **„4. TFLite exportieren“** anklicken.
2. `best.pt` wählen, normalerweise unter `<Dataset>/runs/detect/train*/weights/`.
3. Speicherort für die `.tflite`-Datei wählen. Eine vorhandene Datei wird nur nach erfolgreicher Konvertierung ersetzt; das Quellmodell bleibt unverändert.
4. Bildgröße wählen: ein Vielfaches von 32, passend zur Ziel-App. Vorgabe ist die zuletzt verwendete Trainingsgröße, sonst 640.

Ein eigenes Konsolenfenster zeigt den Fortschritt; JoLaYOLO bleibt bedienbar. Exportiert wird **Float32, Batch 1, ohne eingebautes NMS**. Die Ziel-App muss dieselbe Eingabegröße, die Klassenreihenfolge des Modells und eine eigene Nachverarbeitung/NMS verwenden. Das Modell wird nicht automatisch in ein Android-Projekt kopiert.

Bei Erfolg zeigt JoLaYOLO den tatsächlichen Dateipfad. Bei Fehlern bleibt die Windows-Konsole bis Enter offen; Details stehen in `export_error.log` neben der gewählten Ausgabedatei. Bei einem WSL-Fehler zuerst die Einrichtung oben prüfen. Die GUI muss für ihre Abschlussmeldung offen bleiben; beim Schließen läuft der gestartete Export weiter.

### Linux

Die Pakete aus `requirements-export.txt` in einer Python-3.10–3.12-Umgebung installieren und JoLaYOLO mit dieser Umgebung starten; der Button exportiert dann direkt, ohne WSL. Alternativ funktioniert der Worker ohne GUI:

```bash
python export_worker.py --model "./my_dataset/runs/detect/train/weights/best.pt" --output "./model.tflite" --imgsz 640
```

Unter Windows funktioniert derselbe Worker-Aufruf mit dem Windows-Python und leitet lokal an die oben eingerichtete WSL-Umgebung weiter.

Technischer Hintergrund: [Ultralytics-Exporter der verwendeten Version](https://github.com/ultralytics/ultralytics/blob/v8.3.203/ultralytics/engine/exporter.py), [WSL installieren](https://learn.microsoft.com/windows/wsl/install).

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
- `export_worker.py` — lokaler TFLite-Export, unter Windows über WSL2
- `requirements-export.txt` — separate Export-Abhängigkeiten (Python 3.10–3.12)
- `requirements.txt` — Python-Abhängigkeiten
- `jolayolo.json` — Einstellungen im Dataset-Ordner
- `data.yaml` — Wird vor dem Training neu generiert

## Hinweise

- **TFLite-Export:** lokal, unter Windows über Ubuntu/WSL2; Einrichtung siehe oben. Kein Upload und kein Export auf einem fremden Rechner.
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
