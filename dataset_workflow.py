"""Portable dataset preparation and training process arguments (no GUI imports)."""
import json
import os
from pathlib import Path
import random
import shutil
import sys


def prepare_split(dataset_dir, image_files, label_for_image, classes, val_ratio=0.2, seed=None):
    root = Path(dataset_dir).expanduser().resolve()
    usable = [(image, label_for_image(image)) for image in image_files]
    usable = [(image, label) for image, label in usable if label is not None]
    if len(usable) < 2:
        raise ValueError("Mindestens zwei manuell gelabelte oder verifizierte Bilder erforderlich.")
    if not 0 < val_ratio < 1:
        raise ValueError("val_ratio muss zwischen 0 und 1 liegen.")
    # Labels are keyed by stem, including on case-insensitive Windows filesystems.
    stems = [image.stem.casefold() for image in image_files]
    if len(stems) != len(set(stems)):
        raise ValueError("Bildnamen müssen auch ohne Dateiendung eindeutig sein (Groß-/Kleinschreibung zählt nicht).")
    prepared = {}
    for image, label in usable:
        rows = []
        for line in label.read_text(encoding="utf-8").splitlines():
            if line.strip():
                parts = line.split()
                if len(parts) not in (5, 6):
                    raise ValueError(f"Ungültiges YOLO-Label: {label}")
                # Confidence is review metadata, not part of a detection training label.
                rows.append(" ".join(parts[:5]))
        prepared[image] = "\n".join(rows) + ("\n" if rows else "")
    if not any(prepared.values()):
        raise ValueError("Keine Bounding-Boxen vorhanden; nur Hintergrundbilder reichen nicht zum Training.")
    random.Random(seed).shuffle(usable)
    cut = max(1, min(len(usable) - 1, int(len(usable) * (1 - val_ratio))))
    splits = {"train": usable[:cut], "val": usable[cut:]}
    for split, pairs in splits.items():
        # Only generated split artifacts are replaced; all/status labels stay untouched.
        for kind in ("images", "labels"):
            folder = root / kind / split
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(parents=True)
        cache = root / "labels" / f"{split}.cache"
        cache.unlink(missing_ok=True)
        lines = []
        for image, label in pairs:
            target = root / "images" / split / image.name
            try:
                os.link(image, target)
            except OSError:
                shutil.copy2(image, target)  # No symlink privileges required on Windows.
            (root / "labels" / split / f"{image.stem}.txt").write_text(prepared[image], encoding="utf-8")
            # ./ is significant: Ultralytics resolves it relative to the list file.
            lines.append(f"./images/{split}/{image.name}")
        (root / f"{split}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # JSON quoting is valid YAML and preserves spaces, Unicode, colons and backslashes.
    data = {"path": root.as_posix(), "train": "train.txt", "val": "val.txt", "nc": len(classes), "names": classes}
    (root / "data.yaml").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return [p for p, _ in splits["train"]], [p for p, _ in splits["val"]]


def training_command(dataset_dir, epochs, imgsz, batch):
    root = Path(dataset_dir).expanduser().resolve()
    # Use this environment's Python, never a potentially unrelated yolo.exe on PATH.
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return [str(executable), str(Path(__file__).with_name("train_worker.py").resolve()),
            "--dataset", str(root), "--epochs", str(epochs), "--imgsz", str(imgsz), "--batch", str(batch)]
