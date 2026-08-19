"""格式/导出设置面板（设计文档 4.5 / 8）。"""

from __future__ import annotations

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config.presets import (
    DEFAULT_FORMAT,
    FILE_EXTENSIONS,
    FORMATS,
    FULL_PAGE_DEFAULT,
    GIF_FPS,
    GIF_FPS_RANGE,
    GIF_LOOP,
)


class ExportPanel(QWidget):
    paramsChanged = Signal()
    outputChanged = Signal(str)  # v1.4.0：输出路径变更（供设置记忆）

    def __init__(self, parent=None):
        super().__init__(parent)
        group = QGroupBox("导出设置", self)
        form = QFormLayout(group)

        self.format_combo = QComboBox()
        for f in FORMATS:
            self.format_combo.addItem(f)
        self.format_combo.setCurrentText(DEFAULT_FORMAT)
        self.format_combo.currentTextChanged.connect(self._format_changed)
        form.addRow("导出格式", self.format_combo)

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("选择输出文件路径…")
        self.output_edit.textChanged.connect(lambda t: self.outputChanged.emit(t.strip()))
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._browse)
        out_row = QHBoxLayout()
        out_row.addWidget(self.output_edit, 1)
        out_row.addWidget(browse_btn)
        form.addRow("输出文件", out_row)

        # ---- GIF 参数组
        self.gif_group = QGroupBox("GIF 参数", self)
        gform = QFormLayout(self.gif_group)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(*GIF_FPS_RANGE)
        self.fps_spin.setValue(GIF_FPS)
        self.fps_spin.setSuffix(" fps")
        self.fps_spin.valueChanged.connect(self._changed)
        gform.addRow("帧率", self.fps_spin)

        self.loop_spin = QSpinBox()
        self.loop_spin.setRange(0, 100)
        self.loop_spin.setValue(GIF_LOOP)
        self.loop_spin.setSpecialValueText("0 (无限循环)")
        self.loop_spin.valueChanged.connect(self._changed)
        gform.addRow("循环次数", self.loop_spin)

        self.maxwait_spin = QSpinBox()
        self.maxwait_spin.setRange(1, 120)
        self.maxwait_spin.setValue(15)
        self.maxwait_spin.setSuffix(" 秒")
        self.maxwait_spin.setToolTip("动画最长录制/等待时间")
        self.maxwait_spin.valueChanged.connect(self._changed)
        gform.addRow("动画时长上限", self.maxwait_spin)

        # ---- 整页导出（PNG / PDF / GIF 生效）----
        self.full_page_check = QCheckBox("整页导出（高度按网页实际内容长度）")
        self.full_page_check.setChecked(FULL_PAGE_DEFAULT)
        self.full_page_check.setToolTip(
            "导出宽度为面板设定的视口宽度，高度跟随网页实际内容长度；"
            "关闭后 PNG/PDF 按视口首屏导出，GIF 按视口高度录制。"
        )
        self.full_page_check.toggled.connect(self._changed)

        # ---- PNG 参数组
        self.png_group = QGroupBox("PNG 参数", self)
        pform = QFormLayout(self.png_group)
        self.transparent_check = QCheckBox("保留透明背景")
        self.transparent_check.setChecked(False)
        self.transparent_check.toggled.connect(self._changed)
        pform.addRow(self.transparent_check)

        # ---- PDF 参数组
        self.pdf_group = QGroupBox("PDF 参数", self)
        pdf_form = QFormLayout(self.pdf_group)
        self.paper_combo = QComboBox()
        self.paper_combo.addItem("Fit（按内容尺寸）", "Fit")
        self.paper_combo.addItem("A4", "A4")
        self.paper_combo.addItem("Letter", "letter")
        self.paper_combo.currentIndexChanged.connect(self._changed)
        pdf_form.addRow("纸张", self.paper_combo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)
        layout.addWidget(self.full_page_check)
        layout.addWidget(self.gif_group)
        layout.addWidget(self.png_group)
        layout.addWidget(self.pdf_group)
        self._format_changed()

    # ------------------------------------------------------------------ API
    def get_params(self) -> dict:
        fmt = self.format_combo.currentText()
        return {
            "format": fmt,
            "output_path": self.output_edit.text().strip(),
            "fps": self.fps_spin.value(),
            "loop": self.loop_spin.value(),
            "max_wait": float(self.maxwait_spin.value()),
            "transparent": self.transparent_check.isChecked(),
            "paper": self.paper_combo.currentData(),
            "full_page": self.full_page_check.isChecked(),
        }

    def set_output_suggestion(self, base_dir: str, name: str) -> None:
        """基于源路径与当前格式预填输出路径。"""
        if self.output_edit.text().strip():
            return
        fmt = self.format_combo.currentText()
        ext = FILE_EXTENSIONS[fmt]
        self._suggest_dir = base_dir
        self.output_edit.setText(os.path.join(base_dir, name + ext))

    def set_output_path(self, path: str) -> None:
        """外部设置输出路径（设置记忆回填等，v1.4.0）。"""
        if path and not path.lower().endswith(FILE_EXTENSIONS[self.format_combo.currentText()]):
            root, _ext = os.path.splitext(path)
            path = root + FILE_EXTENSIONS[self.format_combo.currentText()]
        self.output_edit.setText(path or "")
        self.outputChanged.emit(self.output_edit.text().strip())

    def _changed(self, *_) -> None:
        self.paramsChanged.emit()

    def _format_changed(self, _=None) -> None:
        fmt = self.format_combo.currentText()
        self.gif_group.setVisible(fmt == "GIF")
        self.png_group.setVisible(fmt == "PNG")
        self.pdf_group.setVisible(fmt == "PDF")
        self.full_page_check.setEnabled(True)
        if self.output_edit.text().strip():
            path = self.output_edit.text().strip()
            root, _ext = os.path.splitext(path)
            self.output_edit.setText(root + FILE_EXTENSIONS[fmt])
        self._changed()

    def _browse(self) -> None:
        fmt = self.format_combo.currentText()
        ext = FILE_EXTENSIONS[fmt]
        current = self.output_edit.text().strip()
        start = current if current else os.path.expanduser("~")
        path, _ = QFileDialog.getSaveFileName(
            self, "选择导出路径", start, f"{fmt} 文件 (*{ext})"
        )
        if path:
            if not path.lower().endswith(ext):
                path += ext
            self.output_edit.setText(path)