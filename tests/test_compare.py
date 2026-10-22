import csv
import json
import threading

import numpy as np
import pytest

from framecheck.cli import main
from framecheck.compare import Options, compare, pixel_metrics
from framecheck.media import Cancelled, MediaError, find_tools
from framecheck.report import write_report


def test_one_channel_delta_counts_as_changed_pixel():
    a = np.zeros((2, 2, 3), dtype=np.uint8)
    b = a.copy()
    b[0, 0, 2] = 1
    result = pixel_metrics(a, b)
    assert result["changed_pixels_percent"] == 25
    assert result["mae"] == pytest.approx(1 / 12)
    assert result["max_channel_delta"] == 1


@pytest.mark.parametrize("setting", [
    {"max_mae": -1}, {"max_mae": float("nan")}, {"max_mae": 256},
    {"max_timing_ms": -1}, {"max_timing_ms": float("inf")},
    {"max_frames": 0}, {"reference_start": -1}, {"candidate_start": -2}, {"previews": 31},
])
def test_invalid_thresholds_rejected(setting):
    with pytest.raises(MediaError):
        Options(**setting).validate()


def test_missing_ffmpeg_is_actionable(tmp_path):
    with pytest.raises(MediaError, match="FFmpeg not found"):
        find_tools(str(tmp_path / "not-installed.exe"))


def test_identical_video_passes_with_all_frames(make_video, tmp_path):
    source = make_video(name="中文 带空格.mkv")
    original = source.read_bytes()
    output = tmp_path / "report"
    result = compare(source, source, output)
    assert result["status"] == "PASS"
    assert result["scope"] == "whole_video"
    assert result["byte_identical"]
    assert result["summary"]["compared_frames"] == 12
    assert result["summary"]["max_mae"] == 0
    assert result["summary"]["psnr_db"] is None
    assert result["summary"]["decoded_pixels_identical"]
    assert source.read_bytes() == original
    assert str(tmp_path) not in (output / "result.json").read_text(encoding="utf-8")
    assert (output / "report.html").is_file()


