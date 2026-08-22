"""工作目录项目卡片面板（布局左侧）。

- 以 QGroupBox「工作目录」呈现，目录地址显示在标题下方；
- 含 index.html 的文件夹为「项目」卡片（正方形圆角 + 4 主色色卡）；
- 不含 index.html 的文件夹视为「子目录卡片」，点击可进入继续搜索
  （二级 / 三级 / 四级…），并提供「返回上级」导航；
- 若某目录内存在 pure.html 标记文件（仅校验名字与后缀，不读内容），该目录
  本身不作为项目，而是作为可进入的「二级文件夹」；其内除 pure.html 外的每个
  .html/.htm 文件各视为一个独立项目（进入该文件夹后展开为独立卡片）；
- 色卡通过高性能静态资源扫描异步提取，不阻塞界面。
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import (
    Property,
    QEvent,
    QPropertyAnimation,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from config.presets import app_base_dir, default_workspace_dir
from core.color_profiler import extract_palette
from core.static_server import list_html_files, resolve_index
from gui import tokens as T


def _add_icon_path() -> str:
    """「+」按钮图标（加号.svg），优先取打包/仓库 assets，兜底用户原路径。"""
    name = "加号.svg"
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", app_base_dir())
        for base in (meipass, app_base_dir()):
            p = os.path.join(base, "assets", name)
            if os.path.isfile(p):
                return p
    p = os.path.join(app_base_dir(), "assets", name)
    if os.path.isfile(p):
        return p
    return r"E:\平日资料\GitHub\图标\icon\加号.svg"


def _load_add_icon() -> QIcon:
    """渲染加号 SVG 为图标。

    采用 QSvgRenderer 直接绘制（依赖保留的 Qt6Svg 运行库），避免依赖可能被
    打包剔除的 qsvg 图片格式插件，保证 exe 内图标仍正常显示。
    """
    path = _add_icon_path()
    try:
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtGui import QPainter as _QP, QPixmap
        renderer = QSvgRenderer(path)
        if renderer.isValid():
            pm = QPixmap(20, 20)
            pm.fill(Qt.transparent)
            _QP(pm).render(renderer)
            return QIcon(pm)
    except Exception:
        pass
    return QIcon(path)

_CARD_SIZE = 168  # 卡片边长（px），自适应排版按此计算列数


class _PaletteTask(QRunnable):
    """后台提取单项目主色，完成后经面板信号回传（线程安全）。

    key 为项目唯一标识；html_path 为待提取主色的具体 HTML 文件（single_file
    模式：仅扫描该文件及其同目录被引用的样式/脚本，保证同目录各 HTML 独立配色）。
    """

    def __init__(self, key: str, html_path: str, panel: WorkspacePanel):
        super().__init__()
        self.key = key
        self.html_path = html_path
        self.panel = panel

    def run(self) -> None:
        colors = extract_palette(self.html_path, top=4, single_file=True)
        # emit 跨线程自动使用 QueuedConnection，回到 GUI 线程执行
        self.panel.paletteReady.emit(self.key, tuple(colors))


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

    项目内存在多个 HTML 文件时，入口文件从静态标签改为下拉框，
    用户可切换选择要预览 / 导出 / 浏览器打开的页面。
    """

    previewRequested = Signal(str)
    browserRequested = Signal(str)
    activated = Signal(str)
    # 下拉框切换入口 HTML 后，请求按新文件重新提取主色
    paletteRequest = Signal(str)
    # 卡片鼠标点击（project_dir, ctrl 按下, shift 按下）→ 多选逻辑
    clicked = Signal(str, bool, bool)

    def __init__(self, project_dir: str, parent=None, entry_html: str | None = None):
        super().__init__(parent)
        self._entry_html = entry_html
        if entry_html:
            # pure.html 模式下的「单文件项目」：project_dir 仍是挂载/取色目录，
            # 唯一标识用文件完整路径，避免同目录多文件互相覆盖。
            self.project_dir = project_dir
            self._key = os.path.join(project_dir, entry_html)
            display = (
                entry_html[:-5] if entry_html.lower().endswith(".html")
                else entry_html
            )
        else:
            self.project_dir = os.path.abspath(project_dir)
            self._key = self.project_dir
            display = os.path.basename(os.path.normpath(project_dir))
        self.setObjectName("projectCard")
        self.setFixedSize(_CARD_SIZE, _CARD_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self._selected = False
        self._multi = False        # 当前是否处于多选（≥2）态，决定蓝/绿配色
        self._export_all = False   # 是否导出项目内全部 HTML

        # 项目内全部 HTML 文件
        self.html_files: list[str] = (
            [entry_html] if entry_html else list_html_files(self.project_dir)
        )
        self.selected_html: str = (
            entry_html
            or resolve_index(self.project_dir)
            or (self.html_files[0] if self.html_files else "")
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(6)

        self.name_label = QLabel(display)
        self.name_label.setObjectName("cardTitle")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.name_label)

        # 入口文件：多 HTML 时用下拉框，单一文件时保持纯标签
        self.export_all_check: QCheckBox | None = None
        if len(self.html_files) > 1:
            # 位于下拉框之前，勾选后导出该项目内全部 HTML
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
        btn_preview.clicked.connect(lambda: self.previewRequested.emit(self._key))
        btns.addWidget(btn_preview, 1)
        btn_browser = QPushButton("浏览器打开")
        btn_browser.setObjectName("cardSecondary")
        btn_browser.clicked.connect(lambda: self.browserRequested.emit(self._key))
        btn_browser.setToolTip("用系统默认浏览器打开该项目（可 F12 审查元素）")
        btns.addWidget(btn_browser, 1)
        lay.addLayout(btns)

    # 下拉框切换入口 HTML
    def _on_entry_changed(self, html_name: str) -> None:
        if not html_name:
            return
        self.selected_html = html_name
        self.activated.emit(self._key)
        # 入口 HTML 变化 → 按新文件重新提取 4 主题色
        self.paletteRequest.emit(self._key)

    def selected_html_path(self) -> str:
        """当前选中的入口 HTML 完整路径。"""
        return os.path.join(self.project_dir, self.selected_html)

    # 勾选「导出全部 HTML」后，导出项目内每一个 HTML 文件
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

    # ---- 背景 / 边框（悬停与选中以缓动系数插值；绿/蓝选中色）----
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
        self.clicked.emit(self._key, ctrl, shift)
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
    paletteReady = Signal(str, object)  # (key, colors) 后台线程回传
    workdirChanged = Signal(str)    # 当前标签页根目录切换（供设置记忆）
    tabsChanged = Signal(list)      # 标签页路径列表（顺序即排序，供设置记忆）
    selectionChanged = Signal(list) # 多选集合变化（项目 dir 列表）

    def __init__(self, parent=None):
        super().__init__("工作目录", parent)
        self.setObjectName("workdirBox")
        self._stack: list[str] = []      # 导航栈：从当前标签页根目录到当前目录
        self._cards: dict[str, ProjectCard] = {}
        self._folder_cards: dict[str, FolderCard] = {}
        self._active: str | None = None
        self._entries: list = []         # 保序存放当前渲染条目
        self._last_cols: int = -1        # 重排守卫（列数未变则跳过）
        self._last_entries: object | None = None
        self._selected_projects: set[str] = set()  # 多选集合
        self._anchor: str | None = None             # Shift 连选锚点
        self._multi: bool = False                   # 是否处于多选（≥2）态

        # 多工作目录标签页（WorkerFile 固定首位且不可关闭/移动）
        self._tabs: list[str] = []
        self._current: int = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(T.SPACE_LG, T.SPACE_SM, T.SPACE_LG, T.SPACE_LG)
        root.setSpacing(6)

        # 标签页行：目录标签 + 右侧「+」按钮（永远在最右）
        tab_row = QHBoxLayout()
        tab_row.setSpacing(4)
        tab_row.setContentsMargins(0, 0, 0, 8)   # 与下方项目列表保持安全距离
        self._tabbar = QTabBar()
        self._tabbar.setObjectName("workdirTabs")
        self._tabbar.setMovable(True)
        self._tabbar.setTabsClosable(True)
        self._tabbar.setDrawBase(False)
        self._tabbar.currentChanged.connect(self._on_tab_selected)
        self._tabbar.tabCloseRequested.connect(self._on_tab_close)
        self._tabbar.tabMoved.connect(self._on_tab_moved)
        self._tabbar.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tabbar.customContextMenuRequested.connect(self._on_tab_context_menu)
        tab_row.addWidget(self._tabbar, 1)
        self._add_tab_btn = QPushButton()
        self._add_tab_btn.setObjectName("tabAdd")
        self._add_tab_btn.setToolTip("添加工作目录（新建标签页）")
        self._add_tab_btn.setFixedSize(30, 30)
        self._add_tab_btn.setIcon(_load_add_icon())
        self._add_tab_btn.setIconSize(QSize(18, 18))
        self._add_tab_btn.clicked.connect(self.add_directory)
        tab_row.addWidget(self._add_tab_btn)
        root.addLayout(tab_row)

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

        # 空状态容器：纵向 + 横向居中显示提示
        self._empty_container = QWidget()
        self._empty_container.setObjectName("emptyBox")
        self._empty_layout = QVBoxLayout(self._empty_container)
        self._empty_layout.setContentsMargins(0, 0, 0, 0)
        self._empty_layout.addStretch(1)
        self.empty_label = QLabel("无可用项目")
        self.empty_label.setObjectName("emptyTitle")  # 字号加大
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
        # 水平居中，消除「最后一列右侧贴着滚动条」的留白观感
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
        """返回项目当前选中的入口 HTML 完整路径。

        project_dir 为空时取当前激活项目；找不到返回 None（调用方回退到目录）。
        """
        project = project_dir or self._active
        if project and project in self._cards:
            return self._cards[project].selected_html_path()
        return None

    # ------------------------------------------------------------------ tabs
    def init_tabs(self, tabs: list[str], current: str | None = None) -> None:
        """初始化标签页（顺序即排序）。WorkerFile 默认存在且不可删除，但可移动。

        tabs：调用方从设置恢复的标签页绝对路径列表；current：当前选中项。
        """
        wf = default_workspace_dir()
        cleaned: list[str] = []
        seen: set[str] = set()
        for p in list(tabs):
            ap = os.path.abspath(p)
            if ap in seen:
                continue
            seen.add(ap)
            cleaned.append(ap)
        if not any(os.path.abspath(t) == os.path.abspath(wf) for t in cleaned):
            cleaned.insert(0, wf)            # 仅当缺失时补入 WorkerFile
        self._tabs = cleaned
        if current and current in self._tabs:
            self._current = self._tabs.index(current)
        else:
            self._current = 0
        self._rebuild_tabbar()
        self.tabsChanged.emit(list(self._tabs))
        self._activate_current()

    def add_directory(self) -> None:
        """弹窗选择目录并作为新标签页加入（右侧「+」按钮调用）。"""
        start = (self._tabs[self._current]
                 if self._tabs and os.path.isdir(self._tabs[self._current])
                 else os.path.expanduser("~"))
        path = QFileDialog.getExistingDirectory(self, "添加工作目录", start)
        if path:
            self.add_tab(path)

    def add_tab(self, path: str) -> None:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return
        if path in self._tabs:                  # 已存在 → 直接切换
            self._current = self._tabs.index(path)
            self._rebuild_tabbar()
            self._activate_current()
            return
        self._tabs.append(path)
        self._current = len(self._tabs) - 1
        self._rebuild_tabbar()
        self.tabsChanged.emit(list(self._tabs))
        self._activate_current()

    def remove_tab(self, index: int) -> None:
        if not (0 <= index < len(self._tabs)):
            return
        if os.path.abspath(self._tabs[index]) == os.path.abspath(default_workspace_dir()):
            return                            # WorkerFile 不可删除
        self._tabs.pop(index)
        if self._current == index:
            self._current = min(index, len(self._tabs) - 1)
        elif self._current > index:
            self._current -= 1
        self._rebuild_tabbar()
        self.tabsChanged.emit(list(self._tabs))
        self._activate_current()

    def _activate_current(self) -> None:
        if not self._tabs:
            return
        root = self._tabs[self._current]
        self._stack = [root]
        self._active = None
        self.refresh()
        self.workdirChanged.emit(root)

    def _rebuild_tabbar(self) -> None:
        self._tabbar.blockSignals(True)
        while self._tabbar.count():
            self._tabbar.removeTab(0)
        wf = default_workspace_dir()
        for p in self._tabs:
            self._tabbar.addTab(os.path.basename(os.path.normpath(p)))
        for i in range(self._tabbar.count()):
            self._tabbar.setTabToolTip(i, self._tabs[i])
            # WorkerFile 不可删除：移除其关闭按钮（位置不固定，按路径判定）
            if os.path.abspath(self._tabs[i]) == os.path.abspath(wf):
                self._tabbar.setTabButton(i, QTabBar.RightSide, None)
        self._tabbar.setCurrentIndex(self._current)
        self._tabbar.blockSignals(False)
        # 标签宽度自适应（布局完成后按实际可用宽度压缩）
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._adjust_tab_widths)

    def _adjust_tab_widths(self) -> None:
        """标签默认 160×30；若总宽超出可用宽度则压缩（下限 48）以适配 UI。"""
        count = self._tabbar.count()
        if count == 0:
            return
        avail = self._tabbar.width()
        if avail <= 0:
            return
        target = 160
        if count * 160 > avail:
            target = max(48, avail // count)
        self._tabbar.setStyleSheet(
            f"QTabBar#workdirTabs::tab {{ min-width: {target}px; "
            f"max-width: {target}px; height: 30px; }}"
        )

    def _on_tab_selected(self, index: int) -> None:
        if 0 <= index < len(self._tabs) and index != self._current:
            self._current = index
            self._activate_current()

    def _on_tab_close(self, index: int) -> None:
        self.remove_tab(index)

    def _on_tab_moved(self, frm: int, to: int) -> None:
        n = len(self._tabs)
        if frm == to or not (0 <= frm < n) or not (0 <= to <= n):
            self._rebuild_tabbar()          # 越界则还原
            return
        cur = self._tabs[self._current]
        item = self._tabs.pop(frm)
        self._tabs.insert(to, item)
        self._current = self._tabs.index(cur)
        self._rebuild_tabbar()
        self.tabsChanged.emit(list(self._tabs))

    def _on_tab_context_menu(self, pos) -> None:
        idx = self._tabbar.tabAt(pos)
        if idx < 0 or idx >= len(self._tabs):
            return
        path = self._tabs[idx]
        menu = QMenu(self)
        act_open = menu.addAction("在文件管理器中打开")
        act_del = menu.addAction("删除这个工作目录")
        if os.path.abspath(path) == os.path.abspath(default_workspace_dir()):
            act_del.setEnabled(False)        # WorkerFile 不可删除
        action = menu.exec(self._tabbar.mapToGlobal(pos))
        if action is None:
            return
        if action == act_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        elif action == act_del:
            self.remove_tab(idx)

    def set_workdir(self, path: str) -> None:
        """兼容旧接口：以目录路径驱动（自动转为对应/新增标签页并激活）。"""
        path = os.path.abspath(path)
        if path in self._tabs:
            self._current = self._tabs.index(path)
        else:
            self._tabs.append(path)
            self._current = len(self._tabs) - 1
        self._rebuild_tabbar()
        self.tabsChanged.emit(list(self._tabs))
        self._activate_current()

    def refresh(self) -> None:
        for card in list(self._cards.values()):
            card.deleteLater()
        self._cards.clear()
        for card in list(self._folder_cards.values()):
            card.deleteLater()
        self._folder_cards.clear()

        # 切换目录 / 重扫时清空多选状态
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
        self._entries = [  # 保序条目（先项目后子目录），供自适应排版 reflow
            (p if isinstance(p, str) else os.path.join(p[0], p[1]))
            for p in projects
        ]
        self._entries.extend(folders)
        self._refresh_cards(projects, folders)
        self._reflow()

        empty = not (projects or folders)
        self._empty_container.setVisible(empty)
        self._scroll.setVisible(not empty)

    def _refresh_cards(self, projects, folders) -> None:
        """仅创建新卡片（每个条目对应一张卡片，顺序记录）。

        projects 元素为目录路径（普通项目）或 (目录, html 文件名) 元组
        （pure.html 模式下的单文件项目）；folders 为子目录路径。
        """
        for proj in projects:
            if isinstance(proj, tuple):
                d, html = proj
                key = os.path.join(d, html)
                if key in self._cards:
                    continue
                card = ProjectCard(d, self, entry_html=html)
            else:
                if proj in self._cards:
                    continue
                card = ProjectCard(proj, self)
            card.previewRequested.connect(self.previewRequested.emit)
            card.browserRequested.connect(self.browserRequested.emit)
            card.activated.connect(self._on_activate)
            card.clicked.connect(self._on_card_clicked)
            card.paletteRequest.connect(self._on_palette_request)
            self._cards[card._key] = card
            task = _PaletteTask(card._key, card.selected_html_path(), self)
            self._pool.start(task)

        for folder in folders:
            if folder in self._folder_cards:
                continue
            card = FolderCard(folder, self)
            card.entered.connect(self._enter_folder)
            self._folder_cards[folder] = card

    # ------------------------------------------------------------ adaptive
    def _reflow(self) -> None:
        """按可用宽度动态计算每行卡片数（替代固定列布局）。

        卡片固定 168×168；UI 宽度每次变化（工作目录面板变宽/窄、窗口缩放）
        时重新计算列数并重排，保证尽可能多显示卡片且缩进居中。
        列数与条目均未变化（如纯拖动缩放未跨列）时跳过重排，
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
        self._adjust_tab_widths()

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
    def _scan_entries(workdir: str) -> tuple[list, list[str]]:
        """返回 (项目列表, 子目录列表)。

        项目列表元素：目录路径（普通项目）或 (目录, html 文件名) 元组
        （pure.html 模式下的单文件项目）。

        pure.html 标记规则：目录内若存在名为 pure.html 的文件（仅校验名字与
        后缀，不读内容），则——
        - 该目录本身不视为项目，而是作为可进入的「二级文件夹」；
        - 该目录内除 pure.html 外的每个 .html/.htm 文件各视为一个独立项目
          （以 (目录, 文件名) 表示，进入该文件夹后展开为独立卡片）。
        """
        projects: list = []
        folders: list[str] = []
        try:
            names = sorted(os.listdir(workdir))
        except OSError:
            return projects, folders
        is_pure = os.path.isfile(os.path.join(workdir, "pure.html"))
        for name in names:
            full = os.path.join(workdir, name)
            if os.path.isdir(full):
                if os.path.isfile(os.path.join(full, "pure.html")):
                    folders.append(full)          # pure 文件夹 → 可进入的二级文件夹
                elif resolve_index(full):
                    projects.append(full)         # 普通目录项目
                else:
                    folders.append(full)          # 普通子目录
            elif is_pure and name.lower().endswith((".html", ".htm")) and name.lower() != "pure.html":
                projects.append((workdir, name))  # pure 目录内的单文件项目
        return projects, folders

    @staticmethod
    def _scan_projects(workdir: str) -> list[str]:
        """兼容旧接口：仅返回含入口 HTML 的项目目录。"""
        projects, _folders = WorkspacePanel._scan_entries(workdir)
        return projects

    def _on_activate(self, project: str) -> None:
        self._set_active(project)
        self.projectSelected.emit(project)

    def _on_palette_request(self, key: str) -> None:
        """下拉框切换入口 HTML 后，按新文件重新提取主色。"""
        card = self._cards.get(key)
        if card is None:
            return
        self._pool.start(_PaletteTask(key, card.selected_html_path(), self))

    def _set_active(self, project: str) -> None:
        """仅记录「当前激活项目」（用于预览 / 输出建议），不改变多选高亮。

        卡片选中高亮统一由 _apply_selection 按多选集合驱动。
        """
        self._active = project

    # ------------------------------------------------------- 多选逻辑
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