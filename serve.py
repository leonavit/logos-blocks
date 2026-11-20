#!/usr/bin/env python3
"""Serve the logo gallery and list image files in the market logos folder."""

import json
import socket
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / "market logos"
ORDER_PATH = ROOT / "order.json"
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".avif"}


def image_files():
    return sorted(
        (path.name for path in FOLDER.iterdir() if path.is_file() and path.suffix.lower() in IMAGES),
        key=lambda name: name.casefold(),
    )


def load_document():
    if not ORDER_PATH.exists():
        return {"order": None, "hidden": None}
    try:
        saved = json.loads(ORDER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"order": None, "hidden": None}
    if isinstance(saved, list):
        return {"order": saved, "hidden": None}
    if isinstance(saved, dict):
        order = saved.get("order")
        hidden = saved.get("hidden")
        return {
            "order": order if isinstance(order, list) else None,
            "hidden": hidden if isinstance(hidden, list) else None,
        }
    return {"order": None, "hidden": None}


def clean_names(names, files):
    known = set(files)
    cleaned = []
    seen = set()
    for name in names or []:
        if isinstance(name, str) and name in known and name not in seen:
            cleaned.append(name)
            seen.add(name)
    return cleaned


def save_document(order, hidden, files):
    payload_order = clean_names(order, files) if isinstance(order, list) else None
    payload_hidden = clean_names(hidden, files) if isinstance(hidden, list) else None
    if payload_hidden:
        document = {"hidden": payload_hidden}
        if payload_order:
            document["order"] = payload_order
        ORDER_PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload_order or []
    if payload_order:
        ORDER_PATH.write_text(json.dumps(payload_order, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload_order
    if ORDER_PATH.exists():
        ORDER_PATH.unlink()
    return []


def read_order(files):
    saved = load_document()["order"]
    if not isinstance(saved, list):
        return None
    ordered = clean_names(saved, files)
    seen = set(ordered)
    for name in files:
        if name not in seen:
            ordered.append(name)
    return ordered


def read_hidden(files):
    saved = load_document()["hidden"]
    if not isinstance(saved, list):
        return None
    return clean_names(saved, files)


def write_order(names, files):
    hidden = load_document()["hidden"]
    return save_document(names, hidden, files)


def write_hidden(names, files):
    order = load_document()["order"]
    save_document(order, names, files)
    return clean_names(names, files)


def send_json(handler, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/api/logos":
            super().do_GET()
            return

        files = image_files()
        send_json(self, {"files": files, "order": read_order(files), "hidden": read_hidden(files)})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/api/order", "/api/hidden"):
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > 1_000_000:
            self.send_error(413)
            return
        raw = self.rfile.read(length) if length else b"[]"
        try:
            names = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(400)
            return
        if not isinstance(names, list):
            self.send_error(400)
            return

        files = image_files()
        if path == "/api/hidden":
            send_json(self, write_hidden(names, files))
            return
        send_json(self, write_order(names, files))


def free_port(start=8765):
    for port in range(start, start + 30):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit("לא נמצא פורט פנוי")


def main():
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"הגלריה זמינה בכתובת {url}", flush=True)
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nהשרת נעצר")


if __name__ == "__main__":
    main()
