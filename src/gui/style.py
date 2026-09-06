"""全局 QSS 构建器:把 tokens 令牌应用到 QtWidgets 控件。

布局语言:左侧为画布上的卡片流(无外框),右侧为「标题在内」的白色
分组卡片;控件圆角统一 6px、卡片 12px;强调色唯一(绿),蓝色仅用于
多选语义;进度条为 6px 细条(文字由界面标签单独显示,避免压色块)。
"""

from __future__ import annotations

import os
import sys

from . import tokens as T


def _arrow_path(name: str) -> str:
    """返回下拉箭头 PNG 资源的绝对路径。

    QSS image:url() 对绝对路径可靠、对 base64 data URI 不可靠,故用真实文件。
    开发模式取 src/gui/assets;PyInstaller 单文件模式取打包内的 gui/assets。
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
        cand = os.path.join(base, "gui", "assets", name)
    else:
        cand = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)
    return cand.replace("\\", "/")


def build_stylesheet() -> str:
    arrow = _arrow_path("down_arrow.png")
    arrow_sm = _arrow_path("down_arrow_sm.png")
    return f"""
* {{ font-family: {T.FONT_FAMILY}; font-size: {T.FONT_SIZE_BODY}px; color: {T.TEXT_STRONG}; }}

QMainWindow, QDialog {{ background: {T.SURFACE}; }}
#root {{ background: {T.SURFACE}; }}

QLabel {{ color: {T.TEXT_STRONG}; background: transparent; }}
QLabel[secondary="true"] {{ color: {T.TEXT_SECONDARY}; }}
QLabel[muted="true"] {{ color: {T.TEXT_MUTED}; }}

/* ---------- 分组卡片:标题位于卡片内部,不再骑在边框线上 ---------- */
QGroupBox {{
    background: {T.WHITE};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_LG}px;
    margin-top: 0px;
    padding: 32px 14px 14px 14px;
    font-weight: normal;
}}
QGroupBox::title {{
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: 13px;
    top: 9px;
    padding: 0 1px;
    color: {T.TEXT_STRONG};
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 600;
}}

/* ---------- 输入控件 ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {T.WHITE};
    border: 1px solid {T.INPUT_BORDER};
    border-radius: {T.RADIUS_SM}px;
    padding: 4px 9px;
    selection-background-color: {T.ACCENT};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: {T.BORDER_HOVER};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {T.ACCENT};
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background: {T.SURFACE_ALT};
    color: {T.TEXT_PLACEHOLDER};
}}
QLineEdit:read-only {{
    background: {T.SURFACE_ALT};
    color: {T.TEXT_SECONDARY};
}}
QComboBox::drop-down {{ border: none; width: 22px; subcontrol-origin: padding; subcontrol-position: top right; }}
QComboBox::drop-down:hover {{ background: {T.SURFACE_HOVER}; border-top-right-radius: {T.RADIUS_SM}px; border-bottom-right-radius: {T.RADIUS_SM}px; }}
QComboBox::down-arrow {{
    image: url({arrow});
    width: 12px; height: 12px;
    subcontrol-origin: padding; subcontrol-position: right center;
}}
QComboBox QAbstractItemView {{
    background: {T.WHITE};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_SM}px;
    padding: 4px;
    selection-background-color: {T.ACCENT_SOFT_STRONG};
    selection-color: {T.TEXT_STRONG};
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 5px 8px;
    border-radius: {T.RADIUS_XS}px;
}}

/* ---------- 按钮(默认 / 主 / 幽灵 / 危险 / 琥珀) ---------- */
QPushButton {{
    background: {T.WHITE};
    color: {T.TEXT_STRONG};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_SM}px;
    padding: 5px 14px;
}}
QPushButton:hover {{ background: {T.SURFACE_HOVER}; border-color: {T.BORDER_HOVER}; }}
QPushButton:pressed {{ background: {T.SURFACE_PRESS}; }}
QPushButton:focus {{ border-color: {T.ACCENT}; }}
QPushButton:disabled {{ color: {T.TEXT_PLACEHOLDER}; background: {T.SURFACE_ALT}; }}

QPushButton#primaryBtn {{
    background: {T.ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: {T.RADIUS_SM}px;
    padding: 6px 20px;
    font-weight: 600;
}}
QPushButton#primaryBtn:hover {{ background: {T.ACCENT_HOVER}; }}
QPushButton#primaryBtn:pressed {{ background: {T.ACCENT_PRESS}; }}
QPushButton#primaryBtn:disabled {{ background: {T.TRACK}; color: {T.TEXT_PLACEHOLDER}; }}
QPushButton#primaryBtn:focus {{
    border: 1px solid {T.ACCENT_SOFT_STRONG};
    padding: 5px 19px;   /* 净尺寸保持不变 */
}}

