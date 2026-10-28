"""Training entry point; direct process launch avoids cmd.exe quoting pitfalls."""
import argparse
from pathlib import Path
import sys
import traceback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--imgsz", type=int, required=True)
    parser.add_argument("--batch", type=int, required=True)
    args = parser.parse_args()
    root = Path(args.dataset).resolve()
    from ultralytics import YOLO
    YOLO(str(root / "yolov8n.pt")).train(
        data=str(root / "data.yaml"), epochs=args.epochs, imgsz=args.imgsz,
        batch=args.batch, project=str(root / "runs" / "detect"), name="train")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        if sys.platform == "win32":
            input("Training fehlgeschlagen. Enter zum Schließen ...")
        sys.exit(1)
    if sys.platform == "win32":
        input("Training beendet. Enter zum Schließen ...")
