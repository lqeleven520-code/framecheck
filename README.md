# FrameCheck

**本地视频对比与质检工具 / Local video comparison with evidence.**

Compare two SDR videos frame by frame, find visual and timing differences, and share an offline HTML report. Includes a Chinese desktop interface, a CLI, per-frame CSV and JSON results. No account, API key, uploads or telemetry.

**Status:** v0.1.0, early public release. Technical metrics are not a guarantee of perceptual or creative quality. Independent adoption has not yet been established.

## 安装与使用

### Windows：桌面版

1. 从本仓库的 [Releases](https://github.com/lqeleven520-code/framecheck/releases) 下载 Windows 压缩包并解压全部文件。
2. 安装 FFmpeg：终端运行 `winget install --id Gyan.FFmpeg --exact`，完成后重新打开软件。也可从 [FFmpeg 官方下载入口](https://ffmpeg.org/download.html) 获取对应系统版本。
3. 双击 `FrameCheck.exe`，选择“参考视频”“待检视频”和报告保存位置，点击“开始比较”。
4. 完成后点击“打开报告”。分享报告时请将整个报告目录一起打包，保留 `images` 子目录。

安装包不捆绑 FFmpeg。自动查找失败时，可在界面选择 `ffmpeg.exe`；`ffprobe.exe` 应与其位于同一目录。Windows 程序暂未购买代码签名证书；不要绕过来源不明的安全提示，请核对官方 Release 文件与校验和。

### Python：Windows / macOS / Linux

需要 Python 3.10+、FFmpeg 5.1+ 和 ffprobe。建议使用虚拟环境：

```bash
git clone https://github.com/lqeleven520-code/framecheck.git
cd framecheck
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
python -m pip install .
framecheck doctor
framecheck gui
```

亦可在虚拟环境中直接安装 Release 附带的 `.whl` 文件：`python -m pip install 路径/eleven_framecheck-0.1.0-py3-none-any.whl`。

macOS 可使用 `brew install ffmpeg`；Debian/Ubuntu 可使用 `sudo apt install ffmpeg python3-tk python3-venv`。桌面界面需要 Python 的 Tk 支持；CLI 不需要显示环境。

## Command line / 命令行

```bash
framecheck compare reference.mp4 candidate.mp4 --output reports/run-001
# Chinese names and spaces are supported: quote each path.
framecheck compare "参考 视频.mp4" "修改 视频.mp4" -o "报告/第一次"
# Explicitly limited scope (report will NOT claim a whole-video pass):
framecheck compare ref.mp4 new.mp4 -o reports/range --candidate-start 2 --max-frames 120
```

Output directories must be new. The app never deletes or overwrites existing reports or source videos.

| Option | Default | Meaning |
| --- | --- | --- |
| `--max-mae` | 2.5 | Maximum allowed per-frame RGB mean absolute error, range 0–255 |
| `--max-timing-ms` | 20 | Maximum relative presentation-time difference in milliseconds |
| `--reference-start`, `--candidate-start` | 0 | Zero-based source start frame |
| `--max-frames` | all | Restrict decoded frame range; explicitly labeled partial |
| `--previews` | 8 | Number of worst-frame thumbnails, 0–30 |
| `--ffmpeg` | PATH | Explicit FFmpeg executable; or use `FRAMECHECK_FFMPEG` |

Exit codes: **0** = metrics within thresholds for the stated scope; **1** = completed with differences; **2** = execution/input error; **130** = interrupted/cancelled. `PASS` on a partial run is not acceptance of the full file.

## What is checked

- Original coded resolution, display rotation metadata, decoded frame counts and presentation timestamps.
- Full-resolution RGB MAE, changed pixels, maximum channel difference and RGB PSNR.
- SHA-256 of both original files, separate from decoded visual equality.
- Offline report: difference timelines, worst-frame reference/candidate/difference images, CSV and JSON.
- The engine streams frames instead of extracting the entire video as PNG files. Only a small set of previews is retained.

Time is normalized to the first selected frame in each file. Frame pairing is by index, not automatic content alignment. To compensate for a known frame offset, select a start frame explicitly. Timestamps are read from FFmpeg; no estimated frame/fps timestamps are substituted.

## Limitations / 使用边界

- v0.1 is intended for SDR render comparisons and regression checks. HDR inputs with PQ/HLG metadata are rejected. RGB conversion is 8-bit; this is not a mastering-grade HDR or color-fidelity validator.
- A pixel mismatch can be intentional. Compression, color conversion, noise, grading and different framing affect the metrics. Choose thresholds for your workflow; defaults are not an industry certification.
- No audio waveform comparison, silence detection, semantic consistency checks, motion-quality score, SSIM or VMAF in this release. Audio stream counts are informational.
- Variable frame rate can produce a timing difference even when average FPS looks similar; inspect the frame CSV. No optical-flow matching or automatic resynchronization is performed.
- File names and selected video frames appear in reports. Local absolute paths are omitted, but reports can still contain private content. Inspect before publishing.
- Up to 40 million coded pixels per frame. Decoding very long/high-resolution videos takes time. Use a frame limit for initial investigation; the scope is recorded honestly.
- macOS/Linux CI is configured. Only runs actually visible in Actions establish those platforms' test status; a workflow file alone is not a passing result.

## Reproducible demo

```bash
python -m pip install ".[dev]"
python examples/make_demo.py --output demo-media
framecheck compare demo-media/reference.mkv demo-media/changed.mkv -o reports/demo
# A FAIL result (exit 1) is expected: the candidate has an intentional changed region.
python -m pytest
```

The demo uses generated geometric patterns, not private or third-party videos. See [English quick start](docs/QUICKSTART.md), [contributing](CONTRIBUTING.md), and [provenance](PROVENANCE.md).

## Build a Windows executable

```powershell
python -m pip install ".[bundle]"
python -m PyInstaller --noconfirm --clean --onedir --windowed --name FrameCheck scripts/desktop.py
```

Distribute the **whole** `dist/FrameCheck` directory. FFmpeg remains an external dependency. See [third-party notices](THIRD_PARTY_NOTICES.md).

## License

MIT for FrameCheck. Dependencies retain their own licenses. FFmpeg is not included in the Python package or Windows bundle. No affiliation with or endorsement by OpenAI is implied.
