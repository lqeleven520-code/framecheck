from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .compare import Options, compare
from .media import Cancelled, MediaError, find_tools, process_options


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FrameCheck: local video comparison / 本地视频对比质检")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Check FFmpeg / 检查依赖")
    doctor.add_argument("--ffmpeg")
    sub.add_parser("gui", help="Open desktop interface / 打开桌面界面")
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
            paths = find_tools(args.ffmpeg)
            for name, path in zip(("ffmpeg", "ffprobe"), paths):
                result = subprocess.run([path, "-version"], check=False, capture_output=True, text=True,
                                        timeout=10, **process_options())
                if result.returncode:
                    raise MediaError(f"{name} did not run successfully.")
                print(result.stdout.splitlines()[0])
            print("Ready / 依赖可用")
            return 0
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
