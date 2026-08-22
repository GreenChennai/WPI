"""静态网站主色快速提取（高性能遍历 + 缓存）。

设计目标：遍历项目目录解析 HTML / CSS / JS / SVG 等文本中的颜色字面量，
按出现次数取 Top-N 作为"网站主色"色卡，供工作目录卡片展示。
为控制开销：限制扫描文件数与单文件大小、跳过重型目录、按 mtime 签名缓存。
"""

from __future__ import annotations

import os
import re
from collections import Counter

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
EXCLUDE_DIRS = {
    "node_modules", ".git", ".hg", ".svn",
    "dist", "build", "out", ".next", "__pycache__",
    ".venv", "venv", ".idea", ".vscode",
}
TEXT_EXTS = {
    ".html", ".htm", ".css", ".js", ".mjs", ".jsx",
    ".ts", ".tsx", ".vue", ".svelte", ".scss", ".sass",
    ".less", ".svg", ".json", ".txt",
}
# 单页面主色提取时，仅纳入该页面自身引用的样式/脚本资源，避免把同目录其他
# HTML 页面也并入统计（否则同目录多页面会呈现相同配色）。
_STYLE_EXTS = {".css", ".scss", ".sass", ".less"}
_SCRIPT_EXTS = {".js", ".mjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
MAX_FILES = 120            # 每个项目最多解析的文件数
MAX_FILE_BYTES = 512 * 1024  # 单文件超过则跳过
MAX_TOTAL_BYTES = 6 * 1024 * 1024  # 项目累计读取上限

_HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
_RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")
_HSL_RE = re.compile(
    r"hsla?\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%"
)
_LINK_RE = re.compile(r"<link\b[^>]*\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I)
_SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)

# 常用 CSS 命名色（完整 148 色中对静态网站最有价值的子集）
NAMED_COLORS: dict[str, str] = {
    "black": "000000", "white": "ffffff", "red": "ff0000",
    "green": "008000", "blue": "0000ff", "yellow": "ffff00",
    "orange": "ffa500", "purple": "800080", "pink": "ffc0cb",
    "gray": "808080", "grey": "808080", "silver": "c0c0c0",
    "maroon": "800000", "olive": "808000", "lime": "00ff00",
    "aqua": "00ffff", "cyan": "00ffff", "teal": "008080",
    "navy": "000080", "fuchsia": "ff00ff", "magenta": "ff00ff",
    "coral": "ff7f50", "gold": "ffd700", "beige": "f5f5dc",
    "ivory": "fffff0", "khaki": "f0e68c", "lavender": "e6e6fa",
    "salmon": "fa8072", "seashell": "fff5ee", "tan": "d2b48c",
    "tomato": "ff6347", "wheat": "f5deb3", "crimson": "dc143c",
    "indigo": "4b0082", "violet": "ee82ee", "orchid": "da70d6",
    "turquoise": "40e0d0", "azure": "f0ffff", "mintcream": "f5fffa",
}

_cache: dict[str, tuple[object, list[str]]] = {}


def _norm_hex(token: str) -> str:
    """将 #RGB / #RGBA / #RRGGBB / #RRGGBBAA 归一化为 #RRGGBB（忽略透明）。"""
    t = token.lstrip("#")
    n = len(t)
    if n in (3, 4):
        t = "".join(ch * 2 for ch in t[:3])
    return "#" + t[:6].lower()


def _hsl_to_hex(h: float, s: float, l: float) -> str | None:
    h = h % 360
    s, l = max(0.0, min(1.0, s / 100.0)), max(0.0, min(1.0, l / 100.0))
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return "#%02x%02x%02x" % (
        int(round((r + m) * 255)), int(round((g + m) * 255)),
        int(round((b + m) * 255)),
    )


def _scan_files(project_dir: str) -> list[str]:
    """返回待解析文本文件路径（受文件数与字节上限约束）。"""
    out: list[str] = []
    total = 0
    for base, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for name in files:
            if len(out) >= MAX_FILES:
                return out
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXTS or name.startswith("."):
                continue
            fp = os.path.join(base, name)
            try:
                size = os.path.getsize(fp)
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                continue
            total += size
            if total > MAX_TOTAL_BYTES:
                return out
            out.append(fp)
    return out


def _signature(project_dir: str, files: list[str]) -> object:
    """文件 mtime 签名，用于缓存校验（避免高频重复遍历）。"""
    marks = []
    for fp in files:
        try:
            marks.append((fp, os.path.getmtime(fp), os.path.getsize(fp)))
        except OSError:
            marks.append((fp, 0, 0))
    return tuple(marks)


def _clean_ref(ref: str) -> str:
    """去掉 URL 中的查询串/锚点，仅保留路径部分。"""
    return ref.split("?")[0].split("#")[0].strip()


def _resolve_same_dir(base_dir: str, ref: str) -> str | None:
    """将相对引用解析为同目录下的绝对路径（仅限同目录，拒绝子目录/上层引用）。"""
    ab = os.path.abspath(base_dir)
    fp = os.path.normpath(os.path.join(ab, ref))
    if os.path.dirname(fp) != ab:
        return None
    return fp if os.path.isfile(fp) else None


def _collect_page_files(html_path: str) -> list[str]:
    """收集单页面主色提取所需的文件：页面本身 + 同目录被其引用的样式/脚本。

    仅纳入同目录（非递归）的资源，且只取样式/脚本类扩展名，避免把同目录其他
    HTML 页面或子目录资源并入统计，从而保证「每个 HTML 文件有各自的主题色」。
    """
    base_dir = os.path.dirname(os.path.abspath(html_path))
    files = [html_path]
    try:
        with open(html_path, "rb") as fh:
            text = fh.read(MAX_FILE_BYTES).decode("utf-8", errors="ignore")
    except OSError:
        return files
    refs: set[str] = set()
    for m in _LINK_RE.finditer(text):
        ref = _clean_ref(m.group(1))
        if not ref or ref.startswith(("http://", "https://", "//", "data:", "mailto:")):
            continue
        if os.path.splitext(ref)[1].lower() not in _STYLE_EXTS:
            continue
        fp = _resolve_same_dir(base_dir, ref)
        if fp:
            refs.add(fp)
    for m in _SCRIPT_RE.finditer(text):
        ref = _clean_ref(m.group(1))
        if not ref or ref.startswith(("http://", "https://", "//", "data:", "mailto:")):
            continue
        if os.path.splitext(ref)[1].lower() not in _SCRIPT_EXTS:
            continue
        fp = _resolve_same_dir(base_dir, ref)
        if fp:
            refs.add(fp)
    files.extend(sorted(refs))
    return files


def _count_in_files(files: list[str], top: int) -> list[str]:
    """统计给定文件中出现的颜色（按频次取 Top-N）。"""
    counter: Counter[str] = Counter()
    for fp in files:
        try:
            with open(fp, "rb") as fh:
                data = fh.read(MAX_FILE_BYTES)
        except OSError:
            continue
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            continue
        for m in _HEX_RE.finditer(text):
            counter[_norm_hex(m.group(1))] += 1
        for r, g, b in _RGB_RE.findall(text):
            counter["#%02x%02x%02x" % (int(r), int(g), int(b))] += 1
        for h, s, l in _HSL_RE.findall(text):
            hexv = _hsl_to_hex(float(h), float(s), float(l))
            if hexv:
                counter[hexv] += 1
        lower = text.lower()
        for name, count in _count_words(lower).items():
            counter["#" + NAMED_COLORS[name]] += count
    return [c for c, _ in counter.most_common(top)]


def extract_palette(target: str, top: int = 4, single_file: bool = False) -> list[str]:
    """返回主色列表（最多 top 个 #RRGGBB），带缓存。

    - target 为目录（single_file=False）：扫描整个目录（整项目概览）。
    - target 为 HTML 文件（single_file=True）：仅扫描该页面自身及其同目录被引用
      的样式/脚本资源，反映单个页面的主题色（同目录多 HTML 互不干扰）。
    """
    if single_file:
        if not os.path.isfile(target):
            return []
        files = _collect_page_files(target)
        sig = _signature(target, files)
        cached = _cache.get(target)
        if cached is not None and cached[0] == sig:
            return cached[1]
        colors = _count_in_files(files, top)
        _cache[target] = (sig, colors)
        return colors

    if not os.path.isdir(target):
        return []
    files = _scan_files(target)
    sig = _signature(target, files)
    cached = _cache.get(target)
    if cached is not None and cached[0] == sig:
        return cached[1]
    colors = _count_in_files(files, top)
    _cache[target] = (sig, colors)
    return colors


_NAMED_RE = re.compile(
    r"\b(?:" + "|".join(sorted(NAMED_COLORS, key=len, reverse=True)) + r")\b"
)


def _count_words(text: str) -> Counter[str]:
    """按词边界一次性统计全部命名色出现次数（单次正则扫描）。"""
    c: Counter[str] = Counter()
    for m in _NAMED_RE.findall(text):
        c[m] += 1
    return c


def clear_cache() -> None:
    _cache.clear()