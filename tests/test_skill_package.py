import ast
import re
import subprocess
import sys
from pathlib import Path

from framecheck import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_skill_bundles_the_same_public_runtime_and_dependencies():
    source = ROOT / "src/framecheck"
    skill = ROOT / "skills/framecheck"
    bundled = skill / "scripts/framecheck"
    assert {p.name for p in bundled.glob("*.py")} == {p.name for p in source.glob("*.py")}
    for path in source.glob("*.py"):
        assert (bundled / path.name).read_bytes() == path.read_bytes(), path.name
    match = re.search(r"^dependencies\s*=\s*(\[[\s\S]*?\])",
                      (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE)
    assert match
    assert (skill / "requirements.txt").read_text().splitlines() == ast.literal_eval(match.group(1))


def test_skill_entrypoint_runs_from_an_unrelated_directory(tmp_path):
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "skills/framecheck/scripts/run_framecheck.py"), "--version"],
        cwd=tmp_path, capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == __version__
