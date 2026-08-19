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
    """把指定目录挂载为本地静态站点，随用随启、随停。"""

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
