"""临时工具:离屏渲染 MainWindow 并保存截图(UI 审计用,不随仓库提交)。

用法:
    python tools/ui_snapshot.py out.png [out2.png ...]
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from gui.style import build_stylesheet
from gui.main_window import MainWindow
from config.presets import APP_NAME, APP_TITLE


def _seed_samples() -> str:
    """生成示例工作区(项目/多 HTML 项目/子目录/pure 项目),返回其路径。"""
    ws = os.path.join(ROOT, "_uireview", "sample_ws")
    os.makedirs(ws, exist_ok=True)

    def _proj(name: str, files: dict[str, str]) -> None:
        d = os.path.join(ws, name)
        os.makedirs(d, exist_ok=True)
        for fn, body in files.items():
            with open(os.path.join(d, fn), "w", encoding="utf-8") as fh:
                fh.write(body)

    page = ("<html><head><style>"
            "body{{background:#4a6cf7;color:#fff;font-family:sans-serif}}"
            ".btn{{background:#7b96ff;border:1px solid #1d2233}}"
            "</style></head><body><h1>{}</h1>"
            "<button class='btn'>ok</button></body></html>")
    _proj("landing-page", {"index.html": page.format("Landing A")})
    _proj("multi-page", {f"page{i}.html": page.format(f"Page {i}")
                         for i in range(1, 4)})
    _proj("pure-demo", {"pure.html": "<html></html>",
                        "ink.html": page.format("Ink"),
                        "wave.html": page.format("Wave")})
    os.makedirs(os.path.join(ws, "docs", "inner"), exist_ok=True)
    _proj(os.path.join("docs", "inner", "nested"), {"index.html": page.format("Nested")})
    return ws


def main() -> int:
    outs = sys.argv[1:] or [os.path.join(ROOT, "ui_snapshot.png")]
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    if os.name == "nt":
        app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(build_stylesheet())
    win = MainWindow()
    win.resize(1380, 800)
    win.show()

    def _seed() -> None:
        win.workspace.init_tabs([_seed_samples()], current=_seed_samples())
        win.workspace._reflow()

    QTimer.singleShot(1200, _seed)

    shots = iter(outs)

    def _shoot() -> None:
        try:
            out = next(shots)
        except StopIteration:
            app.quit()
            return
        win.grab().save(out)
        if win.workspace._cards:
            # 选中两张卡片,展示单选/多选态
            keys = list(win.workspace._cards.keys())[:2]
            win.workspace._apply_selection(set(keys[:1]))
            win.grab().save(out.replace(".png", "_sel.png"))
            win.workspace._apply_selection(set(keys))
            win.grab().save(out.replace(".png", "_multi.png"))
        QTimer.singleShot(200, _shoot)

    QTimer.singleShot(3000, _shoot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
