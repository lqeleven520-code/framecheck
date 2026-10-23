import importlib
import json
import subprocess
import threading

import pytest

from framecheck.analysis_demo import generate_analysis_fixture, run_analysis_demo
from framecheck.analyze import AnalyzeOptions, analyze
from framecheck.media import Cancelled, MediaError, find_tools, probe_media, process_options
from framecheck.speech import parse_srt
from framecheck.storyboard import FIELDS, export_edited_notes
from framecheck.units import display_aspect, make_units


def test_known_cuts_motion_subtitles_and_editable_exports(tmp_path):
    result = run_analysis_demo(tmp_path / "demo")
    assert [s["start_frame"] for s in result["shots"]] == [0, 32, 64]
    assert [s["end_frame_exclusive"] for s in result["shots"]] == [32, 64, 96]
    assert [s["motion"]["kind"] for s in result["shots"]] == ["static", "pan_right", "zoom_in"]
    assert result["duration_s"] == pytest.approx(6, abs=0.001)  # Matroska timestamps have millisecond precision.
    assert result["transcript"]["source"] == "provided_srt"
    assert len(result["transcript"]["segments"]) == 3
    assert result["display_aspect"] == "16:9 横屏"
    report = tmp_path / "demo/report"
    for name in ("analysis.json", "shots.csv", "motion.csv", "transcript.srt", "transcript.txt",
                 "storyboard.json", "storyboard.csv", "storyboard.md", "breakdown.txt", "report.html"):
        assert (report / name).is_file()
    data = json.loads((report / "storyboard.json").read_text(encoding="utf-8"))
    assert len(data["units"]) == 1
    assert data["units"][0]["duration_s"] == pytest.approx(6, abs=0.001)
    text = (report / "breakdown.txt").read_text(encoding="utf-8")
    header = text.split("【整体导演设计】")[1].split("【参考对象】")[0].strip().splitlines()
    assert header == ["画面风格：未作视觉判读"]
    assert all(word not in text for word in ("镜间承接", "主要衔接方式", "制作交接", "影片基调", "导演意图"))
    assert "21:9" not in text
    assert set(data["shots"][0]["fields"]) == set(FIELDS)
    for unit in result["units"]:
        for frame in unit["keyframes"].values():
            assert (report / frame["path"]).is_file()


@pytest.mark.parametrize("duration", [0.4, 4, 14.9, 15, 15.1, 20, 30.1, 61.2, 120])
def test_units_cover_real_timeline_without_padding_or_fixed_fifteen_seconds(duration):
    shots = [{"id": 1, "start_s": 0, "end_s": duration}]
    units = make_units(shots, duration, [])
    assert units[0]["start_s"] == 0
    assert units[-1]["end_s"] == duration
    assert sum(u["duration_s"] for u in units) == pytest.approx(duration)
    for index, unit in enumerate(units):
        assert unit["duration_s"] <= 15
        assert unit["duration_s"] >= 4 or unit["short_source_exception"]
        if index:
            assert units[index - 1]["end_s"] == unit["start_s"]


def test_units_prefer_cuts_outside_dialogue_and_preserve_original_shots():
    shots = [{"id": 1, "start_s": 0, "end_s": 9}, {"id": 2, "start_s": 9, "end_s": 12},
             {"id": 3, "start_s": 12, "end_s": 24}]
    units = make_units(shots, 24, [{"start_s": 8, "end_s": 10}])
    assert units[0]["end_s"] == 12
    assert shots[0]["end_s"] == 9


def test_display_aspect_respects_rotation_and_non_square_pixels():
    assert display_aspect({"width": 1920, "height": 1080, "rotation": 90}) == "9:16 竖屏"
    assert display_aspect({"width": 720, "height": 576, "rotation": 0, "sample_aspect_ratio": "16:15"}) == "4:3 横屏"


def test_no_audio_does_not_load_whisper_and_no_output_is_overwritten(make_video, tmp_path):
    source = make_video()
    before = source.read_bytes()
    output = tmp_path / "analysis"
    result = analyze(source, output)
    assert result["status"] == "COMPLETE"
    assert result["transcript"]["status"] == "no_audio"
    assert result["units"][0]["short_source_exception"]
    with pytest.raises(MediaError, match="already exists"):
        analyze(source, output)
    assert source.read_bytes() == before


