"""Comparison engine adapted from Eleven's local frame-evidence scripts."""

from __future__ import annotations

import csv
import hashlib
import heapq
import itertools
import json
import math
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageEnhance

from . import __version__
from .media import Cancelled, Decoder, MediaError, find_tools, probe_media
from .report import write_report


@dataclass
class Options:
    max_mae: float = 2.5
    max_timing_ms: float = 20.0
    reference_start: int = 0
    candidate_start: int = 0
    max_frames: int | None = None
    previews: int = 8
    ffmpeg: str | None = None

    def validate(self):
        if not math.isfinite(self.max_mae) or not 0 <= self.max_mae <= 255:
            raise MediaError("MAE threshold must be between 0 and 255.")
        if not math.isfinite(self.max_timing_ms) or not 0 <= self.max_timing_ms <= 10_000:
            raise MediaError("Timing tolerance must be between 0 and 10000 ms.")
        if self.reference_start < 0 or self.candidate_start < 0:
            raise MediaError("Start frame must be non-negative (zero-based).")
        if self.max_frames is not None and self.max_frames < 1:
            raise MediaError("Frame limit must be positive.")
        if not 0 <= self.previews <= 30:
            raise MediaError("Preview count must be between 0 and 30.")


def sha256(path: Path, cancel: threading.Event) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            if cancel.is_set():
                raise Cancelled("Comparison cancelled.")
            digest.update(block)
    return digest.hexdigest()


def pixel_metrics(a: np.ndarray, b: np.ndarray) -> dict:
    diff = a.astype(np.int16) - b.astype(np.int16)
    absolute = np.abs(diff)
    mse = float(np.mean(np.square(diff, dtype=np.float64)))
    return {"mae": float(absolute.mean()), "mse": mse,
            "psnr_db": 10 * math.log10(255**2 / mse) if mse else None,
            "max_channel_delta": int(absolute.max()),
            "changed_pixels_percent": float(np.any(diff != 0, axis=2).mean() * 100)}


def preview(frame: np.ndarray, rotation: int) -> Image.Image:
    image = Image.fromarray(frame)
    if rotation:
        image = image.rotate(rotation, expand=True)
    image.thumbnail((720, 405), Image.Resampling.LANCZOS)
    return image


