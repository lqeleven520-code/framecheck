"""Explicit local bundle smoke test using generated media, never private files."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from .compare import Options, compare
from .media import find_tools, process_options


def run(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    ffmpeg, _ = find_tools()
    source = output / "synthetic.mkv"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=80x48:rate=4:duration=1", "-c:v", "ffv1", "-an", str(source)],
                   check=True, timeout=30, **process_options())
    result = compare(source, source, output / "engine", Options())
    if result["status"] != "PASS" or result["summary"]["compared_frames"] != 4:
        raise RuntimeError("Frozen comparison engine did not pass.")
    import tkinter as tk

    from .gui import App
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    try:
        app.reference.set(str(source))
        app.candidate.set(str(source))
        app.destination.set(str(output / "gui"))
        app.start()
        deadline = time.monotonic() + 30
        while app.running and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        if app.running or not app.last_report or not app.last_report.exists():
            raise RuntimeError("Frozen GUI workflow did not finish.")
        gui_result = json.loads((app.last_report.parent / "result.json").read_text(encoding="utf-8"))
        if gui_result["status"] != "PASS":
            raise RuntimeError("Frozen GUI comparison did not pass.")
        app.start_demo()
        deadline = time.monotonic() + 30
        while app.running and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        if app.running or not app.last_report or not app.last_report.exists():
            raise RuntimeError("Frozen GUI demo did not finish.")
        demo_result = json.loads((app.last_report.parent / "result.json").read_text(encoding="utf-8"))
        if demo_result["status"] != "FAIL" or demo_result["summary"]["compared_frames"] != 24:
            raise RuntimeError("Frozen GUI demo did not show the expected difference.")
    finally:
        app.cancel_event.set()
        if hasattr(app, "worker"):
            app.worker.join(timeout=5)
        root.after_cancel(app.poll_id)
        root.destroy()
    (output / "self-test.json").write_text(json.dumps({"engine": "PASS", "gui_worker": "PASS",
                                                     "frames": 4, "gui_demo": "PASS", "demo_frames": 24,
                                                     "synthetic_media_only": True}, indent=2)
                                          + "\n", encoding="utf-8")
    return 0
