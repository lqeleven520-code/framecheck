"""Small reproducible first-run example made entirely from synthetic patterns."""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from .compare import Options, compare
from .media import Cancelled, MediaError, find_tools, process_options


def generate_pair(output: Path, ffmpeg: str | None = None,
                  cancel: threading.Event | None = None) -> tuple[Path, Path]:
    executable, _ = find_tools(ffmpeg)
    if cancel is not None and cancel.is_set():
        raise Cancelled("Demo cancelled.")
    output = output.expanduser().resolve()
    if output.exists():
        raise MediaError("Demo folder already exists. Choose a new folder; existing files are never overwritten.")
    output.mkdir(parents=True, exist_ok=False)
    source = "testsrc2=size=320x180:rate=12:duration=2"
    for name, filters in (("reference", []),
                          ("changed", ["-vf", "drawbox=x=30:y=30:w=80:h=50:color=red:t=fill"])):
        if cancel is not None and cancel.is_set():
            raise Cancelled("Demo cancelled.")
        try:
            process = subprocess.run(
                [executable, "-nostdin", "-v", "error", "-f", "lavfi", "-i", source,
                 *filters, "-c:v", "ffv1", "-an", str(output / f"{name}.mkv")],
                check=False, capture_output=True, timeout=30, **process_options(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MediaError(f"Could not generate demo media: {exc}") from exc
        if process.returncode:
            raise MediaError("Could not generate demo media: " + process.stderr.decode("utf-8", "replace")[-1000:])
    if cancel is not None and cancel.is_set():
        raise Cancelled("Demo cancelled.")
    return output / "reference.mkv", output / "changed.mkv"


def run_demo(output: Path, ffmpeg: str | None = None, progress=None,
             cancel: threading.Event | None = None) -> dict:
    output = output.expanduser().resolve()
    if output.exists():
        raise MediaError("Demo folder already exists. Choose a new folder; existing files are never overwritten.")
    progress = progress or (lambda _: None)
    progress("Creating synthetic examples / 正在生成示例视频…")
    reference, candidate = generate_pair(output / "media", ffmpeg, cancel)
    result = compare(reference, candidate, output / "report", Options(ffmpeg=ffmpeg), progress, cancel)
    if (result["status"] != "FAIL" or result["summary"]["compared_frames"] != 24
            or result["summary"]["frames_over_threshold"] == 0):
        raise MediaError("The demo did not detect the expected synthetic difference. Inspect its report.")
    return result
