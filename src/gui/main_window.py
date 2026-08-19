"""主窗口：工作目录项目卡片（左）+ 尺寸/导出设置（右）。

- 启动提速：不预先导入 QtWebEngine / Playwright，仅在使用时才按需导入；
  窗口骨架先行，初始化步骤通过启动进度条遮罩显示。
"""

from __future__ import annotations

import os
import threading
import webbrowser

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.controller import Controller, ExportParams
from core.static_server import StaticServer
from config.settings import Settings
from gui.export_panel import ExportPanel
from gui.size_panel import SizePanel
from gui.workspace_panel import WorkspacePanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Website Page to Image")
        self.resize(1380, 800)
        self._thread: QThread | None = None
        self._preview_win = None
        self._browser_servers: list[StaticServer] = []
        self._active_project: str | None = None

        self._loading: QWidget | None = None
        self._loaded = False
        self._settings = Settings()   # v1.4.0：启动即加载/创建设置文件
        self._build_shell()
        self._start_boot()

    # ------------------------------------------------------------- boot flow
    def _build_shell(self) -> None:
        """先搭一个带进度条的最小骨架，避免黑屏等待。"""
        shell = QWidget()
        shell.setObjectName("root")
        lay = QVBoxLayout(shell)
        lay.addStretch(1)
        title = QLabel("Website Page to Image")
        title.setObjectName("bootTitle")
        title.setAlignment(title.alignment() | 0x0004)  # Qt.AlignHCenter
        lay.addWidget(title)
        self._boot_progress = QProgressBar()
        self._boot_progress.setRange(0, 100)
        self._boot_progress.setValue(0)
        lay.addWidget(self._boot_progress)
        self._boot_label = QLabel("正在准备…")
        self._boot_label.setProperty("secondary", True)
        self._boot_label.setAlignment(self._boot_label.alignment() | 0x0004)
        lay.addWidget(self._boot_label)
        lay.addStretch(1)
        shell.setMinimumSize(420, 240)
        self.setCentralWidget(shell)
        self._loading = shell

    def _start_boot(self) -> None:
        steps = [
            (10, "加载样式…", self._step_style),
            (40, "构建界面…", self._step_build_ui),
            (70, "扫描工作目录…", self._step_scan),
            (90, "完成", self._step_done),
        ]
        self._boot_steps = iter(steps)
        QTimer.singleShot(20, self._next_boot_step)

    def _next_boot_step(self) -> None:
        try:
            pct, text, fn = next(self._boot_steps)
        except StopIteration:
            return
        self._boot_progress.setValue(pct)
        self._boot_label.setText(text)
        fn()
        QTimer.singleShot(20, self._next_boot_step)

    def _step_style(self) -> None:
        # 全局样式已在 main.py 的 QApplication 上设置，此处无需重复构建。
        pass

    def _step_build_ui(self) -> None:
        self._build_ui()

    def _step_scan(self) -> None:
        self._scan_initial_project()

    def _step_done(self) -> None:
        self._loaded = True
        self._loading = None
        self._boot_progress.setValue(100)

        def _swap() -> None:
            self.setCentralWidget(self._real_central)
            self._boot_progress = None
            self._boot_label = None

        QTimer.singleShot(80, _swap)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("root")
        root = QVBoxLayout(central)
        root.setSpacing(12)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        # 左：工作目录项目卡片
        self.workspace = WorkspacePanel()
        self.workspace.projectSelected.connect(self._on_project_selected)
        self.workspace.previewRequested.connect(self._open_preview_for)
        self.workspace.browserRequested.connect(self._open_in_browser)
        splitter.addWidget(self.workspace)

        # 右：设置区
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        self.size_panel = SizePanel(right)
        self.export_panel = ExportPanel(right)
        right_layout.addWidget(self.size_panel)
        right_layout.addWidget(self.export_panel)

        # 更换目录按钮位于右侧设置栏下方（调用左侧工作目录的选择）
        self.chdir_btn = QPushButton("更换目录…")
        self.chdir_btn.setObjectName("ghostBtn")
        self.chdir_btn.setMinimumHeight(30)
        self.chdir_btn.clicked.connect(self.workspace.choose_directory)
        right_layout.addWidget(self.chdir_btn)

        action_row = QHBoxLayout()
        self.preview_btn = QPushButton("预览当前项目")
        self.preview_btn.setToolTip("在软件内置预览窗口打开当前选中的项目")
        self.preview_btn.clicked.connect(self._open_preview_current)
        self.preview_btn.setMinimumHeight(36)
        action_row.addWidget(self.preview_btn)

        self.export_btn = QPushButton("导出")
        self.export_btn.setObjectName("primaryBtn")
        self.export_btn.setMinimumHeight(36)
        self.export_btn.clicked.connect(self._run_export)
        action_row.addWidget(self.export_btn, 1)
        right_layout.addLayout(action_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        right_layout.addWidget(self.progress)

        self.status_label = QLabel("就绪")
        self.status_label.setProperty("secondary", True)
        self.status_label.setWordWrap(True)
        right_layout.addWidget(self.status_label)
        right_layout.addStretch(1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 5)  # v1.4.0：工作目录占更宽，支持 4 列卡片
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([860, 460])
        root.addWidget(splitter, 1)

        # ---- v1.4.0：设置记忆（任何变更即写回软件同级目录的 WPI_settings.json）
        self.workspace.workdirChanged.connect(self._on_workdir_changed)
        self.size_panel.widthChanged.connect(self._on_width_changed)
        self.export_panel.outputChanged.connect(self._on_output_changed)

        self._real_central = central

    # --------------------------------------------------------- workspace ops
    def _scan_initial_project(self) -> None:
        """v1.4.0：从设置文件恢复上次工作目录 / 宽度 / 输出路径。"""
        from config.presets import default_workspace_dir

        settings = self._settings
        workdir = settings.workspace_dir or default_workspace_dir()
        if os.path.isdir(workdir):
            self.workspace.set_workdir(workdir)
        else:
            self.workspace.set_workdir(default_workspace_dir())
        if settings.width:
            self.size_panel.set_width(settings.width)
        if settings.output_path:
            self.export_panel.set_output_path(settings.output_path)

    # ------------------------------------------------ v1.4.0 设置记忆 handlers
    def _on_workdir_changed(self, path: str) -> None:
        self._settings.workspace_dir = path

    def _on_width_changed(self, width: int) -> None:
        self._settings.width = width

    def _on_output_changed(self, path: str) -> None:
        self._settings.output_path = path

    def _on_project_selected(self, project: str) -> None:
        self._active_project = project
        self.status_label.setText(f"当前项目：{os.path.basename(project)}")
        self.export_panel.set_output_suggestion(os.path.dirname(project), os.path.basename(project))

    # --------------------------------------------------------------- preview
    def _open_preview_current(self) -> None:
        project = self._active_project
        if not project:
            QMessageBox.information(self, "提示", "请先在左侧选择 / 点击一个项目卡片。")
            return
        self._open_preview_for(project)

    def _open_preview_for(self, project: str) -> None:
        from gui.preview_window import PreviewWindow  # 延迟导入，加速启动

        if self._preview_win is not None:
            if self._preview_win.isVisible():
                self._preview_win.raise_()
                self._preview_win.activateWindow()
                return
            self._preview_win = None

        width = self.size_panel.get_width()
        win = PreviewWindow(self, width=width)
        win.setWindowTitle(f"网页预览 - {os.path.basename(project)}")
        win.load(project)
        win.destroyed.connect(lambda: setattr(self, "_preview_win", None))
        self._preview_win = win
        win.show()
        win.raise_()
        win.activateWindow()

    # --------------------------------------------------------- browser open
    def _open_in_browser(self, project: str) -> None:
        """用系统默认浏览器打开项目静态服务地址（可 F12 审查元素）。"""
        try:
            server = StaticServer(os.path.abspath(project))
            server.start()
        except OSError as exc:
            QMessageBox.critical(self, "打开失败", str(exc))
            return
        self._browser_servers.append(server)
        url = server.base_url + "/" + "index.html"
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
        self.status_label.setText(f"已在系统浏览器打开：{url}")

    # --------------------------------------------------------------- export
    def _collect_params(self) -> ExportParams:
        extra = self.export_panel.get_params()
        width, _height = self.size_panel.get_size()
        source = self._active_project or ""
        return ExportParams(
            source=source,
            format=extra["format"],
            width=width,
            height=width,  # v1.2.0：高度跟随网页实际内容长度
            fps=extra["fps"],
            loop=extra["loop"],
            transparent=extra["transparent"],
            output_path=extra["output_path"],
            max_wait=extra["max_wait"],
            full_page=extra["full_page"],
        )

    def _run_export(self) -> None:
        params = self._collect_params()
        source = params.source
        if not source or not os.path.exists(source):
            QMessageBox.warning(self, "提示", "请先在左侧选择 / 点击一个项目卡片。")
            return
        if not params.output_path:
            QMessageBox.warning(self, "提示", "请选择导出文件路径。")
            return
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(self, "提示", "已有导出任务进行中。")
            return

        self.progress.setValue(0)
        self.status_label.setText("准备导出…")
        self.export_btn.setText("导出中…")
        self.export_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)

        self._thread = QThread(self)
        self._export_worker = Controller()
        self._export_worker.set_params(params)
        self._export_worker.moveToThread(self._thread)
        self._thread.started.connect(self._export_worker.run)
        self._export_worker.progress.connect(self.progress.setValue)
        self._export_worker.status.connect(self.status_label.setText)
        self._export_worker.result.connect(self._on_export_done)
        self._export_worker.failed.connect(self._on_export_failed)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_export_done(self, result: dict) -> None:
        self._finish_busy()
        path = result["path"]
        msgs = [
            f"导出完成: {os.path.basename(path)}\n"
            f"尺寸 {result['width']} × {result['height']}  {result['format']}"
        ]
        if result.get("frames", 1) > 1:
            msgs.append(f"帧数 {result['frames']}")
        if result.get("encoder"):
            msgs.append(f"编码器: {result['encoder']}")
        for w in result.get("warnings", []):
            msgs.append(f"提醒: {w}")
        QMessageBox.information(self, "完成", "\n".join(msgs))

    def _on_export_failed(self, message: str) -> None:
        self._finish_busy()
        QMessageBox.critical(
            self, "导出失败",
            message + ("\n\n提示：若提示浏览器内核问题，请安装 Microsoft Edge 或 Google Chrome。"
                       if "浏览器" in message else ""),
        )

    def _finish_busy(self) -> None:
        self.export_btn.setText("导出")
        self.export_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        self._thread = None

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._preview_win is not None:
            self._preview_win.close()
            self._preview_win = None
        for server in self._browser_servers:
            server.stop()
        self._browser_servers.clear()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        super().closeEvent(event)