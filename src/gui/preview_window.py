"""交互式预览窗口：独立弹出 QMainWindow + QWebEngineView。

与主窗口分离（设计需求 4），可滚动 / 点击 / 交互（设计需求 2），
内置本地静态服务，按需打开、关闭即释放（设计需求 1：无需整套 Playwright 渲染链路）。

v1.3.0：预览窗口根据导出设置中的视口宽度呈现页面
（内容区宽度 = 导出宽度，窗口带外框所以实际尺寸更大）。

v1.8.0：
- 窗口高度固定为 850（不再随内容自动撑高）；
- 窗口宽度按用户设定的网页宽度精确贴合（加载后测量并校正，使内容区
  恰好等于设定宽度，左右无多余灰边）；
- 去掉 QScrollArea，直接以 QWebEngineView 作为内容，页面自身滚动条负责
  内容滚动，避免额外外框与宽度误算。
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QLineEdit,
    QMainWindow,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.controller import build_url
from core.static_server import StaticServer


class PreviewWindow(QMainWindow):
    PREVIEW_HEIGHT = 850  # 固定窗口高度（v1.8.0）

    def __init__(self, parent=None, width: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("网页预览")
        self._server: StaticServer | None = None
        self._width = width
        self._pending_content_width: int | None = width  # 待校正的目标内容宽度

        from PySide6.QtWebEngineWidgets import QWebEngineView  # 延迟导入

        self._view = QWebEngineView(self)

        # 直接以 view 作为内容（无 QScrollArea）：页面自带滚动条，宽度精确可控
        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.addWidget(self._view)
        self.setCentralWidget(content)

        # 高度固定 850；宽度先给一个含余量的初值，加载后精确校正
        self.setMinimumHeight(self.PREVIEW_HEIGHT)
        self.setMaximumHeight(self.PREVIEW_HEIGHT)
        if width:
            self._view.setFixedWidth(width)
            self.resize(width + 40, self.PREVIEW_HEIGHT)
        else:
            self._pending_content_width = None
            self.resize(1100, self.PREVIEW_HEIGHT)

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

        # 首次显示后也校正一次宽度（loadFinished 之前也能贴合）
        QTimer.singleShot(60, self._fit_window_width)

    # ----------------------------------------------------- 宽度精确贴合（v1.8.0）
    def _on_load_finished(self, _ok: bool) -> None:
        # 仅校正窗口宽度，绝不改动高度（高度已固定 850）
        self._fit_window_width()

    def _fit_window_width(self) -> None:
        """根据目标内容宽度校正窗口宽度，使内容区恰好等于用户设定宽度。"""
        if not self._pending_content_width:
            return
        target = self._pending_content_width
        # 内容区（central widget）宽 = 当前窗口宽 - 非客户区边框
        content_w = self.centralWidget().width()
        delta = content_w - target
        if delta:
            self.resize(self.width() - delta, self.PREVIEW_HEIGHT)
        self._pending_content_width = None

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
