"""Local subtitle extraction and an isolated, cancellable Whisper worker."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

from .media import Cancelled, MediaError, process_options

TEXT_SUBTITLES = {"subrip", "srt", "ass", "ssa", "webvtt", "mov_text", "text"}


def run_local(command, cancel: threading.Event, timeout: float = 120, env=None) -> str:
    process = subprocess.Popen([str(v) for v in command], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env, **process_options())
    started = time.monotonic()
    try:
        while True:
            if cancel.is_set():
                raise Cancelled("Analysis cancelled / 解析已取消")
            if time.monotonic() - started > timeout:
                raise MediaError("A local processing step timed out. Partial outputs are not a completed analysis.")
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise MediaError(stderr.decode("utf-8", "replace")[-1600:].strip() or "Local process failed.")
        return stdout.decode("utf-8", "replace")
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def timestamp(value: float, separator=",") -> str:
    ms = max(0, round(value * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{ms:03}"


def parse_srt(text: str) -> list[dict]:
    cues = []
    pattern = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
                         r"(\d+):(\d{2}):(\d{2})[,.](\d{3})(?:[^\n]*)\n([\s\S]*)")
    for block in re.split(r"\n\s*\n", text.lstrip("\ufeff").replace("\r\n", "\n").strip()):
        if not block.strip():
            continue
        match = pattern.search(block)
        if not match:
            raise MediaError("Invalid SRT cue. Use a UTF-8 SRT file with timestamps.")
        values = [int(v) for v in match.groups()[:8]]
        start, end = [values[i] * 3600 + values[i + 1] * 60 + values[i + 2] + values[i + 3] / 1000
                      for i in (0, 4)]
        if end <= start or any(values[i] > 59 for i in (1, 2, 5, 6)):
            raise MediaError("Invalid SRT time range.")
        content = re.sub(r"</?(?:i|b|u|font)(?:\s[^>]*)?>", "", match.group(9), flags=re.IGNORECASE).strip()
        if content:
            cues.append({"start_s": start, "end_s": end, "text": content})
    return sorted(cues, key=lambda row: (row["start_s"], row["end_s"]))


def write_transcript(output: Path, transcript: dict):
    segments = transcript.get("segments", [])
    (output / "transcript.srt").write_text("\n\n".join(
        f"{index}\n{timestamp(row['start_s'])} --> {timestamp(row['end_s'])}\n{row['text']}"
        for index, row in enumerate(segments, 1)) + ("\n" if segments else ""), encoding="utf-8")
    (output / "transcript.txt").write_text("\n".join(
        f"[{timestamp(row['start_s'], '.')} → {timestamp(row['end_s'], '.')}] {row['text']}"
        for row in segments) + ("\n" if segments else ""), encoding="utf-8")


def speech_worker(config_path: str) -> int:
    """Invoked only by our own child process; never downloads or executes model code."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    try:
        result = _recognize(config)
    except Exception as exc:  # noqa: BLE001 - A frozen worker must not open a traceback dialog.
        Path(config["result"]).write_text(json.dumps({"error": str(exc)}), encoding="utf-8")
        return 2
    Path(config["result"]).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return 0


