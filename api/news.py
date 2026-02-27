"""GET /api/news?stock=TCS — proxy Google News RSS (CORS blocked from browser)."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
import json
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        stock = params.get("stock", [""])[0]

        if not stock:
            self._json_response(400, {"error": "Missing 'stock' parameter"})
            return

        try:
            articles = self._fetch_news(stock)
            self._json_response(200, {"articles": articles})
        except Exception as e:
            self._json_response(200, {"articles": [], "warning": str(e)})

    def _fetch_news(self, stock_name, count=10):
        query = quote(f"{stock_name} NSE stock")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")

        root = ET.fromstring(data)
        items = root.findall(".//item")
        results = []

        for item in items[:count]:
            title = item.find("title").text if item.find("title") is not None else ""
            source = item.find("source").text if item.find("source") is not None else "Unknown"
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            date_short = ""
            if pub_date:
                try:
                    dt = pd.to_datetime(pub_date)
                    date_short = dt.strftime("%b %d")
                except Exception:
                    date_short = pub_date[:16] if len(pub_date) >= 16 else pub_date

            results.append({
                "title": title,
                "source": source,
                "date": date_short,
            })

        return results

    def _json_response(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
