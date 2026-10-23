import os
import time

import pytest

from framecheck.analysis_gui import AnalysisApp
from framecheck.gui import App


@pytest.fixture(scope="module")
def tk_host():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Requires a graphical Tk session")
def test_gui_worker_generates_report_and_reenables_controls(make_video, tmp_path, tk_host):
    import tkinter as tk
    root = tk.Toplevel(tk_host)
    root.withdraw()
    app = App(root)
    try:
        source = make_video()
        app.reference.set(str(source))
        app.candidate.set(str(source))
        app.destination.set(str(tmp_path / "gui-output"))
        for demo in (False, True):
            app.start_demo() if demo else app.start()
            deadline = time.monotonic() + 30
            while app.running and time.monotonic() < deadline:
                root.update()
                time.sleep(0.01)
            assert not app.running
            assert app.last_report and app.last_report.is_file()
            assert ("示例完成" if demo else "指标通过") in app.status.get()
            assert str(app.start_button["state"]) == "normal"
            assert str(app.demo_button["state"]) == "normal"
    finally:
        app.cancel_event.set()
        if hasattr(app, "worker"):
            app.worker.join(timeout=5)
        root.after_cancel(app.poll_id)
        root.destroy()


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Requires a graphical Tk session")
def test_analysis_gui_demo_creates_editable_report(tmp_path, tk_host):
    import tkinter as tk
    root = tk.Toplevel(tk_host)
    root.withdraw()
    app = AnalysisApp(root)
    try:
        app.destination.set(str(tmp_path / "analysis-gui"))
        app.start_demo()
        deadline = time.monotonic() + 40
        while app.running and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert not app.running
        assert app.last_report and app.last_report.is_file()
        assert "解析完成" in app.status.get()
        assert (app.last_report.parent / "breakdown.txt").is_file()
        assert str(app.start_button["state"]) == "normal"
    finally:
        app.cancel_event.set()
        if hasattr(app, "worker"):
            app.worker.join(timeout=5)
        root.after_cancel(app.poll_id)
        root.destroy()
