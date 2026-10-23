"""Generic editable shot notes. No private production prompts or continuity rules."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .media import MediaError
from .speech import timestamp

FIELDS = ("景别／视角", "机位／运镜", "摄影参数", "画面内容", "人物动作", "人物神态", "台词／声音", "场景光影")


def make_storyboard(result: dict) -> dict:
    source = result["source"]
    fps = f"{source['fps']:.3f}" if source["fps"] else "unknown"
    rows = []
    for shot in result["shots"]:
        dialogue = "\n".join(result["transcript"]["segments"][i]["text"] for i in shot["dialogue"])
        fields = dict.fromkeys(FIELDS, "")
        fields.update({"机位／运镜": shot["motion"]["label"],
                       "摄影参数": f"{source['width']}×{source['height']}；{fps} fps；焦段、光圈与机位未测定",
                       "台词／声音": dialogue})
        rows.append({"shot": shot["id"], "start_s": shot["start_s"], "end_s": shot["end_s"],
                     "keyframe": shot["keyframe"], "fields": fields,
                     "motion_source": "algorithm_estimate", "dialogue_source": result["transcript"]["source"]})
    return {"schema_version": 1, "source_name": source["name"], "source_sha256": source["sha256"],
            "aspect": result["display_aspect"], "units": result["units"],
            "transcript_source": result["transcript"]["source"],
            "notice": "空白视觉字段表示未分析。可结合关键帧/片段填写；运镜为估计，台词需核对。", "shots": rows}


def storyboard_markdown(data: dict) -> str:
    # Indented blocks preserve user text without allowing it to break out of code fences.
    parts = ["# 视频解析镜头表", "", data["notice"], ""]
    for row in data["shots"]:
        parts += [f"## 镜号 {row['shot']:03} · {timestamp(row['start_s'], '.')} → {timestamp(row['end_s'], '.')}", ""]
        for key in FIELDS:
            value = row["fields"].get(key, "") or "未标注"
            parts += [f"**{key}**", "", *["    " + line for line in value.splitlines()], ""]
    return "\n".join(parts)


def breakdown_text(data: dict) -> str:
    blocks = []
    shots = {row["shot"]: row for row in data["shots"]}
    for unit in data["units"]:
        lines = [f"【视频解析｜片段{unit['id']:02}】",
                 f"源视频区间：{timestamp(unit['start_s'], '.')}—{timestamp(unit['end_s'], '.')}",
                 f"画幅：{data['aspect']}", f"总时长：{unit['duration_s']:.3f}秒",
                 f"台词来源：{data.get('transcript_source', 'unknown')}", "",
                 "【整体导演设计】", "画面风格：" + (unit["visual_style"] or "未作视觉判读"), "",
                 "【参考对象】", *[key + "：" + (value or "未作视觉判读")
                                  for key, value in unit["references"].items()], "",
                 "【空间与首帧】", "首帧可见空间与主体：" + (unit["first_frame_notes"] or "未作视觉判读"), "",
                 "【分镜时间轴】"]
        for index, fragment in enumerate(unit["shots"], 1):
            row = shots[fragment["shot_id"]]
            suffix = "（原镜头的部分范围）" if fragment["partial_original_shot"] else ""
            lines += [f"镜号{index:02}｜时间：{fragment['start_s']:.3f}—{fragment['end_s']:.3f}秒{suffix}"]
            lines += [key + "：" + (row["fields"].get(key) or "未作视觉判读") for key in FIELDS]
            lines.append("")
        lines += ["【本片段结束画面】", "末帧可见画面：" + (unit["last_frame_notes"] or "未作视觉判读")]
        if unit["short_source_exception"]:
            lines += ["注：原视频不足4秒，保留实际时长，没有补帧或拉长。"]
        if unit["speech_crosses_boundary"]:
            lines += ["注：有台词跨越本片段边界；请以字幕原时间轴核对，不把整句重复当作再次发声。"]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def write_storyboard(output: Path, result: dict):
    data = make_storyboard(result)
    (output / "storyboard.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "storyboard.md").write_text(storyboard_markdown(data), encoding="utf-8")
    (output / "breakdown.txt").write_text(breakdown_text(data), encoding="utf-8")
    with (output / "storyboard.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["镜号", "开始秒", "结束秒", *FIELDS])
        for row in data["shots"]:
            values = [row["fields"][key] for key in FIELDS]
            safe = ["'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value for value in values]
            writer.writerow([row["shot"], row["start_s"], row["end_s"], *safe])


def export_edited_notes(source: Path, output: Path):
    """Render notes exported by this tool. Paths inside the JSON are never opened."""
    if output.exists():
        raise MediaError("Output file already exists. Choose a new filename.")
    if source.stat().st_size > 16_000_000:
        raise MediaError("Edited notes exceed the 16 MB limit.")
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    try:
        if data["schema_version"] != 1 or not isinstance(data["aspect"], str):
            raise ValueError("Unsupported notes schema")
        ids = set()
        for shot in data["shots"]:
            if shot["shot"] in ids or set(shot["fields"]) != set(FIELDS):
                raise ValueError("Keep the original shot IDs and field names")
            ids.add(shot["shot"])
            if not all(isinstance(value, str) and len(value) <= 100_000 for value in shot["fields"].values()):
                raise ValueError("Shot notes must be text")
        end = 0.0
        for unit in data["units"]:
            if (abs(unit["start_s"] - end) > 0.001 or not 0 < unit["duration_s"] <= 15.001
                    or abs(unit["end_s"] - unit["start_s"] - unit["duration_s"]) > 0.001):
                raise ValueError("Keep the original contiguous 4–15 second unit timeline")
            if unit["duration_s"] < 4 and not (unit["short_source_exception"] and len(data["units"]) == 1):
                raise ValueError("Only a source shorter than four seconds may produce a short unit")
            end = unit["end_s"]
            for key in ("visual_style", "first_frame_notes", "last_frame_notes"):
                if not isinstance(unit[key], str) or len(unit[key]) > 100_000:
                    raise ValueError("Unit notes must be text")
            if set(unit["references"]) != {"场景", "出场人物", "道具"}:
                raise ValueError("Keep the reference field names")
            if not all(isinstance(v, str) for v in unit["references"].values()):
                raise ValueError("References must be text")
            if any(fragment["shot_id"] not in ids for fragment in unit["shots"]):
                raise ValueError("Unknown shot ID")
        text = breakdown_text(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise MediaError(f"Invalid edited notes: {exc}. Edit text fields in the exported storyboard.json.") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(text)


EDITOR_SCRIPT = r'''
const data = JSON.parse(document.getElementById('storyboard-data').textContent);
const names = ['景别／视角','机位／运镜','摄影参数','画面内容','人物动作','人物神态','台词／声音','场景光影'];
for (const unit of data.units) {
  const box = document.querySelector('#unit-' + unit.id + ' .unit-notes');
  const fields = [['画面风格',unit,'visual_style'],['场景',unit.references,'场景'],
    ['出场人物',unit.references,'出场人物'],['道具',unit.references,'道具'],
    ['首帧可见空间与主体',unit,'first_frame_notes'],['末帧可见画面',unit,'last_frame_notes']];
  for (const [name, target, key] of fields) {
    const label = document.createElement('label'); label.textContent = name;
    const input = document.createElement('textarea'); input.rows = 2; input.value = target[key];
    input.placeholder = '仅填写从画面实际观察到的内容';
    input.addEventListener('input', () => { target[key] = input.value; });
    label.appendChild(input); box.appendChild(label);
  }
}
for (const shot of data.shots) {
  const box = document.querySelector('#shot-' + shot.shot + ' .notes');
  for (const name of names) {
    const label = document.createElement('label'); label.textContent = name;
    const input = document.createElement('textarea'); input.rows = 2; input.value = shot.fields[name];
    input.placeholder = '未自动分析，可根据画面补充 / Optional visual note';
    input.addEventListener('input', () => { shot.fields[name] = input.value; });
    label.appendChild(input); box.appendChild(label);
  }
}
function download(name, type, text) {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  document.getElementById('save-status').textContent = '已发起下载；请保留下载文件。页面关闭后不会保存未导出的修改。';
}
document.getElementById('save-notes-json').onclick = () => download('storyboard-edited.json','application/json',JSON.stringify(data,null,2));
document.getElementById('save-breakdown').onclick = () => {
  const blocks = [], shots = new Map(data.shots.map(s => [s.shot,s]));
  for (const unit of data.units) {
    const lines = ['【视频解析｜片段' + unit.id + '】','源视频区间：' + unit.start_s + '—' + unit.end_s + '秒',
      '画幅：' + data.aspect,'总时长：' + unit.duration_s + '秒','台词来源：' + data.transcript_source,'','【整体导演设计】',
      '画面风格：' + (unit.visual_style || '未作视觉判读'),'','【参考对象】',
      ...Object.entries(unit.references).map(([k,v]) => k + '：' + (v || '未作视觉判读')),'',
      '【空间与首帧】','首帧可见空间与主体：' + (unit.first_frame_notes || '未作视觉判读'),'','【分镜时间轴】'];
    unit.shots.forEach((fragment,index) => {
      const shot = shots.get(fragment.shot_id);
      lines.push('镜号' + (index+1) + '｜时间：' + fragment.start_s + '—' + fragment.end_s + '秒',
        ...names.map(name => name + '：' + (shot.fields[name] || '未作视觉判读')),'');
    });
    lines.push('【本片段结束画面】','末帧可见画面：' + (unit.last_frame_notes || '未作视觉判读'));
    if (unit.short_source_exception) lines.push('注：原视频不足4秒，保留实际时长。');
    if (unit.speech_crosses_boundary) lines.push('注：台词跨越片段边界，请按原字幕时间轴核对。');
    blocks.push(lines.join('\n'));
  }
  download('breakdown-edited.txt','text/plain',blocks.join('\n\n'));
};
document.getElementById('save-notes-md').onclick = () => {
  const lines = ['# 视频解析镜头表','',data.notice,''];
  for (const shot of data.shots) {
    lines.push('## 镜号 ' + shot.shot + ' · ' + shot.start_s + ' → ' + shot.end_s + ' 秒','');
    for (const name of names) lines.push('**' + name + '**','',...(shot.fields[name] || '未标注').split('\n').map(t => '    ' + t),'');
  }
  download('storyboard-edited.md','text/markdown',lines.join('\n'));
};
'''
