# Contributing

Install with `python -m pip install ".[dev]"`; ensure FFmpeg and ffprobe are on PATH. Run `python -m pytest` and `python -m ruff check src tests examples` before opening a pull request.

Useful contributions include reproducible decoder issues, Windows/macOS/Linux installation fixes, accessibility and localization, and better evidence reports. File an issue with OS, Python/FrameCheck/FFmpeg versions, the exact command and a small non-private synthetic reproduction. Do not upload someone else's video, access tokens or personal report contents.

Tests must distinguish `PASS`, `FAIL`, partial scope and execution errors. Never silently rescale, drop frames, auto-align or accept incomplete decoding. New visual metrics must document what they measure and what they do not.

By contributing, you agree your contribution is licensed under the repository's MIT license. Retain attribution and dependency notices. No contributor agreement is required beyond that license.
