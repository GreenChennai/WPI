"""全局 QSS 构建器：将 MomentShift 令牌风格应用到本应用的 QtWidgets 控件。"""

from __future__ import annotations

from . import tokens as T


def build_stylesheet() -> str:
    return f"""
* {{ font-family: {T.FONT_FAMILY}; font-size: {T.FONT_SIZE_BODY}px; color: {T.TEXT_STRONG}; }}

QMainWindow, QDialog {{ background: {T.SURFACE}; }}
#root {{ background: {T.SURFACE}; }}

QLabel {{ color: {T.TEXT_STRONG}; background: transparent; }}
QLabel[secondary="true"] {{ color: {T.TEXT_SECONDARY}; }}
QLabel[muted="true"] {{ color: {T.TEXT_MUTED}; }}
QLabel#panelTitle {{ font-size: {T.FONT_SIZE_TITLE}px; font-weight: 700; color: {T.TEXT_TITLE}; }}

/* ---------- 组卡片（复用 MomentShift ThemedCard 外观） ---------- */
QGroupBox {{
    background: {T.WHITE};
    border: 1px solid {T.BORDER};
    border-radius: {T.CARD_RADIUS}px;
    margin-top: 8px;
    padding-top: 14px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {T.SPACE_MD}px;
    padding: 0 4px;
    color: {T.TEXT_SECONDARY};
    font-size: 12px;
    font-weight: 600;
}}

/* ---------- 输入控件 ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {T.WHITE};
    border: 1px solid {T.INPUT_BORDER};
    border-radius: {T.INPUT_RADIUS}px;
    padding: 4px 8px;
    selection-background-color: {T.ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {T.ACCENT};
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background: {T.SURFACE};
    color: {T.TEXT_PLACEHOLDER};
}}
QLineEdit:read-only {{ background: {T.SURFACE}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 1px solid {T.BORDER};
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {T.WHITE};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_SM}px;
    selection-background-color: {T.ACCENT_SOFT_STRONG};
    selection-color: {T.TEXT_STRONG};
    outline: none;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {T.WHITE};
    color: {T.TEXT_STRONG};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_MD}px;
    padding: 6px 16px;
}}
QPushButton:hover {{ background: {T.SURFACE_HOVER}; border-color: {T.BORDER_HOVER}; }}
QPushButton:pressed {{ background: {T.SURFACE_PRESS}; }}
QPushButton:disabled {{ color: {T.TEXT_PLACEHOLDER}; background: {T.SURFACE}; }}

QPushButton#primaryBtn {{
    background: {T.ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: {T.RADIUS_MD}px;
    padding: 7px 20px;
    font-weight: 600;
}}
QPushButton#primaryBtn:hover {{ background: {T.ACCENT_HOVER}; }}
QPushButton#primaryBtn:pressed {{ background: {T.ACCENT_PRESS}; }}
QPushButton#primaryBtn:disabled {{ background: {T.PROGRESS_TRACK}; color: {T.TEXT_PLACEHOLDER}; }}

QPushButton#ghostBtn {{
    background: transparent;
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_MD}px;
    padding: 5px 14px;
}}
QPushButton#ghostBtn:hover {{ background: {T.SURFACE_HOVER}; border-color: {T.BORDER_HOVER}; }}

/* ---------- 工作目录项目卡片（背景/边框由 paintEvent 自绘，QSS 只留透明） ---------- */
#projectCard, #folderCard {{
    background: transparent;
    border: none;
}}
#projectCard:hover, #folderCard:hover {{
    background: transparent;
    border: none;
}}
#projectCard[selected="true"] {{
    background: transparent;
    border: none;
}}
#cardTitle {{
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 700;
    color: {T.TEXT_STRONG};
}}
QPushButton#cardPrimary {{
    background: {T.ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: {T.RADIUS_SM}px;
    padding: 5px 8px;
    font-weight: 600;
}}
QPushButton#cardPrimary:hover {{ background: {T.ACCENT_HOVER}; }}
QPushButton#cardSecondary {{
    background: transparent;
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_SM}px;
    padding: 5px 8px;
}}
QPushButton#cardSecondary:hover {{ background: {T.SURFACE_HOVER}; }}

/* ---------- 子目录卡片 / 主色色卡 ---------- */
#workdirBox {{ background: {T.SURFACE}; }}
#workdirBox QScrollArea, #workdirBox QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
#swatchBox {{ border-radius: 4px; }}

/* ---------- 启动进度遮罩 ---------- */
#bootTitle {{
    font-size: 20px;
    font-weight: 700;
    color: {T.TEXT_TITLE};
}}

/* ---------- 勾选框 ---------- */
QCheckBox {{ background: transparent; spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {T.INPUT_BORDER};
    border-radius: {T.RADIUS_XS}px;
    background: {T.WHITE};
}}
QCheckBox::indicator:checked {{ background: {T.ACCENT}; border-color: {T.ACCENT}; }}

/* ---------- 进度条 ---------- */
QProgressBar {{
    background: {T.PROGRESS_TRACK};
    border: none;
    border-radius: 4px;
    height: 16px;
    text-align: center;
    color: #000000;  /* v1.4.0：百分比文字黑色，保证清晰 */
    font-size: 11px;
    font-weight: 600;
}}
QProgressBar::chunk {{ background: {T.PROGRESS_CHUNK}; border-radius: 4px; }}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {T.SCROLLBAR_HANDLE}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {T.SCROLLBAR_HANDLE_HOVER}; }}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {T.SCROLLBAR_HANDLE}; border-radius: 4px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {T.SCROLLBAR_HANDLE_HOVER}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- 菜单 / 工具提示 ---------- */
QMenu {{
    background: {T.WHITE};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_MD}px;
    padding: 6px;
}}
QMenu::item {{ padding: 6px 24px; border-radius: {T.RADIUS_SM}px; }}
QMenu::item:selected {{ background: {T.ACCENT_SOFT}; color: {T.TEXT_STRONG}; }}
QToolTip {{
    background: {T.WHITE};
    color: {T.TEXT_STRONG};
    border: 1px solid {T.BORDER};
    border-radius: {T.RADIUS_SM}px;
    padding: 4px 8px;
}}

QStatusBar {{ background: {T.WHITE}; border-top: 1px solid {T.BORDER}; }}
"""
# ---------------------------------------------------------------- 便捷函数


def apply_object_names(widget) -> None:
    """给常见控件打上样式所需的对象名（主按钮等）。"""
    pass  # 现由各控件直接 setObjectName


def primary_style() -> str:
    """供 QPushButton 动态取用的主按钮样式（以 objectName 为准，备用）。"""
    return f"""
    background: {T.ACCENT}; color: #FFFFFF; border: none;
    border-radius: {T.RADIUS_MD}px; padding: 7px 20px; font-weight: 600;
    """