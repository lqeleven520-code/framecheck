from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

from . import __version__
from .compare import Options, compare
from .media import Cancelled, MediaError, tool_versions


def main(argv=None) -> int:
    # Windows redirected output can use a legacy code page. Keep its encoding,
    # but escape unsupported characters instead of failing a successful check.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="FrameCheck: local video comparison / 本地视频对比质检")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Check FFmpeg / 检查依赖")
    doctor.add_argument("--ffmpeg")
    doctor.add_argument("--json", action="store_true", help="Shareable version information without local paths")
    sub.add_parser("gui", help="Open desktop interface / 打开桌面界面")
    demo = sub.add_parser("demo", help="Generate and compare a synthetic video pair / 运行内置示例")
    demo.add_argument("--output", "-o", required=True, type=Path, help="New demo folder")
    demo.add_argument("--ffmpeg")
    run = sub.add_parser("compare", help="Compare two videos / 比较两个视频")
    run.add_argument("reference", type=Path)
    run.add_argument("candidate", type=Path)
    run.add_argument("--output", "-o", required=True, type=Path, help="New output folder (must not already exist)")
    run.add_argument("--max-mae", type=float, default=2.5)
    run.add_argument("--max-timing-ms", type=float, default=20)
    run.add_argument("--reference-start", type=int, default=0, help="Zero-based start frame")
    run.add_argument("--candidate-start", type=int, default=0, help="Zero-based start frame")
    run.add_argument("--max-frames", type=int)
    run.add_argument("--previews", type=int, default=8)
    run.add_argument("--ffmpeg", help="Path to ffmpeg executable (ffprobe should be beside it)")
    args = parser.parse_args(argv)
    try:
        if args.command == "gui":
            from .gui import main as gui_main
            gui_main()
            return 0
        if args.command == "doctor":
            versions = tool_versions(args.ffmpeg)
            if args.json:
                print(json.dumps({"status": "READY", "framecheck": __version__,
                                  "python": platform.python_version(), "os": platform.system(),
                                  **versions}, ensure_ascii=False, indent=2))
            else:
                print("\n".join(versions.values()))
                print("Ready / 依赖可用")
            return 0
        if args.command == "demo":
            from .demo import run_demo
            result = run_demo(args.output, args.ffmpeg, lambda message: print(message, file=sys.stderr))
            print(json.dumps({"demo_completed": True, "expected_difference_detected": True,
                              "report_status": result["status"], "compared_frames": 24,
                              "report": str(args.output.resolve() / "report" / "report.html")},
                             ensure_ascii=False, indent=2))
            return 0  # The intentional FAIL in this synthetic example is the expected result.
        options = Options(**{k: getattr(args, k) for k in Options.__dataclass_fields__})
        result = compare(args.reference, args.candidate, args.output, options,
                         progress=lambda msg: print(msg, file=sys.stderr))
        print(json.dumps({"status": result["status"], "scope": result["scope"],
                          "report": str(args.output.resolve() / "report.html"),
                          "summary": result["summary"]}, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "PASS" else 1
    except (MediaError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"FrameCheck: {exc}", file=sys.stderr)
        return 130 if isinstance(exc, Cancelled) else 2
    except KeyboardInterrupt:
        print("Interrupted / 已中断", file=sys.stderr)
        return 130
