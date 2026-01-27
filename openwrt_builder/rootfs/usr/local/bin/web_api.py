#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

MAX_BODY_BYTES = 1024 * 1024 # 1 MiB

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}\n')
            return

        self.send_response(404)
        self.end_headers()
    
    def do_POST(self):
        if self.path != "/api":
            self.send_response(404)
            self.end_headers()
            return

        length_raw = self.headers.get("Content-Length")
        if not length_raw:
            return self._send_json(411, {"error": "missing_content_length"})

        try:
            length = int(length_raw)
        except ValueError:
            return self._send_json(400, {"error": "invalid_content_length"})

        if length < 0 or length > MAX_BODY_BYTES:
            return self._send_json(413, {"error": "payload_too_large", "max_bytes": MAX_BODY_BYTES})

        ctype = self.headers.get("Content-Type", "")
        if ctype != "application/json":
            return self._send_json(415, {"error": "unsupported_media_type", "expected": "application/json"})

        body = self.rfile.read(length)
        try:
            obj = json.loads(body.decode("utf-8"))
        except Exception:
            return self._send_json(400, {"error": "invalid_json"})

        if not isinstance(obj, dict):
            return self._send_json(400, {"error": "json_must_be_object"})

        # Пример обработки: echo + метаданные
        return self._send_json(200, {"ok": True, "received": obj})

    def log_message(self, *_):
        # quiet
        pass

if __name__ == "__main__":
    print("listening on 0.0.0.0:8080", flush=True)
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
