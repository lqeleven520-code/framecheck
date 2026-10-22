"""Self-contained offline HTML with local evidence images and CSV links."""

from __future__ import annotations

import csv
import html
import math
from pathlib import Path


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def metric(value, suffix="") -> str:
    return "—" if value is None else f"{value:.3f}{suffix}"


def chart(output: Path, key: str, threshold: float, count: int) -> str:
    buckets = []
    step = max(1, math.ceil(count / 650))
    current = 0.0
    with (output / "frames.csv").open(encoding="utf-8", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream)):
            current = max(current, float(row[key]))
            if (index + 1) % step == 0:
                buckets.append(current)
                current = 0.0
        if count % step:
            buckets.append(current)
    if not buckets:
        return '<p class="muted">No comparable frames / 没有可比较的帧</p>'
    maximum = max(max(buckets), threshold, 0.01) * 1.1
    points = " ".join(f"{35 + i * 900 / max(1, len(buckets) - 1):.2f},{155 - v / maximum * 125:.2f}"
                      for i, v in enumerate(buckets))
    line_y = 155 - threshold / maximum * 125
    return f'''<svg viewBox="0 0 970 185" role="img" aria-label="{esc(key)} per-frame chart">
      <path d="M35 20V155H935" fill="none" stroke="#cad3df"/>
      <line x1="35" x2="935" y1="{line_y}" y2="{line_y}" stroke="#e06445" stroke-dasharray="5 5"/>
      <polyline points="{points}" fill="none" stroke="#187b75" stroke-width="2"/>
      <text x="38" y="17" fill="#607083" font-size="12">max {maximum:.3f}</text>
      <text x="35" y="177" fill="#607083" font-size="12">frame 1</text>
      <text x="850" y="177" fill="#607083" font-size="12">frame {count}</text>
    </svg>'''