@pytest.mark.parametrize("offset", [0, 5])
def test_embedded_subtitles_align_with_nonzero_video_timestamps(tmp_path, ffmpeg, offset):
    video, subtitle = generate_analysis_fixture(tmp_path / "fixture")
    muxed = tmp_path / "with-subtitles.mkv"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-i", str(video), "-i", str(subtitle),
                    "-map", "0:v", "-map", "1:s", "-c", "copy", "-output_ts_offset", str(offset), str(muxed)],
                   check=True, timeout=30, **process_options())
    result = analyze(muxed, tmp_path / "report", AnalyzeOptions(transcript="subtitles"))
    assert result["status"] == "COMPLETE", result["transcript"]
    assert result["transcript"]["source"] == "embedded_subtitles"
    assert result["source_first_pts_s"] == pytest.approx(offset)
    assert result["transcript"]["segments"][0]["start_s"] == pytest.approx(0.2)


def test_transcription_failure_keeps_evidence_but_returns_partial(make_video, tmp_path, monkeypatch):
    module = importlib.import_module("framecheck.analyze")
    def fail(*args, **kwargs):
        raise MediaError("Model not available offline")
    monkeypatch.setattr(module, "extract_transcript", fail)
    result = analyze(make_video(), tmp_path / "partial")
    assert result["status"] == "PARTIAL"
    assert result["transcript"]["status"] == "unavailable"
    assert result["shots"]
    assert (tmp_path / "partial/report.html").is_file()


def test_cancel_stops_decoder_and_records_cancelled(make_video, tmp_path):
    event = threading.Event()
    def stop(message):
        if "Decoded" in message:
            event.set()
    with pytest.raises(Cancelled):
        analyze(make_video(duration=3), tmp_path / "cancelled", progress=stop, cancel=event)
    result = json.loads((tmp_path / "cancelled/analysis.json").read_text(encoding="utf-8"))
    assert result["status"] == "CANCELLED"
    assert result["decoded_frames"] < 36


def test_exported_clips_have_actual_shot_durations(tmp_path):
    video, subtitle = generate_analysis_fixture(tmp_path / "fixture")
    output = tmp_path / "clips-report"
    result = analyze(video, output, AnalyzeOptions(subtitles=str(subtitle), export_clips=True))
    _, probe = find_tools()
    for shot in result["shots"]:
        meta = probe_media(output / shot["clip"], probe)
        assert meta["duration"] == pytest.approx(2, abs=0.02)


def test_untrusted_subtitles_are_escaped_and_csv_safe(make_video, tmp_path):
    subtitle = tmp_path / "unsafe.srt"
    subtitle.write_text('1\n00:00:00,000 --> 00:00:00,800\n=1+1 </script><script>alert(1)</script>\n',
                        encoding="utf-8")
    output = tmp_path / "safe"
    analyze(make_video(), output, AnalyzeOptions(subtitles=str(subtitle)))
    html = (output / "report.html").read_text(encoding="utf-8")
    assert "</script><script>alert(1)" not in html
    assert "&lt;script&gt;alert(1)" in html
    assert "'=1+1" in (output / "storyboard.csv").read_text(encoding="utf-8-sig")


def test_srt_rejects_malformed_time_and_preserves_unicode():
    assert parse_srt('1\n00:00:01,000 --> 00:00:02,100\n<i>你好。</i>')[0]["text"] == "你好。"
    with pytest.raises(MediaError):
        parse_srt('1\n00:00:03,000 --> 00:00:02,100\nwrong')


def test_reviewed_notes_export_does_not_include_production_handoffs(tmp_path):
    run_analysis_demo(tmp_path / "demo")
    source = tmp_path / "demo/report/storyboard.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    data["units"][0]["visual_style"] = "程序生成的几何测试图案。"
    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    target = tmp_path / "reviewed.txt"
    export_edited_notes(source, target)
    assert "画面风格：程序生成的几何测试图案。" in target.read_text(encoding="utf-8")
    with pytest.raises(MediaError, match="already exists"):
        export_edited_notes(source, target)


def test_reviewed_notes_rejects_changed_unit_timing(tmp_path):
    run_analysis_demo(tmp_path / "demo")
    source = tmp_path / "demo/report/storyboard.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    data["units"][0]["duration_s"] = 25
    source.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(MediaError, match="timeline"):
        export_edited_notes(source, tmp_path / "invalid.txt")
