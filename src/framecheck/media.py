"""FFmpeg integration. Never invokes a shell or sends media over the network."""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
from collections import deque
from fractions import Fraction
from pathlib import Path

import numpy as np


class MediaError(RuntimeError):
    pass


class Cancelled(MediaError):
    pass


def process_options() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def find_tools(ffmpeg: str | None = None) -> tuple[str, str]:
    override = ffmpeg or os.environ.get("FRAMECHECK_FFMPEG")
    candidate = str(Path(override).expanduser().resolve()) if override else shutil.which("ffmpeg")
    if not candidate or not Path(candidate).is_file():
        raise MediaError("FFmpeg not found. Install FFmpeg or select ffmpeg.exe / set FRAMECHECK_FFMPEG.")
    sibling = Path(candidate).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    probe = str(sibling) if sibling.is_file() else shutil.which("ffprobe")
    if not probe:
        raise MediaError("ffprobe not found. Install the complete FFmpeg package (ffmpeg and ffprobe).")
    return candidate, probe


def number(value, default=None):
    try:
        result = float(value)
        return result if np.isfinite(result) else default
    except (ValueError, TypeError):
        return default


def rate(value) -> float | None:
    try:
        result = float(Fraction(value))
        return result if result > 0 else None
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def probe_media(path: Path, ffprobe: str) -> dict:
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe,crypto,data",
             "-show_streams", "-show_format", "-of", "json", str(path)],
            check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
            **process_options(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaError(f"Cannot inspect {path.name}: {exc}") from exc
    if result.returncode:
        raise MediaError(f"Cannot inspect {path.name}: {result.stderr[-1500:].strip()}")
    try:
        data = json.loads(result.stdout)
        stream = next(s for s in data.get("streams", []) if s.get("codec_type") == "video"
                      and not s.get("disposition", {}).get("attached_pic"))
    except (ValueError, StopIteration) as exc:
        raise MediaError(f"No readable video stream: {path.name}") from exc
    rotation = 0
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            rotation = int(side["rotation"]) % 360
    width, height = int(stream.get("width", 0)), int(stream.get("height", 0))
    if width < 1 or height < 1 or width * height > 40_000_000:
        raise MediaError("Unsupported dimensions; maximum 40 million pixels per frame.")
    return {
        "name": path.name, "bytes": path.stat().st_size,
        "width": width, "height": height, "rotation": rotation,
        "codec": stream.get("codec_name"), "pixel_format": stream.get("pix_fmt"),
        "fps": rate(stream.get("avg_frame_rate")), "nominal_fps": rate(stream.get("r_frame_rate")),
        "duration": number(stream.get("duration"), number(data.get("format", {}).get("duration"))),
        "stream_index": stream["index"],
        "color_transfer": stream.get("color_transfer"),
        "audio_streams": sum(s.get("codec_type") == "audio" for s in data.get("streams", [])),
    }


class Decoder:
    """Stream original-size RGB frames and their actual presentation timestamps."""

    def __init__(self, path: Path, meta: dict, ffmpeg: str, start: int = 0,
                 limit: int | None = None, cancel: threading.Event | None = None):
        self.meta = meta
        self.path = path
        self.cancel = cancel or threading.Event()
        self.timestamps: queue.Queue[float] = queue.Queue()
        self.tail: deque[str] = deque(maxlen=12)
        self.closed = False
        self.finished = threading.Event()
        filters = (f"select=gte(n\\,{start})," if start else "") + "format=rgb24,showinfo"
        cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "info", "-xerror",
               "-protocol_whitelist", "file,pipe,crypto,data", "-noautorotate", "-i", str(path),
               "-map", f"0:{meta['stream_index']}",
               "-an", "-sn", "-dn", "-filter_threads", "1", "-vf", filters,
               "-fps_mode", "passthrough"]
        if limit is not None:
            cmd += ["-frames:v", str(limit)]
        cmd += ["-threads", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         **process_options())
        except OSError as exc:
            raise MediaError(f"Cannot start FFmpeg: {exc}") from exc
        self.reader = threading.Thread(target=self._read_log, daemon=True)
        self.reader.start()
        self.watcher = threading.Thread(target=self._watch_cancel, daemon=True)
        self.watcher.start()

    def _read_log(self):
        pattern = re.compile(r"\bn:\s*\d+.*?\bpts_time:([-+\d.eE]+)")
        for raw in self.proc.stderr:
            line = raw.decode("utf-8", errors="replace").strip()
            match = pattern.search(line)
            if match and "showinfo" in line:
                timestamp = number(match.group(1))
                if timestamp is not None:
                    self.timestamps.put(timestamp)
            elif "showinfo" not in line:
                self.tail.append(line)

    def _watch_cancel(self):
        while not self.finished.wait(0.1):
            if self.cancel.is_set():
                if self.proc.poll() is None:
                    self.proc.kill()
                return

    def __iter__(self):
        return self

    def __next__(self) -> tuple[np.ndarray, float]:
        if self.closed:
            raise StopIteration
        if self.cancel.is_set():
            raise Cancelled("Comparison cancelled.")
        size = self.meta["width"] * self.meta["height"] * 3
        data = bytearray()
        while len(data) < size:
            chunk = self.proc.stdout.read(size - len(data))
            if not chunk:
                break
            data.extend(chunk)
        if self.cancel.is_set():
            raise Cancelled("Comparison cancelled.")
        if not data:
            try:
                code = self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired as exc:
                raise MediaError("FFmpeg did not finish after decoding.") from exc
            self.reader.join(timeout=5)
            if code:
                raise MediaError(f"Decode failed for {self.path.name}: {' '.join(self.tail)[-1500:]}")
            raise StopIteration
        if len(data) != size:
            raise MediaError(f"Incomplete decoded frame in {self.path.name}.")
        try:
            pts = self.timestamps.get(timeout=10)
        except queue.Empty as exc:
            raise MediaError("FFmpeg did not provide a presentation timestamp; no estimated result was used.") from exc
        return np.frombuffer(data, dtype=np.uint8).reshape(self.meta["height"], self.meta["width"], 3), pts

    def close(self):
        self.closed = True
        self.finished.set()
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=10)
        self.reader.join(timeout=5)
        self.proc.stdout.close()
        self.proc.stderr.close()
