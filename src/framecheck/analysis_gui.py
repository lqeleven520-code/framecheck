"""Desktop entry for single-video analysis; all worker status is explicit."""
from __future__ import annotations

import queue
import threading
import uuid
import webbrowser
from pathlib import Path

from .analysis_demo import run_analysis_demo
from .analyze import AnalyzeOptions, analyze
from .media import Cancelled, MediaError, find_tools


class AnalysisApp:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.root = root
        root.title("FrameCheck · 单视频解析")
        root.geometry("900x760")
        root.minsize(800, 700)
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="视频解析 · 镜头 / 运镜 / 台词", font=("Microsoft YaHei UI", 20, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(frame, text="按原视频比例，整理为 4—15 秒解析单元。保留实际镜头时间，生成可编辑镜头表。",
                  wraplength=810).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 15))
        self.video = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / "FrameCheck Reports"))
        self.ffmpeg = tk.StringVar()
        self.subtitles = tk.StringVar()
        self.controls = []
        for row, title, variable, kind in ((2, "视频文件", self.video, "video"),
                                           (3, "报告保存位置", self.destination, "directory"),
                                           (4, "现有 SRT（可选）", self.subtitles, "srt"),
                                           (5, "FFmpeg（可选）", self.ffmpeg, "executable")):
            ttk.Label(frame, text=title).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=8)
            entry = ttk.Entry(frame, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew")
            button = ttk.Button(frame, text="选择…", command=lambda v=variable, k=kind: self.choose(v, k))
            button.grid(row=row, column=2, padx=(10, 0))
            self.controls += [entry, button]
        options = ttk.Frame(frame)
        options.grid(row=6, column=0, columnspan=3, sticky="w", pady=12)
        self.mode = tk.StringVar(value="auto")
        self.model = tk.StringVar(value="base")
        self.language = tk.StringVar(value="auto")
        for col, (label, variable, values) in enumerate((
            ("台词：auto 自动 / none 关闭", self.mode, ("auto", "subtitles", "asr", "none")),
            ("语音模型（越大越慢）", self.model, ("tiny", "base", "small", "medium")),
            ("语言：auto / zh / en", self.language, ("auto", "zh", "en")),
        )):
            box = ttk.Frame(options)
            box.grid(row=0, column=col, padx=(0, 15), sticky="w")
            ttk.Label(box, text=label).pack(anchor="w")
            entry = ttk.Combobox(box, textvariable=variable, values=values, width=24)
            entry.pack(anchor="w", pady=5)
            self.controls.append(entry)
        self.offline = tk.BooleanVar(value=False)
        self.export_clips = tk.BooleanVar(value=False)
        for row, label, variable in ((7, "只用已缓存或本地模型（不下载）", self.offline),
                                     (8, "另导出每个检测镜头的 MP4（耗时与磁盘占用增加）", self.export_clips)):
            check = ttk.Checkbutton(frame, text=label, variable=variable)
            check.grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            self.controls.append(check)
        ttk.Label(frame, text="自动模式优先读取内嵌字幕；没有字幕时在本机识别语音。首次识别会从 Hugging Face 下载模型"
                  "（base 约 150 MB），不上传视频。自动结果需要核对，空白视觉字段可在报告中补充。",
                  wraplength=810).grid(row=9, column=0, columnspan=3, sticky="w", pady=14)
        actions = ttk.Frame(frame)
        actions.grid(row=10, column=0, columnspan=3, sticky="w")
        self.start_button = ttk.Button(actions, text="开始解析", command=self.start)
        self.demo_button = ttk.Button(actions, text="运行解析示例", command=self.start_demo)
        self.cancel_button = ttk.Button(actions, text="取消", command=self.cancel, state="disabled")
        self.report_button = ttk.Button(actions, text="打开报告", command=self.open_report, state="disabled")
        for button in (self.start_button, self.demo_button, self.cancel_button, self.report_button):
            button.pack(side="left", padx=(0, 10))
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(18, 10))
        self.status = tk.StringVar(value="就绪 · 每次创建新报告，不覆盖原视频或旧报告。")
        ttk.Label(frame, textvariable=self.status, wraplength=810).grid(row=12, column=0, columnspan=3, sticky="w")
        self.running, self.last_report = False, None
        self.messages, self.cancel_event = queue.Queue(), threading.Event()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.poll_id = root.after(150, self.poll)

    def choose(self, variable, kind):
        from tkinter import filedialog
        types = {"video": [("Video", "*.mp4 *.mkv *.mov *.avi *.webm"), ("All files", "*")],
                 "srt": [("UTF-8 SRT", "*.srt")], "executable": [("FFmpeg", "*")]}
        value = filedialog.askdirectory(parent=self.root) if kind == "directory" else filedialog.askopenfilename(
            parent=self.root, filetypes=types[kind])
        if value:
            variable.set(value)

    def start(self):
        self.begin(False)

    def start_demo(self):
        self.begin(True)

    def begin(self, demo):
        from tkinter import messagebox
        if self.running:
            return
        try:
            video = Path(self.video.get().strip())
            if not demo and not video.is_file():
                raise MediaError("请选择一个有效的本地视频文件。")
            if not self.destination.get().strip():
                raise MediaError("请选择报告保存位置。")
            settings = AnalyzeOptions(ffmpeg=self.ffmpeg.get().strip() or None,
                                      subtitles=self.subtitles.get().strip() or None, transcript=self.mode.get(),
                                      model=self.model.get().strip(), offline=self.offline.get(),
                                      language=None if self.language.get() == "auto" else self.language.get(),
                                      export_clips=self.export_clips.get())
            if not demo:
                settings.validate()
            find_tools(settings.ffmpeg)
        except (ValueError, OSError, MediaError) as exc:
            messagebox.showerror("请检查设置", str(exc), parent=self.root)
            return
        target = Path(self.destination.get()) / ("analysis-demo-" if demo else "analysis-")
        target = target.with_name(target.name + uuid.uuid4().hex[:10])
        self.running, self.last_report = True, None
        self.cancel_event.clear()
        for control in self.controls + [self.start_button, self.demo_button, self.report_button]:
            control.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress.start(12)
        self.status.set("正在解析…")
        self.worker = threading.Thread(target=self.work, args=(video, target, settings, demo), daemon=True)
        self.worker.start()

    def work(self, video, target, settings, demo):
        report_dir = target / "report" if demo else target
        try:
            progress = lambda message: self.messages.put(("progress", message))
            result = (run_analysis_demo(target, settings.ffmpeg, progress, self.cancel_event) if demo
                      else analyze(video, target, settings, progress, self.cancel_event))
            self.messages.put(("done", (result, report_dir)))
        except Exception as exc:  # noqa: BLE001 - Never show a failed worker as completed.
            self.messages.put(("error", (str(exc), report_dir, isinstance(exc, Cancelled))))

    def poll(self):
        while not self.messages.empty():
            event, payload = self.messages.get_nowait()
            if event == "progress":
                self.status.set(payload)
                continue
            self.running = False
            self.progress.stop()
            for control in self.controls + [self.start_button, self.demo_button]:
                control.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            if event == "done":
                result, target = payload
                label = "解析完成" if result["status"] == "COMPLETE" else "部分完成：台词提取失败，请看报告"
                self.status.set(f"{label} · {len(result['shots'])} 个镜头 · {len(result['units'])} 个解析单元\n{target}")
            else:
                message, target, cancelled = payload
                self.status.set(("已取消：" if cancelled else "执行失败：") + message)
            if (target / "report.html").is_file():
                self.last_report = target / "report.html"
                self.report_button.configure(state="normal")
        self.poll_id = self.root.after(150, self.poll)

    def cancel(self):
        self.cancel_event.set()
        self.status.set("正在取消本地解析…")

    def open_report(self):
        if self.last_report:
            webbrowser.open(self.last_report.resolve().as_uri())

    def close(self):
        if self.running:
            self.cancel()
            self.root.after(150, self.close)
            return
        self.root.after_cancel(self.poll_id)
        self.root.destroy()