def write_report(output: Path, data: dict) -> Path:
    s = data["summary"]
    status = data["status"]
    title = {"PASS": "Within thresholds / 指标通过", "FAIL": "Review differences / 发现差异",
             "ERROR": "Run incomplete / 执行未完成", "CANCELLED": "Cancelled / 已取消"}[status]
    scope = "Whole video / 整段视频" if data["scope"] == "whole_video" else "Selected range only / 仅所选范围"
    reasons = "".join(f"<li>{esc(reason)}</li>" for reason in data["reasons"])
    if not reasons:
        reasons = "<li>All compared frames are within the configured pixel and timing thresholds.<br>已比较的帧均在设置的像素与时间容差内。</li>"
    warnings = "".join(f"<li>{esc(warning)}</li>" for warning in data["warnings"])
    cards = []
    for item in data["previews"]:
        images = "".join(f'<figure><img loading="lazy" src="{esc(item[field])}" alt="{label}">'
                         f'<figcaption>{label}</figcaption></figure>' for field, label in (
                             ("reference_image", "Reference / 参考"),
                             ("candidate_image", "Candidate / 待检"),
                             ("difference_image", "Difference ×4 / 差异增强")))
        cards.append(f'''<article class="frame"><div class="frame-title"><strong>Frame {item['frame']}</strong>
          <span>参考 {item['reference_time_s']:.3f}s · 待检 {item['candidate_time_s']:.3f}s · MAE {item['mae']:.3f}</span>
          </div><div class="images">{images}</div></article>''')
    metadata = []
    for label, field in (("File / 文件", "name"), ("Dimensions / 编码尺寸", "dimensions"),
                         ("Frame rate / 平均帧率", "fps"), ("Duration / 时长", "duration"),
                         ("Rotation / 旋转标记", "rotation"), ("Codec / 编码", "codec"),
                         ("Audio streams / 音轨数", "audio_streams"), ("SHA-256", "sha256")):
        values = []
        for name in ("reference", "candidate"):
            meta = data[name]
            value = f"{meta['width']} × {meta['height']}" if field == "dimensions" else meta.get(field)
            values.append(f"<td>{esc(value if value is not None else 'Unknown')}</td>")
        metadata.append(f"<tr><th>{label}</th>{''.join(values)}</tr>")
    pixel_chart = chart(output, "mae", data["options"]["max_mae"], s["compared_frames"])
    time_chart = chart(output, "relative_timing_error_ms", data["options"]["max_timing_ms"], s["compared_frames"])
    psnr = "Identical pixels / 像素相同" if s["decoded_pixels_identical"] else metric(s["psnr_db"], " dB")
    content = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'">
    <title>FrameCheck — {esc(data['candidate']['name'])}</title>
    <style>
    :root{{color-scheme:light}}*{{box-sizing:border-box}}body{{margin:0;background:#f2f5f7;color:#203247;font:15px/1.6 system-ui,"Microsoft YaHei",sans-serif}}
    main{{max-width:1160px;margin:auto;padding:36px 24px 60px}}header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}}
    .logo{{font-size:24px;font-weight:800;letter-spacing:-.6px}}.logo b{{color:#187b75}}.muted,small{{color:#647487}}
    .hero{{background:#102c3b;color:#f0f7f9;padding:28px 32px;border-radius:18px}}.hero h1{{font-size:30px;margin:8px 0}}
    .hero p{{margin:0;opacity:.85}}.tag{{display:inline-block;border-radius:20px;padding:4px 12px;background:#d5f5e6;color:#14553f;font-size:12px;font-weight:700}}
    .tag.FAIL{{background:#ffecd2;color:#84450b}}.tag.ERROR,.tag.CANCELLED{{background:#fbe0df;color:#8f2930}}
    .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0}}.card,section{{background:white;border:1px solid #dce4e9;border-radius:14px;padding:22px}}
    .card strong{{display:block;font-size:25px;margin-top:5px}}.card small{{display:block}}section{{margin-top:20px}}h2{{font-size:18px;margin:0 0 14px}}h3{{font-size:14px}}
    ul{{padding-left:22px}}li{{margin:5px 0}}a{{color:#16766f;text-underline-offset:3px}}.links{{display:flex;gap:20px;flex-wrap:wrap;margin-top:16px}}
    svg{{width:100%;display:block}}.frame{{padding:18px 0;border-top:1px solid #e4eaef}}.frame-title{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}
    .frame-title span{{color:#647487;font-size:13px}}.images{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px}}figure{{margin:0}}
    img{{width:100%;display:block;background:#18222a;border-radius:8px}}figcaption{{font-size:12px;color:#647487;margin-top:6px}}
    .table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed}}th,td{{border-bottom:1px solid #e4eaef;padding:10px;text-align:left;overflow-wrap:anywhere}}th{{width:23%}}
    footer{{margin-top:24px;font-size:12px;color:#647487}}@media(max-width:700px){{main{{padding:20px 12px}}.grid{{grid-template-columns:repeat(2,1fr)}}.images{{grid-template-columns:1fr}}.hero{{padding:22px}}.hero h1{{font-size:23px}}}}
    </style></head><body><main>
    <header><div class="logo">Frame<b>Check</b></div><small>LOCAL VIDEO QA · v{esc(data['version'])}</small></header>
    <div class="hero"><span class="tag {status}">{status}</span><h1>{title}</h1>
    <p>{esc(data['reference']['name'])} → {esc(data['candidate']['name'])}</p><p>{scope}</p></div>
    <div class="grid"><div class="card"><small>Compared / 已比较</small><strong>{s['compared_frames']}</strong><small>参考 {s['reference_frames']} · 待检 {s['candidate_frames']} 帧</small></div>
    <div class="card"><small>Peak MAE / 最大像素误差</small><strong>{metric(s['max_mae'])}</strong><small>容差 {data['options']['max_mae']:g} / 255</small></div>
    <div class="card"><small>Timing / 最大时间误差</small><strong>{metric(s['max_timing_error_ms'], ' ms')}</strong><small>相对首帧的呈现时间</small></div>
    <div class="card"><small>PSNR / 峰值信噪比</small><strong style="font-size:18px">{psnr}</strong><small>RGB 8-bit comparison</small></div></div>
    <section><h2>Findings / 检查结果</h2><ul>{reasons}</ul><div class="links"><a href="frames.csv">逐帧 CSV</a><a href="result.json">完整 JSON</a></div>
    <p class="muted">逐帧编号从 1 开始；起始偏移设置从 0 开始。文件路径不写入报告，但文件名与截图仍可能含私人内容，请在分享前检查。</p></section>
    <section><h2>Difference timeline / 差异时间线</h2><h3>Pixel error (MAE) / 像素误差</h3>{pixel_chart}
    <h3>Presentation timing (ms) / 呈现时间差</h3>{time_chart}<p class="muted">橙色虚线为容差。长视频曲线按区间最大值压缩展示；完整数据保留在 CSV 中。</p></section>
    <section><h2>Largest visual differences / 最大画面差异</h2>{''.join(cards) or '<p class="muted">没有生成截图。</p>'}
    <p class="muted">截图为缩小预览，差异图亮度增强 4 倍；数值指标使用全部原始尺寸的已解码帧计算。</p></section>
    <section><h2>Source evidence / 源文件证据</h2><div class="table-wrap"><table><thead><tr><th>Property</th><td>Reference / 参考</td><td>Candidate / 待检</td></tr></thead><tbody>{''.join(metadata)}</tbody></table></div>
    <p>文件字节相同：{'是 / Yes' if data['byte_identical'] else '否 / No'}</p></section>
    <section><h2>Scope & limitations / 范围与限制</h2><ul>{warnings}</ul>
    <p>按帧序号配对，不自动对齐内容；时间差以各自首个所选帧为零点。没有音频质量、静音、剧情、人物一致性或主观观感验收。</p></section>
    <footer>Generated {esc(data['created_utc'])} · No uploads, accounts, cloud models or analytics / 全程本地，无上传与统计</footer>
    </main></body></html>'''
    target = output / "report.html"
    target.write_text(content, encoding="utf-8")
    return target
