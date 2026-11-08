"""Small standard-library JSON API for the TerraGauge frontend."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .repository import ValidationError
from .service import TerraGaugeService


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "sample_cells.json"
MAX_BODY_BYTES = 1_000_000


class TerraGaugeHandler(BaseHTTPRequestHandler):
    service = TerraGaugeService(os.environ.get("TERRAGAUGE_DATASET", DEFAULT_DATASET))

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._json(HTTPStatus.OK, {"status": "ok", "service": "terragauge-api"})
        if parsed.path == "/v1/summary":
            return self._json(HTTPStatus.OK, self.service.summary())
        if parsed.path == "/v1/cells":
            return self._json(HTTPStatus.OK, {"cells": self.service.cells()})
        if parsed.path == "/v1/data-ledger":
            return self._json(HTTPStatus.OK, self.service.data_ledger())
        if parsed.path.startswith("/v1/review-packets/"):
            cell_id = parsed.path.removeprefix("/v1/review-packets/")
            result = self.service.review_packet(cell_id)
            if result is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "cell_not_found"})
            return self._json(HTTPStatus.OK, result)
        if parsed.path.startswith("/v1/cells/"):
            cell_id = parsed.path.removeprefix("/v1/cells/")
            result = self.service.cell(cell_id)
            if result is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "cell_not_found"})
            return self._json(HTTPStatus.OK, result)
        return self._json(HTTPStatus.NOT_FOUND, {"error": "route_not_found"})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._body()
            if self.path == "/v1/analyze-cell":
                return self._json(HTTPStatus.OK, self.service.analyze_cell(payload))
            if self.path == "/v1/gnss/noise-floor":
                return self._json(HTTPStatus.OK, self.service.node_noise_floor(payload))
            return self._json(HTTPStatus.NOT_FOUND, {"error": "route_not_found"})
        except (ValueError, ValidationError, json.JSONDecodeError) as error:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "message": str(error)})

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body must be between 1 and 1,000,000 bytes")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _json(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def run() -> None:
    host = os.environ.get("TERRAGAUGE_HOST", "127.0.0.1")
    port = int(os.environ.get("TERRAGAUGE_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), TerraGaugeHandler)
    print(f"TerraGauge API listening on http://{host}:{port}")
    server.serve_forever()
