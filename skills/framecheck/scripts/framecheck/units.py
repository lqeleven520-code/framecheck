"""Group the observed timeline into usable 4–15 second analysis units."""
from __future__ import annotations

from fractions import Fraction
from itertools import pairwise


def display_aspect(meta: dict) -> str:
    try:
        sar = Fraction(meta.get("sample_aspect_ratio", "1:1").replace(":", "/"))
        if sar <= 0:
            sar = Fraction(1)
    except (ValueError, ZeroDivisionError, AttributeError):
        sar = Fraction(1)
    ratio = Fraction(meta["width"], meta["height"]) * sar
    if meta["rotation"] in {90, 270}:
        ratio = 1 / ratio
    ratio = ratio.limit_denominator(10000)
    orientation = "横屏" if ratio > 1 else "竖屏" if ratio < 1 else "方形"
    return f"{ratio.numerator}:{ratio.denominator} {orientation}"


def make_units(shots: list[dict], duration: float, segments: list[dict], min_seconds=4.0, max_seconds=15.0):
    cuts = [shot["start_s"] for shot in shots[1:]]
    boundaries = [0.0]
    while duration - boundaries[-1] > max_seconds + 1e-6:
        start = boundaries[-1]
        limit = min(start + max_seconds, duration - min_seconds)
        target = min(start + 10.0, limit)
        candidates = [cut for cut in cuts if start + min_seconds <= cut <= limit]
        def cost(time_s, target=target):
            speech_crossing = any(row["start_s"] + 0.03 < time_s < row["end_s"] - 0.03 for row in segments)
            return abs(time_s - target) + (50 if speech_crossing else 0)
        # Prefer real cuts. A long uncut shot must be split without altering its timing.
        boundary = min(candidates, key=cost) if candidates else target
        boundaries.append(round(boundary, 6))
    boundaries.append(duration)
    units = []
    for index, (start, end) in enumerate(pairwise(boundaries), 1):
        fragments = []
        for shot in shots:
            if shot["end_s"] <= start or shot["start_s"] >= end:
                continue
            fragments.append({"shot_id": shot["id"], "start_s": round(max(start, shot["start_s"]) - start, 6),
                              "end_s": round(min(end, shot["end_s"]) - start, 6),
                              "source_start_s": max(start, shot["start_s"]),
                              "source_end_s": min(end, shot["end_s"]),
                              "partial_original_shot": shot["start_s"] < start or shot["end_s"] > end})
        units.append({"id": index, "start_s": start, "end_s": end, "duration_s": round(end - start, 6),
                      "short_source_exception": duration < min_seconds,
                      "speech_crosses_boundary": any(row["start_s"] < end < row["end_s"] for row in segments),
                      "shots": fragments, "keyframes": {}, "visual_style": "",
                      "references": {"场景": "", "出场人物": "", "道具": ""},
                      "first_frame_notes": "", "last_frame_notes": ""})
    return units
