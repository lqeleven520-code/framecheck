import json
import os
import threading
from pathlib import Path

import pytest

from framecheck.cli import main
from framecheck.demo import generate_pair, run_demo
from framecheck.media import Cancelled, MediaError, find_tools


def test_demo_is_reproducible_and_reports_expected_differences(tmp_path):
    result = run_demo(tmp_path / "demo")
    assert result["status"] == "FAIL"
    assert result["scope"] == "whole_video"
    assert result["summary"]["compared_frames"] == 24
    assert result["summary"]["frames_over_threshold"] > 0
    assert (tmp_path / "demo/report/report.html").is_file()
    assert (tmp_path / "demo/media/reference.mkv").is_file()


def test_demo_refuses_existing_folder_and_honors_pre_cancel(tmp_path):
    folder = tmp_path / "existing"
    folder.mkdir()
    marker = folder / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(MediaError, match="already exists"):
        run_demo(folder)
    assert marker.read_text() == "keep"
    event = threading.Event()
    event.set()
    with pytest.raises(Cancelled):
        generate_pair(tmp_path / "cancelled", cancel=event)
    assert not (tmp_path / "cancelled").exists()


def test_demo_cli_success_is_distinct_from_intentional_report_fail(tmp_path, capsys):
    assert main(["demo", "-o", str(tmp_path / "demo")]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["demo_completed"] and data["expected_difference_detected"]
    assert data["report_status"] == "FAIL"
    assert Path(data["report"]).is_file()


def test_doctor_json_does_not_leak_local_tool_paths(capsys):
    assert main(["doctor", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "READY"
    assert set(data) == {"status", "framecheck", "python", "os", "ffmpeg", "ffprobe"}


def test_tool_discovery_accepts_portable_pair_without_path(tmp_path, monkeypatch):
    from framecheck import media
    monkeypatch.delenv("FRAMECHECK_FFMPEG", raising=False)
    monkeypatch.setattr(media.shutil, "which", lambda _: None)
    suffix = ".exe" if os.name == "nt" else ""
    decoder, probe = tmp_path / ("ffmpeg" + suffix), tmp_path / ("ffprobe" + suffix)
    decoder.touch()
    probe.touch()
    monkeypatch.setattr(media, "_additional_ffmpeg_candidates", lambda: [decoder])
    assert find_tools() == (str(decoder), str(probe))
    with pytest.raises(MediaError, match="FFmpeg not found"):
        find_tools(str(tmp_path / "explicit-missing"))
    probe.unlink()
    with pytest.raises(MediaError, match="ffprobe not found"):
        find_tools()