QPushButton#ghostBtn {{
    background: transparent;
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_SM}px;
    padding: 5px 14px;
}}
QPushButton#ghostBtn:hover {{ background: {T.WHITE}; border-color: {T.BORDER_HOVER}; }}
QPushButton#ghostBtn:focus {{ border-color: {T.ACCENT}; }}

QPushButton#dangerBtn {{
    background: {T.DANGER_STRONG};
    color: #FFFFFF;
    border: none;
    border-radius: {T.RADIUS_SM}px;
    padding: 6px 16px;
    font-weight: 600;
}}
QPushButton#dangerBtn:hover {{ background: {T.DANGER_STRONG_HOVER}; }}
QPushButton#dangerBtn:pressed {{ background: {T.DANGER_STRONG_PRESS}; }}
QPushButton#dangerBtn:disabled {{ background: {T.TRACK}; color: {T.TEXT_PLACEHOLDER}; }}
QPushButton#dangerBtn:focus {{
    border: 1px solid rgba(255, 255, 255, 0.65);
    padding: 5px 15px;   /* 净尺寸保持不变 */
}}

/* 「添加工作目录」琥珀按钮 */
QPushButton#warningBtn {{
    background: {T.WARNING};
    color: #FFFFFF;
    border: none;
    border-radius: {T.RADIUS_SM}px;
    padding: 6px 16px;
    font-weight: 600;
}}
QPushButton#warningBtn:hover {{ background: {T.WARNING_HOVER}; }}
QPushButton#warningBtn:pressed {{ background: {T.WARNING_PRESS}; }}
QPushButton#warningBtn:disabled {{ background: {T.TRACK}; color: {T.TEXT_PLACEHOLDER}; }}
QPushButton#warningBtn:focus {{
    border: 1px solid rgba(255, 255, 255, 0.65);
    padding: 5px 15px;   /* 净尺寸保持不变 */
}}

/* ---------- 工作目录标签页(画布上的分段式标签,自然宽度+超长截断) ---------- */
QTabBar#workdirTabs {{
    qproperty-drawBase: 0;
    background: transparent;
}}
QTabBar#workdirTabs::tab {{
    background: transparent;
    color: {T.TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: {T.RADIUS_SM}px;
    padding: 4px 14px;
    margin-right: 4px;
    min-width: 0px;
    max-width: 190px;
}}
QTabBar#workdirTabs::tab:selected {{
    background: {T.WHITE};
    border: 1px solid {T.BORDER};
    color: {T.TEXT_STRONG};
    font-weight: 600;
}}
QTabBar#workdirTabs::tab:hover:!selected {{
    background: {T.ACCENT_SOFT_FAINT};
    color: {T.TEXT_STRONG};
}}
QTabBar#workdirTabs::close-button {{
    image: none;
    subcontrol-position: right;
    margin: 0 2px 0 0;
}}
QPushButton#tabAdd {{
    background: {T.WHITE};
    color: {T.TEXT_SECONDARY};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_SM}px;
}}
QPushButton#tabAdd:hover {{
    background: {T.SURFACE_HOVER};
    color: {T.TEXT_STRONG};
    border-color: {T.BORDER_HOVER};
}}

/* ---------- 工作目录项目卡片(背景/边框由 paintEvent 自绘,QSS 只留透明) ---------- */
#projectCard, #folderCard {{
    background: transparent;
    border: none;
}}
#cardTitle {{
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 600;
    color: {T.TEXT_STRONG};
}}
QPushButton#cardPrimary {{
    background: {T.ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: {T.RADIUS_SM}px;
    padding: 4px 8px;
    font-weight: 600;
}}
QPushButton#cardPrimary:hover {{ background: {T.ACCENT_HOVER}; }}
QPushButton#cardPrimary:pressed {{ background: {T.ACCENT_PRESS}; }}
QPushButton#cardPrimary:disabled {{ background: {T.TRACK}; color: {T.TEXT_PLACEHOLDER}; }}
QPushButton#cardSecondary {{
    background: {T.WHITE};
    color: {T.TEXT_STRONG};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_SM}px;
    padding: 4px 8px;
}}
QPushButton#cardSecondary:hover {{ background: {T.SURFACE_HOVER}; border-color: {T.BORDER_HOVER}; }}
QPushButton#cardSecondary:pressed {{ background: {T.SURFACE_PRESS}; }}

