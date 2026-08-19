"""尺寸设置面板（v1.2.0 简化版）。

v1.2.0 起尺寸语义修正：用户在面板中只设置"宽度"（浏览器视口宽度），
导出时高度跟随网页实际内容长度（PNG / PDF / GIF 均适用）。
面板提供 2400 / 1440 / 1080 / 800 预设，并可输入任意自定义宽度。
"""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.presets import DEFAULT_WIDTH, WIDTH_PRESETS


class SizePanel(QWidget):
    widthChanged = Signal(int)
    # v2.0.0：在线网站预览 / 浏览器打开
    onlinePreview = Signal(str)
    onlineBrowser = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        group = QGroupBox("导出尺寸", self)
        form = QFormLayout(group)

        self.hint = QLabel("宽度为浏览器视口宽度，\n高度跟随网页实际内容长度")
        self.hint.setProperty("muted", True)
        self.hint.setWordWrap(True)
        form.addRow(self.hint)

        row = QHBoxLayout()
        self.width_combo = QComboBox()
        self.width_combo.setEditable(True)
        for w in WIDTH_PRESETS:
            self.width_combo.addItem(str(w), w)
        self.width_combo.setCurrentText(str(DEFAULT_WIDTH))
        self.width_combo.setInsertPolicy(QComboBox.NoInsert)
        self.width_combo.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^\d{1,5}$"))
        )
        self.width_combo.setToolTip("输入任意像素宽度，或从下拉预设中选择")
        self.width_combo.currentTextChanged.connect(self._text_changed)
        row.addWidget(self.width_combo, 1)
        self.unit = QLabel("px")
        self.unit.setProperty("muted", True)
        row.addWidget(self.unit)
        form.addRow("宽度", row)

        # ---- v2.0.0：导出在线网站（URL 源）----
        online_group = QGroupBox("在线网站", self)
        og = QVBoxLayout(online_group)
        og.setSpacing(6)
        self.online_url = QLineEdit()
        self.online_url.setPlaceholderText("https://example.com/…")
        self.online_url.setClearButtonEnabled(True)
        self.online_url.setToolTip("输入在线网站地址后，可直接预览 / 浏览器打开 / 导出")
        og.addWidget(self.online_url)
        row = QHBoxLayout()
        btn_preview = QPushButton("预览")
        btn_preview.setObjectName("ghostBtn")
        btn_preview.clicked.connect(self._emit_online_preview)
        btn_browser = QPushButton("浏览器打开")
        btn_browser.setObjectName("ghostBtn")
        btn_browser.clicked.connect(self._emit_online_browser)
        row.addWidget(btn_preview)
        row.addWidget(btn_browser)
        og.addLayout(row)
        layout.addWidget(online_group)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

    # ------------------------------------------------------------------ API
    def get_width(self) -> int:
        """返回当前宽度（像素）；非法输入回退到预设默认值。"""
        try:
            v = int(self.width_combo.currentText().strip())
        except ValueError:
            return DEFAULT_WIDTH
        return max(1, min(v, 99999))

    def set_width(self, width: int) -> None:
        self.width_combo.setCurrentText(str(int(width)))

    # v2.0.0：在线网站
    def get_online_url(self) -> str:
        return self.online_url.text().strip()

    def set_online_url(self, url: str) -> None:
        self.online_url.setText(url or "")

    # ------------------------------------------------------------- internal
    def _text_changed(self, _text: str) -> None:
        self.widthChanged.emit(self.get_width())

    def _emit_online_preview(self) -> None:
        url = self.get_online_url()
        if url:
            self.onlinePreview.emit(url)

    def _emit_online_browser(self) -> None:
        url = self.get_online_url()
        if url:
            self.onlineBrowser.emit(url)