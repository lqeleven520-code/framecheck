"""Single-video shot, image-motion and dialogue analysis using public algorithms."""
from __future__ import annotations

import csv
import json
import math
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from . import __version__
from .analysis_report import write_analysis_report
from .compare import sha256
from .media import Cancelled, Decoder, MediaError, find_tools, probe_media
from .motion import cut_score, estimate_motion, opencv, summarize_motion
from .speech import extract_transcript, run_local, write_transcript
from .storyboard import write_storyboard
from .units import display_aspect, make_units


@dataclass
class AnalyzeOptions:
    threshold: float = 27.0
    min_shot_seconds: float = 0.35
    analysis_size: int = 480
    motion_fps: float = 8.0
    transcript: str = "auto"
    subtitles: str | None = None
    subtitle_stream: int | None = None
    audio_stream: int | None = None
    model: str = "base"
    language: str | None = None
    offline: bool = False
    export_clips: bool = False
    max_frames: int | None = None
    ffmpeg: str | None = None

    def validate(self):
        if not math.isfinite(self.threshold) or not 1 <= self.threshold <= 255:
            raise MediaError("Shot threshold must be between 1 and 255.")
        if not math.isfinite(self.min_shot_seconds) or not 0 <= self.min_shot_seconds <= 60:
            raise MediaError("Minimum shot length must be between 0 and 60 seconds.")
        if not 160 <= self.analysis_size <= 1280:
            raise MediaError("Analysis size must be between 160 and 1280 pixels.")
        if not math.isfinite(self.motion_fps) or not 1 <= self.motion_fps <= 30:
            raise MediaError("Motion sampling rate must be between 1 and 30.")
        if self.transcript not in {"auto", "subtitles", "asr", "none"}:
            raise MediaError("Unknown transcript mode.")
        if self.subtitles and (not Path(self.subtitles).is_file() or self.transcript == "none"):
            raise MediaError("Choose an existing UTF-8 SRT and enable transcription.")
        if self.subtitle_stream is not None and self.subtitle_stream < 0:
            raise MediaError("Subtitle stream index must be non-negative.")
        if self.audio_stream is not None and self.audio_stream < 0:
            raise MediaError("Audio stream index must be non-negative.")
        if self.max_frames is not None and self.max_frames < 1:
            raise MediaError("Frame limit must be positive.")
        names = {"tiny", "base", "small", "medium", "large-v3", "turbo", "tiny.en", "base.en", "small.en"}
        if self.model not in names and not Path(self.model).is_dir():
            raise MediaError("Use a supported Whisper model name or an existing local CTranslate2 model folder.")


