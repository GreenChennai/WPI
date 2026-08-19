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
    QRunnable,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from core.static_server import list_html_files, resolve_index
from gui import tokens as T

_CARD_SIZE = 168  # 卡片边长（px），自适应排版按此计算列数（v1.4.0）


class _PaletteTask(QRunnable):
    """后台提取单项目主色，完成后经面板信号回传（线程安全）。"""

    def __init__(self, project_dir: str, panel: WorkspacePanel):
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
    def enterEvent(self, event: QEvent) -> None:
        self._entered = True
        self._animate.stop()
        self._animate.setStartValue(self._hover)
        self._animate.setEndValue(1.0)
        self._animate.start()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
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

    def paintEvent(self, event) -> None:
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
    """单个项目方块卡片。

    v1.7.0：项目内存在多个 HTML 文件时，入口文件从静态标签改为下拉框，
    用户可切换选择要预览 / 导出 / 浏览器打开的页面。
    """

    previewRequested = Signal(str)
    browserRequested = Signal(str)
    activated = Signal(str)
    # v1.9.0：卡片鼠标点击（project_dir, ctrl 按下, shift 按下）→ 多选逻辑
    clicked = Signal(str, bool, bool)

    def __init__(self, project_dir: str, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.setObjectName("projectCard")
        self.setFixedSize(_CARD_SIZE, _CARD_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self._selected = False
        self._multi = False        # v1.9.0：当前是否处于多选（≥2）态，决定蓝/绿配色
        self._export_all = False   # v1.9.0：是否导出项目内全部 HTML

        # v1.7.0：项目内全部 HTML 文件
        self.html_files: list[str] = list_html_files(project_dir)
        self.selected_html: str = (
            resolve_index(project_dir)
            or (self.html_files[0] if self.html_files else "")
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(6)

        self.name_label = QLabel(os.path.basename(os.path.normpath(project_dir)))
        self.name_label.setObjectName("cardTitle")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.name_label)

        # 入口文件：多 HTML 时用下拉框，单一文件时保持纯标签
        self.export_all_check: QCheckBox | None = None
        if len(self.html_files) > 1:
            # v1.9.0：位于下拉框之前，勾选后导出该项目内全部 HTML
            self.export_all_check = QCheckBox("导出全部 HTML")
            self.export_all_check.setObjectName("cardCheck")
            self.export_all_check.setToolTip("勾选后批量导出该项目内的每一个 HTML 文件")
            self.export_all_check.toggled.connect(self._on_export_all_toggled)
            lay.addWidget(self.export_all_check)

            self.entry_combo = QComboBox()
            self.entry_combo.setObjectName("cardEntry")
            self.entry_combo.addItems(self.html_files)
            self.entry_combo.setCurrentText(self.selected_html)
            self.entry_combo.setToolTip("项目内包含多个 HTML，选择要预览/导出的页面")
            self.entry_combo.currentTextChanged.connect(self._on_entry_changed)
            lay.addWidget(self.entry_combo)
            self.entry_label: QLabel | None = None
        else:
            self.entry_combo: QComboBox | None = None
            entry_label = QLabel(self.selected_html)
            entry_label.setProperty("muted", True)
            entry_label.setAlignment(Qt.AlignCenter)
            entry_label.setToolTip("项目入口 HTML 文件")
            lay.addWidget(entry_label)
            self.entry_label = entry_label

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

    # v1.7.0：下拉框切换入口 HTML
    def _on_entry_changed(self, html_name: str) -> None:
        if not html_name:
            return
        self.selected_html = html_name
        self.activated.emit(self.project_dir)

    def selected_html_path(self) -> str:
        """当前选中的入口 HTML 完整路径。"""
        return os.path.join(self.project_dir, self.selected_html)

    # v1.9.0：勾选「导出全部 HTML」后，导出项目内每一个 HTML 文件
    def _on_export_all_toggled(self, checked: bool) -> None:
        self._export_all = bool(checked)

    def export_htmls(self) -> list[str]:
        """返回待导出的 HTML 完整路径列表。

        勾选「导出全部 HTML」且项目含多个 HTML 时返回全部；
        否则仅返回当前选中的入口 HTML。
        """
        if self._export_all and len(self.html_files) > 1:
            return [os.path.join(self.project_dir, h) for h in self.html_files]
        return [self.selected_html_path()]

    # ---- 背景 / 边框（悬停与选中以缓动系数插值；v1.9.0 绿/蓝选中色）----
    def _bg_color(self) -> QColor:
        if self._selected:
            return QColor(T.SELECT_FILL_MULTI if self._multi else T.SELECT_FILL_SINGLE)
        base = QColor(T.WHITE)
        tint = QColor(T.ACCENT_TINT_BG)
        return self._lerp(base, tint, self._hover * 0.55)

    def _border_color(self) -> QColor:
        if self._selected:
            return QColor(T.SELECT_BORDER_MULTI if self._multi else T.SELECT_BORDER_SINGLE)
        base = QColor(T.BORDER)
        ho = QColor(T.ACCENT)
        return self._lerp(base, ho, self._hover)

    def _border_width(self) -> int:
        return 2 if self._selected else 1 + int(round(self._hover))

    @staticmethod
    def _lerp(a: QColor, b: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        r = int(a.red() + (b.red() - a.red()) * t)
        g = int(a.green() + (b.green() - a.green()) * t)
        bl = int(a.blue() + (b.blue() - a.blue()) * t)
        return QColor(r, g, bl)

    def mousePressEvent(self, event) -> None:
        from PySide6.QtWidgets import QApplication
        mods = QApplication.keyboardModifiers()
        ctrl = bool(mods & Qt.ControlModifier)
        shift = bool(mods & Qt.ShiftModifier)
        self.clicked.emit(self.project_dir, ctrl, shift)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool, multi: bool = False) -> None:
        if self._selected == selected and self._multi == multi:
            return
        self._selected = selected
        self._multi = multi
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

    def mousePressEvent(self, event) -> None:
        self.entered.emit(self.folder)
        super().mousePressEvent(event)


class WorkspacePanel(QGroupBox):
    projectSelected = Signal(str)   # 激活项目（目录）
    previewRequested = Signal(str)  # 打开预览窗口
    browserRequested = Signal(str)  # 系统浏览器打开
    paletteReady = Signal(str, object)  # (project_dir, colors) 后台线程回传
    workdirChanged = Signal(str)    # v1.4.0：工作目录切换（供设置记忆）
    selectionChanged = Signal(list) # v1.9.0：多选集合变化（项目 dir 列表）

    def __init__(self, parent=None):
        super().__init__("工作目录", parent)
        self.setObjectName("workdirBox")
        self._stack: list[str] = []      # 导航栈：从根目录到当前目录
        self._cards: dict[str, ProjectCard] = {}
        self._folder_cards: dict[str, FolderCard] = {}
        self._active: str | None = None
        self._entries: list = []         # v1.4.0：保序存放当前渲染条目
        self._last_cols: int = -1        # v1.8.0：重排守卫（列数未变则跳过）
        self._last_entries: object | None = None
        self._selected_projects: set[str] = set()  # v1.9.0：多选集合
        self._anchor: str | None = None             # v1.9.0：Shift 连选锚点
        self._multi: bool = False                   # v1.9.0：是否处于多选（≥2）态

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

        # 空状态容器：纵向 + 横向居中显示提示（v1.9.0 居中修复）
        self._empty_container = QWidget()
        self._empty_container.setObjectName("emptyBox")
        self._empty_layout = QVBoxLayout(self._empty_container)
        self._empty_layout.setContentsMargins(0, 0, 0, 0)
        self._empty_layout.addStretch(1)
        self.empty_label = QLabel("无可用项目")
        self.empty_label.setObjectName("emptyTitle")  # v2.2.0：字号加大
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self._empty_layout.addWidget(self.empty_label, 0, Qt.AlignHCenter | Qt.AlignVCenter)
        self._empty_layout.addStretch(1)
        self._empty_container.setVisible(False)
        root.addWidget(self._empty_container, 1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(12)
        # v1.8.0：水平居中，消除「最后一列右侧贴着滚动条」的留白观感
        self._grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._scroll.setWidget(self._grid_host)
        # 工作目录背景统一为 SURFACE(#F6F8FA)
        from PySide6.QtGui import QColor, QPalette

        self.setAutoFillBackground(False)
        for w in (self._scroll, self._scroll.viewport(), self._grid_host, self._empty_container):
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

    def selected_html_path(self, project_dir: str | None = None) -> str | None:
        """返回项目当前选中的入口 HTML 完整路径（v1.7.0）。

        project_dir 为空时取当前激活项目；找不到返回 None（调用方回退到目录）。
        """
        project = project_dir or self._active
        if project and project in self._cards:
            return self._cards[project].selected_html_path()
        return None

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

        # v1.9.0：切换目录 / 重扫时清空多选状态
        self._selected_projects.clear()
        self._anchor = None
        self._multi = False
        self.selectionChanged.emit([])

        current = self.current_dir()
        self.path_label.setText(current)
        self.back_btn.setVisible(len(self._stack) > 1)

        if not os.path.isdir(current):
            self.empty_label.setText("工作目录不可用，请选择现有文件夹。")
            self._empty_container.setVisible(True)
            self._scroll.setVisible(False)
            return

        projects, folders = self._scan_entries(current)
        self._entries = [  # v1.4.0：保序条目（先项目后子目录），供自适应排版 reflow
            *projects, *folders
        ]
        self._refresh_cards(projects, folders)
        self._reflow()

        empty = not (projects or folders)
        self._empty_container.setVisible(empty)
        self._scroll.setVisible(not empty)

    def _refresh_cards(self, projects: list[str], folders: list[str]) -> None:
        """v1.4.0：仅创建新卡片（每个条目对应一张卡片，顺序记录）。"""
        for project in projects:
            if project in self._cards:
                continue
            card = ProjectCard(project, self)
            card.previewRequested.connect(self.previewRequested.emit)
            card.browserRequested.connect(self.browserRequested.emit)
            card.activated.connect(self._on_activate)
            card.clicked.connect(self._on_card_clicked)
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
        v1.8.0：列数与条目均未变化（如纯拖动缩放未跨列）时跳过重排，
        减少重复布局与卡片抖动。
        """
        avail = max(200, self._scroll.viewport().width()
                    - T.SPACE_LG * 2 - self._grid.spacing())
        card_w = _CARD_SIZE + self._grid.spacing()
        cols = max(1, (avail + self._grid.spacing()) // card_w)
        if cols == self._last_cols and self._entries is self._last_entries:
            return
        self._last_cols = cols
        self._last_entries = self._entries

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

    def resizeEvent(self, event) -> None:
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
        """仅记录「当前激活项目」（用于预览 / 输出建议），不改变多选高亮。

        v1.9.0：卡片选中高亮统一由 _apply_selection 按多选集合驱动。
        """
        self._active = project

    # ------------------------------------------------------- v1.9.0 多选逻辑
    def _on_card_clicked(self, project: str, ctrl: bool, shift: bool) -> None:
        """卡片点击：普通=单选；Ctrl=切换；Shift=从锚点连选（批量导出）。"""
        order = list(self._cards.keys())  # 项目显示顺序（扫描序，稳定）
        if shift and self._anchor is not None and self._anchor in self._cards:
            try:
                a = order.index(self._anchor)
                b = order.index(project)
            except ValueError:
                a = b = 0
            lo, hi = (a, b) if a <= b else (b, a)
            self._apply_selection(set(order[lo:hi + 1]), anchor=self._anchor)
        elif ctrl:
            sel = set(self._selected_projects)
            if project in sel:
                sel.discard(project)
            else:
                sel.add(project)
            self._apply_selection(sel, anchor=project)
        else:
            self._apply_selection({project}, anchor=project)
        # 激活项目用于预览 / 输出建议（即使被取消选中也保留最后交互项）
        self._set_active(project)
        self.projectSelected.emit(project)

    def _apply_selection(self, sel: set[str], anchor: str | None = None) -> None:
        self._selected_projects = set(sel)
        if anchor is not None:
            self._anchor = anchor
        self._multi = len(self._selected_projects) >= 2
        for proj, card in self._cards.items():
            card.set_selected(proj in self._selected_projects, self._multi)
        self.selectionChanged.emit(sorted(self._selected_projects))

    def selected_projects(self) -> list[str]:
        """当前多选集合（项目 dir 列表，排序）。"""
        return sorted(self._selected_projects)

    def export_entries(self) -> list[str]:
        """返回所有选中项目待导出的 HTML 完整路径（含「导出全部 HTML」展开）。"""
        out: list[str] = []
        for proj in sorted(self._selected_projects):
            card = self._cards.get(proj)
            if card is None:
                continue
            out.extend(card.export_htmls())
        return out

    def _apply_palette(self, project: str, colors: object) -> None:
        """后台色卡提取完成后更新对应卡片（GUI 线程槽）。"""
        card = self._cards.get(project)
        if card is None or not colors:
            return
        card.set_palette(colors)