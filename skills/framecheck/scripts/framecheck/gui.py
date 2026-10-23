"""Tk desktop interface. File selection and video processing remain local."""

from __future__ import annotations

import queue
import threading
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

from . import __version__
from .compare import Options, compare
from .demo import run_demo
from .media import Cancelled, MediaError, find_tools, tool_versions


class App:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.root = tk, ttk, root
        root.title("FrameCheck · 视频对比与解析")
        root.geometry("880x740")
        root.minsize(760, 680)
        root.configure(bg="#f2f5f7")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f5f7")
        style.configure("TLabel", background="#f2f5f7", foreground="#203247", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 23, "bold"))
        style.configure("Muted.TLabel", foreground="#647487")
        style.configure("TButton", padding=(12, 7), font=("Microsoft YaHei UI", 10))
        style.configure("Accent.TButton", background="#187b75", foreground="white")
        frame = ttk.Frame(root, padding=26)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="FrameCheck", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Button(frame, text="解析单个视频 →", command=self.open_analysis).grid(row=0, column=2, sticky="e")
        ttk.Label(frame, text="比较每一帧，定位差异，生成离线报告。视频始终留在本机。",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 22))
        self.reference = tk.StringVar()
        self.candidate = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / "FrameCheck Reports"))
        self.ffmpeg = tk.StringVar()
        self.entries = []
        for row, label, var, kind in ((2, "参考视频", self.reference, "video"),
                                       (3, "待检视频", self.candidate, "video"),
                                       (4, "报告保存位置", self.destination, "directory"),
                                       (5, "FFmpeg（可选）", self.ffmpeg, "executable")):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=8)
            entry = ttk.Entry(frame, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", pady=8)
            button = ttk.Button(frame, text="选择…", command=lambda v=var, k=kind: self.choose(v, k))
            button.grid(row=row, column=2, padx=(10, 0))
            self.entries.extend((entry, button))
        ttk.Label(frame, text="FFmpeg 留空时自动寻找；手动选择时，ffprobe 应与它放在同一目录。",
                  style="Muted.TLabel").grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 14))
        settings = ttk.Frame(frame)
        settings.grid(row=7, column=0, columnspan=3, sticky="ew", pady=8)
        self.mae = tk.StringVar(value="2.5")
        self.timing = tk.StringVar(value="20")
        self.limit = tk.StringVar(value="")
        for col, (label, var) in enumerate((("像素容差 MAE", self.mae), ("时间容差 ms", self.timing),
                                            ("最多比较帧数（留空为全部）", self.limit))):
            box = ttk.Frame(settings)
            box.grid(row=0, column=col, sticky="ew", padx=(0, 18))
            ttk.Label(box, text=label).pack(anchor="w")
            entry = ttk.Entry(box, textvariable=var, width=18)
            entry.pack(anchor="w", pady=5)
            self.entries.append(entry)
        ttk.Label(frame, text="按帧序号配对，不自动同步内容。支持 SDR；本版不比较音频或评价创作质量。",
                  style="Muted.TLabel").grid(row=8, column=0, columnspan=3, sticky="w", pady=(8, 16))
        actions = ttk.Frame(frame)
        actions.grid(row=9, column=0, columnspan=3, sticky="w")
        self.start_button = ttk.Button(actions, text="开始比较", style="Accent.TButton", command=self.start)
        self.start_button.pack(side="left", padx=(0, 10))
        self.demo_button = ttk.Button(actions, text="运行内置示例", command=self.start_demo)
        self.demo_button.pack(side="left", padx=(0, 10))
        self.cancel_button = ttk.Button(actions, text="取消", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(0, 10))
        self.report_button = ttk.Button(actions, text="打开报告", command=self.open_report, state="disabled")
        self.report_button.pack(side="left")
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(22, 12))
        self.status = tk.StringVar(value="就绪 · 每次创建独立报告目录，不覆盖已有文件。")
        ttk.Label(frame, textvariable=self.status, wraplength=760).grid(row=11, column=0, columnspan=3, sticky="w")
        help_bar = ttk.Frame(frame)
        help_bar.grid(row=12, column=0, columnspan=3, sticky="w", pady=(18, 0))
        environment_button = ttk.Button(help_bar, text="检查环境", command=self.check_environment)
        environment_button.pack(side="left", padx=(0, 10))
        self.entries.append(environment_button)
        ttk.Button(help_bar, text="使用说明（在线）", command=lambda: webbrowser.open(
            "https://lqeleven520-code.github.io/framecheck/")).pack(side="left")
        self.messages = queue.Queue()
        self.cancel_event = threading.Event()
        self.running = False
        self.last_report = None
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.poll_id = root.after(150, self.poll)

    def choose(self, variable, kind):
        from tkinter import filedialog
        if kind == "directory":
            value = filedialog.askdirectory(parent=self.root)
        else:
            types = [("Video files", "*.mp4 *.mkv *.mov *.webm *.avi *.m4v"), ("All files", "*")]
            value = filedialog.askopenfilename(parent=self.root, filetypes=types if kind == "video" else [("FFmpeg", "*")])
        if value:
            variable.set(value)

    def open_analysis(self):
        from .analysis_gui import AnalysisApp
        window = self.tk.Toplevel(self.root)
        AnalysisApp(window)

    def start(self):
        from tkinter import messagebox
        if self.running:
            return
        try:
            reference, candidate = Path(self.reference.get().strip()), Path(self.candidate.get().strip())
            if not reference.is_file() or not candidate.is_file():
                raise ValueError("请选择两个有效的视频文件。")
            if not self.destination.get().strip():
                raise ValueError("请选择报告保存位置。")
            options = Options(max_mae=float(self.mae.get()), max_timing_ms=float(self.timing.get()),
                              max_frames=int(self.limit.get()) if self.limit.get().strip() else None,
                              ffmpeg=self.ffmpeg.get().strip() or None)
            options.validate()
            find_tools(options.ffmpeg)
        except (ValueError, OSError, MediaError) as exc:
            messagebox.showerror("请检查设置", str(exc), parent=self.root)
            return
        self.begin_work(reference, candidate, options)

    def check_environment(self):
        from tkinter import messagebox
        try:
            versions = tool_versions(self.ffmpeg.get().strip() or None)
            messagebox.showinfo("环境可用", f"FrameCheck {__version__}\n\n" + "\n".join(versions.values())
                                + "\n\n可以点击“运行内置示例”体验完整流程。", parent=self.root)
        except MediaError as exc:
            messagebox.showerror("需要安装或选择 FFmpeg", str(exc) + "\n\nWindows：双击下载包中的“安装FFmpeg.cmd”，"
                                 "或运行 winget install --id Gyan.FFmpeg --exact。\n"
                                 "也可在本窗口选择已有的 ffmpeg.exe，ffprobe.exe 应位于同一目录。",
                                 parent=self.root)

    def start_demo(self):
        from tkinter import messagebox
        if self.running:
            return
        try:
            if not self.destination.get().strip():
                raise MediaError("请选择示例报告的保存位置。")
            options = Options(ffmpeg=self.ffmpeg.get().strip() or None)
            find_tools(options.ffmpeg)
        except (OSError, MediaError) as exc:
            messagebox.showerror("请先检查环境", str(exc) + "\n可点击“检查环境”查看安装提示。", parent=self.root)
            return
        self.begin_work(None, None, options, is_demo=True)

    def begin_work(self, reference, candidate, options, is_demo=False):
        prefix = "demo-" if is_demo else ""
        target = Path(self.destination.get()) / (prefix + datetime.now().strftime("%Y%m%d-%H%M%S")
                                                 + "-" + uuid.uuid4().hex[:6])
        self.running = True
        self.last_report = None
        self.cancel_event.clear()
        for widget in self.entries + [self.start_button, self.demo_button, self.report_button]:
            widget.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress.start(12)
        self.status.set("正在生成并比较示例…" if is_demo else "正在比较…")
        self.worker = threading.Thread(target=self.work, args=(reference, candidate, target, options, is_demo),
                                       daemon=True)
        self.worker.start()

    def work(self, reference, candidate, target, options, is_demo=False):
        report_folder = target / "report" if is_demo else target
        try:
            def progress(message):
                self.messages.put(("progress", message))
            result = (run_demo(target, options.ffmpeg, progress, self.cancel_event) if is_demo else
                      compare(reference, candidate, target, options, progress, self.cancel_event))
            self.messages.put(("done", (result, report_folder, is_demo)))
        except Exception as exc:  # noqa: BLE001 - Surface worker failures in the UI, never leave a fake success.
            self.messages.put(("error", (str(exc), report_folder, isinstance(exc, Cancelled))))

    def poll(self):
        while not self.messages.empty():
            event, payload = self.messages.get_nowait()
            if event == "progress":
                self.status.set(payload)
                continue
            self.running = False
            self.progress.stop()
            for widget in self.entries + [self.start_button, self.demo_button]:
                widget.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            if event == "done":
                result, target, is_demo = payload
                scope = "（仅所选范围）" if result["scope"] != "whole_video" else ""
                label = ("示例完成：已找到预设差异（报告 FAIL 是预期结果）" if is_demo else
                         "指标通过" if result["status"] == "PASS" else "发现差异，请查看报告")
                self.status.set(f"{label}{scope} · 已比较 {result['summary']['compared_frames']} 帧\n{target}")
            else:
                message, target, cancelled = payload
                self.status.set(("已取消" if cancelled else "执行未完成") + "：" + message)
            report = target / "report.html"
            if report.exists():
                self.last_report = report
                self.report_button.configure(state="normal")
        self.poll_id = self.root.after(150, self.poll)

    def cancel(self):
        self.cancel_event.set()
        self.status.set("正在停止并保存执行状态…")

    def open_report(self):
        if self.last_report:
            webbrowser.open(self.last_report.resolve().as_uri())

    def close(self):
        if self.running:
            self.cancel()
            self.root.after(200, self.close)
            return
        self.root.after_cancel(self.poll_id)
        self.root.destroy()


def main():
    import tkinter as tk
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
