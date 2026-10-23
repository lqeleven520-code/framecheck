# 安装 FrameCheck 技能包 / Install the agent skill

这个技能指导助手解析单个视频的镜头、运镜和台词，按原视频比例输出4—15秒的逐片段解析，也能比对两段视频。它不包含私人做剧流程或视频接续方法。画面风格、动作、神态等内容需要助手实际查看画面后填写。

## 使用时必须先选择用途

技能包 **0.3.1** 规定：每次开始新的使用任务，助手都必须先询问并等待回答，即使最初的需求已经写明“解析”或“检查”：

> 请选择这次要使用的功能：
>
> **A｜解析视频**：拆分镜头、分析运镜、提取台词，输出逐片段解析。
>
> **B｜检查视频问题**：检查视频差异与技术问题，定位问题时间点。

回答前不开始视频处理。选定后，同一任务内部不重复提问；新任务重新选择。B 当前需要参考视频与待检视频，不代表已经具备全面的单视频自动质检能力。

本次更新的是助手技能规则，附带的视频处理程序仍为0.3.0，功能和命令保持不变。已安装旧技能的人需要更新技能，旧ZIP不会自动改变。

## 用 skills CLI 安装

需要 Node.js 22.20 或以上版本。在你希望使用技能的项目目录运行：

```bash
npx skills add lqeleven520-code/framecheck --skill framecheck
```

按提示选择 Codex、Claude Code 或其他受支持的客户端。默认安装到当前项目；需要跨项目使用时才增加 `--global`。安装前只看技能列表：

```bash
npx skills add lqeleven520-code/framecheck --list
```

此命令会安装最新技能说明和随包的 FrameCheck Python 源码，无需再下载 FrameCheck wheel。运行需要 Python 3.10+、NumPy、Pillow 和 FFmpeg；用户选择A/B之后，技能才检查环境并准备所选功能的依赖。安装完成后可让助手执行：

> 使用 framecheck 比较这两个本地视频，参考视频是 A，待检视频是 B，把报告保存到一个新目录，并说明具体差异。

单视频解析可这样使用：

> 使用 framecheck 解析这个本地视频，拆镜头、估计运镜、提取台词。按原比例整理成4—15秒的单元，实际查看关键帧后补充画面内容，输出逐片段解析文本和报告。整体导演设计只保留画面风格，不加入视频衔接方法。

## 直接下载

从[技能0.3.1发布页](https://github.com/lqeleven520-code/framecheck/releases/tag/skill-v0.3.1)下载 `framecheck-skill-0.3.1.zip`。解压后将其中的 `framecheck` 文件夹放进客户端支持的技能目录，再重新载入技能。里面包含 `SKILL.md`、可阅读的运行源码、Python 依赖声明、界面元数据和 MIT 许可。

源码路径是 [`skills/framecheck`](../skills/framecheck)。不要把整个软件源码目录当作单个技能目录。

## 验证

独立技能不要求另外安装 FrameCheck。让助手定位技能目录后，在选定的 Python 虚拟环境中运行（将路径换成真实安装目录）：

```bash
python -m pip install -r "技能目录/requirements.txt"
python -m pip install -r "技能目录/requirements-analysis.txt"
# 无现有字幕、需要本地语音识别时再安装：
python -m pip install -r "技能目录/requirements-speech.txt"
python "技能目录/scripts/run_framecheck.py" doctor --json
python "技能目录/scripts/run_framecheck.py" demo -o framecheck-demo-001
python "技能目录/scripts/run_framecheck.py" analyze-demo -o analysis-demo-001
```

打开输出中的 `report/report.html`。示例故意加入红色色块，报告应发现差异；demo 命令正常结束返回 0。

解析示例包含3个合成镜头和已有字幕，不下载语音模型。正式视频没有文字字幕时默认使用本地语音识别；首次下载模型，`--offline` 可限制为已缓存模型。CLI不会上传媒体；助手查看画面的隐私范围由所选客户端决定。具体选项见[解析说明](ANALYSIS.md)。

Skills CLI is an independent open-source installer. Its current commands and supported agents are documented in [vercel-labs/skills](https://github.com/vercel-labs/skills). This project does not claim an official marketplace endorsement or guaranteed search-engine indexing.
