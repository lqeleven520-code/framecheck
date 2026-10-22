import subprocess
from pathlib import Path

import pytest

from framecheck.media import find_tools, process_options


@pytest.fixture(scope="session")
def ffmpeg():
    return find_tools()[0]  # A missing decoder must fail CI, not silently skip media checks.


@pytest.fixture
def make_video(tmp_path, ffmpeg):
    def build(name="reference.mkv", size="80x48", rate=12, duration=1, filters=None):
        path = tmp_path / name
        cmd = [ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i",
               f"testsrc2=size={size}:rate={rate}:duration={duration}"]
        if filters:
            cmd += ["-vf", filters]
        subprocess.run(cmd + ["-c:v", "ffv1", "-an", str(path)], check=True, timeout=30,
                       **process_options())
        return Path(path)
    return build
