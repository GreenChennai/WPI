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
    QVBoxLayout,
    QWidget,
)

from config.presets import DEFAULT_WIDTH, WIDTH_PRESETS


class SizePanel(QWidget):
    widthChanged = Signal(int)

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

    # ------------------------------------------------------------- internal
    def _text_changed(self, _text: str) -> None:
        self.widthChanged.emit(self.get_width())