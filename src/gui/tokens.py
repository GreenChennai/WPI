"""视觉令牌：移植自 MomentShift 的 gui/tokens.py（GitHub 绿 + 灰阶浅色主题）。

零 Qt 依赖的纯数据模块，集中管理色值 / 圆角 / 间距 / 字号。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 主色 / 品牌绿
# ---------------------------------------------------------------------------
ACCENT = "#1F883D"
ACCENT_HOVER = "#1A7F37"
ACCENT_PRESS = "#197935"
ACCENT_SOFT_FAINT = "rgba(31, 136, 61, 0.04)"
ACCENT_SOFT = "rgba(31, 136, 61, 0.08)"
ACCENT_SOFT_STRONG = "rgba(31, 136, 61, 0.15)"
ACCENT_TINT_BG = "#E8F5E9"
ACCENT_TINT_BORDER = "#C8E6C9"
ACCENT_TINT_TEXT = "#2E7D32"

# ---------------------------------------------------------------------------
# 背景 / 表面 / 边框
# ---------------------------------------------------------------------------
WHITE = "#FFFFFF"
SURFACE = "#F6F8FA"
SURFACE_HOVER = "#F3F4F6"
SURFACE_PRESS = "#EBECF0"
BORDER = "#D0D7DE"
BORDER_HOVER = "#AFB8C1"
INPUT_BORDER = "#D0D7DE"
PROGRESS_TRACK = "#EAEFF2"

# ---------------------------------------------------------------------------
# 文字
# ---------------------------------------------------------------------------
TEXT_STRONG = "#1F2328"
TEXT_SECONDARY = "#656D76"
TEXT_MUTED = "#57606A"
TEXT_PLACEHOLDER = "#9E9E9E"
TEXT_LINK = "#0969DA"
TEXT_TITLE = "#1A1A1A"
TEXT_BODY = "#424242"
TEXT_SUBTLE = "#333333"
ICON_MUTED = "#888888"

# ---------------------------------------------------------------------------
# 状态色
# ---------------------------------------------------------------------------
SUCCESS = "#3EB68F"
DANGER = "#FF7279"
DANGER_TEXT = "#B4324B"
DANGER_STRONG = "#CF222E"
WARNING = "#C7920A"
INFO = "#3964FE"
RUNNING = "#2F98FF"
PENDING = "#8A8A8A"
PROGRESS_CHUNK = "#0969DA"

SCROLLBAR_HANDLE = "rgba(140, 140, 140, 0.6)"
SCROLLBAR_HANDLE_HOVER = "rgba(120, 120, 120, 0.85)"

# ---------------------------------------------------------------------------
# 选择态配色（卡片多选）
# ---------------------------------------------------------------------------
# 单选（仅 1 个被选中）：绿色 —— 用户给定的填充/描边
SELECT_FILL_SINGLE = "#E8F5E9"
SELECT_BORDER_SINGLE = "#1F883D"
# 多选（≥2 个被选中）：蓝色 —— GitHub 蓝，浅蓝填充 + 中蓝描边，观感清爽
SELECT_FILL_MULTI = "#E3F0FF"
SELECT_BORDER_MULTI = "#0969DA"

# ---------------------------------------------------------------------------
# 度量 / 字号（MomentShift 惯例）
# ---------------------------------------------------------------------------
RADIUS_XS = 3
RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_LG = 12
CARD_RADIUS = 12
INPUT_RADIUS = 4

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
LAYOUT_SPACING = 12
CARD_MARGIN = 16

FONT_FAMILY = "'HarmonyOS Sans SC', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
FONT_SIZE_BODY = 13
FONT_SIZE_TITLE = 16


def rgba(hex_color: str, alpha: float) -> str:
    """将 '#RRGGBB' 转成 rgba(r,g,b,a) 字符串。"""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"