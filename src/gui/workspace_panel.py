"""工作目录项目卡片面板（布局左侧，v1.2.0；v1.3.0 自绘高亮卡片）。

- 以 QGroupBox「工作目录」呈现，目录地址显示在标题下方；
- 含 index.html 的文件夹为「项目」卡片（正方形圆角 + 4 主色色卡）；
- 不含 index.html 的文件夹视为「子目录卡片」，点击可进入继续搜索
  （二级 / 三级 / 四级…），并提供「返回上级」导航；
- 色卡通过高性能静态资源扫描异步提取，不阻塞界面。
"""

from __future__ import annotations

import os

from PySide6.QtCore import (
    Property,
    QEvent,
    QPropertyAnimation,
    QThreadPool,
    QRunnable,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.color_profiler import extract_palette
from core.static_server import resolve_index
from gui import tokens as T

_CARD_SIZE = 168  # 卡片边长（px），自适应排版按此计算列数（v1.4.0）


class _PaletteTask(QRunnable):
    """后台提取单项目主色，完成后经面板信号回传（线程安全）。"""

    def __init__(self, project_dir: str, panel: "WorkspacePanel"):
        super().__init__()
        self.project_dir = project_dir
        self.panel = panel

    def run(self) -> None:
        colors = extract_palette(self.project_dir, top=4)
        # emit 跨线程自动使用 QueuedConnection，回到 GUI 线程执行
        self.panel.paletteReady.emit(self.project_dir, tuple(colors))


class SwatchBox(QFrame):
    """单个色卡小方块。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("swatchBox")
        self.setFixedSize(20, 20)
        self.setStyleSheet(
            "border-radius: 4px; border: 1px solid rgba(0,0,0,0.08);"
        )

    def set_color(self, hex_color: str) -> None:
        self.setStyleSheet(
            f"background: {hex_color}; border-radius: 4px;"
            " border: 1px solid rgba(0,0,0,0.08);"
        )
        self.setToolTip(hex_color)


class _CardBase(QWidget):
    """正方形圆角卡片基类：自定义绘制背景 + 悬停高亮动画 + 选中变色。"""

    _RADIUS = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardBase")
        self._hover = 0.0      # 0~1 缓动系数
        self._animate = QPropertyAnimation(self, b"hover", self)
        self._animate.setDuration(160)
        self._entered = False

    # ---- hover 属性（供 QPropertyAnimation 驱动）----
    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, v: float) -> None:
        self._hover = v
        self.update()

    hover = Property(float, get_hover, set_hover)

    # ---- 鼠标进出动画 ----
    def enterEvent(self, event: QEvent) -> None:  # noqa: N802
        self._entered = True
        self._animate.stop()
        self._animate.setStartValue(self._hover)
        self._animate.setEndValue(1.0)
        self._animate.start()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        self._entered = False
        self._animate.stop()
        self._animate.setStartValue(self._hover)
        self._animate.setEndValue(0.0)
        self._animate.start()
        super().leaveEvent(event)

    def is_hovered(self) -> bool:
        return self._entered

    def _bg_color(self) -> QColor:
        return QColor(T.WHITE)

    def _border_color(self) -> QColor:
        return QColor(T.BORDER)

    def _border_width(self) -> int:
        return 1

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, _CardBase._RADIUS, _CardBase._RADIUS)
        p.fillPath(path, self._bg_color())
        pen = p.pen()
        pen.setColor(self._border_color())
        pen.setWidth(self._border_width())
        p.setPen(pen)
        p.drawPath(path)


class ProjectCard(_CardBase):
    """单个项目方块卡片。"""

    previewRequested = Signal(str)
    browserRequested = Signal(str)
    activated = Signal(str)

    def __init__(self, project_dir: str, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.setObjectName("projectCard")
        self.setFixedSize(_CARD_SIZE, _CARD_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self._selected = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(6)

        self.name_label = QLabel(os.path.basename(os.path.normpath(project_dir)))
        self.name_label.setObjectName("cardTitle")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.name_label)

        entry = resolve_index(project_dir) or ""
        entry_label = QLabel(entry)
        entry_label.setProperty("muted", True)
        entry_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(entry_label)

        # 主色色卡（异步填充）
        swatch_row = QHBoxLayout()
        swatch_row.setAlignment(Qt.AlignCenter)
        swatch_row.setSpacing(4)
        self.swatches: list[SwatchBox] = []
        for _ in range(4):
            sw = SwatchBox(self)
            sw.setStyleSheet(
                "border-radius: 4px; border: 1px solid rgba(0,0,0,0.08);"
                " background: rgba(0,0,0,0.04);"
            )
            self.swatches.append(sw)
            swatch_row.addWidget(sw)
        lay.addLayout(swatch_row)

        btns = QHBoxLayout()
        btns.setSpacing(6)
        btn_preview = QPushButton("预览")
        btn_preview.setObjectName("cardPrimary")
        btn_preview.clicked.connect(lambda: self.previewRequested.emit(self.project_dir))
        btns.addWidget(btn_preview, 1)
        btn_browser = QPushButton("浏览器打开")
        btn_browser.setObjectName("cardSecondary")
        btn_browser.clicked.connect(lambda: self.browserRequested.emit(self.project_dir))
        btn_browser.setToolTip("用系统默认浏览器打开该项目（可 F12 审查元素）")
        btns.addWidget(btn_browser, 1)
        lay.addLayout(btns)

    # ---- 背景 / 边框（悬停与选中以缓动系数插值）----
    def _bg_color(self) -> QColor:
        base = QColor(T.WHITE)
        tint = QColor(T.ACCENT_TINT_BG)
        return self._selection_color(base, tint)

    def _border_color(self) -> QColor:
        base = QColor(T.BORDER)
        ho = QColor(T.ACCENT)
        if self._selected:
            return QColor(T.ACCENT)
        return self._lerp(base, ho, self._hover)

    def _border_width(self) -> int:
        return 2 if self._selected else 1 + int(round(self._hover))

    def _selection_color(self, base: QColor, tint: QColor) -> QColor:
        """选中时向强调色浅底过渡，悬停时向强调色过渡。"""
        strength = 1.0 if self._selected else self._hover * 0.55
        c = base
        c = self._lerp(c, tint, strength)
        return c

    @staticmethod
    def _lerp(a: QColor, b: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        r = int(a.red() + (b.red() - a.red()) * t)
        g = int(a.green() + (b.green() - a.green()) * t)
        bl = int(a.blue() + (b.blue() - a.blue()) * t)
        return QColor(r, g, bl)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.activated.emit(self.project_dir)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self.update()

    def set_palette(self, colors: tuple[str, ...] | list[str]) -> None:
        for idx, sw in enumerate(self.swatches):
            if idx < len(colors):
                sw.set_color(colors[idx])


class FolderCard(_CardBase):
    """不含 index.html 的子目录卡片，点击进入继续搜索。"""

    entered = Signal(str)

    def __init__(self, folder: str, parent=None):
        super().__init__(parent)
        self.folder = folder
        self.setObjectName("folderCard")
        self.setFixedSize(_CARD_SIZE, _CARD_SIZE)
        self.setCursor(Qt.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        icon = QLabel("📁")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 28px; border: none;")
        lay.addWidget(icon, 0, Qt.AlignCenter)

        self.name_label = QLabel(os.path.basename(os.path.normpath(folder)))
        self.name_label.setObjectName("cardTitle")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.name_label, 1)

        tag = QLabel("子目录 · 点击进入")
        tag.setProperty("muted", True)
        tag.setAlignment(Qt.AlignCenter)
        lay.addWidget(tag)

        btn_enter = QPushButton("进入")
        btn_enter.setObjectName("cardPrimary")
        btn_enter.clicked.connect(lambda: self.entered.emit(self.folder))
        lay.addWidget(btn_enter)

    # ---- 悬停高亮（同样走缓动插值）----
    def _bg_color(self) -> QColor:
        base = QColor(T.WHITE)
        tint = QColor(T.ACCENT_TINT_BG)
        return ProjectCard._lerp(base, tint, self._hover * 0.55)

    def _border_color(self) -> QColor:
        base = QColor(T.BORDER)
        ho = QColor(T.ACCENT)
        return ProjectCard._lerp(base, ho, self._hover)

    def _border_width(self) -> int:
        return 1 + int(round(self._hover))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.entered.emit(self.folder)
        super().mousePressEvent(event)


class WorkspacePanel(QGroupBox):
    projectSelected = Signal(str)   # 激活项目（目录）
    previewRequested = Signal(str)  # 打开预览窗口
    browserRequested = Signal(str)  # 系统浏览器打开
    paletteReady = Signal(str, object)  # (project_dir, colors) 后台线程回传
    workdirChanged = Signal(str)    # v1.4.0：工作目录切换（供设置记忆）

    def __init__(self, parent=None):
        super().__init__("工作目录", parent)
        self.setObjectName("workdirBox")
        self._stack: list[str] = []      # 导航栈：从根目录到当前目录
        self._cards: dict[str, ProjectCard] = {}
        self._folder_cards: dict[str, FolderCard] = {}
        self._active: str | None = None
        self._entries: list = []         # v1.4.0：保序存放当前渲染条目

        root = QVBoxLayout(self)
        root.setContentsMargins(T.SPACE_LG, T.SPACE_SM, T.SPACE_LG, T.SPACE_LG)
        root.setSpacing(6)

        # 目录地址显示在标题下方
        self.path_label = QLabel()
        self.path_label.setProperty("muted", True)
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.path_label)

        # 导航行：返回上级
        nav = QHBoxLayout()
        self.back_btn = QPushButton("← 返回上级")
        self.back_btn.setObjectName("ghostBtn")
        self.back_btn.clicked.connect(self._go_up)
        self.back_btn.setVisible(False)
        nav.addWidget(self.back_btn)
        nav.addStretch(1)
        root.addLayout(nav)

        self.empty_label = QLabel("该目录下暂无可用项目。\n"
                                  "把包含 index.html 的网页项目文件夹放入工作目录，\n"
                                  "或点击上方子目录进入继续搜索。")
        self.empty_label.setProperty("secondary", True)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)
        root.addWidget(self.empty_label)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(12)
        self._grid.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._grid_host)
        # 工作目录背景统一为 SURFACE(#F6F8FA)
        from PySide6.QtGui import QColor, QPalette

        self.setAutoFillBackground(False)
        for w in (self._scroll, self._scroll.viewport(), self._grid_host):
            pal = QPalette()
            pal.setColor(QPalette.Window, QColor(T.SURFACE))
            w.setAutoFillBackground(True)
            w.setPalette(pal)
        root.addWidget(self._scroll, 1)

        self._pool = QThreadPool.globalInstance()
        self.paletteReady.connect(self._apply_palette)

    # ------------------------------------------------------------------ API
    def workdir(self) -> str:
        return self._stack[0] if self._stack else ""

    def active_project(self) -> str | None:
        return self._active

    def set_workdir(self, path: str) -> None:
        path = os.path.abspath(path)
        self._stack = [path]
        self._active = None
        self.refresh()
        self.workdirChanged.emit(path)

    def choose_directory(self) -> None:
        """弹窗选择新的工作目录（右侧「更换目录」按钮调用）。"""
        start = self.workdir() if os.path.isdir(self.workdir()) else os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "选择工作目录", start)
        if path:
            self.set_workdir(path)

    def refresh(self) -> None:
        for card in list(self._cards.values()):
            card.deleteLater()
        self._cards.clear()
        for card in list(self._folder_cards.values()):
            card.deleteLater()
        self._folder_cards.clear()

        current = self.current_dir()
        self.path_label.setText(current)
        self.back_btn.setVisible(len(self._stack) > 1)

        if not os.path.isdir(current):
            self.empty_label.setText("工作目录不可用，请选择现有文件夹。")
            self.empty_label.setVisible(True)
            return

        projects, folders = self._scan_entries(current)
        self._entries = [  # v1.4.0：保序条目（先项目后子目录），供自适应排版 reflow
            *projects, *folders
        ]
        self._refresh_cards(projects, folders)
        self._reflow()

        empty = not (projects or folders)
        self.empty_label.setVisible(empty)

    def _refresh_cards(self, projects: list[str], folders: list[str]) -> None:
        """v1.4.0：仅创建新卡片（每个条目对应一张卡片，顺序记录）。"""
        for project in projects:
            if project in self._cards:
                continue
            card = ProjectCard(project, self)
            card.previewRequested.connect(self.previewRequested.emit)
            card.browserRequested.connect(self.browserRequested.emit)
            card.activated.connect(self._on_activate)
            self._cards[project] = card
            task = _PaletteTask(project, self)
            self._pool.start(task)

        for folder in folders:
            if folder in self._folder_cards:
                continue
            card = FolderCard(folder, self)
            card.entered.connect(self._enter_folder)
            self._folder_cards[folder] = card

    # ------------------------------------------------------------ adaptive
    def _reflow(self) -> None:
        """v1.4.0：按可用宽度动态计算每行卡片数，替换固定的 3 列布局。

        卡片固定 168×168；UI 宽度每次变化（工作目录面板变宽/窄、窗口缩放）
        时重新计算列数并重排，保证尽可能多显示卡片且缩进居中。
        """
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()  # 先隐藏再在下方 addWidget，避免重排抖动

        # 可用宽度 = 滚动区域视口宽度 - 面板内边距
        avail = max(200, self._scroll.viewport().width()
                    - T.SPACE_LG * 2 - self._grid.spacing())
        card_w = _CARD_SIZE + self._grid.spacing()
        cols = max(1, (avail + self._grid.spacing()) // card_w)

        row = 0
        col = 0
        for path in self._entries:
            widget = self._cards.get(path) or self._folder_cards.get(path)
            if widget is None:
                continue
            self._grid.addWidget(widget, row, col)
            widget.show()
            col += 1
            if col >= cols:
                col = 0
                row += 1
        self._grid.setColumnStretch(cols, 0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._grid.count() and self._entries and self.isVisible():
            self._reflow()

    # ------------------------------------------------------------- internal
    def current_dir(self) -> str:
        return self._stack[-1] if self._stack else ""

    def _enter_folder(self, folder: str) -> None:
        self._stack.append(os.path.abspath(folder))
        self._active = None
        self.refresh()

    def _go_up(self) -> None:
        if len(self._stack) > 1:
            self._stack.pop()
            self._active = None
            self.refresh()

    @staticmethod
    def _scan_entries(workdir: str) -> tuple[list[str], list[str]]:
        """返回 (含入口 HTML 的项目目录列表, 无入口的子目录列表)。"""
        projects: list[str] = []
        folders: list[str] = []
        try:
            names = sorted(os.listdir(workdir))
        except OSError:
            return projects, folders
        for name in names:
            full = os.path.join(workdir, name)
            if os.path.isdir(full):
                if resolve_index(full):
                    projects.append(full)
                else:
                    folders.append(full)
        return projects, folders

    @staticmethod
    def _scan_projects(workdir: str) -> list[str]:
        """兼容旧接口：仅返回含入口 HTML 的项目目录。"""
        projects, _folders = WorkspacePanel._scan_entries(workdir)
        return projects

    def _on_activate(self, project: str) -> None:
        self._set_active(project)
        self.projectSelected.emit(project)

    def _set_active(self, project: str) -> None:
        if self._active == project:
            return
        if self._active in self._cards:
            self._cards[self._active].set_selected(False)
        self._active = project
        if project in self._cards:
            self._cards[project].set_selected(True)

    def _apply_palette(self, project: str, colors: object) -> None:
        """后台色卡提取完成后更新对应卡片（GUI 线程槽）。"""
        card = self._cards.get(project)
        if card is None or not colors:
            return
        card.set_palette(colors)