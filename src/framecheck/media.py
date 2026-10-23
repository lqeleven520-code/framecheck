"""FFmpeg integration. Never invokes a shell or sends media over the network."""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
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


def _additional_ffmpeg_candidates() -> list[Path]:
    """Check explicit portable-app and Windows WinGet locations, never scan drives."""
    candidates = []
    if getattr(sys, "frozen", False):
        app = Path(sys.executable).resolve().parent
        suffix = ".exe" if os.name == "nt" else ""
        candidates.extend(folder / ("ffmpeg" + suffix)
                          for folder in (app / "ffmpeg" / "bin", app / "ffmpeg", app / "bin"))
    local = os.environ.get("LOCALAPPDATA") if os.name == "nt" else None
    if local:
        winget = Path(local) / "Microsoft" / "WinGet"
        candidates.append(winget / "Links" / "ffmpeg.exe")
        try:
            for package in sorted((winget / "Packages").glob("Gyan.FFmpeg_Microsoft.Winget.Source_*")):
                candidates.extend(sorted(package.glob("ffmpeg-*/bin/ffmpeg.exe"), reverse=True))
        except OSError:
            pass  # An inaccessible optional location does not hide valid PATH tools.
    return candidates


def find_tools(ffmpeg: str | None = None) -> tuple[str, str]:
    override = ffmpeg or os.environ.get("FRAMECHECK_FFMPEG")
    if override:
        candidates = [Path(override).expanduser().resolve()]
    else:
        on_path = shutil.which("ffmpeg")
        candidates = ([Path(on_path)] if on_path else []) + _additional_ffmpeg_candidates()
    found_decoder = False
    for candidate in candidates:
        if not candidate.is_file():
            continue
        found_decoder = True
        sibling = candidate.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        probe = str(sibling) if sibling.is_file() else shutil.which("ffprobe")
        if probe:
            return str(candidate), probe
    if not found_decoder:
        raise MediaError("FFmpeg not found. Install FFmpeg or select ffmpeg.exe / set FRAMECHECK_FFMPEG.")
    raise MediaError("ffprobe not found. Install the complete FFmpeg package (ffmpeg and ffprobe).")


def tool_versions(ffmpeg: str | None = None) -> dict[str, str]:
    result = {}
    for name, path in zip(("ffmpeg", "ffprobe"), find_tools(ffmpeg)):
        try:
            process = subprocess.run([path, "-version"], check=False, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=10, **process_options())
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MediaError(f"Cannot run {name}: {exc}") from exc
        lines = process.stdout.splitlines()
        if process.returncode or not lines:
            raise MediaError(f"{name} did not run successfully.")
        result[name] = lines[0]
    return result


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
        "start_time": number(stream.get("start_time"), 0.0),
        "sample_aspect_ratio": stream.get("sample_aspect_ratio", "1:1"),
        "format_start_time": number(data.get("format", {}).get("start_time"), 0.0),
        "subtitle_streams": [{"index": s["index"], "codec": s.get("codec_name"),
                              "language": s.get("tags", {}).get("language", "und")}
                             for s in data.get("streams", []) if s.get("codec_type") == "subtitle"],
    }


class Decoder:
    """Stream original-size RGB frames and their actual presentation timestamps."""

    def __init__(self, path: Path, meta: dict, ffmpeg: str, start: int = 0,
                 limit: int | None = None, cancel: threading.Event | None = None,
                 max_size: int | None = None, preserve_timestamps: bool = False):
        self.meta = meta
        self.path = path
        self.cancel = cancel or threading.Event()
        self.timestamps: queue.Queue[float] = queue.Queue()
        self.tail: deque[str] = deque(maxlen=12)
        self.closed = False
        self.finished = threading.Event()
        self.width, self.height = meta["width"], meta["height"]
        scale = ""
        if max_size is not None and max(self.width, self.height) > max_size:
            ratio = max_size / max(self.width, self.height)
            self.width, self.height = max(2, int(self.width * ratio)), max(2, int(self.height * ratio))
            scale = f"scale={self.width}:{self.height},"
        filters = (f"select=gte(n\\,{start})," if start else "") + scale + "format=rgb24,showinfo"
        cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "info", "-xerror",
               "-protocol_whitelist", "file,pipe,crypto,data", "-noautorotate", "-i", str(path),
               "-map", f"0:{meta['stream_index']}",
               "-an", "-sn", "-dn", "-filter_threads", "1", "-vf", filters,
               "-fps_mode", "passthrough"]
        if preserve_timestamps:
            cmd.insert(1, "-copyts")
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
        size = self.width * self.height * 3
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
        return np.frombuffer(data, dtype=np.uint8).reshape(self.height, self.width, 3), pts

    def close(self):
        self.closed = True
        self.finished.set()
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=10)
        self.reader.join(timeout=5)
        self.proc.stdout.close()
        self.proc.stderr.close()