def compare(reference: Path, candidate: Path, output: Path, options: Options | None = None,
            progress: Callable[[str], None] | None = None,
            cancel: threading.Event | None = None) -> dict:
    options = options or Options()
    options.validate()
    progress = progress or (lambda _: None)
    cancel = cancel or threading.Event()
    reference, candidate, output = (p.expanduser().resolve() for p in (reference, candidate, output))
    for path in (reference, candidate):
        if not path.is_file():
            raise MediaError(f"Video file not found: {path.name}")
    if output.exists():
        raise MediaError("Output folder already exists. Choose a new folder; existing files are never overwritten.")
    ffmpeg, ffprobe = find_tools(options.ffmpeg)
    progress("Inspecting videos / 正在读取视频信息…")
    ref_meta, cand_meta = probe_media(reference, ffprobe), probe_media(candidate, ffprobe)
    progress("Hashing source files / 正在核对源文件…")
    ref_hash, cand_hash = sha256(reference, cancel), sha256(candidate, cancel)
    config = asdict(options)
    config.pop("ffmpeg")  # No local executable path in shareable reports.
    result = {
        "schema_version": 1, "tool": "FrameCheck", "version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(), "status": "ERROR",
        "scope": "selected_range" if (options.max_frames or options.reference_start or options.candidate_start)
        else "whole_video",
        "reference": {**ref_meta, "sha256": ref_hash}, "candidate": {**cand_meta, "sha256": cand_hash},
        "byte_identical": ref_hash == cand_hash, "options": config,
        "reasons": [], "warnings": [], "summary": {}, "previews": [],
    }
    reasons, warnings = result["reasons"], result["warnings"]
    warnings.append("Visual metrics are technical evidence, not a judgment of creative or perceptual quality.")
    warnings.append("Audio is not compared; audio stream counts are informational only.")
    if result["scope"] != "whole_video":
        warnings.append("Only the requested frame range is assessed; this is not a whole-video pass.")
    for meta in (ref_meta, cand_meta):
        if meta["color_transfer"] in {"smpte2084", "arib-std-b67"}:
            raise MediaError("HDR input is not supported in v0.1. Convert to a defined SDR baseline first.")
    dimensions_match = (ref_meta["width"], ref_meta["height"]) == (cand_meta["width"], cand_meta["height"])
    compatible = dimensions_match and ref_meta["rotation"] == cand_meta["rotation"]
    if not dimensions_match:
        reasons.append("Resolution mismatch; frames were not resized or compared.")
    if ref_meta["rotation"] != cand_meta["rotation"]:
        reasons.append("Display rotation metadata differs.")
    if ref_meta["fps"] and cand_meta["fps"] and abs(ref_meta["fps"] - cand_meta["fps"]) > 0.001:
        warnings.append("Reported frame rates differ. Alignment is by frame index; presentation times are checked.")
        reasons.append("Average frame rate metadata differs.")
    if (result["scope"] == "whole_video" and ref_meta["duration"] is not None
            and cand_meta["duration"] is not None
            and abs(ref_meta["duration"] - cand_meta["duration"]) * 1000 > options.max_timing_ms):
        reasons.append("Reported video duration differs beyond the timing tolerance.")
    output.mkdir(parents=True, exist_ok=False)
    rows_path = output / "frames.csv"
    ref_count = cand_count = compared = bad = timing_bad = 0
    mae_sum = mse_sum = max_mae = max_timing = 0.0
    max_delta = 0
    saved = []
    decoders = []
    fields = ["frame", "reference_frame", "candidate_frame", "reference_time_s", "candidate_time_s",
              "relative_timing_error_ms", "mae", "psnr_db", "max_channel_delta", "changed_pixels_percent"]
    try:
        with rows_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fields)
            writer.writeheader()
            if compatible:
                for path, meta, start in ((reference, ref_meta, options.reference_start),
                                          (candidate, cand_meta, options.candidate_start)):
                    decoders.append(Decoder(path, meta, ffmpeg, start, options.max_frames, cancel))
                first_ref = first_cand = None
                for index, (ref, cand) in enumerate(itertools.zip_longest(*decoders), start=1):
                    if cancel.is_set():
                        raise Cancelled("Comparison cancelled.")
                    ref_count += ref is not None
                    cand_count += cand is not None
                    if ref is None or cand is None:
                        continue
                    a, ta = ref
                    b, tb = cand
                    if first_ref is None:
                        first_ref, first_cand = ta, tb
                    timing = abs((ta - first_ref) - (tb - first_cand)) * 1000
                    metrics = pixel_metrics(a, b)
                    row = {"frame": index, "reference_frame": index + options.reference_start,
                           "candidate_frame": index + options.candidate_start,
                           "reference_time_s": ta, "candidate_time_s": tb,
                           "relative_timing_error_ms": timing,
                           **{k: v for k, v in metrics.items() if k != "mse"}}
                    writer.writerow(row)
                    compared += 1
                    mae_sum += metrics["mae"]
                    mse_sum += metrics["mse"]
                    max_mae = max(max_mae, metrics["mae"])
                    max_delta = max(max_delta, metrics["max_channel_delta"])
                    max_timing = max(max_timing, timing)
                    bad += metrics["mae"] > options.max_mae
                    timing_bad += timing > options.max_timing_ms
                    if options.previews and (len(saved) < options.previews or metrics["mae"] > saved[0][0]):
                        item = (metrics["mae"], index, row, preview(a, ref_meta["rotation"]),
                                preview(b, cand_meta["rotation"]))
                        if len(saved) < options.previews:
                            heapq.heappush(saved, item)
                        else:
                            heapq.heapreplace(saved, item)
                    if index == 1 or index % 25 == 0:
                        progress(f"Compared {index} frames / 已比较 {index} 帧")
        if compatible:
            if not compared:
                reasons.append("No comparable frames in the requested range.")
            if ref_count != cand_count:
                reasons.append(f"Decoded frame counts differ: reference {ref_count}, candidate {cand_count}.")
            if bad:
                reasons.append(f"{bad} frames exceed the MAE threshold {options.max_mae:g}.")
            if timing_bad:
                reasons.append(f"{timing_bad} frames exceed the timing tolerance {options.max_timing_ms:g} ms.")
        result["status"] = "FAIL" if reasons else "PASS"
        if saved:
            image_dir = output / "images"
            image_dir.mkdir()
            for _, index, row, a, b in sorted(saved, key=lambda item: (-item[0], item[1])):
                prefix = f"frame-{index:06d}"
                a.save(image_dir / f"{prefix}-reference.jpg", quality=88)
                b.save(image_dir / f"{prefix}-candidate.jpg", quality=88)
                difference = ImageEnhance.Brightness(ImageChops.difference(a, b)).enhance(4)
                difference.save(image_dir / f"{prefix}-difference.png")
                result["previews"].append({**row, "reference_image": f"images/{prefix}-reference.jpg",
                                           "candidate_image": f"images/{prefix}-candidate.jpg",
                                           "difference_image": f"images/{prefix}-difference.png"})
    except (Exception, KeyboardInterrupt) as exc:
        result["status"] = "CANCELLED" if isinstance(exc, (Cancelled, KeyboardInterrupt)) else "ERROR"
        result["reasons"].append(str(exc) or "Interrupted.")
        raise
    finally:
        for decoder in decoders:
            decoder.close()
        mean_mse = mse_sum / compared if compared else None
        result["summary"] = {"reference_frames": ref_count, "candidate_frames": cand_count,
                             "compared_frames": compared, "frames_over_threshold": bad,
                             "timing_mismatch_frames": timing_bad,
                             "average_mae": mae_sum / compared if compared else None,
                             "max_mae": max_mae if compared else None, "max_channel_delta": max_delta,
                             "max_timing_error_ms": max_timing if compared else None,
                             "psnr_db": 10 * math.log10(255**2 / mean_mse) if mean_mse else None,
                             "decoded_pixels_identical": bool(result["status"] in {"PASS", "FAIL"}
                                                              and compared and ref_count == cand_count
                                                              and max_delta == 0)}
        (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
                                          + "\n", encoding="utf-8")
        write_report(output, result)
    progress(f"{result['status']} — {compared} frames / 报告已保存")
    return result
