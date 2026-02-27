"""GET /api/industries — returns sector → industry mapping."""
from http.server import BaseHTTPRequestHandler
import json

from yfinance.screener.query import EQUITY_SCREENER_EQ_MAP


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        raw = EQUITY_SCREENER_EQ_MAP.get("industry", {})
        sectors = {sector: sorted(industries) for sector, industries in raw.items()}

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"sectors": sectors}).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
