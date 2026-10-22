---
name: framecheck
description: Compare two local SDR videos frame by frame with FrameCheck and produce an offline HTML, CSV and JSON evidence report. Use for render/export regression checks, compression comparisons, frame-count or timing mismatches, and 视频逐帧对比、导出质检. This does not extract a video's story or shots, compare audio, or judge creative quality.
metadata:
  version: "0.2.1"
---

# FrameCheck video comparison

Use the FrameCheck source bundled in this skill to turn a reference/candidate pair into reproducible local evidence. The engine streams decoded RGB frames and actual presentation timestamps. Videos stay on the local machine. The runtime is inspectable Python source in `scripts/framecheck`; no separately downloaded FrameCheck wheel is required.

## Setup

Resolve the installed skill directory from the location of this `SKILL.md`. Use its `scripts/run_framecheck.py` helper with an appropriate Python 3.10+ interpreter. In the examples below, replace `<skill-directory>` with that observed absolute directory; keep reports in the user's working project, not inside the installed skill.

```bash
python "<skill-directory>/scripts/run_framecheck.py" --version
python "<skill-directory>/scripts/run_framecheck.py" doctor --json
```

If NumPy or Pillow is absent, install this skill's `requirements.txt` into the chosen virtual environment, then use that environment's Python for the helper. The dependencies match the public project's declared dependencies. Do not replace the bundled runtime with code fetched from an arbitrary URL.

```bash
python -m pip install -r "<skill-directory>/requirements.txt"
```

FFmpeg 5.1+ and ffprobe are external dependencies. Use the platform's package manager or the [official FFmpeg download links](https://ffmpeg.org/download.html). On Windows, `winget install --id Gyan.FFmpeg --exact` is supported. An explicit `--ffmpeg` path takes precedence; keep ffprobe beside it. Do not install into unrelated environments or change global configuration merely to run a comparison.

For a self-contained first run, use a new output folder:

```bash
python "<skill-directory>/scripts/run_framecheck.py" demo --output framecheck-demo-001
```

This generates synthetic videos with an intentional changed region. A successful demo command exits 0 while its report says FAIL; that difference is expected and is explained in the command output.

## Compare the requested pair

Identify which file is the reference and which is the candidate from the user's request. Preserve that order. Use a new report directory and quote paths containing spaces or non-ASCII characters:

```bash
python "<skill-directory>/scripts/run_framecheck.py" compare "reference.mp4" "candidate.mp4" --output "reports/check-001"
```

Use defaults unless the user or an established workflow specifies tolerances. The default maximum per-frame RGB MAE is 2.5 (0–255); the relative timing tolerance is 20 ms. These are configurable technical thresholds, not a perceptual-quality standard.

For a known frame offset, `--reference-start` and `--candidate-start` are zero-based. `--max-frames` limits work explicitly. These options yield `selected_range`, never a whole-video acceptance. The tool pairs frames by index and does not perform content alignment, resizing, optical flow or synchronization.

## Interpret the evidence

Read `result.json` and the relevant rows of `frames.csv`; use `report.html` and its preview images for visual inspection when available.

- Compare exits: 0 = PASS for the recorded scope; 1 = completed with differences; 2 = input/execution error; 130 = cancelled.
- Report the recorded `status`, `scope`, compared frame counts, timing mismatches and concrete reasons. An execution error or cancellation is not a quality verdict.
- Byte equality, decoded pixel equality and perceptual similarity are different facts. Infinite/undefined PSNR is represented as JSON null, with pixel equality recorded separately.
- The engine rejects HDR PQ/HLG inputs. It does not compare audio or determine whether a creative change is good or bad.
- Reports omit local absolute source paths, but contain file names, hashes and selected frames. Share a report or upload videos only within the user's requested scope; keep the whole report folder when sharing.

Deliver a short finding with a usable report link and meaningful examples of detected differences. If only a range was checked or visual inspection was unavailable, say so. Keep the original videos and existing reports untouched.

Project and installation help: [FrameCheck](https://github.com/lqeleven520-code/framecheck), [public demo](https://lqeleven520-code.github.io/framecheck/demo.html).
