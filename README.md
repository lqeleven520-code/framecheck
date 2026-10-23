# FrameCheck

**本地视频解析、镜头拆分与对比工具 / Local video analysis and comparison.**

Analyze a single SDR video into shots, estimated camera motion, timed dialogue and editable 4–15 second breakdown units, or compare two videos frame by frame. Includes a Chinese desktop interface, CLI and offline reports. The CLI does not upload media or require an API key. Speech models download on first use; cached models work offline.

**Status:** v0.3.0, early public release. Technical metrics are not a guarantee of perceptual or creative quality. Independent adoption has not yet been established.

[![Tests](https://github.com/lqeleven520-code/framecheck/actions/workflows/tests.yml/badge.svg)](https://github.com/lqeleven520-code/framecheck/actions/workflows/tests.yml)

**[项目主页与在线示例 / Website & demo](https://lqeleven520-code.github.io/framecheck/)** · **[问题与使用反馈](https://github.com/lqeleven520-code/framecheck/issues/new/choose)**

| 你想怎样使用 | 直接入口 |
| --- | --- |
| Windows 桌面工具 | [下载 Windows x64 ZIP](https://github.com/lqeleven520-code/framecheck/releases/download/v0.3.0/FrameCheck-0.3.0-windows-x64.zip) |
| 先了解报告 | [无需安装，查看真实合成示例](https://lqeleven520-code.github.io/framecheck/demo.html) |
| Codex / Claude Code 技能 | [安装说明](docs/INSTALL_SKILL.md) · [技能 ZIP](https://github.com/lqeleven520-code/framecheck/releases/download/skill-v0.3.1/framecheck-skill-0.3.1.zip) |
| Python CLI / 自动化 | [下载 wheel](https://github.com/lqeleven520-code/framecheck/releases/download/v0.3.0/eleven_framecheck-0.3.0-py3-none-any.whl) |

支持单视频解析，也保留导出版本对比、压缩检查与渲染回归测试。运镜属于可核对的图像运动估计；画面内容、人物动作等语义字段由用户或具备视觉能力的助手结合实际画面补充。

## 单视频解析 / Analyze one video

Windows 桌面版点击 **“解析单个视频”**，选择文件后点“开始解析”；也可先运行不需要语音模型的“解析示例”。原来的双视频比较入口继续保留。

Python 从源码安装：

```bash
python -m pip install ".[analysis,speech]"
framecheck analyze-demo -o analysis-demo-001
framecheck analyze "video.mp4" -o analysis-001
# Existing UTF-8 SRT; no speech model needed:
framecheck analyze "video.mp4" --subtitles dialogue.srt -o analysis-002
# Only use cached/local speech models:
framecheck analyze "video.mp4" --model base --offline -o analysis-003
# Also export each detected shot as an MP4:
framecheck analyze "video.mp4" --export-clips -o analysis-004
```

自动模式先读取内嵌文字字幕，无字幕且有音轨时使用本地 Whisper。首次会下载模型（base 约 150 MB）；视频和音频不上传。可用 `--transcript none` 跳过台词，或用 `--model` 指定本地 CTranslate2 模型目录。图像字幕/OCR、说话人身份和声纹区分不在本版范围内。

输出 `report.html`、`analysis.json`、`shots.csv`、`motion.csv`、`transcript.srt`、`transcript.txt`、`storyboard.json/md/csv` 和 `breakdown.txt`。报告中的镜头备注可以编辑，再下载逐片段解析或 JSON；页面关闭前须导出修改。

- 画幅取原视频实际显示比例，处理旋转与像素比例，不固定为21:9。
- 解析单元按 **4—15秒** 组织，优先使用实际切点；原始镜头时长保留。视频不足4秒时保留真实时长，不补帧或拉长。
- 逐片段格式包含源区间、比例、时长、参考对象、首帧、逐镜时间轴和末帧观察；**整体导演设计只含画面风格**，没有基调或导演意图栏目。
- 不包含视频续接法、镜间承接指令、下一条起点、制作交接、私人技能或私人剧情示例。
- 运动拟合不能证明实际摄影机运动；快速动作、闪光、叠化和低纹理画面可能误检。台词识别也须核对。

自动引擎不编造人物动作、表情、风格或设备。语义备注默认未分析；可在报告中填写，或让视觉助手查看实际证据后完善。编辑导出的 JSON 后可运行：

```bash
framecheck export-notes storyboard-reviewed.json -o breakdown-reviewed.txt
```

分析退出码：0 = 所选流程完成；1 = 部分完成（如台词提取失败）；2 = 执行错误；130 = 已取消。COMPLETE 不表示人工内容验收。[解析说明](docs/ANALYSIS.md)

## 安装与使用

### Windows：桌面版

1. 从本仓库的 [Releases](https://github.com/lqeleven520-code/framecheck/releases) 下载 Windows 压缩包并解压全部文件。
2. 双击 `FrameCheck.exe`，点击“检查环境”。缺少 FFmpeg 时，运行包内的 `安装FFmpeg.cmd` 并按提示安装；也可从 [FFmpeg 官方下载入口](https://ffmpeg.org/download.html) 获取对应系统版本。
3. 第一次使用可直接点“运行内置示例”。检查自己的素材时，选择“参考视频”“待检视频”和报告保存位置，点击“开始比较”。
4. 完成后点击“打开报告”。分享报告时请将整个报告目录一起打包，保留 `images` 子目录。

安装包不捆绑 FFmpeg，也不会静默下载。程序会查找 PATH、标准 WinGet 目录以及桌面程序旁的 `ffmpeg/bin`。自动查找失败时，可在界面选择 `ffmpeg.exe`；`ffprobe.exe` 应与其位于同一目录。Windows 程序暂未购买代码签名证书；请核对 Release 来源与校验和，遵循系统安全提示。

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

不需要克隆仓库，也可以在虚拟环境中直接安装已发布的 wheel：

```bash
python -m pip install "eleven-framecheck[analysis,speech] @ https://github.com/lqeleven520-code/framecheck/releases/download/v0.3.0/eleven_framecheck-0.3.0-py3-none-any.whl"
framecheck doctor
framecheck demo -o demo-001
```

`demo-001/report/report.html` 是生成的报告。示例故意加入差异：**demo 命令退出 0，报告 FAIL 是预期结果**。输入自己的视频时，`compare` 的退出码仍按下方规则执行。包目前从 GitHub Releases 分发，不要求 PyPI 账号。

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

## Agent skill / 安装技能

**技能包0.3.1：每次新任务必须先选A/B。** 助手首先询问“A｜解析视频”或“B｜检查视频问题”，等待用户回答后才开始，即使原始需求已写明用途也必须询问。同一任务的内部步骤不重复问，新任务重新选择。B当前使用参考视频与待检视频进行技术对比；附带的处理程序仍为0.3.0。

With Node.js 22.20+, run this in the project where you want the skill:

```bash
npx skills add lqeleven520-code/framecheck --skill framecheck
```

Choose a supported agent such as Codex or Claude Code. The skill includes the same inspectable runtime source. It supports single-video breakdowns and pair comparisons; semantic descriptions require actual visual inspection by the agent. Python 3.10+, base dependencies and FFmpeg are required; analysis adds OpenCV, speech adds faster-whisper. [Installation instructions](docs/INSTALL_SKILL.md).

## What is checked

- Original coded resolution, display rotation metadata, decoded frame counts and presentation timestamps.
- Full-resolution RGB MAE, changed pixels, maximum channel difference and RGB PSNR.
- SHA-256 of both original files, separate from decoded visual equality.
- Offline report: difference timelines, worst-frame reference/candidate/difference images, CSV and JSON.
- The engine streams frames instead of extracting the entire video as PNG files. Only a small set of previews is retained.

Time is normalized to the first selected frame in each file. Frame pairing is by index, not automatic content alignment. To compensate for a known frame offset, select a start frame explicitly. Timestamps are read from FFmpeg; no estimated frame/fps timestamps are substituted.

## Limitations / 使用边界

- FrameCheck is intended for SDR render comparisons and regression checks. HDR inputs with PQ/HLG metadata are rejected. RGB conversion is 8-bit; this is not a mastering-grade HDR or color-fidelity validator.
- A pixel mismatch can be intentional. Compression, color conversion, noise, grading and different framing affect the metrics. Choose thresholds for your workflow; defaults are not an industry certification.
- No audio waveform comparison, silence detection, semantic consistency checks, motion-quality score, SSIM or VMAF in this release. Audio stream counts are informational.
- Variable frame rate can produce a timing difference even when average FPS looks similar; inspect the frame CSV. No optical-flow matching or automatic resynchronization is performed.
- File names and selected video frames appear in reports. Local absolute paths are omitted, but reports can still contain private content. Inspect before publishing.
- Up to 40 million coded pixels per frame. Decoding very long/high-resolution videos takes time. Use a frame limit for initial investigation; the scope is recorded honestly.
- macOS/Linux CI is configured. Only runs actually visible in Actions establish those platforms' test status; a workflow file alone is not a passing result.

## Reproducible demo

```bash
python -m pip install ".[dev,analysis]"
framecheck demo -o demo-001
# Generates local synthetic videos and a report; no media download needed.
python -m pytest
```

The demo uses generated geometric patterns, not private or third-party videos. See [English quick start](docs/QUICKSTART.md), [contributing](CONTRIBUTING.md), and [provenance](PROVENANCE.md).

## Build a Windows executable

```powershell
python -m pip install ".[bundle,analysis,speech]"
python -m PyInstaller --noconfirm --clean --onedir --windowed --name FrameCheck --collect-all faster_whisper --collect-all ctranslate2 --collect-all onnxruntime --collect-all tokenizers --copy-metadata huggingface-hub --copy-metadata tqdm scripts/desktop.py
python scripts/bundle_notices.py dist/FrameCheck
```

Distribute the **whole** `dist/FrameCheck` directory. FFmpeg remains an external dependency. See [third-party notices](THIRD_PARTY_NOTICES.md).

Maintainers: run `python scripts/sync_agent_skill.py` after changing the runtime. Packaging tests verify that the skill contains the same source and dependency declarations.

## Feedback / 使用反馈

Try the built-in demo, then a small pair from your actual workflow. If installation fails or the evidence is confusing, [open a report](https://github.com/lqeleven520-code/framecheck/issues/new/choose) with the steps and `framecheck doctor --json` output. The version output omits local paths. Send only files and report contents you intend to make public.

## License

MIT for FrameCheck. Dependencies retain their own licenses. FFmpeg is not included in the Python package or Windows bundle. No affiliation with or endorsement by OpenAI is implied.
