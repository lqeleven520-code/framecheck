"""A self-contained readable index of machine evidence; no external scripts or uploads."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from .speech import timestamp
from .storyboard import EDITOR_SCRIPT, make_storyboard


def write_analysis_report(output: Path, result: dict):
    e = lambda value: escape(str(value), quote=True)
    transcript = result["transcript"]
    cards = []
    for shot in result["shots"]:
        dialogue = "".join(f"<p><time>{timestamp(transcript['segments'][i]['start_s'], '.')}</time> "
                           f"{e(transcript['segments'][i]['text'])}</p>" for i in shot["dialogue"])
        clip = f'<a href="{e(shot["clip"])}">打开镜头片段 / Clip</a>' if shot.get("clip") else ""
        cards.append(f'''<article id="shot-{shot['id']}"><div><img src="{e(shot['keyframe'])}"
          alt="镜头 {shot['id']} 的第一帧" loading="lazy"><p class="muted">第一帧 / First frame ·
          {timestamp(shot['keyframe_time_s'], '.')}</p></div><div><h2>镜头 / Shot {shot['id']:03}</h2>
          <p class="time">{timestamp(shot['start_s'], '.')} → {timestamp(shot['end_s'], '.')} ·
          {shot['duration_s']:.2f} s</p><p><strong>{e(shot['motion']['label'])}</strong></p>
          <p class="muted">拟合支持分数 / Fit support: {shot['motion']['confidence']:.2f} ·
          {shot['motion']['valid_pairs']}/{shot['motion']['sample_pairs']} 有效采样对
          （不是正确率 / not accuracy）</p><div class="dialogue">{dialogue or '<p>此段无提取到的台词 / No extracted dialogue</p>'}</div>
          {clip}<details><summary>补充视觉解析 / Edit shot notes</summary><div class="notes"></div></details>
          </div></article>''')
    warnings = "".join(f"<li>{e(item)}</li>" for item in result["warnings"] + result["limitations"])
    transcript_error = f'<p class="notice">{e(transcript["error"])}</p>' if transcript.get("error") else ""
    storyboard_data = json.dumps(make_storyboard(result), ensure_ascii=False).replace("<", "\\u003c")
    unit_cards = []
    for unit in result["units"]:
        images = ''.join(f'<figure><img src="{e(frame["path"])}" alt="片段 {unit["id"]} {e(label)}">'
                         f'<figcaption>{e(label)} · {timestamp(frame["time_s"], ".")}</figcaption></figure>'
                         for label, frame in unit["keyframes"].items())
        unit_cards.append(f'<section class="unit" id="unit-{unit["id"]}"><h2>解析片段 {unit["id"]:02} · '
                          f'{unit["duration_s"]:.2f} 秒</h2><p>{timestamp(unit["start_s"], ".")} → '
                          f'{timestamp(unit["end_s"], ".")} · {e(result["display_aspect"])}</p>'
                          f'<div class="gallery">{images}</div><details><summary>画面风格与片段观察备注</summary>'
                          '<div class="unit-notes"></div></details></section>')
    html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>FrameCheck 视频解析 · {e(result['source']['name'])}</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f3f6f8;color:#203247;font:16px/1.6 system-ui,sans-serif}}
    main{{max-width:1100px;margin:auto;padding:32px 22px}}header{{margin-bottom:28px}}h1{{font-size:34px;line-height:1.25}}
    h2{{font-size:23px;margin:0 0 10px}}a{{color:#087d73}}nav{{display:flex;flex-wrap:wrap;gap:18px}}
    article{{display:grid;grid-template-columns:minmax(240px,42%) 1fr;gap:25px;background:white;border:1px solid #dce4e8;
    border-radius:15px;margin:20px 0;padding:22px}}img{{width:100%;height:auto;border-radius:8px}}p{{margin:8px 0}}
    .muted{{color:#637487;font-size:13px}}.time,time{{font-variant-numeric:tabular-nums}}.status{{display:inline-block;
    border-radius:6px;padding:4px 10px;background:#d7eee7;color:#205a47;font-weight:700}}.notice{{background:#fff2d6;
    border-left:4px solid #bb8021;padding:13px;overflow-wrap:anywhere}}.dialogue{{border-top:1px solid #e5eaee;margin:12px 0;
    padding-top:10px;white-space:pre-wrap}}li{{margin:7px 0}}code{{overflow-wrap:anywhere}}
    textarea{{display:block;width:100%;font:inherit;padding:8px;border:1px solid #b9c9d3;border-radius:5px}}
    label{{display:block;margin:12px 0}}button{{padding:9px 15px;margin:8px 8px 8px 0;cursor:pointer}}
    .unit{{padding:22px;background:white;border-radius:12px;margin:20px 0}}.gallery{{display:grid;
    grid-template-columns:repeat(3,1fr);gap:12px}}figure{{margin:0}}figcaption{{font-size:12px;color:#637487}}
    @media(max-width:720px){{article{{grid-template-columns:1fr}}main{{padding:20px 14px}}h1{{font-size:28px}}}}
    </style><main><header><p>FRAMECHECK {e(result['version'])} · 本地视频解析 / Local video analysis</p>
    <h1>{e(result['source']['name'])}</h1><span class="status">{e(result['status'])}</span>
    <p>{len(result['shots'])} 个检测镜头 · {result['decoded_frames']} 帧 · {result['duration_s']:.2f} 秒 ·
    范围 / Scope: {e(result['scope'])}</p><p>台词来源 / Transcript source: <strong>{e(transcript['source'])}</strong> ·
    状态 / Status: {e(transcript['status'])}</p>
    <p class="notice">镜头边界与运镜属于自动估计，请结合画面核对；台词可能有错字、漏字。COMPLETE 表示所选处理流程完成，
    不代表内容经过人工验收。这里不生成剧情、私人制作流程或复刻提示词。</p>{transcript_error}
    <nav><a href="analysis.json">JSON</a><a href="shots.csv">镜头表 CSV</a><a href="motion.csv">运动证据 CSV</a>
    <a href="transcript.srt">字幕 SRT</a><a href="transcript.txt">台词 TXT</a>
    <a href="storyboard.md">解析镜头表 Markdown</a><a href="storyboard.csv">解析镜头表 CSV</a>
    <a href="breakdown.txt">逐片段解析 TXT</a></nav>
    <p class="muted">展开每个镜头的“补充视觉解析”可填写画面、动作、神态和光影。空白表示未分析，不能当作识别结论。
    修改只留在当前页面，关闭前请导出。</p>
    <button id="save-breakdown">导出逐片段解析</button><button id="save-notes-md">导出编辑后的镜头表</button>
    <button id="save-notes-json">导出编辑数据 JSON</button>
    <p id="save-status" class="muted" role="status"></p></header>
    <h2>按 4—15 秒组织的解析单元</h2><p class="muted">按原视频实际比例与时间整理，优先选择切点。原视频不足4秒时保留真实时长。
    下方仍保留原始镜头边界，不把每个镜头硬改成固定长度。</p>{''.join(unit_cards)}
    <h2>原始镜头与台词</h2>{''.join(cards)}<details><summary>方法、限制与执行提示 / Methods & limitations</summary><ul>{warnings}</ul>
    <p>Source SHA-256: <code>{e(result['source']['sha256'])}</code></p>
    <p>基于逐帧 HSV 变化检测硬切；稀疏光流与 RANSAC 估计整体画面运动。快速运动、闪光、叠化、移动主体、
    遮挡或低纹理画面均可能影响结果。镜头末帧时长依据相邻时间戳估计。</p></details>
    <footer class="muted">视频处理留在本机。分享此报告会公开文件名、关键帧及台词，请按需分享整个目录。</footer>
    </main><script type="application/json" id="storyboard-data">{storyboard_data}</script>
    <script>{EDITOR_SCRIPT}</script></html>'''
    (output / "report.html").write_text(html, encoding="utf-8")
