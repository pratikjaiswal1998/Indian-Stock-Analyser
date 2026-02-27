"""GET /api/analyze?symbol=TCS.NS&peers=INFY.NS,WIPRO.NS — full stock analysis data."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

import yfinance as yf
import pandas as pd


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        symbol = params.get("symbol", [""])[0]
        peers_str = params.get("peers", [""])[0]
        peers = [p.strip() for p in peers_str.split(",") if p.strip()] if peers_str else []

        if not symbol:
            self._json_response(400, {"error": "Missing 'symbol' parameter"})
            return

        try:
            all_tickers = [symbol] + peers
            result = self._fetch_data(symbol, all_tickers)
            self._json_response(200, result)
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _fetch_data(self, symbol, all_tickers):
        annual_revenue = {}
        quarterly_revenue = {}

        for t in all_tickers:
            try:
                tk = yf.Ticker(t)

                # Annual income
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
                            yr = col.year if hasattr(col, "year") else int(str(col)[:4])
                            val = row[col]
                            if pd.notna(val):
                                yearly[str(yr)] = float(val)
                        if yearly:
                            annual_revenue[t] = yearly

                # Quarterly income
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
                                dt = pd.Timestamp(col)
                                qkey = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
                                qdata[qkey] = float(val)
                        if qdata:
                            quarterly_revenue[t] = qdata
            except Exception:
                pass

        # Price history (selected stock only)
        ohlc = []
        price_yearly = {}
        price_quarterly = {}

        try:
            hist = yf.Ticker(symbol).history(period="4y")
            if hist is not None and not hist.empty:
                hist.index = pd.to_datetime(hist.index)

                # OHLC array for candlestick
                for dt, row in hist.iterrows():
                    ohlc.append({
                        "date": dt.strftime("%Y-%m-%d"),
                        "open": round(float(row["Open"]), 2),
                        "high": round(float(row["High"]), 2),
                        "low": round(float(row["Low"]), 2),
                        "close": round(float(row["Close"]), 2),
                        "volume": int(row["Volume"]),
                    })

                # Yearly avg prices
                for yr, gdf in hist.groupby(hist.index.year):
                    price_yearly[str(yr)] = round(float(gdf["Close"].mean()), 2)

                # Quarterly avg prices
                for (yr, qtr), gdf in hist.groupby(
                        [hist.index.year, (hist.index.month - 1) // 3 + 1]):
                    price_quarterly[f"{yr}-Q{qtr}"] = round(float(gdf["Close"].mean()), 2)
        except Exception:
            pass

        # Financials for news impact
        financials = {}
        try:
            sel_rev = annual_revenue.get(symbol, {})
            if sel_rev:
                years = sorted(sel_rev.keys())
                financials["revenue_cr"] = round(sel_rev[years[-1]] / 1e7, 0)
                if len(years) >= 2 and sel_rev[years[-2]] != 0:
                    financials["revenue_growth"] = round(
                        (sel_rev[years[-1]] - sel_rev[years[-2]]) / sel_rev[years[-2]] * 100, 1)

            inc = yf.Ticker(symbol).income_stmt
            if inc is not None and not inc.empty:
                for lbl in ["Net Income", "Net Income Common Stockholders"]:
                    if lbl in inc.index:
                        pat_row = inc.loc[lbl]
                        pat_vals = {}
                        for col in pat_row.index:
                            yr = col.year if hasattr(col, "year") else int(str(col)[:4])
                            val = pat_row[col]
                            if pd.notna(val):
                                pat_vals[str(yr)] = float(val)
                        if pat_vals:
                            yrs = sorted(pat_vals.keys())
                            financials["net_profit_cr"] = round(pat_vals[yrs[-1]] / 1e7, 0)
                            if len(yrs) >= 2 and pat_vals[yrs[-2]] != 0:
                                financials["profit_growth"] = round(
                                    (pat_vals[yrs[-1]] - pat_vals[yrs[-2]]) / pat_vals[yrs[-2]] * 100, 1)
                        break

            info = yf.Ticker(symbol).info
            pe = info.get("trailingPE")
            if pe:
                financials["pe"] = round(pe, 1)
            mcap = info.get("marketCap", 0)
            if mcap:
                financials["mcap_cr"] = round(mcap / 1e7, 0)
        except Exception:
            pass

        return {
            "annual_revenue": annual_revenue,
            "quarterly_revenue": quarterly_revenue,
            "ohlc": ohlc,
            "price_yearly": price_yearly,
            "price_quarterly": price_quarterly,
            "financials": financials,
        }

    def _json_response(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
