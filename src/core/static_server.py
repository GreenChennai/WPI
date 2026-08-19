"""本地静态服务子系统。

用 Python 标准库 http.server 把源目录挂载到 http://127.0.0.1:<port>/，
避免仅以 file:// 打开导致的资源/模块加载失效（设计文档 4.4）。
"""

from __future__ import annotations

import functools
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from config.presets import INDEX_FILENAMES


class _QuietHandler(SimpleHTTPRequestHandler):
    """静默日志，避免控制台被请求日志刷屏。"""

    def log_message(self, fmt, *args):
        pass


class _SharedHandler(SimpleHTTPRequestHandler):
    """共享服务处理器（v2.1.0）。

    每个请求到达时会新建一个处理器实例；从 SharedServer 快照当前挂载目录
    并作为 `directory` 传给基类（必须在 super().__init__ 之前取好——基类的
    BaseRequestHandler.__init__ 会在内部同步调用 handle()→do_GET()，事后
    再赋值 self.directory 已经来不及）。mount() 切换目录后，后续请求自动
    从新目录取文件。
    """

    shared = None  # SharedServer 实例（ensure_started 时挂上）

    def __init__(self, *args, **kwargs):
        kwargs.pop("directory", None)
        shared = type(self).shared
        directory = shared.directory if shared is not None else None
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, fmt, *args):
        pass


def list_html_files(directory: str) -> list[str]:
    """返回目录内全部 HTML 文件名（相对路径，按名称排序），不含时返回 []。"""
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    return sorted(
        n for n in names
        if n.lower().endswith((".html", ".htm"))
        and os.path.isfile(os.path.join(directory, n))
    )


def resolve_index(directory: str) -> str | None:
    """返回目录内优先使用的入口文件名（相对路径），找不到返回 None。

    v1.7.0：优先 index.html / index.htm，否则取排序后的第一个 HTML。
    """
    names = set(list_html_files(directory))
    if not names:
        return None
    for name in INDEX_FILENAMES:
        if name in names:
            return name
    return sorted(names)[0]


class StaticServer:
    """把指定目录挂载为本地静态站点，随用随启、随停（导出用，每次一个）。"""

    def __init__(self, directory: str):
        self.directory = os.path.abspath(directory)
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not os.path.isdir(self.directory):
            raise NotADirectoryError(f"源目录不存在: {self.directory}")
        handler = functools.partial(_QuietHandler, directory=self.directory)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            daemon=True,
            name="WPI-StaticServer",
        )
        self._thread.start()

    @property
    def port(self) -> int:
        if self._httpd is None:
            raise RuntimeError("静态服务尚未启动")
        return self._httpd.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        httpd, self._httpd = self._httpd, None
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()


class SharedServer:
    """全局唯一静态服务（v2.1.0）：进程内只占一个端口。

    预览 / 「浏览器打开」都挂载到同一台服务上，通过 mount() 切换当前目录，
    不再为每个项目开新端口，避免端口占用过多。
    """

    def __init__(self):
        self.directory = os.getcwd()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def ensure_started(self) -> None:
        if self._httpd is None:
            _SharedHandler.shared = self
            self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _SharedHandler)
            self._thread = threading.Thread(
                target=self._httpd.serve_forever,
                daemon=True,
                name="WPI-SharedStatic",
            )
            self._thread.start()

    def mount(self, directory: str) -> None:
        """切换挂载目录：后续请求将从新目录取文件（旧目录请求不受影响）。"""
        self.directory = os.path.abspath(directory)

    @property
    def base_url(self) -> str:
        if self._httpd is None:
            raise RuntimeError("共享静态服务尚未启动")
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def stop(self) -> None:
        httpd, self._httpd = self._httpd, None
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()


_shared_instance: SharedServer | None = None


def shared_server() -> SharedServer:
    """返回进程内唯一的共享静态服务单例（v2.1.0）。"""
    global _shared_instance
    if _shared_instance is None:
        _shared_instance = SharedServer()
    return _shared_instance
