"""交互式预览窗口：独立弹出 QMainWindow + QWebEngineView。

与主窗口分离（设计需求 4），可滚动 / 点击 / 交互（设计需求 2），
内置本地静态服务，按需打开、关闭即释放（设计需求 1：无需整套 Playwright 渲染链路）。

v1.3.0：预览窗口根据导出设置中的视口宽度呈现页面
（内容区宽度 = 导出宽度，窗口带外框所以实际尺寸更大）。

QtWebEngine 延迟导入：QWebEngineView 从属于 QtWebEngineWidgets，加载较重，
按需（首次打开预览窗口）才 import，加速软件启动（v1.1.0 界面体验优化）。
"""

from __future__ import annotations

import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QLineEdit,
    QMainWindow,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.controller import build_url
from core.static_server import StaticServer


class PreviewWindow(QMainWindow):
    def __init__(self, parent=None, width: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("网页预览")
        self._server: StaticServer | None = None
        self._width = width

        from PySide6.QtWebEngineWidgets import QWebEngineView  # 延迟导入

        self._view = QWebEngineView(self)
        content_wrapper = QWidget()
        cv = QVBoxLayout(content_wrapper)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.addWidget(self._view)
        self._content = content_wrapper

        if width:
            # 内容区宽度固定为导出宽度，高度自适应网页实际内容（v1.4.0）
            self._view.setFixedWidth(width)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content_wrapper)
            self.setCentralWidget(scroll)
            self._scroll_area = scroll
            self._content_wrapper = content_wrapper
            self._auto_fit = True
            self.resize(width + 140, 800)
        else:
            self.resize(1100, 780)
            self.setCentralWidget(content_wrapper)

        toolbar = QToolBar("导航", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        act_back = toolbar.addAction("←")
        act_back.triggered.connect(lambda: self._view.back())
        act_fwd = toolbar.addAction("→")
        act_fwd.triggered.connect(lambda: self._view.forward())
        act_reload = toolbar.addAction("刷新")
        act_reload.triggered.connect(lambda: self._view.reload())

        self._addr = QLineEdit()
        self._addr.setReadOnly(True)
        self._addr.setPlaceholderText("加载页面后显示地址…")
        toolbar.addWidget(self._addr)

        self._width_label = QLineEdit()
        self._width_label.setReadOnly(True)
        self._width_label.setMaximumWidth(90)
        self._width_label.setToolTip("当前预览视口宽度（px）")
        if width:
            self._width_label.setText(f"{width} px")
        toolbar.addWidget(self._width_label)

        self._view.urlChanged.connect(lambda u: self._addr.setText(u.toString()))
        self._view.loadProgress.connect(self._on_progress)
        self._view.loadFinished.connect(self._on_load_finished)
        self._view.setContextMenuPolicy(
            self._view.contextMenuPolicy()  # 保留默认右键菜单
        )

    # ------------------------------------------------------- auto fit height
    def _on_load_finished(self, _ok: bool) -> None:
        if not getattr(self, "_auto_fit", False):
            return
        self._measure_and_fit()
        # 页面内替换内容 / 异步加载后高度可能变化，延迟再次测量
        QTimer.singleShot(600, self._measure_and_fit)

    def _measure_and_fit(self) -> None:
        """按网页实际内容高度调整窗口尺寸，消除多余空白（v1.4.0）。"""
        self._view.page().runJavaScript(
            "Math.max(document.documentElement.scrollHeight,"
            " document.body ? document.body.scrollHeight : 0)",
            self._apply_content_height,
        )
        self._view.page().runJavaScript(
            "Math.max(document.documentElement.scrollWidth,"
            " document.body ? document.body.scrollWidth : 0)",
            self._apply_content_width,
        )

    def _apply_content_height(self, height) -> None:
        try:
            h = max(0, int(height))
        except (TypeError, ValueError):
            return
        # 内容高度 + 工具栏/外框高度 = 窗口总高（外框差值 = 窗口高 - 页面区高）
        chrome = self.height() - self._view.height() if self._view.height() else 0
        target = h + chrome + 8
        screen = self.screen()
        geom = screen.availableGeometry() if screen is not None else None
        if geom:
            target = max(300, min(target, geom.height() - 40))
        self.resize(self.width(), target)

    def _apply_content_width(self, width) -> None:
        try:
            w = max(0, int(width))
        except (TypeError, ValueError):
            return
        # 内容宽度固定为导出宽度；仅当网页受内容驱动更宽时让外框跟随
        if not self._width or w > self._width:
            chrome = self.width() - self._view.width() if self._view.width() else 0
            target = w + chrome
            target = max(target, 420)
            screen = self.screen()
            geom = screen.availableGeometry() if screen is not None else None
            if geom:
                target = min(target, geom.width() - 40)
            self.resize(target, self.height())

    def _on_progress(self, pct: int) -> None:
        self._addr.setPlaceholderText(f"加载中… {pct}%")

    def load(self, source: str, url_override: str | None = None) -> None:
        """加载本地源（HTML 文件或目录）。自动启动/复用本地静态服务。"""
        if self._server is not None:
            self._server.stop()
            self._server = None
        if url_override:
            url = url_override
        else:
            mount = (
                source if os.path.isdir(source)
                else os.path.dirname(os.path.abspath(source))
            )
            self._server = StaticServer(mount)
            self._server.start()
            url = build_url(source, self._server)
        self._view.load(url)

    def closeEvent(self, event) -> None:
        self._view.setPage(None)
        if self._server is not None:
            self._server.stop()
            self._server = None
        super().closeEvent(event)