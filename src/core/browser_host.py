"""渲染子系统（BrowserHost）。

封装 Playwright，通过系统通道（msedge / chrome）调用已安装的浏览器内核，
不内置任何浏览器二进制（设计文档 5.1 定项：走系统内核，不可用即报错提醒）。

在线网站导出走**独立持久化用户目录**（use_profile=True）：cookies / 登录态
跨导出保留，且与系统浏览器数据隔离——需要登录或有人机校验的站点不必每次
重新登录（默认的临时上下文没有 cookie，访问此类站点会退到登录页/验证页）。
"""

from __future__ import annotations

import os
import tempfile
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


def profile_dir() -> str:
    """返回 WPI 自有的持久化浏览器用户目录（隔离环境，cookies 跨导出保留）。

    放在系统用户数据区（%LOCALAPPDATA%），与系统浏览器配置完全隔离：
    不读取 / 不写入用户日常浏览器的 profile，登录态只服务于 WPI 导出。
    可用环境变量 WPI_PROFILE_DIR 覆盖（测试 / 临时隔离用）。
    """
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    override = os.environ.get("WPI_PROFILE_DIR")
    if override:
        return os.path.abspath(override)
    return os.path.join(base, "WPI", "browser-profile")


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
    def __init__(
        self,
        channel: str | None = None,
        headless: bool = True,
        use_profile: bool = False,
    ):
        self.channel = channel or os.environ.get("WPI_BROWSER_CHANNEL") or detect_browser_channel()
        self.headless = headless
        self.use_profile = use_profile
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def launch(
        self,
        device_scale_factor: float = 1,
        viewport: tuple[int, int] | None = None,
    ) -> BrowserHost:
        if not self.channel:
            raise BrowserUnavailableError(
                "未检测到系统浏览器内核（Microsoft Edge / Google Chrome）。\n"
                "本软件不内置浏览器，请安装其中任意一个后重试。"
            )
        self._pw = sync_playwright().start()
        args = [
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        try:
            if self.use_profile:
                # 持久化用户目录：登录态 / cookies 跨导出保留，隔离于系统浏览器。
                # 隐藏自动化标记，降低目标站点的人机校验误判。
                self._context = self._pw.chromium.launch_persistent_context(
                    user_data_dir=profile_dir(),
                    channel=self.channel,
                    headless=self.headless,
                    viewport=(
                        {"width": viewport[0], "height": viewport[1]}
                        if viewport else None
                    ),
                    device_scale_factor=device_scale_factor,
                    args=args + ["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                )
            else:
                self._browser = self._pw.chromium.launch(
                    channel=self.channel,
                    headless=self.headless,
                    args=args,
                )
        except PlaywrightError as exc:
            # 持久化目录被占用（上次导出异常退出残留浏览器进程）时降级为
            # 临时上下文，保证导出仍可用（仅丢失登录态）
            if self.use_profile:
                try:
                    self._context = self._pw.chromium.launch_persistent_context(
                        user_data_dir=os.path.join(tempfile.gettempdir(), "WPI-export-fallback"),
                        channel=self.channel,
                        headless=self.headless,
                        args=args,
                        ignore_default_args=["--enable-automation"],
                    )
                    return self
                except Exception:
                    pass
            self.close()
            raise BrowserUnavailableError(
                f"启动系统浏览器内核失败（{self.channel}）: {exc}"
            ) from exc
        return self

    @property
    def browser(self) -> Browser | None:
        return self._browser

    def new_page(
        self,
        viewport: tuple[int, int],
        device_scale_factor: float = 1,
    ) -> tuple[BrowserContext, Page]:
        if self._browser is None and self._context is None:
            raise RuntimeError("浏览器尚未启动")
        width, height = viewport
        if self._context is not None:
            # 持久化模式：context 已在 launch 时按分辨率倍率建好，
            # 这里只按导出宽度开新页（视口高度用默认值，加载后由引擎调整）
            page = self._context.new_page()
            page.set_viewport_size({"width": width, "height": height})
            return self._context, page
        context = self._browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=device_scale_factor,
        )
        page = context.new_page()
        return context, page

    def close(self) -> None:
        context, self._context = self._context, None
        browser, self._browser = self._browser, None
        pw, self._pw = self._pw, None
        try:
            if context is not None:
                # 持久化模式：close 会写回 cookies，登录态得以保留
                context.close()
            elif browser is not None:
                browser.close()
        finally:
            if pw is not None:
                pw.stop()
