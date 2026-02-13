from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import socket
import threading
import urllib.error
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _top_list(items: list[str], limit: int = 8) -> str:
    if not items:
        return "None"
    clipped = items[:limit]
    tail = "" if len(items) <= limit else f" ... (+{len(items) - limit} more)"
    return ", ".join(clipped) + tail


def extract_slx_summary(slx_bytes: bytes, filename: str) -> dict[str, Any]:
    systems: list[str] = []
    block_names: list[str] = []
    block_types: list[str] = []
    lines: list[tuple[str, str]] = []
    parse_notes: list[str] = []

    with zipfile.ZipFile(io.BytesIO(slx_bytes), "r") as archive:
        archive_entries = archive.namelist()
        xml_entries = [name for name in archive_entries if name.endswith(".xml")]

        for xml_name in xml_entries:
            try:
                payload = archive.read(xml_name)
                root = ET.fromstring(payload)
            except Exception as exc:
                parse_notes.append(f"Skipped {xml_name}: {exc}")
                continue

            for elem in root.iter():
                tag = _local_tag(elem.tag)

                if tag == "System":
                    sys_name = elem.attrib.get("Name", "")
                    if sys_name:
                        systems.append(sys_name)

                if tag == "Block":
                    block_name = elem.attrib.get("Name", "")
                    block_type = elem.attrib.get("BlockType", "Unknown")
                    if block_name:
                        block_names.append(block_name)
                    block_types.append(block_type)

                if tag == "Line":
                    src = elem.attrib.get("Src", "")
                    dst = elem.attrib.get("Dst", "")
                    lines.append((src, dst))

    type_counts = Counter(block_types)
    top_types = [f"{name}: {count}" for name, count in type_counts.most_common(8)]

    readable = [
        f"SLX summary for: {filename}",
        "",
        "Overview",
        f"- Systems found: {len(systems)}",
        f"- Blocks found: {len(block_types)}",
        f"- Signals/lines found: {len(lines)}",
        "",
        "Top block types",
        f"- {_top_list(top_types)}",
        "",
        "Example systems",
        f"- {_top_list(systems)}",
        "",
        "Example blocks",
        f"- {_top_list(block_names)}",
    ]

    if parse_notes:
        readable.extend(["", "Parser notes", f"- {_top_list(parse_notes, limit=4)}"])

    return {
        "readable_text": "\n".join(readable),
        "stats": {
            "systems": len(systems),
            "blocks": len(block_types),
            "lines": len(lines),
            "xml_files": len(xml_entries),
        },
    }


def call_model(prompt: str, readable_text: str, model_config: dict[str, str] | None = None) -> str:
    model_config = model_config or {}

    api_key = model_config.get("api_key") or os.environ.get("OPENAI_API_KEY") or os.environ.get("MODEL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No model API key configured. Provide one in the UI, or set OPENAI_API_KEY / MODEL_API_KEY in your environment."
        )

    base_url = (model_config.get("base_url") or os.environ.get("MODEL_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model_name = model_config.get("model") or os.environ.get("OPENAI_MODEL") or os.environ.get("MODEL_NAME") or "gpt-4o-mini"

    system_msg = (
        "You are an engineering assistant for modeling and simulation workflows. "
        "Answer with concise, technically grounded guidance using the provided SLX-readable text."
    )
    user_msg = (
        f"Readable SLX data:\n{readable_text}\n\n"
        f"User question:\n{prompt}\n\n"
        "Provide a clear answer and mention any uncertainty if data is incomplete."
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Model API error ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Model API connection error: {exc}") from exc

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("Model API returned no choices.")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))

    if not content:
        raise RuntimeError("Model API returned an empty response.")

    return content.strip()


class SDPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/convert":
            self._handle_convert()
            return
        if self.path == "/api/ask":
            self._handle_ask()
            return
        self._send_json({"error": "Not found"}, status=404)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _handle_convert(self) -> None:
        try:
            body = self._read_json_body()
            filename = str(body.get("filename", "model.slx"))
            content_b64 = body.get("content_b64", "")

            if not content_b64:
                raise ValueError("No file content provided.")
            if not filename.lower().endswith(".slx"):
                raise ValueError("Please upload a .slx file.")

            slx_bytes = base64.b64decode(content_b64)
            result = extract_slx_summary(slx_bytes, filename)
            self._send_json({"ok": True, **result})
        except zipfile.BadZipFile:
            self._send_json({"ok": False, "error": "Invalid .slx file (zip parse failed)."}, status=400)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)

    def _handle_ask(self) -> None:
        try:
            body = self._read_json_body()
            prompt = str(body.get("prompt", "")).strip()
            readable_text = str(body.get("readable_text", "")).strip()
            model_config = body.get("model_config", {})

            if not prompt:
                raise ValueError("Prompt is required.")
            if not readable_text:
                raise ValueError("Readable SLX data is required.")

            answer = call_model(prompt, readable_text, model_config)
            self._send_json({"ok": True, "answer": answer})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)


def find_open_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def main() -> None:
    port = find_open_port()
    server = ThreadingHTTPServer((HOST, port), SDPHandler)
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
