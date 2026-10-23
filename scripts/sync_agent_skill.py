"""Bundle the reviewed public Python sources in the standalone agent skill."""
from __future__ import annotations

import ast
import re
import shutil
from pathlib import Path

MODULES = ("__init__.py", "__main__.py", "cli.py", "compare.py", "demo.py", "gui.py", "media.py",
           "report.py", "selftest.py", "analyze.py", "motion.py", "speech.py", "analysis_report.py",
           "analysis_demo.py", "storyboard.py", "units.py", "analysis_gui.py")


def sync():
    project = Path(__file__).resolve().parents[1]
    source = project / "src" / "framecheck"
    target = project / "skills" / "framecheck" / "scripts" / "framecheck"
    if {p.name for p in source.glob("*.py")} != set(MODULES):
        raise RuntimeError("Review the public module list before adding or removing bundled code.")
    if target.exists() and {p.name for p in target.glob("*.py")} - set(MODULES):
        raise RuntimeError("Stale bundled modules need explicit review; no files were deleted.")
    target.mkdir(parents=True, exist_ok=True)
    for name in MODULES:
        shutil.copy2(source / name, target / name)
    match = re.search(r"^dependencies\s*=\s*(\[[\s\S]*?\])",
                      (project / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise RuntimeError("Project dependencies were not found.")
    dependencies = ast.literal_eval(match.group(1))
    if not isinstance(dependencies, list) or not all(isinstance(d, str) for d in dependencies):
        raise RuntimeError("Review the dependency declarations.")
    (target.parent.parent / "requirements.txt").write_text("\n".join(dependencies) + "\n",
                                                         encoding="utf-8", newline="\n")
    config = (project / "pyproject.toml").read_text(encoding="utf-8")
    for name in ("analysis", "speech"):
        extra = re.search(r"^" + name + r"\s*=\s*(\[[\s\S]*?\])", config, re.MULTILINE)
        requirements = ast.literal_eval(extra.group(1))
        (target.parent.parent / f"requirements-{name}.txt").write_text(
            "-r requirements.txt\n" + "\n".join(requirements) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    sync()
