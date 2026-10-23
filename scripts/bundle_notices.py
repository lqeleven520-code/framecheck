"""Collect actual installed dependency license files into a Windows bundle."""

from __future__ import annotations

import importlib.metadata
import json
import shutil
import sys
from pathlib import Path


def collect(destination: Path):
    notices = destination / "licenses"
    notices.mkdir(parents=True, exist_ok=True)
    versions = {}
    for name in ("numpy", "Pillow", "pyinstaller", "altgraph", "packaging", "pywin32-ctypes",
                 "opencv-python-headless", "faster-whisper", "ctranslate2", "av", "onnxruntime",
                 "huggingface-hub", "tokenizers", "tqdm", "pyyaml", "flatbuffers", "protobuf",
                 "filelock", "fsspec", "hf-xet", "httpx2", "httpcore2", "anyio", "idna", "h11",
                 "truststore", "typing-extensions", "click", "colorama"):
        dist = importlib.metadata.distribution(name)
        versions[name] = dist.version
        selected = [item for item in (dist.files or []) if item.suffix not in (".pyc", ".pyo")
                    and (any(word in item.name.lower() for word in ("license", "licence", "copyright", "copying", "notice"))
                         or "licenses" in item.parts)]
        count = 0
        for item in selected:
            path = Path(dist.locate_file(item))
            if path.is_file():
                target = notices / name / str(item).replace("..", "_")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                count += 1
        if not count:
            fallback = Path(__file__).resolve().parents[1] / "third_party" / f"{name}-{dist.version}-LICENSE"
            if fallback.is_file():
                (notices / name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(fallback, notices / name / "LICENSE")
            else:
                raise RuntimeError(f"No license files found for {name}; review before distributing.")
    base = Path(sys.base_prefix)
    python_license = base / "LICENSE.txt"
    if not python_license.exists():
        raise RuntimeError("Python runtime license is missing.")
    shutil.copy2(python_license, notices / "Python-LICENSE.txt")
    for name in ("tcl8.6", "tk8.6"):
        license_path = base / "tcl" / name / "license.terms"
        if name == "tcl8.6" and not license_path.exists():
            import tkinter
            if tkinter.Tcl().eval("info patchlevel") == "8.6.15":
                license_path = Path(__file__).resolve().parents[1] / "third_party" / "Tcl-8.6.15-license.terms"
        if not license_path.exists():
            raise RuntimeError(f"Missing Tcl/Tk notice: {name}")
        shutil.copy2(license_path, notices / f"{name}-license.terms")
    project = Path(__file__).resolve().parents[1]
    for name in ("FFmpeg-LGPLv3", "FFmpeg-GPLv3", "additional-license-sources.json"):
        shutil.copy2(project / "third_party" / name, notices / name)
    for name in ("LICENSE", "README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(project / name, destination / name)
    installer = project / "scripts" / "安装FFmpeg.cmd"
    (destination / installer.name).write_text(installer.read_text(encoding="utf-8"),
                                              encoding="utf-8", newline="\r\n")
    (notices / "versions.json").write_text(json.dumps({"python": sys.version, **versions}, indent=2) + "\n",
                                         encoding="utf-8")


if __name__ == "__main__":
    collect(Path(sys.argv[1]))
