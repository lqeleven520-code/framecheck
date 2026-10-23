---
name: framecheck
description: Always start a new use by asking the user to choose A 解析视频 (default) or B 检查视频问题 and wait for their answer. Analyze a local SDR video into shots, motion, dialogue and editable 4–15 second breakdowns, or compare a reference/candidate pair. Use for 视频解析、拆分镜头、分析运镜、提取台词、视频检查 and export comparisons. Does not generate videos or supply a private production workflow.
metadata:
  version: "0.3.2"
  runtime_version: "0.3.0"
---

# FrameCheck video analysis and comparison

Use the inspectable FrameCheck source bundled in `scripts/framecheck` for local video analysis or pair comparison. No separately downloaded FrameCheck wheel is required.

## Required first step: ask A or B

At the beginning of **every new use of this skill**, ask the user this question and wait for their response:

> 请选择这次要使用的功能：
>
> **A｜解析视频（默认）**：拆分镜头、分析运镜、提取台词，输出逐片段解析。
>
> **B｜检查视频问题**：检查视频差异与技术问题，定位问题时间点。

This question is mandatory even if the initial request already says "analyze" or "check". Do not choose a mode from the wording, number of files or a previous task's choice. Do not inspect/process video, install dependencies, run a demo or begin either workflow before the user answers this question.

**A is the default.** With a question tool, put A first and preselect it if supported; otherwise label A as the default in chat. After the question, replies such as "默认", "按默认", "继续", "开始" or "解析视频" select A. A clear B/checking reply selects B. A preselected option is not a submitted answer: no reply means keep waiting, not automatic processing. Clarify a genuinely ambiguous reply rather than guessing.

After the answer:

- **A:** use `analyze` and the analysis guidance. The engine measures evidence; semantic descriptions require actual visual inspection.
- **B:** use `compare` for a reference/candidate pair. The current engine checks visual differences, frame counts and timing. If the required pair or its reference order is missing, explain this scope and request the missing input. Do not silently switch to A or claim comprehensive single-video problem detection.

Keep that choice while completing the same requested job, including its internal steps. A new use starts with the question again; do not reuse a previous job's choice.

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

Single-video analysis additionally needs `requirements-analysis.txt` (OpenCV). Local speech recognition needs `requirements-speech.txt` (faster-whisper). Install these with the same `python -m pip install -r` pattern only in the selected environment.

FFmpeg 5.1+ and ffprobe are external dependencies. Use the platform's package manager or the [official FFmpeg download links](https://ffmpeg.org/download.html). On Windows, `winget install --id Gyan.FFmpeg --exact` is supported. An explicit `--ffmpeg` path takes precedence; keep ffprobe beside it. Do not install into unrelated environments or change global configuration merely to run a comparison.

For a self-contained first run, use a new output folder:

```bash
python "<skill-directory>/scripts/run_framecheck.py" demo --output framecheck-demo-001
```

This generates synthetic videos with an intentional changed region. A successful demo command exits 0 while its report says FAIL; that difference is expected and is explained in the command output.

## Analyze one video

Read [analysis guidance](references/analysis.md) for the per-unit output format, evidence checks and visual interpretation.

```bash
python "<skill-directory>/scripts/run_framecheck.py" analyze "video.mp4" -o "reports/analysis-001"
python "<skill-directory>/scripts/run_framecheck.py" analyze-demo -o "analysis-demo-001"
```

Auto mode uses embedded text subtitles first, then local Whisper when audio exists. The first speech run downloads model weights from Hugging Face; use `--offline` for cached/local models only. Media is not uploaded by the CLI. `--subtitles file.srt` uses an existing UTF-8 SRT on the video's relative timeline; `--transcript none` intentionally skips dialogue. `--export-clips` creates an MP4 for each detected shot. The analysis demo uses synthetic geometry and supplied subtitles, not speech recognition.

Read `analysis.json`, `storyboard.json` and the report. Analysis exits: 0 = COMPLETE for the requested processing, 1 = PARTIAL (for example transcription failed), 2 = error, 130 = cancelled. Completion does not establish semantic accuracy. Keep the actual aspect and source timing; delivery units are 4–15 seconds, while original shot times remain unchanged.

The HTML report permits local note editing and export. To save an agent-reviewed result, copy `storyboard.json` to a new file, fill only supported text fields after inspection and render it:

```bash
python "<skill-directory>/scripts/run_framecheck.py" export-notes "storyboard-reviewed.json" -o "breakdown-reviewed.txt"
```

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
- The comparison engine rejects HDR PQ/HLG inputs. It does not compare audio waveforms or determine whether a creative change is good or bad. Analysis also requires SDR; it does not identify speakers or recover exact lenses.
- Reports omit local absolute source paths, but contain file names, hashes and selected frames. Share a report or upload videos only within the user's requested scope; keep the whole report folder when sharing.

Deliver a short finding with a usable report link and meaningful examples of detected differences. If only a range was checked or visual inspection was unavailable, say so. Keep the original videos and existing reports untouched.

Reports contain screenshots and dialogue. Sharing them follows the user's intended scope. Agent visual-inspection tools follow the chosen provider's privacy rules separately from the local CLI. Do not import private skills, production rules or examples into this skill or distributable reports.

Project and installation help: [FrameCheck](https://github.com/lqeleven520-code/framecheck), [public demo](https://lqeleven520-code.github.io/framecheck/demo.html).
