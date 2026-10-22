# English quick start

FrameCheck compares a reference and candidate video locally. It is useful for checking a render/export revision and recording reproducible technical differences.

1. Install Python 3.10+ and FFmpeg (including ffprobe).
2. In a virtual environment, run `python -m pip install .` from the repository.
3. Run `framecheck doctor`, then `framecheck gui` or `framecheck compare reference.mp4 candidate.mp4 -o reports/first`.
4. Open `reports/first/report.html`. Keep the report folder intact when sharing.

The desktop labels are currently Chinese. Reference is “参考视频”, candidate is “待检视频”, start is “开始比较”, cancel is “取消”, and open report is “打开报告”. Reports are bilingual.

The output directory must not already exist. Videos are decoded at original coded resolution with no automatic resizing. The tool compares the first video stream (excluding attached cover art); audio is not assessed. Start offsets are zero-based; report frame numbers are one-based.

MAE measures average absolute RGB error on a 0–255 scale; lower is closer. PSNR is calculated from mean squared RGB error; higher is closer. JSON uses `null` for infinite/undefined PSNR and separately records whether decoded pixels are identical. Metrics do not assess intent, narrative, motion plausibility or subjective quality.

`PASS` only means the stated scope is within selected technical thresholds. `FAIL` means completed with differences. `ERROR` or `CANCELLED` means the run did not complete. Error runs do not turn into passing reports. Results are intended as evidence for human review.