/* 项目卡片内入口 HTML 下拉框(紧凑样式) */
QComboBox#cardEntry {{
    background: {T.WHITE};
    border: 1px solid {T.INPUT_BORDER};
    border-radius: {T.RADIUS_SM}px;
    padding: 2px 5px;
    font-size: {T.FONT_SIZE_SM}px;
}}
QComboBox#cardEntry:hover {{ border-color: {T.BORDER_HOVER}; }}
QComboBox#cardEntry:focus {{ border-color: {T.ACCENT}; }}
QComboBox#cardEntry::drop-down {{ border: none; width: 16px; subcontrol-origin: padding; subcontrol-position: top right; }}
QComboBox#cardEntry::down-arrow {{
    image: url({arrow_sm});
    width: 10px; height: 10px;
    subcontrol-origin: padding; subcontrol-position: right center;
}}
QComboBox#cardEntry QAbstractItemView {{
    font-size: {T.FONT_SIZE_SM}px;
    border-radius: {T.RADIUS_SM}px;
}}

/* ---------- 子目录卡片 / 色卡 ---------- */
/* 工作目录区是画布上的卡片流,无外框;横向内边距归零,把宽度留给卡片网格
   (默认窗口宽度下要排满 4 列),顶部保留标题占位 */
#workdirBox {{ background: transparent; border: none; padding: 28px 0px 0px 0px; }}
#workdirBox QScrollArea, #workdirBox QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
#swatchBox {{ border-radius: {T.RADIUS_XS}px; }}

/* ---------- 启动进度遮罩 ---------- */
#bootTitle {{
    font-size: 21px;
    font-weight: 600;
    color: {T.TEXT_TITLE};
}}
#bootSubtitle {{
    font-size: {T.FONT_SIZE_SM}px;
    color: {T.TEXT_MUTED};
}}

/* 空工作目录提示 */
QLabel#emptyTitle {{
    font-size: {T.FONT_SIZE_TITLE}px;
    font-weight: 600;
    color: {T.TEXT_STRONG};
}}
QLabel#emptyHint {{
    font-size: {T.FONT_SIZE_SM}px;
    color: {T.TEXT_SECONDARY};
}}

/* ---------- 勾选框 ---------- */
QCheckBox {{ background: transparent; spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {T.INPUT_BORDER};
    border-radius: {T.RADIUS_XS}px;
    background: {T.WHITE};
}}
QCheckBox::indicator:hover {{ border-color: {T.BORDER_HOVER}; }}
QCheckBox::indicator:checked {{ background: {T.ACCENT}; border-color: {T.ACCENT}; }}
QCheckBox::indicator:checked:hover {{ background: {T.ACCENT_HOVER}; border-color: {T.ACCENT_HOVER}; }}
QCheckBox::indicator:disabled {{ background: {T.SURFACE_ALT}; border-color: {T.BORDER}; }}

/* ---------- 进度条:6px 细条,无内嵌文字(百分比由旁边标签显示) ---------- */
QProgressBar {{
    background: {T.TRACK};
    border: none;
    border-radius: {T.PROGRESS_RADIUS}px;
    color: transparent;
    font-size: 1px;
}}
QProgressBar::chunk {{ background: {T.PROGRESS_CHUNK}; border-radius: {T.PROGRESS_RADIUS}px; }}

/* ---------- 左右分栏拖拽条 ---------- */
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {T.ACCENT_SOFT}; }}
QSplitter::handle:horizontal {{ width: 5px; border-radius: 2px; }}
QSplitter::handle:vertical {{ height: 5px; border-radius: 2px; }}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {T.SCROLLBAR_HANDLE}; border-radius: 4px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {T.SCROLLBAR_HANDLE_HOVER}; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {T.SCROLLBAR_HANDLE}; border-radius: 4px; min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: {T.SCROLLBAR_HANDLE_HOVER}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- 菜单 / 工具提示 ---------- */
QMenu {{
    background: {T.WHITE};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_MD}px;
    padding: 5px;
}}
QMenu::item {{ padding: 6px 24px; border-radius: {T.RADIUS_XS}px; }}
QMenu::item:selected {{ background: {T.ACCENT_SOFT}; color: {T.TEXT_STRONG}; }}
QMenu::separator {{ height: 1px; background: {T.BORDER_MUTED}; margin: 4px 8px; }}
QToolTip {{
    background: {T.WHITE};
    color: {T.TEXT_STRONG};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_XS}px;
    padding: 4px 8px;
}}

/* ---------- 预览窗口工具栏 ---------- */
QToolBar {{
    background: {T.WHITE};
    border: none;
    border-bottom: 1px solid {T.BORDER_MUTED};
    padding: 4px 8px;
    spacing: 4px;
}}
QToolBar::separator {{ width: 1px; background: {T.BORDER_MUTED}; margin: 3px 5px; }}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {T.RADIUS_SM}px;
    padding: 3px 9px;
    color: {T.TEXT_SECONDARY};
}}
QToolButton:hover {{
    background: {T.SURFACE_HOVER};
    border-color: {T.BORDER};
    color: {T.TEXT_STRONG};
}}
QToolButton:pressed {{ background: {T.SURFACE_PRESS}; }}
"""
