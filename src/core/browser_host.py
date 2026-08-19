"""渲染子系统（BrowserHost）。

封装 Playwright，通过系统通道（msedge / chrome）调用已安装的浏览器内核，
不内置任何浏览器二进制（设计文档 5.1 定项：走系统内核，不可用即报错提醒）。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page

EDGE_PATHS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
CHROME_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


class BrowserUnavailableError(RuntimeError):
    """系统浏览器内核不可用时抛出，用于向用户给出安装引导。"""


def detect_browser_channel() -> str | None:
    """探测系统已安装的浏览器通道：优先 Edge，其次 Chrome。"""
    for exe in EDGE_PATHS:
        if os.path.isfile(exe):
            return "msedge"
    for exe in CHROME_PATHS:
        if os.path.isfile(exe):
            return "chrome"
    return None


class BrowserHost:
    def __init__(self, channel: str | None = None, headless: bool = True):
        self.channel = channel or os.environ.get("WPI_BROWSER_CHANNEL") or detect_browser_channel()
        self.headless = headless
        self._pw = None
        self._browser: Browser | None = None

    def launch(self) -> BrowserHost:
        if not self.channel:
            raise BrowserUnavailableError(
                "未检测到系统浏览器内核（Microsoft Edge / Google Chrome）。\n"
                "本软件不内置浏览器，请安装其中任意一个后重试。"
            )
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(
                channel=self.channel,
                headless=self.headless,
                args=["--disable-dev-shm-usage", "--no-first-run"],
            )
        except PlaywrightError as exc:
            self.close()
            raise BrowserUnavailableError(
                f"启动系统浏览器内核失败（{self.channel}）: {exc}"
            ) from exc
        return self

    @property
    def browser(self) -> Browser | None:
        return self._browser

    def new_page(self, viewport: tuple[int, int]) -> tuple[BrowserContext, Page]:
        if self._browser is None:
            raise RuntimeError("浏览器尚未启动")
        width, height = viewport
        context = self._browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page = context.new_page()
        return context, page

    def close(self) -> None:
        browser, self._browser = self._browser, None
        pw, self._pw = self._pw, None
        try:
            if browser is not None:
                browser.close()
        finally:
            if pw is not None:
                pw.stop()
