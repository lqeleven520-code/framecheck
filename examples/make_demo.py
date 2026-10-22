"""Generate original synthetic video pairs; does not download any media."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from framecheck.media import find_tools, process_options


def make_demo(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    ffmpeg, _ = find_tools()
    source = "testsrc2=size=320x180:rate=12:duration=2"
    for name, filters in (("reference", []), ("changed", ["-vf", "drawbox=x=30:y=30:w=80:h=50:color=red:t=fill"])):
        subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", source,
                        *filters, "-c:v", "ffv1", "-an", str(output / f"{name}.mkv")],
                       check=True, timeout=60, **process_options())
    print(output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="New folder")
    make_demo(parser.parse_args().output)
