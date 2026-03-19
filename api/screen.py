"""GET /api/screen?type=sector&value=Technology — equity screener."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import re
import logging

import yfinance as yf

# Ensure yfinance cache writes go to /tmp (Vercel filesystem is read-only)
os.environ.setdefault("XDG_CACHE_HOME", "/tmp")
from yfinance.screener.query import EquityQuery

logger = logging.getLogger(__name__)

VALID_TYPES = {"sector", "industry"}
VALUE_RE = re.compile(r'^[A-Za-z0-9 &\-/,.\(\)]{1,100}$')


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        qtype = params.get("type", ["sector"])[0]
        value = params.get("value", [""])[0]

        if not value:
            self._json_response(400, {"error": "Missing 'value' parameter"})
            return

        if qtype not in VALID_TYPES:
            self._json_response(400, {"error": "Parameter 'type' must be 'sector' or 'industry'"})
            return

        if not VALUE_RE.match(value):
            self._json_response(400, {"error": "Invalid 'value' format"})
            return

        try:
            if qtype == "sector":
                stocks = self._screen_sector(value)
            else:
                stocks = self._screen_industry(value)

            self._json_response(200, {"stocks": stocks})
        except Exception as exc:
            logger.exception("screen: unhandled error type=%s value=%s", qtype, value)
            self._json_response(500, {
                "error": f"{type(exc).__name__}: {exc}",
                "type": qtype,
                "value": value,
            })

    # Catch-all for unsupported methods
    def do_POST(self):
        self._json_response(405, {"error": "Method not allowed"})

    do_PUT = do_POST
    do_DELETE = do_POST

    def _screen_sector(self, sector):
        q = EquityQuery("and", [
            EquityQuery("eq", ["region", "in"]),
            EquityQuery("eq", ["exchange", "NSI"]),
            EquityQuery("eq", ["sector", sector]),
        ])
        resp = yf.screen(q, size=250)
        if resp is None:
            return []
        rows = resp.get("quotes", [])
        return self._normalize_rows(rows)

    def _screen_industry(self, industry):
        q = EquityQuery("and", [
            EquityQuery("eq", ["region", "in"]),
            EquityQuery("eq", ["exchange", "NSI"]),
            EquityQuery("eq", ["industry", industry]),
        ])
        resp = yf.screen(q, size=100)
        if resp is None:
            return []
        rows = resp.get("quotes", [])
        return self._normalize_rows(rows)

    def _normalize_rows(self, rows):
        """Return consistent fields for both sector and industry results."""
        stocks = []
        for r in rows:
            stocks.append({
                "symbol": r.get("symbol", ""),
                "name": r.get("shortName", r.get("longName", "")),
                "industry": r.get("industry", ""),
                "sector": r.get("sector", ""),
                "marketCap": r.get("marketCap", 0),
                "currentPrice": r.get("regularMarketPrice", 0),
                "trailingPE": r.get("trailingPE", None),
                "priceToBook": r.get("priceToBook", None),
                "dividendYield": r.get("dividendYield", None),
                "evToEbitda": r.get("enterpriseToEbitda", None),
            })
        return stocks

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=300, s-maxage=300")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
