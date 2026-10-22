# 安装 FrameCheck 技能包 / Install the agent skill

这个技能指导 AI 编程助手调用 FrameCheck，比对两段本地视频并解释报告。它不包含私人做剧流程，不拆解单个视频的剧情或分镜。

## 用 skills CLI 安装

需要 Node.js 22.20 或以上版本。在你希望使用技能的项目目录运行：

```bash
npx skills add lqeleven520-code/framecheck --skill framecheck
```

按提示选择 Codex、Claude Code 或其他受支持的客户端。默认安装到当前项目；需要跨项目使用时才增加 `--global`。安装前只看技能列表：

```bash
npx skills add lqeleven520-code/framecheck --list
```

此命令安装的是技能说明。实际比较仍需要 Python 版 FrameCheck 和 FFmpeg，技能会先检查环境并提供安装步骤。安装完成后可让助手执行：

> 使用 framecheck 比较这两个本地视频，参考视频是 A，待检视频是 B，把报告保存到一个新目录，并说明具体差异。

## 直接下载

从 [Releases](https://github.com/lqeleven520-code/framecheck/releases) 下载 `framecheck-skill-0.2.0.zip`。解压后将其中的 `framecheck` 文件夹放进客户端支持的技能目录，再重新载入技能。里面包含 `SKILL.md`、界面元数据和 MIT 许可。

源码路径是 [`skills/framecheck`](../skills/framecheck)。不要把整个软件源码目录当作单个技能目录。

## 验证

在已安装 Python 工具的环境运行：

```bash
framecheck doctor --json
framecheck demo -o framecheck-demo-001
```

打开输出中的 `report/report.html`。示例故意加入红色色块，报告应发现差异；demo 命令正常结束返回 0。

Skills CLI is an independent open-source installer. Its current commands and supported agents are documented in [vercel-labs/skills](https://github.com/vercel-labs/skills). This project does not claim an official marketplace endorsement or guaranteed search-engine indexing.
