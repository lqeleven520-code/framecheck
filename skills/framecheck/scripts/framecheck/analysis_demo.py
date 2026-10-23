"""Public synthetic fixtures with known hard cuts and two kinds of image motion."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .analyze import AnalyzeOptions, analyze
from .media import Cancelled, MediaError, find_tools, process_options
from .motion import opencv


def synthetic_frames():
    cv2 = opencv()
    bases = []
    for scene, background in enumerate(((30, 38, 60), (180, 175, 140), (25, 110, 70))):
        image = Image.new("RGB", (320, 180), background)
        draw = ImageDraw.Draw(image)
        rng = np.random.default_rng(120 + scene)
        for _ in range(100):
            x, y = rng.integers(4, 308), rng.integers(4, 168)
            color = tuple(int(v) for v in rng.integers(20, 240, 3))
            draw.rectangle((x, y, x + 7, y + 7), fill=color)
        draw.text((18, 18), f"FrameCheck synthetic shot {scene + 1}", fill="white")
        bases.append(np.array(image))
    for scene, base in enumerate(bases):
        for index in range(32):
            if scene == 0:
                frame = base.copy()
            elif scene == 1:
                matrix = np.float32([[1, 0, -index * 1.8], [0, 1, 0]])
                frame = cv2.warpAffine(base, matrix, (320, 180), borderMode=cv2.BORDER_REFLECT)
            else:
                matrix = cv2.getRotationMatrix2D((160, 90), 0, 1 + index * 0.005)
                frame = cv2.warpAffine(base, matrix, (320, 180), borderMode=cv2.BORDER_REFLECT)
            yield frame


def generate_analysis_fixture(output: Path, ffmpeg=None, cancel=None):
    if output.exists():
        raise MediaError("Demo folder already exists; choose a new folder.")
    executable, _ = find_tools(ffmpeg)
    output.mkdir(parents=True, exist_ok=False)
    video = output / "synthetic-shots.mkv"
    subtitle = output / "synthetic-dialogue.srt"
    frames = []
    for frame in synthetic_frames():
        if cancel and cancel.is_set():
            raise Cancelled("Demo cancelled.")
        frames.append(frame.tobytes())
    process = subprocess.run([executable, "-nostdin", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", "320x180", "-r", "16", "-i", "pipe:0", "-an", "-c:v", "ffv1", video],
                             input=b"".join(frames), check=False, capture_output=True, timeout=30, **process_options())
    if process.returncode:
        raise MediaError(process.stderr.decode("utf-8", "replace")[-1000:])
    subtitle.write_text("1\n00:00:00,200 --> 00:00:01,500\n这是合成字幕示例，不是语音识别结果。\n\n"
                        "2\n00:00:02,200 --> 00:00:03,500\n第二个镜头：整体画面向左移动。\n\n"
                        "3\n00:00:04,200 --> 00:00:05,600\n第三个镜头：画面逐渐放大。\n", encoding="utf-8")
    return video, subtitle


def run_analysis_demo(output: Path, ffmpeg=None, progress=None, cancel=None):
    if output.exists():
        raise MediaError("Demo folder already exists; choose a new folder.")
    video, subtitles = generate_analysis_fixture(output / "media", ffmpeg, cancel)
    result = analyze(video, output / "report", AnalyzeOptions(ffmpeg=ffmpeg, subtitles=str(subtitles)),
                     progress, cancel)
    if (result["status"] != "COMPLETE" or result["decoded_frames"] != 96
            or [shot["start_frame"] for shot in result["shots"]] != [0, 32, 64]):
        raise MediaError("Synthetic shot boundaries did not match the known example; inspect the report.")
    return result
