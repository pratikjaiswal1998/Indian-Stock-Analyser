"""GET /api/market-overview — aggregated market data across all NSE sectors."""
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import math
import logging

os.environ.setdefault("XDG_CACHE_HOME", "/tmp")

import yfinance as yf
from yfinance.screener.query import EquityQuery

try:
    from yfinance.screener.query import EQUITY_SCREENER_EQ_MAP
except Exception:
    EQUITY_SCREENER_EQ_MAP = {}

logger = logging.getLogger(__name__)


def _median(values):
    """Compute median of a list of numbers."""
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return round(s[n // 2], 2)
    return round((s[n // 2 - 1] + s[n // 2]) / 2, 2)


def _safe_float(val):
    """Return float if finite, else None."""
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _screen_sector(sector):
    """Screen a single sector and return aggregated data + stock list."""
    try:
        q = EquityQuery("and", [
            EquityQuery("eq", ["region", "in"]),
            EquityQuery("eq", ["exchange", "NSI"]),
            EquityQuery("eq", ["sector", sector]),
        ])
        resp = yf.screen(q, size=100)
        if resp is None:
            return sector, None
        rows = resp.get("quotes", [])
        if not rows:
            return sector, None

        stocks = []
        pe_vals = []
        pb_vals = []
        dy_vals = []
        total_mcap = 0
        weighted_pe_sum = 0
        weighted_pe_mcap = 0

        for r in rows:
            mcap = r.get("marketCap") or 0
            pe = _safe_float(r.get("trailingPE"))
            pb = _safe_float(r.get("priceToBook"))
            dy = _safe_float(r.get("dividendYield"))
            ev = _safe_float(r.get("enterpriseToEbitda"))
            price = _safe_float(r.get("regularMarketPrice"))
            change = _safe_float(r.get("regularMarketChange"))
            change_pct = _safe_float(r.get("regularMarketChangePercent"))

            stock = {
                "symbol": r.get("symbol", ""),
                "name": r.get("shortName", r.get("longName", "")),
                "sector": sector,
                "industry": r.get("industry", ""),
                "marketCap": mcap,
                "currentPrice": price,
                "trailingPE": pe,
                "priceToBook": pb,
                "dividendYield": dy,
                "evToEbitda": ev,
                "priceChange": change,
                "priceChangePercent": change_pct,
            }
            stocks.append(stock)

            total_mcap += mcap
            if pe and pe > 0:
                pe_vals.append(pe)
                if mcap > 0:
                    weighted_pe_sum += pe * mcap
                    weighted_pe_mcap += mcap
            if pb and pb > 0:
                pb_vals.append(pb)
            if dy is not None and dy >= 0:
                dy_vals.append(dy)

        # Top 3 by market cap
        stocks.sort(key=lambda s: s.get("marketCap") or 0, reverse=True)
        top_stocks = []
        for s in stocks[:3]:
            top_stocks.append({
                "symbol": s["symbol"],
                "name": s["name"],
                "marketCap": s["marketCap"],
                "currentPrice": s["currentPrice"],
                "priceChange": s["priceChange"],
                "priceChangePercent": s["priceChangePercent"],
            })

        sector_data = {
            "name": sector,
            "totalMarketCap": total_mcap,
            "stockCount": len(stocks),
            "medianPE": _median(pe_vals),
            "medianPB": _median(pb_vals),
            "medianDividendYield": _median(dy_vals),
            "topStocks": top_stocks,
        }

        return sector, (sector_data, stocks, weighted_pe_sum, weighted_pe_mcap)

    except Exception as exc:
        logger.warning("market_overview: sector %s failed — %s: %s", sector, type(exc).__name__, exc)
        return sector, None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            raw = EQUITY_SCREENER_EQ_MAP.get("industry", {})
            sectors = list(raw.keys())

            if not sectors:
                self._json_response(200, {
                    "sectors": [],
                    "topGainers": [],
                    "topLosers": [],
                    "totalStocks": 0,
                    "totalMarketCap": 0,
                    "avgPE": 0,
                })
                return

            sector_results = []
            all_stocks = []
            grand_total_mcap = 0
            grand_weighted_pe_sum = 0
            grand_weighted_pe_mcap = 0

            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {pool.submit(_screen_sector, s): s for s in sectors}
                for fut in as_completed(futures, timeout=50):
                    try:
                        sector_name, result = fut.result(timeout=5)
                        if result is None:
                            continue
                        sector_data, stocks, wpe_sum, wpe_mcap = result
                        sector_results.append(sector_data)
                        all_stocks.extend(stocks)
                        grand_total_mcap += sector_data["totalMarketCap"]
                        grand_weighted_pe_sum += wpe_sum
                        grand_weighted_pe_mcap += wpe_mcap
                    except Exception as exc:
                        logger.warning("market_overview: future failed — %s", exc)

            # Sort sectors by market cap desc
            sector_results.sort(key=lambda s: s["totalMarketCap"], reverse=True)

            # Top gainers and losers
            stocks_with_change = [
                s for s in all_stocks
                if s.get("priceChangePercent") is not None
            ]
            stocks_with_change.sort(
                key=lambda s: s["priceChangePercent"], reverse=True
            )

            top_gainers = []
            for s in stocks_with_change[:10]:
                if s["priceChangePercent"] > 0:
                    top_gainers.append({
                        "symbol": s["symbol"],
                        "name": s["name"],
                        "sector": s["sector"],
                        "currentPrice": s["currentPrice"],
                        "marketCap": s["marketCap"],
                        "trailingPE": s["trailingPE"],
                        "priceChange": s["priceChange"],
                        "priceChangePercent": s["priceChangePercent"],
                    })

            top_losers = []
            for s in reversed(stocks_with_change[-10:]):
                if s["priceChangePercent"] is not None and s["priceChangePercent"] < 0:
                    top_losers.append({
                        "symbol": s["symbol"],
                        "name": s["name"],
                        "sector": s["sector"],
                        "currentPrice": s["currentPrice"],
                        "marketCap": s["marketCap"],
                        "trailingPE": s["trailingPE"],
                        "priceChange": s["priceChange"],
                        "priceChangePercent": s["priceChangePercent"],
                    })

            avg_pe = round(grand_weighted_pe_sum / grand_weighted_pe_mcap, 1) if grand_weighted_pe_mcap > 0 else 0

            self._json_response(200, {
                "sectors": sector_results,
                "topGainers": top_gainers,
                "topLosers": top_losers,
                "totalStocks": len(all_stocks),
                "totalMarketCap": grand_total_mcap,
                "avgPE": avg_pe,
            })

        except Exception as exc:
            logger.exception("market_overview: unhandled error")
            self._json_response(500, {
                "error": f"{type(exc).__name__}: {exc}",
            })

    def do_POST(self):
        self._json_response(405, {"error": "Method not allowed"})

    do_PUT = do_POST
    do_DELETE = do_POST

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=600, s-maxage=600, stale-while-revalidate=1200")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str, allow_nan=False).encode())
