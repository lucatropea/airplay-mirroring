from __future__ import annotations

import html
import io
import json
import secrets
import socket
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import qrcode

from mirror.hub import FrameHub

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
STATIC_TYPES = {
    "base.css": "text/css; charset=utf-8",
    "stream.js": "text/javascript; charset=utf-8",
    "host.js": "text/javascript; charset=utf-8",
    "send.js": "text/javascript; charset=utf-8",
}
_STATIC_CACHE: dict[str, bytes] = {}
MAX_FRAME_BYTES = 5_000_000


@dataclass
class AppState:
    hub: FrameHub
    stop: threading.Event
    port: int
    token: str
    lan_ip: str
    qr_png: bytes = b""
    send_url: str = ""
    viewers: int = 0
    viewer_lock: threading.Lock = field(default_factory=threading.Lock)
    sender_lock: threading.Lock = field(default_factory=threading.Lock)
    last_sender_at: float = 0.0
    sender_announced: bool = False

    def refresh_link(self) -> None:
        self.send_url = f"http://{self.lan_ip}:{self.port}/send/{self.token}"
        self.qr_png = make_qr_png(self.send_url)

    def viewer_count(self) -> int:
        with self.viewer_lock:
            return self.viewers

    def note_sender(self) -> None:
        with self.sender_lock:
            self.last_sender_at = time.monotonic()
            if not self.sender_announced:
                self.sender_announced = True
                print("iPad sending")

    def sender_active(self) -> bool:
        with self.sender_lock:
            return (time.monotonic() - self.last_sender_at) < 3.0


class MirrorHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def bind_server(handler: type[BaseHTTPRequestHandler], start_port: int) -> MirrorHTTPServer:
    last_error: OSError | None = None
    for port in range(start_port, start_port + 10):
        try:
            return MirrorHTTPServer(("0.0.0.0", port), handler)
        except OSError as exc:
            last_error = exc
    raise SystemExit(f"No free port from {start_port} ({last_error})")


def build_handler(state: AppState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            dispatch_get(self, state)

        def do_POST(self) -> None:
            dispatch_post(self, state)

        def log_message(self, fmt: str, *args: object) -> None:
            message = str(fmt % args)
            noisy = ("/status", "/live/", "/frame/", "/push/", "/qr.png", "/base.css", ".js")
            if any(part in message for part in noisy):
                return
            print(f"{self.address_string()} {message}")

    return Handler


def dispatch_get(handler: BaseHTTPRequestHandler, state: AppState) -> None:
    parsed = urlparse(handler.path)
    parts = [part for part in parsed.path.split("/") if part]

    if not parts:
        if is_local(handler):
            redirect(handler, "/host")
        else:
            send_bytes(handler, 200, help_page(), "text/html; charset=utf-8")
        return

    head, *rest = parts
    if head == "favicon.ico":
        send_empty(handler, 204)
        return
    if head in STATIC_TYPES and not rest:
        send_bytes(handler, 200, static_file(head), STATIC_TYPES[head])
        return
    if head == "host" and not rest:
        if not ensure_local(handler):
            return
        page = render_page("host.html", url=state.send_url, token=state.token)
        send_bytes(handler, 200, page, "text/html; charset=utf-8")
        return
    if head == "qr.png" and not rest:
        if not ensure_local(handler):
            return
        send_bytes(handler, 200, state.qr_png, "image/png")
        return
    if head == "status" and not rest:
        if not ensure_local(handler):
            return
        send_json(handler, status_payload(state))
        return
    if len(rest) != 1 or head not in {"send", "live", "frame"}:
        send_bytes(handler, 404, message_page("Page not found."), "text/html; charset=utf-8")
        return
    if not token_ok(state.token, rest[0]):
        send_bytes(handler, 403, message_page("Invalid link. Scan the QR code on the PC again."), "text/html; charset=utf-8")
        return

    if head == "send":
        send_bytes(handler, 200, render_page("send.html", token=state.token), "text/html; charset=utf-8")
        return
    if head == "frame":
        serve_frame(handler, state)
        return
    serve_live(handler, state, parse_qs(parsed.query))


def dispatch_post(handler: BaseHTTPRequestHandler, state: AppState) -> None:
    parts = [part for part in urlparse(handler.path).path.split("/") if part]
    if len(parts) == 2 and parts[0] == "push" and token_ok(state.token, parts[1]):
        serve_push(handler, state)
        return

    if not ensure_local(handler):
        return
    path = urlparse(handler.path).path
    if path == "/shutdown":
        send_text(handler, 200, "ok")
        state.stop.set()
        threading.Thread(target=handler.server.shutdown, daemon=True).start()
        return
    send_text(handler, 404, "Not found")


def serve_push(handler: BaseHTTPRequestHandler, state: AppState) -> None:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        send_text(handler, 400, "Bad request")
        return
    if length <= 0 or length > MAX_FRAME_BYTES:
        send_text(handler, 400, "Invalid frame")
        return

    jpeg = handler.rfile.read(length)
    if len(jpeg) != length or jpeg[:3] != b"\xff\xd8\xff":
        send_text(handler, 400, "Invalid frame")
        return

    width = parse_frame_header(handler.headers.get("X-Frame-Width"))
    height = parse_frame_header(handler.headers.get("X-Frame-Height"))
    state.hub.publish(jpeg, (width, height))
    state.note_sender()
    send_empty(handler, 204)


def serve_live(handler: BaseHTTPRequestHandler, state: AppState, query: dict[str, list[str]]) -> None:
    role = query.get("role", ["view"])[0]
    if role not in {"view", "host"}:
        role = "view"
    if not acquire_viewer(state, role):
        send_text(handler, 503, "Too many connections")
        return
    try:
        write_stream(handler, state)
    finally:
        release_viewer(state, role)


def serve_frame(handler: BaseHTTPRequestHandler, state: AppState) -> None:
    jpeg = state.hub.latest()
    if jpeg is None:
        send_text(handler, 503, "No frame yet")
        return
    send_bytes(handler, 200, jpeg, "image/jpeg")


def write_stream(handler: BaseHTTPRequestHandler, state: AppState) -> None:
    """Binary stream: each frame is a big-endian uint32 length followed by JPEG bytes."""
    handler.send_response(200)
    handler.send_header("Content-Type", "application/octet-stream")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Transfer-Encoding", "chunked")
    handler.send_header("Connection", "close")
    handler.end_headers()
    try:
        handler.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass

    seq = 0
    try:
        while not state.stop.is_set():
            item = state.hub.wait_after(seq, 1.0)
            if item is None:
                continue
            seq, jpeg = item
            packet = len(jpeg).to_bytes(4, "big") + jpeg
            handler.wfile.write(b"%X\r\n" % len(packet))
            handler.wfile.write(packet)
            handler.wfile.write(b"\r\n")
            handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError, OSError):
        return


