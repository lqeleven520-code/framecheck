"""Observable 2D global motion, not a claim about a physical camera path."""
from __future__ import annotations

import math

import numpy as np

from .media import MediaError


def opencv():
    try:
        import cv2
    except ImportError as exc:
        raise MediaError('Video analysis needs OpenCV: install "eleven-framecheck[analysis]" '
                         'or this skill\'s requirements-analysis.txt.') from exc
    return cv2


def cut_score(previous, current) -> float:
    """HSV content change, on decoded downscaled frames. Range approximately 0..255."""
    cv2 = opencv()
    a = cv2.cvtColor(previous, cv2.COLOR_RGB2HSV).astype(np.float32)
    b = cv2.cvtColor(current, cv2.COLOR_RGB2HSV).astype(np.float32)
    hue = np.abs(a[:, :, 0] - b[:, :, 0])
    hue = np.minimum(hue, 180 - hue) * (255 / 90)
    # Hue is undefined in grayscale; do not let it manufacture a cut.
    hue *= np.minimum(a[:, :, 1], b[:, :, 1]) / 255
    return float((hue.mean() + np.abs(a[:, :, 1:] - b[:, :, 1:]).mean() * 2) / 3)


def estimate_motion(previous, current, elapsed: float) -> dict:
    cv2 = opencv()
    result = {"valid": False, "reason": "insufficient_features", "tracked": 0, "inliers": 0,
              "inlier_ratio": 0.0, "coverage": 0.0}
    if elapsed <= 0 or previous.shape != current.shape:
        return {**result, "reason": "invalid_pair"}
    a, b = (cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY) for frame in (previous, current))
    points = cv2.goodFeaturesToTrack(a, maxCorners=300, qualityLevel=0.01, minDistance=8, blockSize=7)
    if points is None or len(points) < 12:
        return result
    moved, status, _ = cv2.calcOpticalFlowPyrLK(a, b, points, None, winSize=(21, 21), maxLevel=3)
    if moved is None:
        return result
    restored, reverse_status, _ = cv2.calcOpticalFlowPyrLK(b, a, moved, None, winSize=(21, 21), maxLevel=3)
    if restored is None:
        return result
    good = ((status.ravel() == 1) & (reverse_status.ravel() == 1)
            & (np.linalg.norm(points - restored, axis=2).ravel() < 1.5))
    origin, target = points[good].reshape(-1, 2), moved[good].reshape(-1, 2)
    result["tracked"] = len(origin)
    if len(origin) < 12:
        return result
    matrix, mask = cv2.estimateAffinePartial2D(origin, target, method=cv2.RANSAC,
                                             ransacReprojThreshold=2.0, maxIters=1500, confidence=0.99)
    if matrix is None or mask is None or not np.isfinite(matrix).all():
        return {**result, "reason": "fit_failed"}
    mask = mask.ravel().astype(bool)
    height, width = a.shape
    cells = {(min(3, max(0, int(x * 4 / width))), min(3, max(0, int(y * 4 / height))))
             for x, y in origin[mask]}
    ratio, coverage = float(mask.mean()), len(cells) / 16
    result.update(inliers=int(mask.sum()), inlier_ratio=ratio, coverage=coverage)
    if mask.sum() < 12 or ratio < 0.6 or coverage < 0.25:
        return {**result, "reason": "weak_global_support"}
    scale = math.hypot(matrix[0, 0], matrix[1, 0])
    if not 0.75 < scale < 1.3:
        return {**result, "reason": "implausible_pair_scale"}
    center = np.array([width / 2, height / 2])
    delta = matrix[:, :2] @ center + matrix[:, 2] - center
    predicted = origin @ matrix[:, :2].T + matrix[:, 2]
    result.update(valid=True, reason="estimated", confidence=round(ratio * coverage, 4),
                  x_percent_per_s=float(delta[0] / width * 100 / elapsed),
                  y_percent_per_s=float(delta[1] / height * 100 / elapsed),
                  scale_percent_per_s=float(math.log(scale) * 100 / elapsed),
                  rotation_deg_per_s=float(math.degrees(math.atan2(matrix[1, 0], matrix[0, 0])) / elapsed),
                  residual_px=float(np.median(np.linalg.norm(predicted[mask] - target[mask], axis=1))))
    return result


LABELS = {
    "static": "整体画面近似静止 / approximately static",
    "pan_right": "疑似向右摇摄或平移（画面左移） / possible pan right",
    "pan_left": "疑似向左摇摄或平移（画面右移） / possible pan left",
    "tilt_down": "疑似向下摇摄或移动（画面上移） / possible tilt down",
    "tilt_up": "疑似向上摇摄或移动（画面下移） / possible tilt up",
    "zoom_in": "画面放大，疑似推进或变焦 / apparent zoom in",
    "zoom_out": "画面缩小，疑似拉远或变焦 / apparent zoom out",
    "rotate_clockwise": "画面顺时针旋转 / image rotates clockwise",
    "rotate_counterclockwise": "画面逆时针旋转 / image rotates counterclockwise",
    "mixed": "运动方向变化或复合运动 / mixed motion",
    "uncertain": "证据不足，无法可靠估计 / insufficient evidence",
}


def summarize_motion(samples: list[dict]) -> dict:
    valid = [row for row in samples if row["valid"]]
    base = {"method": "sparse_optical_flow_ransac_affine", "sample_pairs": len(samples),
            "valid_pairs": len(valid), "kind": "uncertain", "confidence": 0.0,
            "caveat": "2D image motion cannot distinguish camera movement, digital transforms or moving subjects."}
    if len(valid) < 2 or len(valid) / max(1, len(samples)) < 0.5:
        return {**base, "label": LABELS["uncertain"]}
    keys = ("x_percent_per_s", "y_percent_per_s", "scale_percent_per_s", "rotation_deg_per_s")
    values = np.array([[row[key] for key in keys] for row in valid])
    median = np.median(values, axis=0)
    strength = np.median(np.abs(values), axis=0)
    thresholds = np.array([1.5, 1.5, 2.0, 2.0])
    active = np.flatnonzero(strength > thresholds)
    if not len(active):
        kind = "static"
    elif len(active) > 1 or abs(median[active[0]]) < strength[active[0]] * 0.5:
        kind = "mixed"
    else:
        axis = active[0]
        choices = (("pan_right", "pan_left"), ("tilt_down", "tilt_up"),
                   ("zoom_out", "zoom_in"), ("rotate_counterclockwise", "rotate_clockwise"))
        kind = choices[axis][int(median[axis] > 0)]
    confidence = float(np.median([r["confidence"] for r in valid])) * len(valid) / len(samples)
    return {**base, "kind": kind, "label": LABELS[kind], "confidence": round(confidence, 3),
            "median": {k: round(float(v), 4) for k, v in zip(keys, median)}}
