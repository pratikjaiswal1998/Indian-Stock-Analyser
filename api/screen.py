"""GET /api/screen?type=sector&value=Technology — equity screener."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

import yfinance as yf
from yfinance.screener.query import EquityQuery


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        qtype = params.get("type", ["sector"])[0]
        value = params.get("value", [""])[0]

        if not value:
            self._json_response(400, {"error": "Missing 'value' parameter"})
            return

        try:
            if qtype == "sector":
                stocks = self._screen_sector(value)
            else:
                stocks = self._screen_industry(value)

            self._json_response(200, {"stocks": stocks})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _screen_sector(self, sector):
        q = EquityQuery("and", [
            EquityQuery("eq", ["region", "in"]),
            EquityQuery("eq", ["exchange", "NSI"]),
            EquityQuery("eq", ["sector", sector]),
        ])
        resp = yf.screen(q, size=250)
        rows = resp.get("quotes", [])
        stocks = []
        for r in rows:
            stocks.append({
                "symbol": r.get("symbol", ""),
                "name": r.get("shortName", r.get("longName", "")),
                "industry": r.get("industry", ""),
                "marketCap": r.get("marketCap", 0),
            })
        return stocks

    def _screen_industry(self, industry):
        q = EquityQuery("and", [
            EquityQuery("eq", ["region", "in"]),
            EquityQuery("eq", ["exchange", "NSI"]),
            EquityQuery("eq", ["industry", industry]),
        ])
        resp = yf.screen(q, size=100)
        rows = resp.get("quotes", [])
        stocks = []
        for r in rows:
            stocks.append({
                "symbol": r.get("symbol", ""),
                "name": r.get("shortName", r.get("longName", "")),
                "industry": r.get("industry", ""),
                "marketCap": r.get("marketCap", 0),
                "currentPrice": r.get("regularMarketPrice", 0),
                "trailingPE": r.get("trailingPE", None),
                "priceToBook": r.get("priceToBook", None),
                "dividendYield": r.get("dividendYield", None),
                "evToEbitda": r.get("enterpriseToEbitda", None),
                "sector": r.get("sector", ""),
            })
        return stocks

    def _json_response(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
