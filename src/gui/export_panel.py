"""格式/导出设置面板（设计文档 4.5 / 8）。"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
    GIF_FPS,
    GIF_FPS_PRESETS,
    GIF_LOOP,
    MP4_FPS,
    MP4_FPS_PRESETS,
)


class ExportPanel(QWidget):
    paramsChanged = Signal()
    outputChanged = Signal(str)  # 输出路径变更（供设置记忆）

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

        # ---- 动画参数组（GIF / MP4 共用）
        self.gif_group = QGroupBox("动画参数", self)
        gform = QFormLayout(self.gif_group)

        self.fps_combo = QComboBox()
        # 帧率严格限制为延迟恒为整数的档位（GIF 用 10/20/25/50，MP4 用 24/30/48/60），
        # 避免 GIF 非整数百分秒延迟 BUG；随导出格式自动切换
        for f in GIF_FPS_PRESETS:
            self.fps_combo.addItem(f"{f} fps", f)
        self.fps_combo.setCurrentText(f"{GIF_FPS} fps")
        self.fps_combo.currentIndexChanged.connect(self._changed)
        gform.addRow("帧率", self.fps_combo)

        # 循环控件垂直左对齐——上「无限循环」勾选，下次数输入；
        # 只有取消勾选时才显示次数输入窗口（默认勾选 = 无限循环）
        self.loop_widget = QWidget(self)
        lw = QVBoxLayout(self.loop_widget)
        lw.setContentsMargins(0, 0, 0, 0)
        lw.setSpacing(4)
        self.loop_chk = QCheckBox("无限循环")
        self.loop_chk.setChecked(GIF_LOOP == 0)
        self.loop_chk.setToolTip("开启 = 无限循环；关闭 = 指定循环次数（最小 1）")
        self.loop_chk.toggled.connect(self._on_loop_toggled)
        lw.addWidget(self.loop_chk, 0, Qt.AlignLeft)
        self.loop_spin_row = QWidget(self)
        lsr = QHBoxLayout(self.loop_spin_row)
        lsr.setContentsMargins(0, 0, 0, 0)
        lsr.addWidget(QLabel("循环次数"))
        self.loop_spin = QSpinBox()
        self.loop_spin.setRange(1, 1000)
        self.loop_spin.setValue(1)
        self.loop_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)  # 去掉 +/- 步进按钮
        self.loop_spin.valueChanged.connect(self._changed)
        lsr.addWidget(self.loop_spin)
        lsr.addStretch(1)
        lw.addWidget(self.loop_spin_row, 0, Qt.AlignLeft)
        # 默认「无限循环」勾选 → 不显示次数输入窗口且禁用
        self.loop_spin_row.setVisible(False)
        self.loop_spin.setEnabled(False)
        gform.addRow(self.loop_widget)

        self.maxwait_spin = QSpinBox()
        self.maxwait_spin.setRange(1, 120)
        self.maxwait_spin.setValue(15)
        self.maxwait_spin.setSuffix(" 秒")
        self.maxwait_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)  # 去步进按钮
        self.maxwait_spin.setToolTip("动画最长录制/等待时间")
        self.maxwait_spin.valueChanged.connect(self._changed)
        gform.addRow("动画时长上限", self.maxwait_spin)

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
        layout.addWidget(self.gif_group)
        layout.addWidget(self.png_group)
        layout.addWidget(self.pdf_group)
        self._format_changed()

    # ------------------------------------------------------------------ API
    def get_format(self) -> str:
        return self.format_combo.currentText()

    def get_output_path(self) -> str:
        return self.output_edit.text().strip()

    def get_params(self) -> dict:
        fmt = self.format_combo.currentText()
        return {
            "format": fmt,
            "output_path": self.output_edit.text().strip(),
            "fps": int(self.fps_combo.currentData()),
            "loop": 0 if self.loop_chk.isChecked() else self.loop_spin.value(),
            "max_wait": float(self.maxwait_spin.value()),
            "transparent": self.transparent_check.isChecked(),
            "paper": self.paper_combo.currentData(),
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
        """外部设置输出路径（设置记忆回填等）。"""
        if path and not path.lower().endswith(FILE_EXTENSIONS[self.format_combo.currentText()]):
            root, _ext = os.path.splitext(path)
            path = root + FILE_EXTENSIONS[self.format_combo.currentText()]
        self.output_edit.setText(path or "")
        self.outputChanged.emit(self.output_edit.text().strip())

    def _changed(self, *_) -> None:
        self.paramsChanged.emit()

    def _format_changed(self, _=None) -> None:
        fmt = self.format_combo.currentText()
        # 动画参数组 GIF / MP4 共用；循环次数仅 GIF 需要（MP4 无循环概念）
        self.gif_group.setVisible(fmt in ("GIF", "MP4"))
        self.loop_widget.setVisible(fmt == "GIF")
        self.png_group.setVisible(fmt == "PNG")
        self.pdf_group.setVisible(fmt == "PDF")
        self._rebuild_fps(fmt)
        if self.output_edit.text().strip():
            path = self.output_edit.text().strip()
            root, _ext = os.path.splitext(path)
            self.output_edit.setText(root + FILE_EXTENSIONS[fmt])
        self._changed()

    def _rebuild_fps(self, fmt: str) -> None:
        """帧率预设随格式切换——GIF 用 10/20/25/50，MP4 用 24/30/48/60。

        切回当前格式时尽量保留已选帧率，仅在不在新预设内时回退到该格式默认值。
        """
        if fmt == "MP4":
            presets, default = MP4_FPS_PRESETS, MP4_FPS
        else:
            presets, default = GIF_FPS_PRESETS, GIF_FPS
        self.fps_combo.blockSignals(True)
        cur = self.fps_combo.currentData()
        self.fps_combo.clear()
        for f in presets:
            self.fps_combo.addItem(f"{f} fps", f)
        if cur not in presets:
            cur = default
        idx = self.fps_combo.findData(cur)
        self.fps_combo.setCurrentIndex(max(0, idx))
        self.fps_combo.blockSignals(False)

    def _on_loop_toggled(self, checked: bool) -> None:
        # 取消勾选「无限循环」时才显示次数输入窗口
        self.loop_spin_row.setVisible(not checked)
        self.loop_spin.setEnabled(not checked)
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