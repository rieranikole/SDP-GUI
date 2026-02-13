from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import re
import socket
import subprocess
import threading
import urllib.error
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(exist_ok=True)


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


def _extract_code_block(text: str) -> str:
    match = re.search(r"```(?:matlab)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _safe_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


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


def _model_defaults(model_config: dict[str, str] | None = None) -> tuple[str, str, str]:
    model_config = model_config or {}

    api_key = model_config.get("api_key") or os.environ.get("OPENAI_API_KEY") or os.environ.get("MODEL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No model API key configured. Provide one in the UI, or set OPENAI_API_KEY / MODEL_API_KEY in your environment."
        )

    base_url = (model_config.get("base_url") or os.environ.get("MODEL_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model_name = model_config.get("model") or os.environ.get("OPENAI_MODEL") or os.environ.get("MODEL_NAME") or "gpt-4o-mini"
    return api_key, base_url, model_name


def _chat_completion(system_msg: str, user_msg: str, model_config: dict[str, str] | None = None, temperature: float = 0.2) -> str:
    api_key, base_url, model_name = _model_defaults(model_config)

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": temperature,
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
        with urllib.request.urlopen(req, timeout=120) as resp:
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


def call_model(prompt: str, readable_text: str, model_config: dict[str, str] | None = None) -> str:
    system_msg = (
        "You are an engineering assistant for modeling and simulation workflows. "
        "Answer with concise, technically grounded guidance using the provided SLX-readable text."
    )
    user_msg = (
        f"Readable SLX data:\n{readable_text}\n\n"
        f"User question:\n{prompt}\n\n"
        "Provide a clear answer and mention any uncertainty if data is incomplete."
    )
    return _chat_completion(system_msg, user_msg, model_config=model_config, temperature=0.2)


def generate_matlab_script(prompt: str, readable_text: str, model_config: dict[str, str] | None = None) -> str:
    system_msg = (
        "You generate MATLAB scripts for Simulink workflows. "
        "Return only MATLAB code. No markdown fences. "
        "Script must be runnable in MATLAB batch mode, robust, and include comments. "
        "If appropriate, create/load a model, set key simulation parameters, run simulation, and summarize outputs in a struct named sdp_result."
    )
    user_msg = (
        f"User request:\n{prompt}\n\n"
        f"Readable model context:\n{readable_text}\n\n"
        "Generate one MATLAB script that attempts this workflow and does not require manual UI interactions."
    )
    code = _chat_completion(system_msg, user_msg, model_config=model_config, temperature=0.15)
    code = _extract_code_block(code)
    if not code:
        raise RuntimeError("Generated MATLAB script is empty.")
    return code


def run_matlab_script(script_text: str, model_name: str, matlab_cmd: str = "matlab", timeout_sec: int = 300) -> dict[str, Any]:
    run_id = _safe_run_id()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    script_path = run_dir / "generated_workflow.m"
    wrapper_path = run_dir / "run_wrapper.m"
    report_path = run_dir / "run_report.txt"

    script_path.write_text(script_text, encoding="utf-8")

    script_abs = str(script_path.resolve()).replace("\\", "/")
    report_abs = str(report_path.resolve()).replace("\\", "/")

    wrapper_text = f"""
clc;
try
    run('{script_abs}');
    if exist('sdp_result','var')
        save('sdp_result.mat','sdp_result');
        disp('SDP_RESULT_STRUCT_SAVED');
    else
        disp('SDP_RESULT_STRUCT_NOT_FOUND');
    end
    fid = fopen('{report_abs}','w');
    if fid > 0
        fprintf(fid, 'MATLAB workflow completed successfully.\\n');
        fclose(fid);
    end
catch ME
    disp(getReport(ME, 'extended', 'hyperlinks', 'off'));
    exit(1);
end
""".strip()

    wrapper_path.write_text(wrapper_text, encoding="utf-8")
    wrapper_abs = str(wrapper_path.resolve()).replace("\\", "/")

    cmd = [matlab_cmd, "-batch", f"run('{wrapper_abs}')"]
    proc = subprocess.run(
        cmd,
        cwd=str(run_dir),
        capture_output=True,
        text=True,
        timeout=max(30, int(timeout_sec)),
        shell=False,
    )

    artifacts = [p.name for p in run_dir.iterdir() if p.is_file()]

    status = "success" if proc.returncode == 0 else "error"
    summary = [
        f"Run ID: {run_id}",
        f"Model: {model_name or 'unspecified'}",
        f"MATLAB command: {' '.join(cmd)}",
        f"Return code: {proc.returncode}",
        f"Artifacts: {', '.join(artifacts) if artifacts else 'none'}",
    ]

    if report_path.exists():
        summary.append("")
        summary.append("Run note:")
        summary.append(report_path.read_text(encoding="utf-8", errors="replace").strip())

    return {
        "status": status,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "return_code": proc.returncode,
        "artifacts": artifacts,
        "summary": "\n".join(summary),
    }


def build_workflow_report(
    prompt: str,
    readable_text: str,
    script_text: str,
    matlab_result: dict[str, Any],
    model_config: dict[str, str] | None = None,
) -> str:
    base_report = [
        "SDP MATLAB/Simulink Workflow Report",
        "",
        "Input prompt",
        prompt,
        "",
        "Execution summary",
        matlab_result.get("summary", ""),
        "",
        "MATLAB stdout",
        matlab_result.get("stdout", "(empty)"),
        "",
        "MATLAB stderr",
        matlab_result.get("stderr", "(empty)"),
    ]

    if matlab_result.get("status") != "success":
        base_report.extend([
            "",
            "Assessment",
            "Execution failed. Review stdout/stderr and adjust generated script or environment (toolboxes, model path, license).",
        ])
        return "\n".join(base_report)

    try:
        system_msg = (
            "You are a senior M&S engineer. Produce a concise technical report from MATLAB run logs. "
            "Mention assumptions, likely next steps, and confidence."
        )
        user_msg = (
            f"Prompt:\n{prompt}\n\n"
            f"Readable SLX context:\n{readable_text[:4000]}\n\n"
            f"Generated MATLAB script:\n{script_text[:4000]}\n\n"
            f"MATLAB summary:\n{matlab_result.get('summary','')}\n\n"
            f"MATLAB stdout:\n{matlab_result.get('stdout','')[:4000]}\n\n"
            f"MATLAB stderr:\n{matlab_result.get('stderr','')[:2000]}\n\n"
            "Write a compact report with sections: Outcome, Key Findings, Risks, Recommended Next Iteration."
        )
        ai_report = _chat_completion(system_msg, user_msg, model_config=model_config, temperature=0.1)
        return ai_report.strip()
    except Exception:
        base_report.extend([
            "",
            "Assessment",
            "Workflow executed, but AI report generation failed. Use stdout/stderr and artifacts for manual analysis.",
        ])
        return "\n".join(base_report)


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
        if self.path == "/api/workflow":
            self._handle_workflow()
            return
        self._send_json({"ok": False, "error": "Not found"}, status=404)

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

    def _handle_workflow(self) -> None:
        try:
            body = self._read_json_body()
            prompt = str(body.get("prompt", "")).strip()
            readable_text = str(body.get("readable_text", "")).strip()
            model_config = body.get("model_config", {})
            matlab_cmd = str(body.get("matlab_cmd", "matlab")).strip() or "matlab"
            timeout_sec = int(body.get("timeout_sec", 300))

            if not prompt:
                raise ValueError("Prompt is required.")
            if not readable_text:
                raise ValueError("Readable SLX data is required.")

            script_text = generate_matlab_script(prompt, readable_text, model_config)
            matlab_result = run_matlab_script(
                script_text=script_text,
                model_name=model_config.get("model", ""),
                matlab_cmd=matlab_cmd,
                timeout_sec=timeout_sec,
            )
            report_text = build_workflow_report(prompt, readable_text, script_text, matlab_result, model_config=model_config)

            self._send_json(
                {
                    "ok": True,
                    "generated_script": script_text,
                    "matlab": matlab_result,
                    "report": report_text,
                }
            )
        except subprocess.TimeoutExpired:
            self._send_json({"ok": False, "error": "MATLAB run timed out."}, status=400)
        except FileNotFoundError:
            self._send_json({"ok": False, "error": "MATLAB executable not found. Set MATLAB command/path in UI."}, status=400)
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
