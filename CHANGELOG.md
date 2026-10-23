# Changelog

## 0.2.1 — 2026-10-23

- Bundle inspectable FrameCheck source in the agent skill, with a local entrypoint and dependency file; remove the separate FrameCheck wheel download from the skill workflow.
- Verify the skill runtime and dependency declarations stay synchronized with the public app.
- Reuse installed FFmpeg in Linux CI and bound package-manager network waits.

## 0.2.0 — 2026-10-23

- Add a one-command and desktop first-run demo using synthetic video pairs.
- Find portable FFmpeg folders and normal per-user Windows WinGet installations.
- Add desktop dependency checks and shareable `doctor --json` output.
- Publish an independent FrameCheck agent skill with direct installation instructions.
- Add a public download/demo page, installation guidance and structured feedback forms.

## 0.1.1 — 2026-10-22

- Fix CLI failures when Windows pipes use a legacy encoding that cannot print Chinese text.
- Preserve Unicode report paths as JSON escapes without changing the configured console encoding.
- Add subprocess regression checks for dependency diagnosis and Chinese-path comparison under CP1252.

## 0.1.0 — 2026-10-22

- First standalone release derived from local frame-comparison utilities.
- Streaming RGB frame comparison, actual presentation timestamps, hash and metadata evidence.
- Chinese desktop UI, CLI with documented exit codes and explicit partial-run scope.
- Offline bilingual HTML report, difference previews, CSV and JSON.
- Synthetic-media regression tests and cross-platform CI configuration.
# 0.3.0 — Video analysis

- Add single-video shot detection, local motion estimates and optional MP4 shot export.
- Extract embedded or supplied text subtitles; add local CPU Whisper transcription with cancellation and an offline option.
- Add editable shot notes and per-unit text export. Units follow actual aspect and timing, normally 4–15 seconds; the overall-design section contains only visual style. No production handoffs or video continuation methods.
- Add a desktop analysis window, synthetic example, agent analysis guidance and standalone skill dependencies.
- Preserve double-video comparison behavior. Record incomplete transcription as PARTIAL rather than reporting success.
