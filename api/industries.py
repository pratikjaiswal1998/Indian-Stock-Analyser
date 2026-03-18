"""GET /api/industries — returns sector -> industry mapping."""
from http.server import BaseHTTPRequestHandler
import json
import logging

logger = logging.getLogger(__name__)

try:
    from yfinance.screener.query import EQUITY_SCREENER_EQ_MAP
except Exception:
    EQUITY_SCREENER_EQ_MAP = {}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            raw = EQUITY_SCREENER_EQ_MAP.get("industry", {})
            sectors = {sector: sorted(industries) for sector, industries in raw.items()}
            self._json_response(200, {"sectors": sectors})
        except Exception:
            logger.exception("industries: unhandled error")
            self._json_response(500, {"error": "Internal server error"})

    # Catch-all for unsupported methods
    def do_POST(self):
        self._json_response(405, {"error": "Method not allowed"})

    do_PUT = do_POST
    do_DELETE = do_POST

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=86400, s-maxage=86400")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
