from __future__ import annotations

import argparse
import secrets
import threading
import webbrowser

from mirror.hub import FrameHub
from mirror.net import lan_ip
from mirror.server import AppState, MirrorHTTPServer, bind_server, build_handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show the iPad screen on this PC (browser mode)")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stop = threading.Event()
    hub = FrameHub()
    state = AppState(
        hub=hub,
        stop=stop,
        port=args.port,
        token=secrets.token_hex(3),
        lan_ip=lan_ip(),
    )
    server = bind_server(build_handler(state), args.port)
    state.port = int(server.server_address[1])
    state.refresh_link()

    host_url = f"http://127.0.0.1:{state.port}/host"
    print("Mirror web server running")
    print(f"iPad (send): {state.send_url}")
    print("On iPad: open the link in Safari, tap Start sharing (not AirPlay mirroring).")
    print("Keep this window open. Allow Python through the firewall if the iPad cannot connect.")
    if state.lan_ip.startswith("127."):
        print("This PC has no LAN address — connect to Wi‑Fi and restart.")
    threading.Timer(0.4, lambda: webbrowser.open(host_url)).start()

    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
