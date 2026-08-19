"""PDF 导出：浏览器原生打印（Page.printToPDF），高保真（设计文档 4.5）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.presets import PDF_PAPER

if TYPE_CHECKING:
    from playwright.sync_api import Page

PX_PER_MM = 96.0 / 25.4
# v2.4.0：Fit 模式单页高度上限（CSS px）。超过则分页输出——浏览器 PDF
# 渲染器（Edge/Chrome PDFium）对超大单页（几十英寸高）兼容性差，常显示纯白，
# 而专业软件（Illustrator 等）可正常解析；分页成常规尺寸后全兼容。
MAX_PAGE_H_PX = 2400


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
        if paper.lower() in ("a4", "a5", "letter"):
            page.add_style_tag(content="@page { margin: 0; }")
            page.pdf(
                path=path,
                format=paper,
                print_background=True,
                prefer_css_page_size=False,
            )
        else:  # Fit：按目标像素等宽输出
            if height_px > MAX_PAGE_H_PX:
                # v2.4.0：超长内容分页输出——CSS @page size 定宽定高，
                # Chromium 将内容流式分到多页（每页 ≤ 上限高），Edge 可正常查看
                page_h_mm = round(px_to_mm(MAX_PAGE_H_PX), 2)
                page.add_style_tag(
                    content=(
                        f"@page {{ size: {width_mm}mm {page_h_mm}mm; margin: 0; }}"
                    )
                )
                page.pdf(
                    path=path,
                    print_background=True,
                    prefer_css_page_size=True,
                )
            else:
                page.add_style_tag(content="@page { margin: 0; }")
                page.pdf(
                    path=path,
                    format=None,
                    width=f"{width_mm}mm",
                    height=f"{round(height_mm * 1.002 + 1.0, 2)}mm",
                    print_background=True,
                    prefer_css_page_size=False,
                )