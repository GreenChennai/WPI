"""PDF 导出：浏览器原生打印（Page.printToPDF），高保真（设计文档 4.5）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.presets import PDF_PAPER

if TYPE_CHECKING:
    from playwright.sync_api import Page

PX_PER_MM = 96.0 / 25.4
# v2.3.0：Chromium 单页打印尺寸上限约 200 英寸，超出会产出空白/异常 PDF
MAX_PAGE_MM = 200.0 * 25.4


def px_to_mm(px: float) -> float:
    return px / PX_PER_MM


class PDFExporter:
    @staticmethod
    def write(
        page: Page,
        path: str,
        width_px: int,
        height_px: int,
        paper: str = PDF_PAPER,
    ) -> None:
        width_mm = round(px_to_mm(width_px), 2)
        height_mm = round(px_to_mm(height_px), 2)
        # v2.3.0：按「屏幕样式」打印（所见即所得）——网页若含 @media print
        # 隐藏类样式，print 媒体下会导出全白；切到 screen 后与预览一致。
        page.emulate_media(media="screen")
        page.add_style_tag(content="@page { margin: 0; }")
        if paper.lower() in ("a4", "a5", "letter"):
            page.pdf(
                path=path,
                format=paper,
                print_background=True,
                prefer_css_page_size=False,
            )
        else:  # Fit：按目标像素等宽高输出（整页导出时高度即内容长度，单页）
            # v2.3.0：高度封顶 200 英寸，防止超长页触发 Chromium 空白 PDF
            height_mm = min(height_mm, MAX_PAGE_MM)
            page.pdf(
                path=path,
                format=None,
                width=f"{width_mm}mm",
                height=f"{round(height_mm * 1.002 + 1.0, 2)}mm",
                print_background=True,
                prefer_css_page_size=False,
            )