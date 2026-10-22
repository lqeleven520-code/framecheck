"""Generate original synthetic video pairs; does not download any media."""

from __future__ import annotations

import argparse
from pathlib import Path

from framecheck.demo import generate_pair


def make_demo(output: Path):
    generate_pair(output)
    print(output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="New folder")
    make_demo(parser.parse_args().output)
