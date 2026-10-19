"""Loopback-only preview and local result endpoint for the prototype."""

import json
import secrets
import struct
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlsplit

from .analysis import Analyzer, Config, Result
from .runner import run_source
from .ui import PAGE
from .video import LocalFileSource, WIDTH, HEIGHT


def bmp(rgb: bytes) -> bytes:
    row_size = ((WIDTH * 3 + 3) // 4) * 4
    data_size = row_size * HEIGHT
    header = b"BM" + struct.pack("<IHHI", 54 + data_size, 0, 0, 54)
    header += struct.pack("<IiiHHIIiiII", 40, WIDTH, HEIGHT, 1, 24, 0,
                          data_size, 2835, 2835, 0, 0)
    rows = []
    for y in range(HEIGHT - 1, -1, -1):
        row = rgb[y * WIDTH * 3:(y + 1) * WIDTH * 3]
        bgr = bytearray(len(row))
        for i in range(0, len(row), 3):
            bgr[i:i + 3] = row[i:i + 3][::-1]
        rows.append(bytes(bgr) + bytes(row_size - len(row)))
    return header + b"".join(rows)


class Controller:
    def __init__(self, path: Path):
        self.path = path
        self.config = Config()
        self.result = Result()
        self.state = "idle"
        self.detail = "已就绪；仅支持本地视频文件"
        self.latest_frame: Optional[bytes] = None
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.worker: Optional[threading.Thread] = None

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "state": self.state, "detail": self.detail,
                "video_name": self.path.name,
                "config": self.config.to_dict(),
                "result": self.result.to_dict(),
                "queue_current_valid": self.state == "running",
                "privacy": "画面与短时轨迹仅在本机内存处理；不上传、不录制",
            }

    def configure(self, data: dict) -> None:
        config = Config.from_dict(data)
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise RuntimeError("请先停止分析，再调整计数线或排队区域")
            self.config = config

    def start(self) -> None:
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise RuntimeError("分析已经在运行")
            self.stop_event = threading.Event()
            self.result = Result()
            self.latest_frame = None
            self.state = "opening"
            self.detail = "正在检查并打开视频"
            config = self.config

        def work() -> None:
            def on_frame(frame: bytes, result: Result) -> None:
                with self.lock:
                    self.latest_frame = frame
                    self.result = result

            def on_state(state: str, detail: str) -> None:
                with self.lock:
                    self.state, self.detail = state, detail

            run_source(LocalFileSource(self.path), Analyzer(config), on_frame,
                       on_state, self.stop_event, paced=True)

        self.worker = threading.Thread(target=work, name="vision-reader", daemon=True)
        self.worker.start()

    def stop(self) -> None:
        self.stop_event.set()
        worker = self.worker
        if worker:
            worker.join(timeout=4)


def serve(path: Path, port: int = 0, open_browser: bool = True) -> None:
    controller = Controller(path)
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            pass

        def _send(self, code: int, payload: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _json(self, code: int, data: dict) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode(),
                       "application/json; charset=utf-8")

        def _allowed(self) -> bool:
            host = self.headers.get("Host", "").split(":")[0]
            origin = self.headers.get("Origin")
            return (host in ("127.0.0.1", "localhost")
                    and (not origin or origin == f"http://127.0.0.1:{server.server_port}"))

        def _auth(self) -> bool:
            return self._allowed() and secrets.compare_digest(
                self.headers.get("X-Campura-Token", ""), token)

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            if not self._allowed():
                self._json(403, {"error": "只允许本机页面访问"})
                return
            if url.path == "/" and parse_qs(url.query).get("token", [""])[0] == token:
                self._send(200, PAGE.replace("__TOKEN__", token).encode(),
                           "text/html; charset=utf-8")
            elif not self._auth():
                self._json(403, {"error": "本机访问令牌无效"})
            elif url.path == "/api/status":
                self._json(200, controller.snapshot())
            elif url.path == "/api/frame":
                with controller.lock:
                    frame = controller.latest_frame
                if frame is None:
                    self._send(204, b"", "image/bmp")
                else:
                    self._send(200, bmp(frame), "image/bmp")
            else:
                self._json(404, {"error": "接口不存在"})

        def do_POST(self) -> None:
            if not self._auth():
                self._json(403, {"error": "本机访问令牌无效"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 8192:
                    raise ValueError("请求过大")
                data = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/config":
                    controller.configure(data)
                elif self.path == "/api/start":
                    controller.start()
                elif self.path == "/api/stop":
                    controller.stop()
                else:
                    self._json(404, {"error": "接口不存在"})
                    return
                self._json(200, controller.snapshot())
            except (ValueError, TypeError, RuntimeError) as error:
                self._json(400, {"error": str(error)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_port}/?token={token}"
    print("本机配置页面：" + url, flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
        server.server_close()
