"""GET /api/news?stock=TCS — proxy Google News RSS (CORS blocked from browser)."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
from email.utils import parsedate_to_datetime
import json
import logging
import urllib.request

import defusedxml.ElementTree as ET

logger = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        stock = params.get("stock", [""])[0]

        if not stock:
            self._json_response(400, {"error": "Missing 'stock' parameter"})
            return

        try:
            articles = self._fetch_news(stock)
            self._json_response(200, {"articles": articles})
        except Exception:
            logger.exception("news: failed to fetch for stock=%s", stock)
            self._json_response(502, {"articles": [], "error": "Failed to fetch news"})

    # Catch-all for unsupported methods
    def do_POST(self):
        self._json_response(405, {"error": "Method not allowed"})

    do_PUT = do_POST
    do_DELETE = do_POST

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
                    dt = parsedate_to_datetime(pub_date)
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
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=1800, s-maxage=1800")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
