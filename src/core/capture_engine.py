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

# 本软件会自产高倍率大图（4X/8X 整页可超 1 亿像素），放开 PIL
# 防炸弹像素上限（默认 178M 会误报 DecompressionBombError）。
Image.MAX_IMAGE_PIXELS = None

from config.presets import (
    ANIMATION_CAPTURE_JPEG_QUALITY,
    ANIMATION_INFINITE_WAIT,
    ANIMATION_MAX_WAIT,
    ANIMATION_SAMPLE_INTERVAL,
    ANIMATION_SETTLE_MAX_WAIT,
    ANIMATION_STABLE_FRAMES,
    ASSET_WAIT,
    RENDER_RAF_THROTTLE_MS,
    SCROLL_REVEAL_MAX_STEPS,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from .browser_host import BrowserHost


# 页面加载前注入的 rAF 节流脚本（所有导出格式）。无头模式下 rAF 不锁 60fps，
# 密集 rAF 画布动画（数百 fps）会占满渲染主线程——`page.evaluate` 中 await 的
# 续跑和 Playwright 自带超时都建立在页面主线程能调度任务之上，主线程被占满时
# 两者同时失效，导出会卡死在固定百分比无法前进（如 PNG 的 40%）。节流到
# ~30fps 后主线程压力骤降不再卡死，同时逐帧动效（墨滴扩散 / 粒子）仍能在
# 数秒内播完，静态与动画导出共用此机制。
_RENDER_THROTTLE_JS = """(() => {
    if (window.__wpiRafThrottled) return;
    window.__wpiRafThrottled = true;
    const INTERVAL = %d;
    window.requestAnimationFrame = (cb) =>
        setTimeout(() => cb(performance.now()), INTERVAL);
    window.cancelAnimationFrame = (id) => clearTimeout(id);
})();""" % RENDER_RAF_THROTTLE_MS


class CaptureEngine:
    def __init__(self, browser: BrowserHost, page: Page, width: int, height: int):
        self.browser = browser
        self.page = page
        self.width = width
        self.height = height

    # ------------------------------------------------------------------ load
    @classmethod
    def load(
        cls,
        browser: BrowserHost,
        url: str,
        viewport: tuple[int, int],
        load_timeout_ms: int = 30000,
        device_scale: int = 1,   # 分辨率倍率（原生渲染，非超分）
        static: bool = False,    # 静态导出（PNG/PDF）：额外模拟减少动效
    ) -> CaptureEngine:
        context, page = browser.new_page(viewport, device_scale_factor=device_scale)
        # 所有格式统一节流 rAF（消除无头模式密集动画占满主线程导致的卡死），
        # 需在页面脚本执行前注入。
        try:
            page.add_init_script(_RENDER_THROTTLE_JS)
        except Exception:
            pass
        if static:
            # 模拟 prefers-reduced-motion 让页面自身的「最小动效」降级生效：
            # 无限 CSS 动画收敛为瞬时完成，密集 rAF 画布动画被页面侧关停，
            # 静态截图取到的是作者为静态读者准备的完整呈现。
            try:
                page.emulate_media(media="screen", reduced_motion="reduce")
            except Exception:
                pass
        page.goto(url, wait_until="load", timeout=load_timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass  # 网络长期不 idle 时以 load 事件为准
        page.wait_for_timeout(200)
        return cls(browser, page, viewport[0], viewport[1])

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _raise_if_cancelled(cancel_event) -> None:
        """长耗时捕获循环里的取消检查（懒导入，避免与 controller 循环依赖）。"""
        if cancel_event is not None and cancel_event.is_set():
            from core.controller import ExportCancelledError

            raise ExportCancelledError()

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
        整页导出时无需等待它（只等有限时长动画）。
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

    def _cdp_session(self):
        """获取（并缓存）CDP 会话，跳过 Playwright 字体等待等开销。"""
        if getattr(self, "_cdp", None) is not None:
            return self._cdp
        try:
            self._cdp = self.page.context.new_cdp_session(self.page)
            self._cdp.send("Page.enable")
        except Exception:
            self._cdp = None
        return self._cdp

    def _screenshot_cdp(self, full_page: bool = False, jpeg: bool = False) -> bytes | None:
        """CDP Page.captureScreenshot 直连（约快 25%），失败回退 Playwright。

        动画逐帧采集走 `format=jpeg`（质量 95 视觉无损）——JPEG 编码/解码
        远快于 PNG，整页采样率可提升数倍，动画更流畅；静帧仍用 PNG 无损通道。
        """
        import base64
        session = self._cdp_session()
        if session is None:
            return None
        params: dict = {"format": "jpeg", "captureBeyondViewport": bool(full_page)}
        if jpeg:
            params["quality"] = ANIMATION_CAPTURE_JPEG_QUALITY
        if full_page:
            try:
                sw, sh = self.content_size()
                params["clip"] = {"x": 0, "y": 0, "width": sw, "height": sh, "scale": 1}
            except Exception:
                pass
        try:
            res = session.send("Page.captureScreenshot", params)
            return base64.b64decode(res["data"])
        except Exception:
            return None

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

    def content_height(self) -> int:
        """返回页面实际内容高度（CSS px）。"""
        return max(1, int(self.content_size()[1]))

    def has_below_fold_canvas(self) -> bool:
        """页面是否有完全处于首屏视口之外的 <canvas>。

        2D canvas 动画在视口外时 Chromium 合成器不刷新其光栅，captureBeyondViewport
        单拍整页会拿到陈旧/欠渲染的画面（静态导出表现为噪波墨流消失、墨滴看
        情况；动画导出表现为一闪一闪）。存在此类 canvas 时应改分块滚动截取，
        让每个 canvas 在屏时再拍。
        """
        try:
            vh = int(self.page.evaluate("() => window.innerHeight || 600"))
            return bool(self.page.evaluate(
                """(vh) => {
                    for (const c of document.querySelectorAll('canvas')) {
                        const r = c.getBoundingClientRect();
                        if (r.width > 0 && r.top >= vh) return true;
                    }
                    return false;
                }""",
                vh,
            ))
        except Exception:
            return False

    def capture_highres(
        self,
        height_css: int | None = None,
        transparent: bool = False,
        scale: int = 1,
        force_tiled: bool = False,
        cancel_event=None,
    ) -> Image.Image:
        """分块截图 + 纵向拼接，用于超长 / 高倍率整页导出。

        方案：滚动到目标行（强制 Chromium 栅格化该区域，避免远端区域白块），
        再用**视口相对 clip**（{y: rel.., height: take}）截图——clip 由浏览器
        按 deviceScaleFactor 自动缩放，块尺寸恒为视口大小（远低于单拍 16384px
        上限），无需手工像素裁切，杜绝拼接错位/模糊；末尾滚动被 clamp 时按
        实际 scrollY 计算视口内偏移（rel = y - scrollY）保证区域精确连续。

        height_css=None 时捕获整页；给定值时只捕获顶部 min(内容高, height_css)
        高度（高度锁定，超出不导出）。

        两条关键优化路径：
        1) **单拍优先**——内容高×倍率在安全上限内时直接 captureBeyondViewport
           单拍（fixed/sticky 元素只画一次、无拼接、无接缝）；force_tiled=True
           时跳过单拍：页面存在视口外 canvas 动画时单拍会拿到陈旧光栅，
           必须分块让每个 canvas 在屏时截取。
        2) 确需分块时，非首块临时隐藏「顶部小条」类 position:fixed 元素，
           拼接后恢复，顶部状态栏不再在每块拼接处重复出现。
           只隐藏 top ≤ 120px 且 height ≤ 200px 的"顶部小条"（顶部导航/状态栏），
           保留其他 fixed 元素（底部装饰/侧边标签/覆盖层），避免一刀切隐藏
           导致非首块「组件缺失」。
        3) 块等待 400ms 并等 2 个 rAF 帧，保证 canvas/JS 重内容在该区域完成
           绘制（过短的等待对含 canvas 卡片的页面不够，会导致卡内空白）。
        """
        vw = self.page.viewport_size
        W = max(1, int(vw["width"]))
        H = max(1, int(vw["height"]))
        total = self.content_height()
        if height_css is not None:
            total = min(total, max(1, int(height_css)))
        # 单拍优先：整页像素尺寸未超安全上限时一次拍全
        # （fixed/sticky 只画一次、无拼接），否则分块
        scale_f = max(1, int(scale or 1))
        if not force_tiled and height_css is None and (W * scale_f) <= 15000 and (total * scale_f) <= 15000:
            return self.capture_final_frame(transparent=transparent, full_page=True)
        chunks: list[Image.Image] = []
        y = 0
        first = True
        while y < total:
            self._raise_if_cancelled(cancel_event)
            try:
                self.page.evaluate("(y) => window.scrollTo(0, y)", y)
            except Exception:
                pass
            # 延长等待 + 等 2 个 rAF 帧，保证 canvas/JS 重内容在该区域完成绘制
            self.page.wait_for_timeout(400)
            try:
                self.page.evaluate(
                    "() => new Promise(r =>"
                    " requestAnimationFrame(() => requestAnimationFrame(r)))"
                )
            except Exception:
                pass
            try:
                actual = int(self.page.evaluate("() => window.scrollY || 0"))
            except Exception:
                actual = y
            rel = max(0, y - actual)          # 目标区域在视口内的偏移
            take = min(H - rel, total - y)    # 本次要截的 CSS 高度
            if take <= 0:
                y += H
                continue
            if first:
                self._toggle_fixed_topbar(False)   # 首块显示固定元素
                first = False
            else:
                self._toggle_fixed_topbar(True)    # 非首块隐藏顶部小条，去重
            shot = self.page.screenshot(
                clip={"x": 0, "y": rel, "width": W, "height": take},
                omit_background=transparent,
            )
            chunks.append(
                Image.open(io.BytesIO(shot)).convert(
                    "RGBA" if transparent else "RGB"
                )
            )
            y += H
        self._toggle_fixed_topbar(False)     # 恢复顶部小条可见性
        try:
            self.page.evaluate("() => window.scrollTo(0, 0)")
        except Exception:
            pass
        if not chunks:
            return self.capture_final_frame(transparent=transparent, full_page=False)
        width = max(c.size[0] for c in chunks)
        height = sum(c.size[1] for c in chunks)
        canvas = Image.new(
            "RGBA" if transparent else "RGB",
            (width, height),
            (0, 0, 0, 0) if transparent else (255, 255, 255),
        )
        ty = 0
        for c in chunks:
            canvas.paste(c, (0, ty))
            ty += c.size[1]
        return canvas

    def _toggle_fixed_topbar(self, hide: bool) -> None:
        """智能隐藏"顶部小条"类 fixed 元素（拼接去重）。

        只隐藏 position:fixed 且 getBoundingClientRect.top ≤ 120px 且 height ≤ 200px
        的元素（顶部导航/状态栏）。其他 fixed 元素（底部装饰条、侧边标签、覆
        盖层等）保留，确保分块截图时它们出现在文档中自己的位置（与单拍一致），
        避免一刀切隐藏导致的「组件缺失」。
        """
        try:
            self.page.evaluate(
                """(hide) => {
                    for (const el of document.querySelectorAll('*')) {
                        try {
                            if (getComputedStyle(el).position !== 'fixed') continue;
                            const r = el.getBoundingClientRect();
                            if (r.top <= 120 && r.height <= 200) {
                                el.style.setProperty('visibility',
                                    hide ? 'hidden' : '', 'important');
                            }
                        } catch (e) {}
                    }
                }""",
                bool(hide),
            )
        except Exception:
            pass

    def prepare_full_page(self, width: int | None, height: int | None) -> tuple[int, int]:
        """按导出目标尺寸设置视口，返回页面实际内容尺寸。

        **不**把视口高度放大到整页内容高度，否则 `vh` / `min-height:
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

    # --------------------------------------------------- 资源 / 动画收敛
    def wait_assets(self, timeout: float = ASSET_WAIT) -> None:
        """等待字体与主资源（图片）加载完成，避免截到未渲染 / 未加载的内容。

        强制将懒加载图片转为 eager 并等待其加载完成；带超时保护，
        任何异常都不抛出（最坏情况退化为直接截图，由调用方兜底）。
        """
        try:
            self.page.evaluate(
                """async () => {
                    try {
                        if (document.fonts && document.fonts.ready) {
                            await Promise.race([
                                document.fonts.ready,
                                new Promise(r => setTimeout(r, 3000)),
                            ]);
                        }
                    } catch (e) {}
                    const lazy = document.querySelectorAll('img[loading="lazy"]');
                    for (const i of lazy) { try { i.loading = 'eager'; } catch (e) {} }
                    const imgs = Array.from(document.images);
                    const pending = imgs.filter(
                        i => !i.complete || i.naturalWidth === 0);
                    if (pending.length) {
                        await Promise.race([
                            Promise.all(pending.map(i => new Promise(res => {
                                if (i.complete && i.naturalWidth) return res();
                                const done = () => res();
                                i.addEventListener('load', done, {once: true});
                                i.addEventListener('error', done, {once: true});
                            }))),
                            new Promise(r => setTimeout(r, 5000)),
                        ]);
                    }
                    return true;
                }"""
            )
        except Exception:
            pass
        # 给渲染线程一点时间把字体 / 图片真正绘制上屏
        self.page.wait_for_timeout(200)

    def freeze_animations(self) -> int:
        """完成所有有限时长动画（跳到终态并渲染），返回仍在播放的无限循环动画数。

        用于 PNG / PDF 导出：将页面动效锁定为「播放完毕」状态（如 opacity 从
        0 渐显、transform 位移入场），避免截到半透明 / 未展开的纯色块。
        无限循环动画无法 finish，交由调用方等待后截取。
        """
        return int(
            self.page.evaluate(
                """() => {
                    if (typeof document.getAnimations !== 'function') return 0;
                    let inf = 0;
                    for (const a of document.getAnimations()) {
                        if (a.playState !== 'running') continue;
                        let isInf = false;
                        try {
                            const eff = a.effect;
                            const t = eff && typeof eff.getTiming === 'function'
                                ? eff.getTiming() : null;
                            isInf = !!(t && (t.iterations === Infinity
                                             || t.duration === Infinity));
                        } catch (e) { /* 个别动画计时读取异常，按有限处理 */ }
                        if (isInf) { inf += 1; continue; }
                        try { a.finish(); } catch (e) {}
                    }
                    return inf;
                }"""
            )
        )

    def trigger_scroll_reveals(
        self, step_ms: int = 130, cancel_event=None
    ) -> None:
        """滚动遍历整页以触发滚动入场动画（IntersectionObserver / 滚动监听的
        reveal-on-scroll），结束后回到顶部。

        整页截图（captureBeyondViewport）一次性捕获整页，但「滚动触发型入场
        动画」只在元素进入视口时才播放；若页面从未被滚动过，这些元素停留在
        初始态（透明 / 下移），截到的是未展开内容。此处主动滚动一遍把它们
        「激活」到终态。任何异常都不抛出，退化为直接截图。

        由 Python 侧驱动（同步 scrollTo + sleep）而非页面侧 async 循环：
        重交互页面的主线程被密集 rAF 占满时，页面侧 `await` 的续跑会被饿死
        （Playwright 超时也失效）导致 evaluate 永不返回、导出卡死；同步
        scrollTo 每次只是「注入-执行-返回」，配合 rAF 节流可稳定完成。
        先强制瞬时滚动（页面自身 scroll-behavior:smooth 是卡死放大器），
        超长页面限步数兜底。
        """
        try:
            try:
                self.page.evaluate(
                    "() => {"
                    " document.documentElement.style.scrollBehavior='auto';"
                    " return true; }"
                )
            except Exception:
                pass
            vh = int(self.page.evaluate("() => window.innerHeight || 600"))
            step = max(150, int(vh * 0.85))
            total = self.content_height()
            steps = 0
            for y in range(0, total + 1, step):
                self._raise_if_cancelled(cancel_event)
                try:
                    self.page.evaluate("(y) => window.scrollTo(0, y)", y)
                except Exception:
                    pass
                time.sleep(step_ms / 1000.0)
                steps += 1
                if steps >= SCROLL_REVEAL_MAX_STEPS:
                    break
            try:
                self.page.evaluate("() => window.scrollTo(0, 0)")
            except Exception:
                pass
            time.sleep(0.13)
        except Exception:
            pass

    def settle(
        self,
        infinite_wait: float = ANIMATION_INFINITE_WAIT,
        cancel_event=None,
    ) -> dict:
        """导出前让页面完整呈现：字体/图片加载 + 滚动触发动画展开 + 有限动画
        收敛到终态 + 无限动画等待固定时长后截取。

        返回 {"infinite": <仍在播放的无限动画数>} 供调用方诊断。
        """
        self.wait_assets()
        # 先滚动一遍触发 reveal-on-scroll 入场动画
        self.trigger_scroll_reveals(cancel_event=cancel_event)
        inf = self.freeze_animations()
        if inf > 0:
            # 无限循环动画无法 finish：按需求等待其「完全展开」再截取
            self.page.wait_for_timeout(int(infinite_wait * 1000))
            # 等待期间可能新触发有限入场动画，再次滚动 + 冻结
            self.trigger_scroll_reveals(cancel_event=cancel_event)
            self.freeze_animations()
            # 仍有无限动画在跑，画面无法稳定，再等固定时长让 JS 驱动的一次性
            # 动效（打字机 / 墨滴扩散等）播完
            self.page.wait_for_timeout(int(infinite_wait * 1000))
        else:
            # 已无 CSS 动画在跑：等画面进入稳定（打字机、墨滴等 JS 动效
            # getAnimations() 看不到，只能靠像素不变判定播完）
            self.wait_visual_stability(cancel_event=cancel_event)
        return {"infinite": inf}

    def wait_visual_stability(
        self,
        max_wait: float = ANIMATION_SETTLE_MAX_WAIT,
        sample_interval: float = ANIMATION_SAMPLE_INTERVAL,
        stable_frames: int = ANIMATION_STABLE_FRAMES,
        min_wait: float = 0.4,
        cancel_event=None,
    ) -> bool:
        """等待整页画面进入稳定（JS 驱动的一次性动效播完）。

        getAnimations() 只能看到 CSS / Web Animations；打字机、墨滴扩散等由
        setTimeout / rAF 驱动的动效看不到，只能靠「连续多帧整页像素不变」判断。
        无限循环动画存在时不要调用本方法（画面永远无法稳定会烧满预算）。
        返回 True=已稳定，False=达到预算强制通过。
        """
        time.sleep(min_wait)
        try:
            prev = self._fast_hash(self._shot(full_page=True, jpeg=True))
        except Exception:
            return False
        stable = 0
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            self._raise_if_cancelled(cancel_event)
            time.sleep(sample_interval)
            try:
                cur = self._fast_hash(self._shot(full_page=True, jpeg=True))
            except Exception:
                return False
            if cur == prev:
                stable += 1
                if stable >= stable_frames:
                    return True
            else:
                stable = 0
            prev = cur
        return False


    # ---------------------------------------------------------------- capture
    def wait_animation_finished(
        self,
        max_wait: float = ANIMATION_MAX_WAIT,
        sample_interval: float = ANIMATION_SAMPLE_INTERVAL,
        stable_frames: int = ANIMATION_STABLE_FRAMES,
    ) -> bool:
        """等待有限时长动画播放完毕。

        判据：`getAnimations()` 中仅存在无限循环动画时直接通过，
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

    def _shot(self, full_page: bool, jpeg: bool = False):
        """截取一帧，优先 CDP（更快约 25%），失败回退 Playwright。
        动画逐帧采集默认 JPEG 加速，静帧仍走 PNG 无损。"""
        data = self._screenshot_cdp(full_page=full_page, jpeg=jpeg)
        if data is not None:
            return Image.open(io.BytesIO(data)).convert("RGB")
        return self.capture_final_frame(full_page=full_page)

    def capture_frames(
        self,
        fps: int,
        max_wait: float = ANIMATION_MAX_WAIT,
        max_frames: int | None = None,
        stable_frames: int = ANIMATION_STABLE_FRAMES,
        early_stop: bool = True,   # False 时录满 max_wait 时长
        full_page: bool = False,
        jpeg: bool = True,         # 动画逐帧 JPEG 加速（视觉无损）
        on_frame=None,
        cancel_event=None,
    ) -> tuple[list[Image.Image], list[float]]:
        """录制动画帧序列（GIF / MP4 用）。

        首帧立即采样，随后以 1/fps 间隔实时采样（播放速度 = 真实时间）。
        early_stop=True 时：有限动画全部停止且画面连续 stable_frames 次不变即
        提前结束；early_stop=False 时：录制满 max_wait 秒（帧数 = max_wait×fps，
        受 max_frames 上限约束）。
        自适应节奏：当单帧截图耗时大于 1/fps 间隔时不再 sleep 等待
        （最大化采样率），减少帧重复让动画更流畅。截屏走 CDP
        Page.captureScreenshot（失败回退），比默认通道快约 25%。
        逐帧默认走 CDP JPEG 直采（质量 95 视觉无损）——JPEG 编码/解码远快于
        PNG，整页采样率提升数倍，动画更流畅。返回的 times 为真实采集时刻，
        供控制器按实际节奏计算播放时长（保证播放速度 = 真实时间，不用帧重复拖慢）。
        full_page=True 时逐帧捕获整页。
        """
        fps_i = max(1, int(fps))
        interval = 1.0 / fps_i
        if max_frames is None:
            max_frames = int(max_wait * fps_i) + 2
        frames: list[Image.Image] = [self._shot(full_page, jpeg)]
        times: list[float] = [time.monotonic()]
        prev = self._fast_hash(frames[0])
        stable = 0
        deadline = time.monotonic() + max_wait
        next_t = time.monotonic()  # 自适应节奏基准
        while time.monotonic() < deadline:
            self._raise_if_cancelled(cancel_event)
            next_t += interval
            wait = next_t - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            # 若已超时（sleep 期间或截图慢导致超时）则不再等，直接采下一帧
            frame = self._shot(full_page, jpeg)
            frames.append(frame)
            times.append(time.monotonic())
            if on_frame is not None:
                on_frame(len(frames))
            if early_stop:
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

    def capture_scroll_frames(
        self,
        fps: int,
        max_wait: float = ANIMATION_MAX_WAIT,
        stable_frames: int = ANIMATION_STABLE_FRAMES,
        on_frame=None,
        scroll_limit: int | None = None,   # 高度锁定时限制录制范围
        cancel_event=None,
    ) -> tuple[list[Image.Image], list[float]]:
        """滚动逐帧录制整页（GIF / MP4 用）。

        从头到尾缓慢滚动视口，自然触发 reveal-on-scroll 入场动画（元素进入
        视口才播放），并覆盖页面全部内容，解决「只录到顶部标题、下方是背景
        色块」的问题。首帧先停在顶部以捕获首屏英雄动画，随后在 max_wait 时长
        内均匀滚到底。scroll_limit 给定（高度锁定）时仅录制顶部该高度范围。
        返回 (帧序列, 各帧采集时刻秒)。

        视口内截取而非 captureBeyondViewport 整页：2D canvas 动画在视口外时
        Chromium 合成器不会刷新其光栅，整页单拍会得到陈旧的冻结帧（表现为
        GIF 里一闪一闪）；视口内（在屏）截取每帧都是最新光栅，动画流畅。
        逐帧走 CDP JPEG 直采加速（与 capture_frames 同通道）。
        """
        vh = self.page.evaluate("() => window.innerHeight || 600")
        total = self.page.evaluate(
            "() => Math.max(document.documentElement.scrollHeight, "
            "document.body ? document.body.scrollHeight : 0) || 0"
        )
        if scroll_limit is not None:
            total = min(total, max(0, int(scroll_limit)))
        interval = 1.0 / max(1, int(fps))
        max_frames = max(int(max_wait * fps), 8)
        frames: list[Image.Image] = [self._shot(full_page=False, jpeg=True)]
        times: list[float] = [time.monotonic()]
        if on_frame is not None:
            on_frame(1)
        # 页面很短（视口已容纳全部内容）：停在顶部录制动画 max_wait 时长即可
        if total <= vh:
            deadline = time.monotonic() + max_wait
            while time.monotonic() < deadline and len(frames) < max_frames:
                self._raise_if_cancelled(cancel_event)
                time.sleep(interval)
                frame = self._shot(full_page=False, jpeg=True)
                frames.append(frame)
                times.append(time.monotonic())
                if on_frame is not None:
                    on_frame(len(frames))
            try:
                self.page.evaluate("() => window.scrollTo(0, 0)")
            except Exception:
                pass
            return frames, times
        # 长页面：在 max_wait 内均匀滚动到底，捕获滚动过程与逐段入场动画
        for i in range(1, max_frames):
            self._raise_if_cancelled(cancel_event)
            p = i / (max_frames - 1)
            y = int(total * p)
            try:
                self.page.evaluate("(y) => window.scrollTo(0, y)", y)
            except Exception:
                pass
            time.sleep(interval)
            frame = self._shot(full_page=False, jpeg=True)
            frames.append(frame)
            times.append(time.monotonic())
            if on_frame is not None:
                on_frame(len(frames))
        try:
            self.page.evaluate("() => window.scrollTo(0, 0)")
        except Exception:
            pass
        return frames, times

    def collect_resource_warnings(self) -> list[str]:
        """收集外链资源加载失败的提醒（支持外链但失败需提醒用户）。"""
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
