from __future__ import annotations

import contextlib
import socket
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"


class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def find_open_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def main() -> None:
    port = find_open_port()
    server = ThreadingHTTPServer((HOST, port), QuietHandler)
    url = f"http://{HOST}:{port}/index.html"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("Serving SDP UI")
    print(f"Open: {url}")
    print("Press Ctrl+C to stop.")

    webbrowser.open(url)

    try:
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()
        server.server_close()
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