def test_modified_region_fails_and_produces_evidence(make_video, tmp_path):
    a = make_video()
    b = make_video(name="changed.mkv", filters="drawbox=x=5:y=5:w=20:h=20:color=red:t=fill")
    output = tmp_path / "report"
    result = compare(a, b, output)
    assert result["status"] == "FAIL"
    assert result["summary"]["frames_over_threshold"] > 0
    assert result["summary"]["max_channel_delta"] > 0
    assert not result["byte_identical"]
    assert len(result["previews"]) == 8
    with (output / "frames.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 12
    assert float(rows[1]["reference_time_s"]) > 0
    for item in result["previews"]:
        assert (output / item["difference_image"]).is_file()


def test_missing_frames_cannot_pass(make_video, tmp_path):
    result = compare(make_video(), make_video(name="short.mkv", duration=0.5), tmp_path / "report")
    assert result["status"] == "FAIL"
    assert result["summary"]["reference_frames"] == 12
    assert result["summary"]["candidate_frames"] == 6
    assert any("frame counts" in reason for reason in result["reasons"])


def test_mismatched_resolution_is_reported_not_resized(make_video, tmp_path):
    result = compare(make_video(), make_video(name="large.mkv", size="96x64"), tmp_path / "report")
    assert result["status"] == "FAIL"
    assert result["summary"]["compared_frames"] == 0
    assert any("Resolution mismatch" in reason for reason in result["reasons"])


def test_timing_difference_uses_actual_pts(make_video, tmp_path):
    result = compare(make_video(), make_video(name="fast.mkv", rate=24, duration=0.5), tmp_path / "report",
                     Options(max_mae=255))
    assert result["summary"]["reference_frames"] == result["summary"]["candidate_frames"] == 12
    assert result["summary"]["timing_mismatch_frames"] > 0
    assert result["summary"]["max_timing_error_ms"] > 400
    assert result["status"] == "FAIL"


def test_frame_limit_is_explicitly_partial(make_video, tmp_path):
    source = make_video()
    result = compare(source, source, tmp_path / "report", Options(max_frames=4))
    assert result["status"] == "PASS"
    assert result["scope"] == "selected_range"
    assert result["summary"]["compared_frames"] == 4
    assert any("not a whole-video pass" in warning for warning in result["warnings"])


def test_offsets_are_zero_based_and_scope_is_recorded(make_video, tmp_path):
    source = make_video()
    output = tmp_path / "report"
    result = compare(source, source, output, Options(reference_start=2, candidate_start=2))
    assert result["status"] == "PASS"
    assert result["summary"]["compared_frames"] == 10
    assert result["scope"] == "selected_range"
    with (output / "frames.csv").open(encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert row["reference_frame"] == "3"


def test_empty_range_fails_without_crash(make_video, tmp_path):
    source = make_video()
    result = compare(source, source, tmp_path / "report", Options(reference_start=100, candidate_start=100))
    assert result["status"] == "FAIL"
    assert result["summary"]["compared_frames"] == 0


def test_existing_report_and_files_are_preserved(make_video, tmp_path):
    source = make_video()
    output = tmp_path / "keep"
    output.mkdir()
    marker = output / "personal.txt"
    marker.write_text("keep")
    with pytest.raises(MediaError, match="already exists"):
        compare(source, source, output)
    assert marker.read_text() == "keep"


def test_non_video_fails_instead_of_claiming_pass(tmp_path):
    source = tmp_path / "invalid.mp4"
    source.write_bytes(b"not a video")
    with pytest.raises(MediaError):
        compare(source, source, tmp_path / "report")
    assert not (tmp_path / "report" / "result.json").exists()


def test_cancellation_preserves_incomplete_status(make_video, tmp_path):
    source = make_video(duration=4)
    event = threading.Event()
    output = tmp_path / "report"
    def progress(message):
        if "Compared 1 frames" in message:
            event.set()
    with pytest.raises(Cancelled):
        compare(source, source, output, progress=progress, cancel=event)
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "CANCELLED"
    assert result["summary"]["compared_frames"] < 48


def test_report_escapes_untrusted_names(make_video, tmp_path):
    source = make_video()
    output = tmp_path / "report"
    result = compare(source, source, output, Options(previews=0))
    result["candidate"]["name"] = '</title><script>alert("x")</script>'
    write_report(output, result)
    text = (output / "report.html").read_text(encoding="utf-8")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "Content-Security-Policy" in text


def test_cli_exit_codes_distinguish_failure_from_error(make_video, tmp_path, capsys):
    source = make_video()
    changed = make_video(name="changed.mkv", filters="negate")
    assert main(["compare", str(source), str(source), "-o", str(tmp_path / "pass")]) == 0
    assert main(["compare", str(source), str(changed), "-o", str(tmp_path / "fail")]) == 1
    assert main(["compare", str(source), str(changed), "-o", str(tmp_path / "fail")]) == 2


def test_decode_error_cannot_leave_success_report(make_video, tmp_path, monkeypatch):
    import importlib
    engine = importlib.import_module("framecheck.compare")
    real_decoder = engine.Decoder
    class BrokenDecoder(real_decoder):
        def __next__(self):
            if getattr(self, "yielded", False):
                raise MediaError("Injected decoder failure")
            self.yielded = True
            return super().__next__()
    monkeypatch.setattr(engine, "Decoder", BrokenDecoder)
    source = make_video()
    output = tmp_path / "error-report"
    with pytest.raises(MediaError, match="Injected"):
        compare(source, source, output)
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "ERROR"
    assert not result["summary"]["decoded_pixels_identical"]


def test_network_playlist_is_rejected(tmp_path):
    source = tmp_path / "network.m3u8"
    source.write_text("#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nhttp://127.0.0.1:9/private.ts\n#EXT-X-ENDLIST\n")
    with pytest.raises(MediaError, match="not on whitelist"):
        compare(source, source, tmp_path / "report")
