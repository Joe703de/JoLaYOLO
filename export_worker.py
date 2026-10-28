"""Local TFLite export, using Ubuntu/WSL on Windows (no remote service)."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback


def wsl_path(path):
    return subprocess.check_output(
        ['wsl.exe', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', '-u', str(Path(path).resolve())],
        text=True, encoding='utf-8').strip()


def run(args):
    model_path = Path(args.model).resolve()
    output = Path(args.output).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f'Modell nicht gefunden: {model_path}')
    if model_path == output:
        raise ValueError('Ausgabe darf das Quellmodell nicht ersetzen.')
    if sys.platform == 'win32':
        # No shell interpolation: even spaces, umlauts and & remain plain arguments.
        script = wsl_path(Path(__file__))
        model = wsl_path(model_path)
        target = wsl_path(output)
        home = subprocess.check_output(
            ['wsl.exe', '-d', 'Ubuntu', '--exec', 'printenv', 'HOME'],
            text=True, encoding='utf-8').strip()
        python = home + '/.venvs/jolayolo-export/bin/python'
        subprocess.run(['wsl.exe', '-d', 'Ubuntu', '--exec', python, script,
                        '--model', model, '--output', target, '--imgsz', str(args.imgsz)], check=True)
        if not output.is_file():
            raise RuntimeError('WSL meldet Erfolg, aber die TFLite-Datei fehlt.')
        return str(output)

    from ultralytics import YOLO
    output.parent.mkdir(parents=True, exist_ok=True)
    # Export a private copy, so best.pt and previous SavedModel exports remain untouched.
    with tempfile.TemporaryDirectory(prefix='jolayolo-export-') as tmp:
        source = Path(tmp) / 'model.pt'
        shutil.copy2(model_path, source)
        exported = Path(YOLO(str(source)).export(
            format='tflite', imgsz=args.imgsz, batch=1, device='cpu',
            half=False, int8=False, nms=False))
        if not exported.is_file() or exported.suffix != '.tflite':
            raise RuntimeError(f'Keine TFLite-Datei erzeugt: {exported}')
        # Stage in destination filesystem before atomically replacing the chosen output.
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.tmp', delete=False) as staged:
            pending = Path(staged.name)
        try:
            shutil.copy2(exported, pending)
            pending.replace(output)
        finally:
            pending.unlink(missing_ok=True)
    return str(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--result-file')
    args = parser.parse_args()
    result = {'success': False}
    try:
        if args.imgsz < 32 or args.imgsz % 32:
            raise ValueError('Bildgröße muss ein positives Vielfaches von 32 sein.')
        result = {'success': True, 'output': run(args)}
    except (Exception, KeyboardInterrupt) as exc:
        details = traceback.format_exc()
        print(details, file=sys.stderr, flush=True)
        log = Path(args.output).resolve().parent / 'export_error.log'
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open('a', encoding='utf-8') as handle:
                handle.write(details + '\n')
        except OSError:
            pass
        result = {'success': False, 'error': str(exc) or 'Export abgebrochen.', 'stderr': details}
    if args.result_file:
        target = Path(args.result_file)
        pending = target.with_suffix('.tmp')
        pending.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        pending.replace(target)
    if sys.platform == 'win32' and not result['success'] and sys.stdin.isatty():
        try:
            input('Export fehlgeschlagen. WSL-Einrichtung siehe README. Enter zum Schließen ...')
        except (EOFError, KeyboardInterrupt):
            pass
    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