def analyze(video: Path, output: Path, options: AnalyzeOptions | None = None, progress=None, cancel=None) -> dict:
    options = options or AnalyzeOptions()
    options.validate()
    progress = progress or (lambda _: None)
    cancel = cancel or threading.Event()
    video, output = video.expanduser().resolve(), output.expanduser().resolve()
    if not video.is_file():
        raise MediaError("Select an existing local video.")
    if output.exists():
        raise MediaError("Output folder already exists. Choose a new folder; existing files are never overwritten.")
    opencv()  # Fail before creating a report if this optional feature is not installed.
    ffmpeg, ffprobe = find_tools(options.ffmpeg)
    meta = probe_media(video, ffprobe)
    if meta["color_transfer"] in {"smpte2084", "arib-std-b67"}:
        raise MediaError("Analysis currently requires SDR video; HDR is not silently tone-mapped.")
    if meta["rotation"] not in {0, 90, 180, 270}:
        raise MediaError("Analysis supports display rotations of 0, 90, 180 or 270 degrees.")
    source_hash = sha256(video, cancel)
    config = asdict(options)
    for private in ("ffmpeg", "subtitles"):
        config.pop(private)
    config["model"] = Path(options.model).name
    result = {"schema_version": 1, "mode": "analyze", "tool": "FrameCheck", "version": __version__,
              "created_utc": datetime.now(timezone.utc).isoformat(), "status": "ERROR",
              "scope": "selected_range" if options.max_frames is not None else "whole_video",
              "source": {**meta, "sha256": source_hash}, "options": config, "shots": [],
              "decoded_frames": 0, "duration_s": 0.0, "warnings": [],
              "transcript": {"status": "not_run", "source": "none", "segments": []}, "units": [],
              "display_aspect": display_aspect(meta),
              "limitations": ["Cut detection is a heuristic. Fades, flashes, fast action and similar shots need review.",
                              "Motion labels describe estimated 2D image motion, not verified camera equipment or intent.",
                              "Transcripts require review. No speaker identification, lip reading or burned-in subtitle OCR."]}
    output.mkdir(parents=True, exist_ok=False)
    (output / "keyframes").mkdir()
    decoder = None
    shots = result["shots"]
    samples = []
    previous = motion_frame = None
    origin = previous_pts = motion_time = None
    deltas = deque(maxlen=64)
    frame_times = []
    rows_fields = ["shot", "time_s", "valid", "reason", "tracked", "inliers", "inlier_ratio", "coverage",
                   "confidence", "x_percent_per_s", "y_percent_per_s", "scale_percent_per_s",
                   "rotation_deg_per_s", "residual_px"]

    def finish_shot(end_frame, end_time):
        shot = shots[-1]
        shot.update(end_frame_exclusive=end_frame, end_s=round(end_time, 6),
                    duration_s=round(end_time - shot["start_s"], 6), motion=summarize_motion(samples))

    def error_text(exc):
        message = str(exc).replace(str(video), meta["name"]).replace(str(output), "[report]")
        return message.replace(str(Path.home()), "[home]")

    try:
        progress("Detecting cuts and measuring motion / 正在检测镜头与估计运镜…")
        decoder = Decoder(video, meta, ffmpeg, limit=options.max_frames, cancel=cancel,
                          max_size=options.analysis_size, preserve_timestamps=True)
        with (output / "motion.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows_fields)
            writer.writeheader()
            for index, (frame, pts) in enumerate(decoder):
                if origin is None:
                    origin = pts
                if previous_pts is not None:
                    if pts <= previous_pts:
                        raise MediaError("Video timestamps must be strictly increasing for shot analysis.")
                    deltas.append(pts - previous_pts)
                time_s = pts - origin
                frame_times.append(time_s)
                if meta["rotation"]:
                    frame = np.ascontiguousarray(np.rot90(frame, meta["rotation"] // 90))
                score = cut_score(previous, frame) if previous is not None else 0.0
                boundary = (not shots or score >= options.threshold
                            and time_s - shots[-1]["start_s"] >= options.min_shot_seconds)
                if boundary:
                    if shots:
                        finish_shot(index, time_s)
                    shot_id = len(shots) + 1
                    image = f"keyframes/shot-{shot_id:04}.jpg"
                    Image.fromarray(frame).save(output / image, quality=88)
                    shots.append({"id": shot_id, "start_frame": index, "start_s": round(time_s, 6),
                                  "cut_score": round(score, 3), "keyframe": image,
                                  "keyframe_time_s": round(time_s, 6), "dialogue": []})
                    samples = []
                    motion_frame, motion_time = frame.copy(), time_s
                elif time_s - motion_time >= 1 / options.motion_fps - 1e-6:
                    evidence = estimate_motion(motion_frame, frame, time_s - motion_time)
                    samples.append(evidence)
                    writer.writerow({"shot": len(shots), "time_s": round(time_s, 6), **evidence})
                    motion_frame, motion_time = frame.copy(), time_s
                previous, previous_pts = frame, pts
                result["decoded_frames"] = index + 1
                if index % 120 == 0:
                    progress(f"Decoded {index + 1} frames · {len(shots)} shots / 已解析 {time_s:.1f} 秒")
        decoder.close()
        decoder = None
        if not shots:
            raise MediaError("No video frames were decoded.")
        last_duration = float(np.median(deltas)) if deltas else (1 / meta["fps"] if meta["fps"] else 0.04)
        duration = previous_pts - origin + last_duration
        result.update(duration_s=round(duration, 6), source_first_pts_s=origin,
                      final_frame_duration_estimated_s=last_duration)
        finish_shot(result["decoded_frames"], duration)
        if options.max_frames is not None:
            result["warnings"].append("Only the selected frame range was analyzed; this is not a whole-video result.")
        try:
            result["transcript"] = extract_transcript(video, output, meta, ffmpeg, options,
                                                       origin, duration, cancel, progress)
        except Cancelled:
            raise
        except (MediaError, OSError, ValueError) as exc:
            result["transcript"] = {"status": "unavailable", "source": "none", "segments": [],
                                    "error": error_text(exc)}
            result["warnings"].append("Dialogue extraction did not complete. Shot and motion results are available.")
        for shot in shots:
            shot["dialogue"] = [index for index, row in enumerate(result["transcript"]["segments"])
                                if row["start_s"] < shot["end_s"] and row["end_s"] > shot["start_s"]]
        result["units"] = make_units(shots, duration, result["transcript"]["segments"])
        progress("Preparing 4–15 second analysis units / 正在整理 4—15 秒解析单元与观察帧…")
        (output / "units").mkdir()
        targets = {}
        for unit in result["units"]:
            for label, time_s in (("start", unit["start_s"]), ("middle", (unit["start_s"] + unit["end_s"]) / 2),
                                  ("end", max(unit["start_s"], unit["end_s"] - last_duration))):
                frame_index = min(len(frame_times) - 1, int(np.searchsorted(frame_times, time_s - 1e-6)))
                relative = f"units/unit-{unit['id']:04}-{label}.jpg"
                unit["keyframes"][label] = {"path": relative, "time_s": round(frame_times[frame_index], 6)}
                targets.setdefault(frame_index, []).append(relative)
        decoder = Decoder(video, meta, ffmpeg, limit=result["decoded_frames"], cancel=cancel, max_size=640,
                          preserve_timestamps=True)
        for index, (frame, _) in enumerate(decoder):
            if index not in targets:
                continue
            if meta["rotation"]:
                frame = np.ascontiguousarray(np.rot90(frame, meta["rotation"] // 90))
            for relative in targets[index]:
                Image.fromarray(frame).save(output / relative, quality=90)
        decoder.close()
        decoder = None
        if options.export_clips:
            clips = output / "clips"
            clips.mkdir()
            for shot in shots:
                progress(f"Exporting shot {shot['id']}/{len(shots)} / 正在导出镜头片段…")
                filename = f"shot-{shot['id']:04}.mp4"
                # Re-encode after seeking so boundaries do not snap to keyframes.
                offset = origin - meta["format_start_time"] + shot["start_s"]
                run_local([ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe,crypto,data",
                           "-ss", f"{max(0, offset):.9f}", "-i", video, "-map", f"0:{meta['stream_index']}",
                           "-map", "0:a:0?", "-t", f"{shot['duration_s']:.9f}", "-sn", "-dn",
                           "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-crf", "18",
                           "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
                           clips / filename], cancel, timeout=600)
                shot["clip"] = f"clips/{filename}"
        result["status"] = "PARTIAL" if result["transcript"]["status"] == "unavailable" else "COMPLETE"
        return result
    except Cancelled:
        result["status"] = "CANCELLED"
        result["warnings"].append("Cancelled; incomplete outputs are not an analysis verdict.")
        raise
    except Exception as exc:
        result["status"] = "ERROR"
        result["warnings"].append(error_text(exc))
        raise
    finally:
        if decoder is not None:
            decoder.close()
        for shot in shots:
            shot.setdefault("end_frame_exclusive", result["decoded_frames"])
            shot.setdefault("end_s", round((previous_pts - origin) if previous_pts is not None else 0, 6))
            shot.setdefault("duration_s", max(0, shot["end_s"] - shot["start_s"]))
            shot.setdefault("motion", summarize_motion(samples))
        write_transcript(output, result["transcript"])
        (output / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                                        allow_nan=False) + "\n", encoding="utf-8")
        with (output / "shots.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["shot", "start_s", "end_s", "duration_s", "start_frame", "end_frame_exclusive",
                             "motion_estimate", "confidence", "dialogue", "keyframe", "clip"])
            for shot in shots:
                dialogue = " / ".join(result["transcript"]["segments"][i]["text"] for i in shot["dialogue"])
                # Spreadsheet formula characters from untrusted subtitle text stay plain text.
                if dialogue.lstrip().startswith(("=", "+", "-", "@")):
                    dialogue = "'" + dialogue
                writer.writerow([shot["id"], shot["start_s"], shot["end_s"], shot["duration_s"],
                                 shot["start_frame"], shot["end_frame_exclusive"], shot["motion"]["label"],
                                 shot["motion"]["confidence"], dialogue, shot["keyframe"], shot.get("clip", "")])
        write_storyboard(output, result)
        write_analysis_report(output, result)
