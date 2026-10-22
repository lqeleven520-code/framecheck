import os
import time

import pytest

from framecheck.gui import App


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"), reason="Requires a graphical Tk session")
def test_gui_worker_generates_report_and_reenables_controls(make_video, tmp_path):
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    try:
        source = make_video()
        app.reference.set(str(source))
        app.candidate.set(str(source))
        app.destination.set(str(tmp_path / "gui-output"))
        app.start()
        deadline = time.monotonic() + 30
        while app.running and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert not app.running
        assert app.last_report and app.last_report.is_file()
        assert "指标通过" in app.status.get()
        assert str(app.start_button["state"]) == "normal"
    finally:
        app.cancel_event.set()
        if hasattr(app, "worker"):
            app.worker.join(timeout=5)
        root.after_cancel(app.poll_id)
        root.destroy()
