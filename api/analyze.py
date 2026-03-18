"""GET /api/analyze?symbol=TCS.NS&peers=INFY.NS,WIPRO.NS — full stock analysis data."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import math
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

SYMBOL_RE = re.compile(r'^[A-Z0-9.\-]{1,20}$')
MAX_PEERS = 5


def _safe_float(val):
    """Return float if finite, else None."""
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _parse_year(col):
    """Extract year int from a column label safely."""
    try:
        ts = pd.Timestamp(col)
        return ts.year
    except Exception:
        return None


class _TimeoutAdapter(requests.adapters.HTTPAdapter):
    """HTTPAdapter that enforces a default timeout on all requests."""

    def __init__(self, timeout=15, **kwargs):
        self._timeout = timeout
        super().__init__(**kwargs)

    def send(self, *args, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        return super().send(*args, **kwargs)


def _make_session(timeout=15):
    """Create a requests Session with default timeout for yfinance."""
    s = requests.Session()
    adapter = _TimeoutAdapter(timeout=timeout)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        symbol = params.get("symbol", [""])[0].upper().strip()
        peers_str = params.get("peers", [""])[0]
        peers = [p.strip().upper() for p in peers_str.split(",") if p.strip()] if peers_str else []

        # --- Input validation ---
        if not symbol:
            self._json_response(400, {"error": "Missing 'symbol' parameter"})
            return

        if not SYMBOL_RE.match(symbol):
            self._json_response(400, {"error": "Invalid 'symbol' format"})
            return

        # Cap and validate peers
        peers = peers[:MAX_PEERS]
        peers = [p for p in peers if SYMBOL_RE.match(p)]

        try:
            all_tickers = [symbol] + peers
            result = self._fetch_data(symbol, all_tickers)
            self._json_response(200, result)
        except Exception as e:
            logger.exception("analyze: unhandled error for symbol=%s", symbol)
            self._json_response(500, {"error": "Internal server error"})

    # Catch-all for unsupported methods
    def do_POST(self):
        self._json_response(405, {"error": "Method not allowed"})

    do_PUT = do_POST
    do_DELETE = do_POST

    # ------------------------------------------------------------------
    # Core data fetching
    # ------------------------------------------------------------------
    def _fetch_data(self, symbol, all_tickers):
        warnings = []
        session = _make_session()

        # Build ONE Ticker object per symbol and reuse
        tickers = {}
        for t in all_tickers:
            tickers[t] = yf.Ticker(t, session=session)

        annual_revenue = {}
        quarterly_revenue = {}

        # --- Parallelize yfinance revenue calls ---
        def _fetch_revenue(t):
            tk = tickers[t]
            annual = None
            quarterly = None

            try:
                inc = tk.income_stmt
                if inc is not None and not inc.empty:
                    row = None
                    for lbl in ["Total Revenue", "Operating Revenue"]:
                        if lbl in inc.index:
                            row = inc.loc[lbl]
                            break
                    if row is not None:
                        yearly = {}
                        for col in row.index:
                            yr = _parse_year(col)
                            if yr is None:
                                continue
                            val = row[col]
                            if pd.notna(val):
                                yearly[str(yr)] = float(val)
                        if yearly:
                            annual = yearly
            except Exception as exc:
                return t, annual, quarterly, f"{t}: annual revenue fetch failed — {type(exc).__name__}"

            try:
                qi = tk.quarterly_income_stmt
                if qi is not None and not qi.empty:
                    qrow = None
                    for lbl in ["Total Revenue", "Operating Revenue"]:
                        if lbl in qi.index:
                            qrow = qi.loc[lbl]
                            break
                    if qrow is not None:
                        qdata = {}
                        for col in qrow.index:
                            val = qrow[col]
                            if pd.notna(val):
                                try:
                                    dt = pd.Timestamp(col)
                                    qkey = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
                                    qdata[qkey] = float(val)
                                except Exception:
                                    continue
                        if qdata:
                            quarterly = qdata
            except Exception as exc:
                return t, annual, quarterly, f"{t}: quarterly revenue fetch failed — {type(exc).__name__}"

            return t, annual, quarterly, None

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(_fetch_revenue, t): t for t in all_tickers}
            for fut in as_completed(futures):
                t, annual, quarterly, warn = fut.result()
                if annual:
                    annual_revenue[t] = annual
                if quarterly:
                    quarterly_revenue[t] = quarterly
                if warn:
                    warnings.append(warn)

        # --- Price history (selected stock only, reuse cached Ticker) ---
        ohlc = []
        price_yearly = {}
        price_quarterly = {}

        try:
            tk_sym = tickers[symbol]
            hist = tk_sym.history(period="4y")
            if hist is not None and not hist.empty:
                hist.index = pd.to_datetime(hist.index)

                for dt, row in hist.iterrows():
                    ohlc.append({
                        "date": dt.strftime("%Y-%m-%d"),
                        "open": round(float(row["Open"]), 2),
                        "high": round(float(row["High"]), 2),
                        "low": round(float(row["Low"]), 2),
                        "close": round(float(row["Close"]), 2),
                    })

                for yr, gdf in hist.groupby(hist.index.year):
                    price_yearly[str(yr)] = round(float(gdf["Close"].mean()), 2)

                for (yr, qtr), gdf in hist.groupby(
                        [hist.index.year, (hist.index.month - 1) // 3 + 1]):
                    price_quarterly[f"{yr}-Q{qtr}"] = round(float(gdf["Close"].mean()), 2)
        except Exception as exc:
            warnings.append(f"Price history fetch failed — {type(exc).__name__}")

        # --- Financials for news impact (reuse cached Ticker) ---
        financials = {}
        try:
            sel_rev = annual_revenue.get(symbol, {})
            if sel_rev:
                years = sorted(sel_rev.keys())
                financials["revenue_cr"] = round(sel_rev[years[-1]] / 1e7, 0)
                if len(years) >= 2 and sel_rev[years[-2]] != 0:
                    growth = (sel_rev[years[-1]] - sel_rev[years[-2]]) / sel_rev[years[-2]] * 100
                    safe = _safe_float(growth)
                    if safe is not None:
                        financials["revenue_growth"] = round(safe, 1)

            tk_sym = tickers[symbol]
            inc = tk_sym.income_stmt
            if inc is not None and not inc.empty:
                for lbl in ["Net Income", "Net Income Common Stockholders"]:
                    if lbl in inc.index:
                        pat_row = inc.loc[lbl]
                        pat_vals = {}
                        for col in pat_row.index:
                            yr = _parse_year(col)
                            if yr is None:
                                continue
                            val = pat_row[col]
                            if pd.notna(val):
                                pat_vals[str(yr)] = float(val)
                        if pat_vals:
                            yrs = sorted(pat_vals.keys())
                            financials["net_profit_cr"] = round(pat_vals[yrs[-1]] / 1e7, 0)
                            if len(yrs) >= 2 and pat_vals[yrs[-2]] != 0:
                                growth = (pat_vals[yrs[-1]] - pat_vals[yrs[-2]]) / pat_vals[yrs[-2]] * 100
                                safe = _safe_float(growth)
                                if safe is not None:
                                    financials["profit_growth"] = round(safe, 1)
                        break

            info = tk_sym.info
            pe = info.get("trailingPE")
            if pe:
                safe = _safe_float(pe)
                if safe is not None:
                    financials["pe"] = round(safe, 1)
            mcap = info.get("marketCap", 0)
            if mcap:
                safe = _safe_float(mcap)
                if safe is not None:
                    financials["mcap_cr"] = round(safe / 1e7, 0)
        except Exception as exc:
            warnings.append(f"Financials fetch failed — {type(exc).__name__}")

        result = {
            "annual_revenue": annual_revenue,
            "quarterly_revenue": quarterly_revenue,
            "ohlc": ohlc,
            "price_yearly": price_yearly,
            "price_quarterly": price_quarterly,
            "financials": financials,
        }
        if warnings:
            result["warnings"] = warnings
        return result

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=300, s-maxage=300, stale-while-revalidate=600")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
