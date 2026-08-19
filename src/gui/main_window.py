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

from config.presets import FILE_EXTENSIONS
from config.settings import Settings
from core.controller import Controller, ExportParams
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
        self.workspace.selectionChanged.connect(self._on_selection_changed)
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
        # v2.0.0：在线网站预览 / 浏览器打开
        self.size_panel.onlinePreview.connect(self._open_preview_online)
        self.size_panel.onlineBrowser.connect(self._open_browser_online)

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
        # v1.7.0：多 HTML 时输出建议名取所选页面（如 index2 → index2.png）
        source = self._selected_source(project)
        if os.path.isfile(source):
            stem = os.path.splitext(os.path.basename(source))[0]
            self.export_panel.set_output_suggestion(os.path.dirname(source), stem)
        else:
            self.export_panel.set_output_suggestion(os.path.dirname(project), os.path.basename(project))

    # v1.9.0：多选集合变化 → 动态按钮标签 + 多选禁用预览
    def _on_selection_changed(self, projects: list) -> None:
        n = len(projects)
        self.preview_btn.setEnabled(n <= 1)  # 多选时「预览当前项目」不可用
        if n >= 2:
            self.export_btn.setText(f"批量导出 ({n})")
        else:
            self.export_btn.setText("导出")
        if n == 0:
            self.status_label.setText("就绪")
        elif n == 1:
            self.status_label.setText(f"已选择 1 个项目：{os.path.basename(projects[0])}")
        else:
            self.status_label.setText(
                f"已选择 {n} 个项目（Shift 连选 / Ctrl 多选）"
            )

    # --------------------------------------------------------------- preview
    def _open_preview_current(self) -> None:
        project = self._active_project
        if not project:
            QMessageBox.information(self, "提示", "请先在左侧选择 / 点击一个项目卡片。")
            return
        self._open_preview_for(project)

    def _selected_source(self, project: str) -> str:
        """v1.7.0：项目内多 HTML 时取卡片下拉框选中的入口；否则回退到项目目录。"""
        path = self.workspace.selected_html_path(project)
        return path or project

    def _open_preview_for(self, project: str) -> None:
        from gui.preview_window import PreviewWindow  # 延迟导入，加速启动

        if self._preview_win is not None:
            if self._preview_win.isVisible():
                self._preview_win.raise_()
                self._preview_win.activateWindow()
                return
            self._preview_win = None

        width = self.size_panel.get_width()
        source = self._selected_source(project)
        win = PreviewWindow(self, width=width)
        win.setWindowTitle(f"网页预览 - {os.path.basename(source)}")
        win.load(source)
        win.destroyed.connect(lambda: setattr(self, "_preview_win", None))
        self._preview_win = win
        win.show()
        win.raise_()
        win.activateWindow()

    # --------------------------------------------------------- browser open
    def _open_in_browser(self, project: str) -> None:
        """用系统默认浏览器打开项目（可 F12 审查元素）。

        v2.1.0：挂载到进程内唯一的共享静态服务（单端口），切换项目即切换目录。
        """
        from core.static_server import resolve_index, shared_server

        source = self._selected_source(project)
        if os.path.isfile(source):
            base_dir = os.path.dirname(source)
            rel = os.path.basename(source)
        else:
            base_dir = os.path.abspath(source)
            rel = resolve_index(base_dir) or "index.html"
        try:
            srv = shared_server()
            srv.ensure_started()
            srv.mount(base_dir)
        except OSError as exc:
            QMessageBox.critical(self, "打开失败", str(exc))
            return
        url = srv.base_url + "/" + rel
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
        self.status_label.setText(f"已在系统浏览器打开：{url}")

    # ------------------------------------------------ v2.0.0 在线网站（URL）
    def _open_preview_online(self, url: str) -> None:
        from gui.preview_window import PreviewWindow  # 延迟导入，加速启动

        if self._preview_win is not None:
            if self._preview_win.isVisible():
                self._preview_win.raise_()
                self._preview_win.activateWindow()
                return
            self._preview_win = None

        width = self.size_panel.get_width()
        win = PreviewWindow(self, width=width)
        win.setWindowTitle(f"网页预览 - {url}")
        win.load("", url_override=url)  # url_override 时不启用本地静态服务
        win.destroyed.connect(lambda: setattr(self, "_preview_win", None))
        self._preview_win = win
        win.show()
        win.raise_()
        win.activateWindow()

    def _open_browser_online(self, url: str) -> None:
        threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
        self.status_label.setText(f"已在系统浏览器打开：{url}")

    # --------------------------------------------------------------- export
    def _build_params(self, source: str, output_path: str) -> ExportParams:
        extra = self.export_panel.get_params()
        width = self.size_panel.get_width()
        return ExportParams(
            source=source,
            format=extra["format"],
            width=width,
            scale=self.size_panel.get_scale(),   # v2.1.0：分辨率倍率
            fps=extra["fps"],
            loop=extra["loop"],
            transparent=extra["transparent"],
            output_path=output_path,
            max_wait=extra["max_wait"],
        )

    def _run_export(self) -> None:
        # v2.0.0：填写了在线网站地址时，优先导出该在线网站（URL 源）
        online_url = self.size_panel.get_online_url()
        if online_url:
            if self._thread is not None and self._thread.isRunning():
                QMessageBox.information(self, "提示", "已有导出任务进行中。")
                return
            output_path = self.export_panel.get_output_path()
            if not output_path:
                QMessageBox.warning(self, "提示", "请选择导出文件路径。")
                return
            params_list = [self._build_params(online_url, output_path)]
            self._start_export_worker(
                params_list, "导出中…", f"准备导出在线网站… {online_url}"
            )
            return

        # v1.9.0：导出当前多选集合（普通点击=单选；Ctrl/Shift 多选=批量）
        entries = self.workspace.export_entries()
        if not entries:
            QMessageBox.warning(
                self, "提示",
                "请先在左侧选择 / 点击一个项目卡片"
                "（可 Ctrl 单选、Shift 连选进行批量导出）。",
            )
            return
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(self, "提示", "已有导出任务进行中。")
            return

        output_path = self.export_panel.get_output_path()
        fmt = self.export_panel.get_format()
        ext = FILE_EXTENSIONS[fmt]

        if len(entries) == 1:
            if not output_path:
                QMessageBox.warning(self, "提示", "请选择导出文件路径。")
                return
            params_list = [self._build_params(entries[0], output_path)]
            label = "导出中…"
        else:
            # 批量：以输出路径所在目录为目标文件夹，每个 HTML 单独成文件
            out_dir = os.path.dirname(output_path) if output_path else ""
            if not out_dir or not os.path.isdir(out_dir):
                out_dir = os.path.dirname(entries[0])
            params_list = []
            for src in entries:
                stem = os.path.splitext(os.path.basename(src))[0]
                params_list.append(
                    self._build_params(src, os.path.join(out_dir, stem + ext))
                )
            label = f"批量导出中…({len(params_list)})"

        self._start_export_worker(params_list, label, "准备导出…")

    def _start_export_worker(self, params_list: list, label: str, status_text: str) -> None:
        """统一启动导出工作线程（本地 / 在线 / 批量共用，v2.0.0 提取）。"""
        self.progress.setValue(0)
        self.status_label.setText(status_text)
        self.export_btn.setText(label)
        self.export_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)

        self._thread = QThread(self)
        self._export_worker = Controller()
        self._export_worker.set_params_list(params_list)
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
        if result.get("batch"):
            results = result.get("results", [])
            n = len(results)
            if n == 1:
                # v2.0.0：单选也走批量通道，按单文件提示「导出完成」而非「批量导出完成」
                r = results[0]
                msgs = [
                    f"导出完成: {os.path.basename(r['path'])}\n"
                    f"尺寸 {r['width']} × {r['height']}  {r['format']}"
                ]
                if r.get("frames", 1) > 1:
                    msgs.append(f"帧数 {r['frames']}")
                if r.get("encoder"):
                    msgs.append(f"编码器: {r['encoder']}")
                for w in result.get("warnings", []):
                    msgs.append(f"提醒: {w}")
                QMessageBox.information(self, "完成", "\n".join(msgs))
                return
            lines = [f"批量导出完成：{n} 个文件"]
            for r in results[:15]:
                lines.append(
                    f"· {os.path.basename(r['path'])}  "
                    f"{r['width']}×{r['height']} {r['format']}"
                )
            if n > 15:
                lines.append(f"…等共 {n} 个文件")
            for w in result.get("warnings", []):
                lines.append(f"提醒: {w}")
            QMessageBox.information(self, "完成", "\n".join(lines))
            return
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
        self.export_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        self._thread = None
        # 依据当前多选状态刷新按钮标签 / 预览可用性（v1.9.0）
        self._on_selection_changed(self.workspace.selected_projects())

    def closeEvent(self, event) -> None:
        if self._preview_win is not None:
            self._preview_win.close()
            self._preview_win = None
        # v2.1.0：唯一共享静态服务在退出时统一停止
        try:
            from core.static_server import shared_server

            shared_server().stop()
        except Exception:
            pass
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        super().closeEvent(event)