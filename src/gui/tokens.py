"""视觉令牌:浅色工作台主题(GitHub Primer 风格,单一绿色强调)。

零 Qt 依赖的纯数据模块,集中管理色值 / 圆角 / 间距 / 字号。

- 形状系统:控件(按钮/输入框)圆角 6,卡片圆角 12,小件(色卡/勾选框)4,
  细进度条 3;全应用只用这一套,不再混用。
- 颜色系统:绿色是唯一强调色(主按钮/焦点框/进度条);蓝色仅表达「多选」
  语义(卡片多选高亮),不作为装饰;红色表达危险,琥珀色表达次要强调。
- 对比度:白字按钮底色全部通过 WCAG AA(≥4.5:1);次要文字对其背景 ≥5:1。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 强调色 / 品牌绿
# ---------------------------------------------------------------------------
ACCENT = "#1F883D"
ACCENT_HOVER = "#1A7F37"
ACCENT_PRESS = "#187033"
ACCENT_SOFT_FAINT = "rgba(31, 136, 61, 0.04)"
ACCENT_SOFT = "rgba(31, 136, 61, 0.09)"
ACCENT_SOFT_STRONG = "rgba(31, 136, 61, 0.16)"
ACCENT_TINT_BG = "#F0F9F1"          # 悬停浅绿底(比旧 #E8F5E9 更收敛)
ACCENT_TINT_BORDER = "#C8E6C9"
ACCENT_TINT_TEXT = "#1A7F37"

# ---------------------------------------------------------------------------
# 背景 / 表面 / 边框
# ---------------------------------------------------------------------------
WHITE = "#FFFFFF"
SURFACE = "#F6F8FA"                  # 应用画布
SURFACE_ALT = "#FBFCFD"              # 次级表面(禁用输入/只读)
SURFACE_HOVER = "#F3F4F6"
SURFACE_PRESS = "#EBECF0"
BORDER = "#D0D7DE"
BORDER_MUTED = "#E4E8EC"             # 卡片内分隔等弱边框
BORDER_HOVER = "#AFB8C1"
INPUT_BORDER = "#D0D7DE"
TRACK = "#E4E8EC"                    # 进度条轨道 / 禁用主按钮底

# ---------------------------------------------------------------------------
# 文字
# ---------------------------------------------------------------------------
TEXT_STRONG = "#1F2328"              # 主文字
TEXT_TITLE = "#1A1A1A"
TEXT_SECONDARY = "#59636E"           # 次要文字(白底 6.1:1)
TEXT_MUTED = "#6E7781"
TEXT_PLACEHOLDER = "#8C959F"
TEXT_LINK = "#0969DA"
ICON_MUTED = "#8C959F"

# ---------------------------------------------------------------------------
# 状态色
# ---------------------------------------------------------------------------
SUCCESS = "#1A7F37"
DANGER_TEXT = "#B4324B"
DANGER_STRONG = "#CF222E"
DANGER_STRONG_HOVER = "#B91F29"
DANGER_STRONG_PRESS = "#A71F29"
# 琥珀「次要强调」按钮:白字对比度 4.9:1(旧 #C7920A 仅 2.8:1,不达标)
WARNING = "#9A6700"
WARNING_HOVER = "#8A5C00"
WARNING_PRESS = "#7A5200"
INFO = "#0969DA"
RUNNING = "#2F98FF"
PENDING = "#8A8A8A"
PROGRESS_CHUNK = ACCENT              # 进度条与主按钮同色,强调色唯一

SCROLLBAR_HANDLE = "rgba(110, 119, 129, 0.45)"
SCROLLBAR_HANDLE_HOVER = "rgba(110, 119, 129, 0.75)"

# ---------------------------------------------------------------------------
# 选择态配色(卡片多选)
# ---------------------------------------------------------------------------
# 单选(仅 1 个被选中):绿色 —— 与强调色一致
SELECT_FILL_SINGLE = "#E9F5EC"
SELECT_BORDER_SINGLE = "#1F883D"
# 多选(≥2 个被选中):蓝色 —— 语义色,区分「批量」与普通单选
SELECT_FILL_MULTI = "#E1EFFE"
SELECT_BORDER_MULTI = "#0969DA"

# ---------------------------------------------------------------------------
# 圆角 / 间距 / 字号
# ---------------------------------------------------------------------------
RADIUS_XS = 4        # 小件:色卡 / 勾选框
RADIUS_SM = 6        # 控件:按钮 / 输入框 / 下拉
RADIUS_MD = 8        # 浮层:菜单 / 工具提示
RADIUS_LG = 12       # 卡片:分组面板 / 项目卡片
CARD_RADIUS = RADIUS_LG
INPUT_RADIUS = RADIUS_SM
PROGRESS_RADIUS = 3

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 20
LAYOUT_SPACING = 12
CARD_MARGIN = 16

FONT_FAMILY = "'HarmonyOS Sans SC', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
FONT_SIZE_SM = 12
FONT_SIZE_BODY = 13
FONT_SIZE_TITLE = 15


def rgba(hex_color: str, alpha: float) -> str:
    """将 '#RRGGBB' 转成 rgba(r,g,b,a) 字符串。"""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"
