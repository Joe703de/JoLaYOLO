"""Training entry point; direct process launch avoids cmd.exe quoting pitfalls."""
import argparse
import io
import json
import os
from pathlib import Path
import sys
import traceback


def run(args):
    root = Path(args.dataset).resolve()
    from ultralytics import YOLO
    model = YOLO(str(root / "yolov8n.pt"))
    model.train(data=str(root / "data.yaml"), epochs=args.epochs, imgsz=args.imgsz,
                batch=args.batch, project=str(root / "runs" / "detect"), name="train")
    return {"success": True, "save_dir": str(Path(model.trainer.save_dir).resolve())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--imgsz", type=int, required=True)
    parser.add_argument("--batch", type=int, required=True)
    parser.add_argument("--result-file")
    args = parser.parse_args()

    # Capture stderr so the GUI can show the real traceback even if the console vanishes.
    stderr_buffer = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = stderr_buffer

    result = {"success": False, "error": "Unbekannter Fehler."}
    try:
        result = run(args)
    except (Exception, KeyboardInterrupt) as exc:
        traceback.print_exc()
        result = {"success": False, "error": str(exc) or "Training abgebrochen."}
    finally:
        sys.stderr = original_stderr

    captured = stderr_buffer.getvalue()
    if captured:
        result["stderr"] = captured
        # Also write a persistent log inside the dataset folder.
        log_path = Path(args.dataset).resolve() / "training_error.log"
        try:
            log_path.write_text(captured, encoding="utf-8")
        except Exception:
            pass

    if args.result_file:
        target = Path(args.result_file)
        pending = target.with_suffix(".tmp")
        pending.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        pending.replace(target)

    # Keep console open on Windows only on errors so the user can inspect output.
    if sys.platform == "win32" and sys.stdin.isatty() and not result["success"]:
        try:
            input("Training fehlgeschlagen. Enter zum Schließen ...")
        except (EOFError, KeyboardInterrupt):
            pass

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