def status_payload(state: AppState) -> dict[str, object]:
    picture = state.hub.snapshot()
    return {
        "fps": picture["fps"],
        "width": picture["width"],
        "height": picture["height"],
        "viewers": state.viewer_count(),
        "url": state.send_url,
        "sender": state.sender_active(),
    }


def acquire_viewer(state: AppState, role: str) -> bool:
    if role == "host":
        return True
    with state.viewer_lock:
        if state.viewers >= 4:
            return False
        state.viewers += 1
        return True


def release_viewer(state: AppState, role: str) -> None:
    if role == "host":
        return
    with state.viewer_lock:
        state.viewers = max(0, state.viewers - 1)


def parse_frame_header(value: str | None) -> int:
    if value is None:
        return 0
    try:
        number = int(value)
    except ValueError:
        return 0
    return max(0, min(number, 8192))


def make_qr_png(url: str) -> bytes:
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    code.add_data(url)
    code.make(fit=True)
    image = code.make_image(fill_color="#111111", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def render_page(name: str, **values: str) -> bytes:
    text = (WEB_DIR / name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", html.escape(value, quote=True))
    return text.encode("utf-8")


def static_file(name: str) -> bytes:
    cached = _STATIC_CACHE.get(name)
    if cached is None:
        cached = (WEB_DIR / name).read_bytes()
        _STATIC_CACHE[name] = cached
    return cached


def token_ok(expected: str, given: str) -> bool:
    if len(expected) != len(given):
        return False
    return secrets.compare_digest(expected, given)


def is_local(handler: BaseHTTPRequestHandler) -> bool:
    host = handler.client_address[0]
    return host.startswith("127.") or host in {"::1", "::ffff:127.0.0.1"}


def ensure_local(handler: BaseHTTPRequestHandler) -> bool:
    if is_local(handler):
        return True
    send_bytes(handler, 403, message_page("This page is only available on the PC."), "text/html; charset=utf-8")
    return False


def send_bytes(handler: BaseHTTPRequestHandler, status: int, body: bytes, content_type: str) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def send_text(handler: BaseHTTPRequestHandler, status: int, text: str) -> None:
    send_bytes(handler, status, text.encode("utf-8"), "text/plain; charset=utf-8")


def send_json(handler: BaseHTTPRequestHandler, payload: dict[str, object]) -> None:
    body = json.dumps(payload).encode("utf-8")
    send_bytes(handler, 200, body, "application/json; charset=utf-8")


def send_empty(handler: BaseHTTPRequestHandler, status: int) -> None:
    handler.send_response(status)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def redirect(handler: BaseHTTPRequestHandler, location: str) -> None:
    handler.send_response(302)
    handler.send_header("Location", location)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def message_page(text: str) -> bytes:
    safe = html.escape(text)
    return (
        "<!DOCTYPE html><html lang=\"en\"><meta charset=\"utf-8\"><title>Mirror</title>"
        "<body style=\"margin:0;font-family:Segoe UI,sans-serif;background:#101010;color:#f3f3f3\">"
        f"<p style=\"padding:32px\">{safe}</p></body></html>"
    ).encode("utf-8")


def help_page() -> bytes:
    return message_page("On the iPad, open the link shown on the PC or scan the QR code.")
