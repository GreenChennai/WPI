"""PDF 导出：浏览器原生打印（Page.printToPDF），高保真（设计文档 4.5）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.presets import PDF_PAPER

if TYPE_CHECKING:
    from playwright.sync_api import Page

PX_PER_MM = 96.0 / 25.4


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
        page.emulate_media(media="print")
        page.add_style_tag(content="@page { size: auto; margin: 0; }")
        if paper.lower() in ("a4", "a5", "letter"):
            page.pdf(
                path=path,
                format=paper,
                print_background=True,
                prefer_css_page_size=False,
            )
        else:  # Fit：按目标像素等宽高输出（整页导出时高度即内容长度，单页）
            page.pdf(
                path=path,
                format=None,
                width=f"{width_mm}mm",
                height=f"{round(height_mm * 1.002 + 1.0, 2)}mm",
                print_background=True,
                prefer_css_page_size=False,
            )