def _recognize(config):
    if config["offline"]:
        os.environ["HF_HUB_OFFLINE"] = "1"
        if Path(config["model"]).is_dir() and not (Path(config["model"]) / "tokenizer.json").is_file():
            raise MediaError("Offline local models must include tokenizer.json; no fallback tokenizer download was used.")
    import numpy as np
    from faster_whisper import WhisperModel
    # FFmpeg already normalized PCM. Passing samples also avoids a second decoder
    # and PyAV-version-specific file-open options inside speech libraries.
    with wave.open(config["audio"], "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, 16000):
            raise MediaError("Expected mono 16 kHz signed 16-bit PCM audio.")
        audio = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").astype(np.float32) / 32768
    model = WhisperModel(config["model"], device="cpu", compute_type="int8",
                         local_files_only=config["offline"], cpu_threads=max(1, min(8, os.cpu_count() or 2)))
    segments, info = model.transcribe(audio, language=config["language"], beam_size=5,
                                     vad_filter=True, condition_on_previous_text=False, word_timestamps=True)
    rows = [{"start_s": segment.start, "end_s": segment.end, "text": segment.text.strip(),
             "avg_logprob": segment.avg_logprob, "no_speech_probability": segment.no_speech_prob,
             "needs_review": segment.avg_logprob < -0.8,
             "words": [{"start_s": word.start, "end_s": word.end, "text": word.word,
                        "probability": word.probability} for word in (segment.words or [])]}
            for segment in segments if segment.text.strip()]
    return {"status": "transcribed", "source": "local_whisper", "model": Path(config["model"]).name,
              "language": info.language, "language_probability": info.language_probability,
              "review_required": True, "segments": rows}


def extract_transcript(video: Path, output: Path, meta: dict, ffmpeg: str, options,
                       origin: float, duration: float, cancel, progress) -> dict:
    mode = options.transcript
    if mode == "none":
        return {"status": "skipped", "source": "none", "segments": []}
    transcript = None
    if options.subtitles:
        subtitle_path = Path(options.subtitles).expanduser().resolve()
        if subtitle_path.stat().st_size > 20_000_000:
            raise MediaError("SRT exceeds the 20 MB input limit.")
        transcript = {"status": "extracted", "source": "provided_srt", "review_required": True,
                      "segments": parse_srt(subtitle_path.read_text(encoding="utf-8-sig"))}
    elif mode in {"auto", "subtitles"}:
        tracks = [row for row in meta["subtitle_streams"] if row["codec"] in TEXT_SUBTITLES]
        if options.subtitle_stream is not None:
            tracks = [row for row in tracks if row["index"] == options.subtitle_stream]
            if not tracks:
                raise MediaError("Selected subtitle stream is absent or is not a text subtitle track.")
        if tracks:
            track = tracks[0]
            progress("Extracting embedded subtitles / 正在提取内嵌字幕…")
            text = run_local([ffmpeg, "-nostdin", "-v", "error", "-copyts",
                              "-protocol_whitelist", "file,pipe,crypto,data", "-i", video,
                              "-map", f"0:{track['index']}", "-c:s", "srt", "-f", "srt", "pipe:1"], cancel)
            rows = parse_srt(text)
            for row in rows:
                row["start_s"] -= origin
                row["end_s"] -= origin
            transcript = {"status": "extracted", "source": "embedded_subtitles", "stream": track,
                          "review_required": True, "segments": rows}
        elif mode == "subtitles":
            raise MediaError("No text subtitle track. Use local speech recognition or provide --subtitles file.srt.")
    if transcript is None:
        if not meta["audio_streams"]:
            return {"status": "no_audio", "source": "none", "segments": []}
        try:
            import importlib.util
            available = importlib.util.find_spec("faster_whisper") is not None
        except (ImportError, ValueError):
            available = False
        if not available:
            raise MediaError('Speech recognition needs "eleven-framecheck[speech]" '
                             'or the skill requirements-speech.txt. Shot and motion results remain available.')
        progress("Local speech recognition / 本地语音识别中（首次使用会下载模型，视频不会上传）…"
                 if not options.offline else "Local speech recognition / 正在使用已缓存模型…")
        with TemporaryDirectory(prefix=".speech-", dir=output) as folder:
            temp = Path(folder)
            audio, config_path, result_path = (temp / name for name in ("audio.wav", "config.json", "result.json"))
            filters = (f"atrim=start={origin:.9f}:end={origin + duration:.9f},"
                       f"asetpts=PTS-({origin:.9f})/TB,aresample=16000:async=1:first_pts=0")
            run_local([ffmpeg, "-nostdin", "-v", "error", "-copyts", "-protocol_whitelist", "file,pipe,crypto,data",
                       "-i", video, "-map", f"0:{options.audio_stream}" if options.audio_stream is not None
                       else "0:a:0", "-vn", "-sn", "-af", filters, "-ac", "1", "-ar", "16000",
                       "-t", str(duration), "-c:a", "pcm_s16le", audio], cancel, timeout=600)
            config_path.write_text(json.dumps({"audio": str(audio), "result": str(result_path),
                                              "model": options.model, "language": options.language,
                                              "offline": options.offline}), encoding="utf-8")
            if getattr(sys, "frozen", False):
                command = [sys.executable, "--speech-worker", str(config_path)]
                env = None
            else:
                command = [sys.executable, "-m", "framecheck.speech", str(config_path)]
                env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)}
            try:
                run_local(command, cancel, timeout=1800, env=env)
            except Cancelled:
                raise
            except MediaError:
                if result_path.exists():
                    failure = json.loads(result_path.read_text(encoding="utf-8"))
                    raise MediaError(failure.get("error", "Speech worker failed.")) from None
                raise
            transcript = json.loads(result_path.read_text(encoding="utf-8"))
    transcript["segments"] = [{**row, "start_s": round(max(0.0, row["start_s"]), 3),
                               "end_s": round(min(duration, row["end_s"]), 3)}
                              for row in transcript["segments"]
                              if row["end_s"] > 0 and row["start_s"] < duration]
    transcript["segments"] = [row for row in transcript["segments"] if row["end_s"] > row["start_s"]]
    return transcript


if __name__ == "__main__":
    raise SystemExit(speech_worker(sys.argv[1]))
