# Provenance

FrameCheck was developed from two local utilities supplied by Eleven: `compare_videos.py` and `verify_frame_sequence.py` from the `rn-replica-qc` toolkit. Eleven requested their adaptation into a standalone open-source project on 2026-10-22. The original local files were left unchanged.

The original approach combined media probing, file hashes, full-frame pixel comparisons and evidence reports. This project replaces the original disk-heavy PNG workflow and Unix `cmp` dependency with streaming FFmpeg decoders and Python hashing, adds actual frame presentation timestamps, packaging, a desktop interface, privacy-conscious offline reports and regression tests. The original optional baseline/temporal-neighbor and SSIM features are not advertised as implemented in this release.

No source code from FFMetrics or pixop/video-compare is included. They were reviewed only as existing products in the space. No drama scripts, private project assets, account information, machine paths or personal workflow rules are included.

Development used AI coding assistance. Maintainer review and the actual published test results, rather than code generation alone, establish the tested behavior. No independent user count or download count is claimed at first release.

`docs/source-fingerprints.json` records hashes of the two supplied input utilities for traceability, without copying the originals or their machine-specific locations.
