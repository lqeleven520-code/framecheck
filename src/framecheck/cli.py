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
    parser = argparse.ArgumentParser(description="FrameCheck: local video comparison and analysis / 视频对比与解析")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Check FFmpeg / 检查依赖")
    doctor.add_argument("--ffmpeg")
    doctor.add_argument("--json", action="store_true", help="Shareable version information without local paths")
    sub.add_parser("gui", help="Open desktop interface / 打开桌面界面")
    demo = sub.add_parser("demo", help="Generate and compare a synthetic video pair / 运行内置示例")
    demo.add_argument("--output", "-o", required=True, type=Path, help="New demo folder")
    demo.add_argument("--ffmpeg")
    analysis_demo = sub.add_parser("analyze-demo", help="Run a synthetic shot-analysis example / 运行解析示例")
    analysis_demo.add_argument("--output", "-o", required=True, type=Path)
    analysis_demo.add_argument("--ffmpeg")
    analysis = sub.add_parser("analyze", help="Detect shots, estimate motion and extract dialogue / 解析单个视频")
    analysis.add_argument("video", type=Path)
    analysis.add_argument("--output", "-o", required=True, type=Path)
    analysis.add_argument("--threshold", type=float, default=27.0)
    analysis.add_argument("--min-shot-seconds", type=float, default=0.35)
    analysis.add_argument("--analysis-size", type=int, default=480)
    analysis.add_argument("--motion-fps", type=float, default=8.0)
    analysis.add_argument("--transcript", choices=["auto", "subtitles", "asr", "none"], default="auto")
    analysis.add_argument("--subtitles", help="Use an existing UTF-8 SRT on the video's relative timeline")
    analysis.add_argument("--subtitle-stream", type=int, help="Absolute ffprobe subtitle stream index")
    analysis.add_argument("--audio-stream", type=int, help="Absolute ffprobe audio stream index for speech")
    analysis.add_argument("--model", default="base", help="Whisper name or local CTranslate2 model directory")
    analysis.add_argument("--language", help="Speech language code, such as zh or en; default: auto")
    analysis.add_argument("--offline", action="store_true", help="Use cached/local speech models; never download")
    analysis.add_argument("--export-clips", action="store_true", help="Re-encode each detected shot as MP4")
    analysis.add_argument("--max-frames", type=int)
    analysis.add_argument("--ffmpeg")
    notes = sub.add_parser("export-notes", help="Export reviewed storyboard JSON as per-unit text / 导出逐片段解析")
    notes.add_argument("notes", type=Path)
    notes.add_argument("--output", "-o", required=True, type=Path)
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
        if args.command == "export-notes":
            from .storyboard import export_edited_notes
            export_edited_notes(args.notes, args.output)
            print(str(args.output.resolve()))
            return 0
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
        if args.command in {"analyze", "analyze-demo"}:
            from .analyze import AnalyzeOptions, analyze
            progress = lambda message: print(message, file=sys.stderr)
            if args.command == "analyze-demo":
                from .analysis_demo import run_analysis_demo
                result = run_analysis_demo(args.output, args.ffmpeg, progress)
                report = args.output.resolve() / "report" / "report.html"
            else:
                settings = AnalyzeOptions(**{key: getattr(args, key) for key in AnalyzeOptions.__dataclass_fields__})
                result = analyze(args.video, args.output, settings, progress)
                report = args.output.resolve() / "report.html"
            print(json.dumps({"status": result["status"], "scope": result["scope"], "shots": len(result["shots"]),
                              "transcript": result["transcript"]["status"], "report": str(report)},
                             ensure_ascii=False, indent=2))
            return 0 if result["status"] == "COMPLETE" else 1
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
