"""捕获子系统（CaptureEngine）。

职责：加载页面、等待动画结束、单帧截图、按 fps 采样帧序列。
动画结束判定：同时用 `document.getAnimations()` 与帧间像素不变双重判据
（兼容 CSS / Web Animations / canvas rAF 动画），设计文档 4.2 / 13。
"""

from __future__ import annotations

import io
import time
from typing import TYPE_CHECKING

from PIL import Image

from config.presets import (
    ANIMATION_MAX_WAIT,
    ANIMATION_SAMPLE_INTERVAL,
    ANIMATION_STABLE_FRAMES,
    GIF_MAX_FRAMES,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from .browser_host import BrowserHost


class CaptureEngine:
    def __init__(self, browser: "BrowserHost", page: "Page", width: int, height: int):
        self.browser = browser
        self.page = page
        self.width = width
        self.height = height

    # ------------------------------------------------------------------ load
    @classmethod
    def load(
        cls,
        browser: "BrowserHost",
        url: str,
        viewport: tuple[int, int],
        load_timeout_ms: int = 30000,
    ) -> "CaptureEngine":
        context, page = browser.new_page(viewport)
        page.goto(url, wait_until="load", timeout=load_timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass  # 网络长期不 idle 时以 load 事件为准
        page.wait_for_timeout(200)
        return cls(browser, page, viewport[0], viewport[1])

    # --------------------------------------------------------------- helpers
    def running_animation_count(self) -> int:
        return self.page.evaluate(
            """() => {
                if (typeof document.getAnimations !== 'function') return 0;
                return document.getAnimations()
                    .filter(a => a.playState === 'running').length;
            }"""
        )

    def animation_running_counts(self) -> tuple[int, int]:
        """返回 (有限时长运行的动画数, 无限循环运行的动画数)。

        无限循环动画（iterations === Infinity）永远不会自然结束，
        整页导出时无需等待它（v1.3.0 需求：只等有限时长动画）。
        """
        return tuple(
            self.page.evaluate(
                """() => {
                    if (typeof document.getAnimations !== 'function') return [0, 0];
                    let finite = 0, infinite = 0;
                    for (const a of document.getAnimations()) {
                        if (a.playState !== 'running') continue;
                        let isInf = false;
                        try {
                            const eff = a.effect;
                            const t = eff && typeof eff.getTiming === 'function'
                                ? eff.getTiming() : null;
                            isInf = !!(t && t.iterations === Infinity);
                        } catch (e) { /* 忽略个别动画计时异常 */ }
                        if (isInf) infinite += 1; else finite += 1;
                    }
                    return [finite, infinite];
                }"""
            )
        )

    def has_infinite_animation(self) -> bool:
        return self.animation_running_counts()[1] > 0

    def _screenshot_bytes(self, transparent: bool = False, full_page: bool = False) -> bytes:
        return self.page.screenshot(omit_background=transparent, full_page=full_page)

    def capture_final_frame(
        self, transparent: bool = False, full_page: bool = False
    ) -> Image.Image:
        img = Image.open(io.BytesIO(self._screenshot_bytes(transparent, full_page)))
        return img.convert("RGBA")

    def content_size(self) -> tuple[int, int]:
        """返回页面实际内容尺寸 (scrollWidth, scrollHeight)。"""
        return tuple(self.page.evaluate(
            """() => [
                Math.max(
                    document.documentElement.scrollWidth,
                    document.body ? document.body.scrollWidth : 0),
                Math.max(
                    document.documentElement.scrollHeight,
                    document.body ? document.body.scrollHeight : 0),
            ]"""
        ))

    def prepare_full_page(self, width: int | None, height: int | None) -> tuple[int, int]:
        """按导出目标尺寸设置视口，返回页面实际内容尺寸。

        v1.3.0：**不再**把视口高度放大到整页内容高度，否则 `vh` / `min-height:
        100vh` 等以视口为基准的样式会被撑爆（表现为背景过大、元素间距失真）。
        整页内容由 `capture_final_frame(full_page=True)` 的 captureBeyondViewport
        单次截图完成，视口宽度即导出宽度、视口高度保持目标窗口高度。
        """
        sw, sh = self.content_size()
        out_w = width if width else sw
        if height:
            self.page.set_viewport_size({"width": out_w, "height": height})
        else:
            current = self.page.viewport_size
            self.page.set_viewport_size({"width": out_w, "height": current["height"]})
        time.sleep(0.1)
        return max(1, int(out_w)), max(1, int(sh))

    @staticmethod
    def _fast_hash(img: Image.Image) -> bytes:
        small = img.convert("RGB").resize((128, 128))
        return small.tobytes()

    def page_frozen(self) -> bool:
        """返回 (动画是否已停, 画面是否已稳定)。"""
        anims = self.running_animation_count()
        return anims == 0

    # ---------------------------------------------------------------- capture
    def wait_animation_finished(
        self,
        max_wait: float = ANIMATION_MAX_WAIT,
        sample_interval: float = ANIMATION_SAMPLE_INTERVAL,
        stable_frames: int = ANIMATION_STABLE_FRAMES,
    ) -> bool:
        """等待有限时长动画播放完毕。

        判据：`getAnimations()` 中仅存在无限循环动画时直接通过（v1.3.0），
        否则等待有限动画全部停止 且 连续多帧画面不变。
        返回 True=自然结束，False=达到上限强制截帧。
        """
        finite, _infinite = self.animation_running_counts()
        if finite == 0:
            # 已无有限动画需要等待（可能全是无限循环动画）→ 直接视为就绪
            prev = self._fast_hash(self.capture_final_frame())
            time.sleep(sample_interval)
            cur = self._fast_hash(self.capture_final_frame())
            return prev == cur
        prev = self._fast_hash(self.capture_final_frame())
        stable = 0
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            time.sleep(sample_interval)
            cur = self._fast_hash(self.capture_final_frame())
            if finite == 0 and cur == prev:
                stable += 1
                if stable >= stable_frames:
                    return True
            else:
                stable = 0
            prev = cur
            finite, _infinite = self.animation_running_counts()
        return False

    def capture_frames(
        self,
        fps: int,
        max_wait: float = ANIMATION_MAX_WAIT,
        max_frames: int = GIF_MAX_FRAMES,
        stable_frames: int = ANIMATION_STABLE_FRAMES,
        full_page: bool = False,
        on_frame=None,
    ) -> tuple[list[Image.Image], list[float]]:
        """从头到尾录制动画帧序列（GIF 用）。

        首帧立即采样，随后以 1/fps 间隔采样；当 `getAnimations()` 中有限动画
        全部停止 且 画面连续 stable_frames 次不变时提前结束，达到 max_frames /
        max_wait 上限则截断（v1.3.0：无限循环动画不阻塞等待）。
        full_page=True 时逐帧捕获整页（captureBeyondViewport 单拍，不撑爆 vh）。
        返回 (帧序列, 各帧采集时刻秒)。
        """
        interval = 1.0 / max(1, int(fps))
        frames: list[Image.Image] = [
            self.capture_final_frame(full_page=full_page)
        ]
        times: list[float] = [time.monotonic()]
        prev = self._fast_hash(frames[0])
        stable = 0
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            time.sleep(interval)
            frame = self.capture_final_frame(full_page=full_page)
            frames.append(frame)
            times.append(time.monotonic())
            if on_frame is not None:
                on_frame(len(frames))
            h = self._fast_hash(frame)
            finite, _infinite = self.animation_running_counts()
            if finite == 0 and h == prev:
                stable += 1
                if stable >= stable_frames:
                    break
            else:
                stable = 0
            prev = h
            if len(frames) >= max_frames:
                break
        return frames, times

    def collect_resource_warnings(self) -> list[str]:
        """收集外链资源加载失败的提醒（设计文档 13：支持外链但失败需提醒）。"""
        failed = self.page.evaluate(
            """() => {
                const out = [];
                for (const el of document.querySelectorAll(
                    'img,video,audio,source,link,script,iframe')) {
                    const src = el.currentSrc || el.src || el.href;
                    if (!src) continue;
                    const tag = el.tagName.toLowerCase();
                    if (tag === 'img' && el.complete && el.naturalWidth === 0) {
                        out.push(src);
                    } else if (tag === 'link' && !el.sheet) {
                        out.push(src);
                    }
                }
                return out;
            }"""
        )
        warnings = []
        for src in failed or []:
            warnings.append(f"外部资源加载失败: {src}")
        return warnings

    def close(self) -> None:
        try:
            self.page.close()
        except Exception:
            pass
