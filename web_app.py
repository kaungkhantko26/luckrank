#!/usr/bin/env python3
"""Local web app for the decision support system."""

from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from decision_support import analysis_to_dict, create_client, generate_analysis, load_dotenv, local_fallback_analysis


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
MAX_BODY_BYTES = 4096
MAX_PROBLEM_CHARS = 800


class DecisionSupportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            self.send_error(404, "Not found")
            return

        try:
            payload = self.read_json()
            problem = str(payload.get("problem", "")).strip()
            if not problem:
                self.write_json({"error": "Enter a problem first."}, status=400)
                return
            if len(problem) > MAX_PROBLEM_CHARS:
                self.write_json({"error": "Keep the problem under 800 characters."}, status=400)
                return

            factors = {"input_style": "single prompt; infer missing factors carefully"}
            api_key = os.getenv("OPENROUTER_API_KEY")
            use_external = os.getenv("WEB_USE_EXTERNAL_ANALYSIS", "").lower() in {"1", "true", "yes"}
            if api_key and use_external:
                try:
                    analysis = generate_analysis(create_client(api_key, use_fallbacks=False), problem, factors)
                except Exception:
                    analysis = local_fallback_analysis(problem)
            else:
                analysis = local_fallback_analysis(problem)

            response = analysis_to_dict(analysis)
            response["problem"] = problem
            self.write_json(response)
        except ValueError as exc:
            self.write_json({"error": str(exc)}, status=400)
        except Exception:
            self.write_json({"error": "Analysis failed. Try a shorter problem."}, status=500)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("Request is too large.")
        raw_body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw_body or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Invalid request.")
        return payload

    def write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:
            return


def main() -> int:
    load_dotenv()
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), DecisionSupportHandler)
    print(f"Decision Support web app running at http://127.0.0.1:{port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
