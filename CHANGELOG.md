# Changelog

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
