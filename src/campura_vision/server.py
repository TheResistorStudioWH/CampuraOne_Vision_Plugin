"""Ephemeral loopback UI. No credentials, frames or results are saved."""
import hmac
import json
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from . import __version__
from .estimator import InputError, estimate
from .samples import NAMES, example

MAX_BODY = 512000


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=0):
        self.token = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', port), Handler)
        self.host = '127.0.0.1:%d' % self.server_port
        self.origin = 'http://' + self.host

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send(self, status, body, content_type='application/json; charset=utf-8'):
        payload = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def allowed(self, auth=False):
        if self.headers.get('Host') != self.server.host:
            self.send(403, {'error': '仅接受本机 Host'})
            return False
        origin = self.headers.get('Origin')
        if origin is not None and origin != self.server.origin:
            self.send(403, {'error': '不接受其他网页来源'})
            return False
        if auth and not hmac.compare_digest(self.headers.get('X-Campura-Token', '').encode('utf-8'),
                                            self.server.token.encode('utf-8')):
            self.send(401, {'error': '本机会话已失效；请从启动地址重新打开'})
            return False
        return True

    def do_GET(self):
        url = urlsplit(self.path)
        if not self.allowed(auth=url.path.startswith('/api/')):
            return
        assets = {'/': ('ui.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if url.path in assets:
            name, mime = assets[url.path]
            return self.send(200, Path(__file__).with_name(name).read_bytes(), mime)
        if url.path == '/api/health':
            return self.send(200, {'version': __version__, 'mode': 'simulation', 'cloud_enabled': False})
        if url.path == '/api/examples':
            return self.send(200, NAMES)
        if url.path == '/api/example':
            name = parse_qs(url.query).get('name', ['dining'])[0]
            if name not in NAMES:
                return self.send(400, {'error': '未知示例'})
            return self.send(200, example(name))
        self.send(404, {'error': '不存在的路径'})

    def do_POST(self):
        if not self.allowed(auth=True):
            return
        if self.path != '/api/estimate':
            return self.send(404, {'error': '不存在的路径'})
        if self.headers.get_content_type() != 'application/json':
            return self.send(415, {'error': '需要 application/json'})
        if self.headers.get('Transfer-Encoding'):
            return self.send(400, {'error': '不支持分块请求'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BODY:
                return self.send(413, {'error': '请求需要为 1–512000 字节'})
            data = json.loads(self.rfile.read(size).decode('utf-8'))
            result = estimate(data)
        except (InputError, ValueError, UnicodeError, RecursionError) as error:
            # Return validation details only for known, safe domain errors.
            message = str(error) if isinstance(error, InputError) else 'JSON 或请求长度无效'
            return self.send(400, {'error': message})
        self.send(200, result)


def serve(port=0, open_browser=False):
    server = LocalServer(port)
    address = server.origin + '/#' + server.token
    print('Campura One 独立试算器（仅模拟数据）\n' + address, flush=True)
    print('按 Ctrl+C 停止；会话令牌随进程结束失效。', flush=True)
    if open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
