import os
import sys
import json
import threading
import time
import re
import tkinter as tk
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

import numpy as np
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from yfinance.screener.query import EquityQuery, EQUITY_SCREENER_EQ_MAP

import customtkinter as ctk

try:
    import mplcyberpunk
    HAS_CYBERPUNK = True
    plt.style.use("cyberpunk")
except Exception:
    HAS_CYBERPUNK = False

# ── Neon Terminal Palette ─────────────────────────────────────
DEEP_BG     = "#0a0e1a"
PANEL_BG    = "#111827"
CARD_BG     = "#1a1f3a"
BORDER      = "#1e293b"
NEON_CYAN   = "#00f0ff"
NEON_PINK   = "#ff006e"
NEON_GREEN  = "#00ff88"
NEON_AMBER  = "#ffaa00"
NEON_RED    = "#ff3366"
TEXT_BRIGHT = "#e2e8f0"
TEXT_DIM    = "#64748b"
TEXT_MUTED  = "#475569"
GLOW_CYAN   = "#00f0ff"
GLOW_GREEN  = "#00ff88"

CHART_COLORS = [
    NEON_CYAN, NEON_GREEN, NEON_AMBER, NEON_PINK, "#a78bfa",
    "#38bdf8", "#fb923c", "#e879f9", "#22d3ee", "#facc15",
    "#f472b6", "#34d399",
]

# ── Paths ─────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    _INITIAL_DIR = os.path.dirname(sys.executable)
else:
    _INITIAL_DIR = os.path.dirname(os.path.abspath(__file__))

_CACHE_FILE = os.path.join(_INITIAL_DIR, "industries_cache.json")
_CACHE_MAX_AGE = 7 * 24 * 3600

# ── Sort options ──────────────────────────────────────────────
SORT_OPTIONS = [
    "Value Divergence (default)",
    "Market Cap",
    "P/E Ratio (low first)",
    "P/B Ratio (low first)",
    "Dividend Yield (high first)",
    "EV/EBITDA (low first)",
]

SORT_EXPLANATIONS = {
    "Value Divergence (default)": (
        "Value Divergence compares a stock's revenue growth to its price growth over the last 2-3 years. "
        "Both are normalized to index 100 at the base year so they can be directly compared.\n\n"
        "How it works: If a company's revenue grew 40% but its stock price only grew 10%, the divergence "
        "score is positive \u2014 the business is growing faster than the market is pricing in. This could mean "
        "the stock is undervalued.\n\n"
        "Example: Stock A had revenue go from \u20b91000 Cr to \u20b91400 Cr (+40%), but price went from \u20b9500 to "
        "\u20b9550 (+10%). Revenue index = 140, Price index = 110. Score = +30. This stock appears undervalued.\n\n"
        "Higher score = more undervalued. Negative score = price grew faster than revenue (potentially overvalued)."
    ),
    "Market Cap": (
        "Market Capitalization is the total market value of a company's outstanding shares. "
        "It's calculated as: Share Price \u00d7 Total Shares Outstanding.\n\n"
        "How it works: Larger market cap means the company is valued higher by the market. "
        "Large-cap companies (\u20b950,000+ Cr) are generally more stable. Mid-caps (\u20b910,000-50,000 Cr) "
        "offer a balance of growth and stability. Small-caps (<\u20b910,000 Cr) can grow faster but carry more risk.\n\n"
        "Example: If a company has 10 crore shares at \u20b9500 each, its market cap is \u20b95,000 Cr.\n\n"
        "Sorting by market cap (high first) shows the biggest, most established companies at the top."
    ),
    "P/E Ratio (low first)": (
        "Price-to-Earnings (P/E) Ratio measures how much investors pay per rupee of earnings. "
        "It's calculated as: Share Price \u00f7 Earnings Per Share (EPS).\n\n"
        "How it works: A low P/E might mean the stock is undervalued \u2014 you're paying less for each rupee "
        "of profit. A high P/E could mean the stock is overpriced, OR that investors expect high future growth.\n\n"
        "Example: Stock at \u20b9100 with EPS of \u20b910 has P/E = 10. Stock at \u20b9100 with EPS of \u20b95 has P/E = 20. "
        "The first stock is 'cheaper' relative to its earnings.\n\n"
        "Important: Always compare P/E within the same industry. IT companies typically have P/E of 25-40, "
        "while banks have P/E of 10-20. A P/E of 30 is cheap for IT but expensive for banking."
    ),
    "P/B Ratio (low first)": (
        "Price-to-Book (P/B) Ratio compares a stock's market price to its book value (net assets). "
        "It's calculated as: Share Price \u00f7 Book Value Per Share.\n\n"
        "How it works: P/B below 1.0 means you're buying the company for less than its net asset value \u2014 "
        "like buying a \u20b9100 note for \u20b980. This can signal undervaluation, especially in asset-heavy industries.\n\n"
        "Example: A bank with assets worth \u20b9200 per share trading at \u20b9160 has P/B = 0.8. "
        "You're getting \u20b9200 of book value for \u20b9160.\n\n"
        "Best for: Banks, NBFCs, real estate, and manufacturing companies where book value is meaningful. "
        "Less useful for IT/tech companies where value comes from intangible assets like software and talent."
    ),
    "Dividend Yield (high first)": (
        "Dividend Yield is the annual dividend payment as a percentage of the stock price. "
        "It's calculated as: Annual Dividend Per Share \u00f7 Current Share Price \u00d7 100.\n\n"
        "How it works: Higher yield means more cash income per rupee invested. A 4% dividend yield means "
        "for every \u20b910,000 invested, you get \u20b9400 per year as dividends.\n\n"
        "Example: Stock at \u20b9100 paying \u20b95 annual dividend = 5% yield. Same stock at \u20b9200 = 2.5% yield.\n\n"
        "Caution: Very high yields (>8%) could signal distress \u2014 the price may have dropped sharply, "
        "inflating the yield. The company might cut dividends soon. Look for consistent dividend history. "
        "Stocks with 0% yield reinvest all profits into growth instead."
    ),
    "EV/EBITDA (low first)": (
        "Enterprise Value to EBITDA measures a company's total value relative to its operating earnings. "
        "EV = Market Cap + Debt - Cash. EBITDA = Earnings Before Interest, Taxes, Depreciation & Amortization.\n\n"
        "How it works: Unlike P/E, EV/EBITDA accounts for a company's debt. Two companies with the same "
        "P/E but different debt levels will have different EV/EBITDA \u2014 the one with more debt costs more "
        "to 'buy entirely'.\n\n"
        "Example: Company A has market cap \u20b91000 Cr, debt \u20b9500 Cr, cash \u20b9100 Cr, EBITDA \u20b9200 Cr. "
        "EV = 1000 + 500 - 100 = \u20b91400 Cr. EV/EBITDA = 7x. Under 10x is generally considered cheap.\n\n"
        "Better than P/E for: Comparing companies with different capital structures (debt levels). "
        "Widely used by institutional investors and in M&A valuations."
    ),
}

# ── News Sentiment ────────────────────────────────────────────
# Multi-word phrases are checked first (higher weight); single words use
# regex word-boundary matching to avoid substring false positives like
# "risk" matching inside "brisk" or "sell" inside "counsel".

BULLISH_PHRASES = [
    "revenue growth", "profit growth", "strong growth", "record profit",
    "record revenue", "record high", "beats estimates", "beats expectations",
    "above expectations", "better than expected", "strong results",
    "strong earnings", "strong demand", "market share gain",
    "order win", "new contract", "strategic partnership",
    "strategic acquisition", "share buyback", "dividend hike",
    "dividend increase", "price target raised", "rating upgrade",
    "upgraded to buy", "positive outlook", "guidance raised",
    "raises guidance", "all-time high", "debt reduction",
    "margin expansion", "margin improvement", "stake increase",
    "fund inflow", "net profit up", "net profit rose",
    "net profit jumped", "top line growth", "bottom line growth",
]
BEARISH_PHRASES = [
    "net loss", "revenue decline", "revenue miss", "profit decline",
    "missed estimates", "missed expectations", "below expectations",
    "worse than expected", "weak results", "weak earnings",
    "weak demand", "market share loss", "order cancellation",
    "rating downgrade", "downgraded to sell", "negative outlook",
    "guidance cut", "lowers guidance", "guidance lowered",
    "debt concern", "debt burden", "high debt", "rising debt",
    "margin pressure", "margin contraction", "stake sale",
    "fund outflow", "net profit fell", "net profit declined",
    "price target cut", "price target lowered", "under investigation",
    "regulatory action", "penalty imposed", "consent order",
    "profit warning", "earnings miss", "layoff announced",
]

# Single-word keywords (matched with word boundaries via regex)
BULLISH_WORDS = [
    "growth", "profit", "expansion", "acquisition", "partnership",
    "dividend", "upgrade", "milestone", "innovation", "launch",
    "beats", "surpass", "breakthrough", "bullish", "rally",
    "buyback", "outperform", "recovery", "boost", "gains",
    "soars", "surges", "jumps", "climbs", "rises",
]
BEARISH_WORDS = [
    "loss", "losses", "debt", "downgrade", "restructuring",
    "layoffs", "fraud", "penalty", "decline", "investigation",
    "lawsuit", "default", "recall", "warning", "bearish",
    "crash", "impairment", "underperform", "plunges", "tumbles",
    "slumps", "plummets", "tanks", "sinks", "slides",
]

# Pre-compile word-boundary patterns for single words
_BULL_WORD_PATTERNS = [(w, re.compile(r'\b' + re.escape(w) + r'\b', re.IGNORECASE))
                       for w in BULLISH_WORDS]
_BEAR_WORD_PATTERNS = [(w, re.compile(r'\b' + re.escape(w) + r'\b', re.IGNORECASE))
                       for w in BEARISH_WORDS]

# Negation phrases that flip sentiment of nearby keywords
_NEGATION_PREFIXES = ["no ", "not ", "without ", "lack of ", "failed to ", "unable to "]


def classify_sentiment(text):
    """Classify text as bullish, bearish, or neutral using phrase + word matching."""
    if not text:
        return "neutral", []

    text_lower = text.lower()

    bull_score = 0
    bear_score = 0
    bull_hits = []
    bear_hits = []

    # Phase 1: Multi-word phrases (weight = 2 each, more reliable)
    for phrase in BULLISH_PHRASES:
        if phrase in text_lower:
            # Check if negated
            negated = False
            idx = text_lower.find(phrase)
            before = text_lower[max(0, idx - 15):idx]
            for neg in _NEGATION_PREFIXES:
                if neg in before:
                    negated = True
                    break
            if negated:
                bear_score += 2
                bear_hits.append(f"not {phrase}")
            else:
                bull_score += 2
                bull_hits.append(phrase)

    for phrase in BEARISH_PHRASES:
        if phrase in text_lower:
            negated = False
            idx = text_lower.find(phrase)
            before = text_lower[max(0, idx - 15):idx]
            for neg in _NEGATION_PREFIXES:
                if neg in before:
                    negated = True
                    break
            if negated:
                bull_score += 2
                bull_hits.append(f"no {phrase}")
            else:
                bear_score += 2
                bear_hits.append(phrase)

    # Phase 2: Single words with word-boundary regex (weight = 1 each)
    for word, pattern in _BULL_WORD_PATTERNS:
        if pattern.search(text):
            bull_score += 1
            if word not in bull_hits:
                bull_hits.append(word)

    for word, pattern in _BEAR_WORD_PATTERNS:
        if pattern.search(text):
            bear_score += 1
            if word not in bear_hits:
                bear_hits.append(word)

    # Decide sentiment — require a meaningful gap to avoid coin-flip calls
    diff = bull_score - bear_score
    if diff >= 2:
        return "bullish", bull_hits
    elif diff <= -2:
        return "bearish", bear_hits
    elif bull_score > 0 and bear_score == 0:
        return "bullish", bull_hits
    elif bear_score > 0 and bull_score == 0:
        return "bearish", bear_hits
    return "neutral", bull_hits + bear_hits if (bull_hits or bear_hits) else []


def build_impact_note(sentiment, keywords, title):
    """Build a short impact explanation from sentiment + matched keywords."""
    if sentiment == "bullish":
        if keywords:
            triggers = ", ".join(kw.title() for kw in keywords[:4])
            return (
                f"This news signals positive momentum. "
                f"Key triggers: {triggers}. "
                f"Such developments typically indicate business growth, "
                f"improved financials, or market confidence \u2014 which can "
                f"support the stock's long-term trajectory."
            )
        return "This news has a positive tone that could support investor confidence."
    elif sentiment == "bearish":
        if keywords:
            triggers = ", ".join(kw.title() for kw in keywords[:4])
            return (
                f"This news raises caution. "
                f"Key concerns: {triggers}. "
                f"These factors may indicate operational challenges, "
                f"financial stress, or governance issues \u2014 which could "
                f"put downward pressure on the stock."
            )
        return "This news has a negative tone that warrants caution for investors."
    else:
        if keywords:
            mixed = ", ".join(kw.title() for kw in keywords[:4])
            return (
                f"This news contains mixed signals ({mixed}) and does not "
                f"clearly lean positive or negative. The impact on the stock "
                f"is ambiguous \u2014 monitor for follow-up developments."
            )
        return (
            "This news is neutral and does not strongly indicate "
            "either positive or negative impact on the stock. "
            "Monitor for follow-up developments."
        )


def fetch_google_news(stock_name, count=10):
    """Fetch news from Google News RSS for a given stock name."""
    query = urllib.parse.quote(f"{stock_name} NSE stock")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")
        root = ET.fromstring(data)
        items = root.findall(".//item")
        results = []
        for item in items[:count]:
            title = item.find("title").text if item.find("title") is not None else ""
            source = item.find("source").text if item.find("source") is not None else "Unknown"
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            # Parse date
            date_short = ""
            if pub_date:
                try:
                    dt = pd.to_datetime(pub_date)
                    date_short = dt.strftime("%b %d")
                except Exception:
                    date_short = pub_date[:16] if len(pub_date) >= 16 else pub_date
            results.append({
                "title": title,
                "summary": "",  # Google RSS doesn't give clean summaries
                "source": source,
                "date": date_short,
            })
        return results
    except Exception:
        return []


def fmt_inr(value):
    """Format a number as \u20b9 in Cr (crore) or \u20b9 in L Cr (lakh crore)."""
    if value is None or value == 0:
        return "N/A"
    cr = value / 1e7
    if cr >= 1e5:
        return f"\u20b9{cr / 1e5:.2f} L Cr"
    if cr >= 1:
        return f"\u20b9{cr:,.0f} Cr"
    return f"\u20b9{value:,.0f}"


# ── Industry cache ────────────────────────────────────────────

def load_industry_cache():
    if not os.path.exists(_CACHE_FILE):
        return None
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        ts = cache.get("timestamp", 0)
        if time.time() - ts > _CACHE_MAX_AGE:
            return None
        return cache.get("sectors", {})
    except Exception:
        return None


def save_industry_cache(sectors_dict):
    cache = {"timestamp": time.time(), "sectors": sectors_dict}
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def build_industry_map():
    raw = EQUITY_SCREENER_EQ_MAP.get("industry", {})
    result = {}
    for sector, industries in raw.items():
        result[sector] = sorted(industries)
    return result


# ══════════════════════════════════════════════════════════════
#  StockPicker  —  Neon Terminal UI
# ══════════════════════════════════════════════════════════════

class StockPicker(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("Stock Picker \u2014 NSE Industry Screener")
        self.configure(fg_color=DEEP_BG)
        self.minsize(1400, 920)

        # State
        self._industry_map = {}
        self._loaded_stocks = []
        self._stock_details = {}
        self._divergence_scores = {}
        self._names_to_symbols = {}
        self._computing_scores = False

        # Pie chart drilldown state
        self._pie_level = 0
        self._sector_data = {}
        self._sector_data_loading = False
        self._pie_canvas = None
        self._pie_fig = None
        self._pie_wedges = []
        self._pie_wedge_keys = []

        # News state
        self._news_items = []
        self._news_panel_visible = False

        self._build_ui()
        self._center_window()
        self._load_industries()

    def _center_window(self):
        self.update_idletasks()
        w, h = 1400, 920
        x = (self.winfo_screenwidth() - w) // 2
        y = max(0, (self.winfo_screenheight() - h) // 2 - 20)
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ══════════════════════════════════════════════════════════
    #  BUILD UI
    # ══════════════════════════════════════════════════════════

    def _build_ui(self):
        # ── Master layout: left content + right news panel ────
        self._master_frame = ctk.CTkFrame(self, fg_color=DEEP_BG, corner_radius=0)
        self._master_frame.pack(fill="both", expand=True)

        # News panel (right side) — created first so it packs on the right
        # before left_frame claims all remaining space. Hidden initially.
        self._news_frame = ctk.CTkFrame(
            self._master_frame, fg_color=PANEL_BG, corner_radius=0,
            width=320, border_width=1, border_color=BORDER)
        # Don't pack yet — shown on analyze

        self._left_frame = ctk.CTkFrame(self._master_frame, fg_color=DEEP_BG, corner_radius=0)
        self._left_frame.pack(side="left", fill="both", expand=True)

        self._build_left_panel()
        self._build_news_panel()

    def _build_left_panel(self):
        parent = self._left_frame

        # ── Header ────────────────────────────────────────────
        header = ctk.CTkFrame(parent, fg_color=DEEP_BG, corner_radius=0)
        header.pack(fill="x", padx=24, pady=(18, 0))

        title_frame = ctk.CTkFrame(header, fg_color=DEEP_BG, corner_radius=0)
        title_frame.pack(side="left")

        ctk.CTkLabel(
            title_frame, text="STOCK PICKER",
            font=ctk.CTkFont("Consolas", 22, "bold"),
            text_color=NEON_CYAN
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame, text="\u2500\u2500\u2500",
            font=ctk.CTkFont("Consolas", 14),
            text_color=TEXT_MUTED
        ).pack(side="left", padx=(12, 12))

        ctk.CTkLabel(
            title_frame, text="NSE Industry Screener",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=TEXT_DIM
        ).pack(side="left", pady=(3, 0))

        # ── Row 1: Sector / Industry / Load ───────────────────
        row1 = ctk.CTkFrame(parent, fg_color=DEEP_BG, corner_radius=0)
        row1.pack(fill="x", padx=24, pady=(14, 0))

        ctk.CTkLabel(
            row1, text="Sector:", font=ctk.CTkFont("Segoe UI", 10),
            text_color=TEXT_DIM
        ).pack(side="left")

        self._sector_var = ctk.StringVar()
        self._sector_combo = ctk.CTkComboBox(
            row1, variable=self._sector_var, state="readonly",
            width=220, font=ctk.CTkFont("Segoe UI", 10),
            fg_color=CARD_BG, border_color=BORDER,
            button_color=NEON_CYAN, button_hover_color=GLOW_CYAN,
            dropdown_fg_color=PANEL_BG, dropdown_hover_color=CARD_BG,
            dropdown_text_color=TEXT_BRIGHT, text_color=TEXT_BRIGHT,
            corner_radius=8, command=self._on_sector_change)
        self._sector_combo.pack(side="left", padx=(6, 18))

        ctk.CTkLabel(
            row1, text="Industry:", font=ctk.CTkFont("Segoe UI", 10),
            text_color=TEXT_DIM
        ).pack(side="left")

        self._industry_var = ctk.StringVar()
        self._industry_combo = ctk.CTkComboBox(
            row1, variable=self._industry_var, state="readonly",
            width=300, font=ctk.CTkFont("Segoe UI", 10),
            fg_color=CARD_BG, border_color=BORDER,
            button_color=NEON_CYAN, button_hover_color=GLOW_CYAN,
            dropdown_fg_color=PANEL_BG, dropdown_hover_color=CARD_BG,
            dropdown_text_color=TEXT_BRIGHT, text_color=TEXT_BRIGHT,
            corner_radius=8)
        self._industry_combo.pack(side="left", padx=(6, 18))

        self._load_btn = ctk.CTkButton(
            row1, text="\u25B6  Load Stocks",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            fg_color=NEON_CYAN, hover_color="#00c8d4",
            text_color=DEEP_BG, corner_radius=10,
            width=140, height=32, cursor="hand2",
            command=self._on_load_stocks)
        self._load_btn.pack(side="left")

        # ── Row 2: Stock selector + Analyze ───────────────────
        row2 = ctk.CTkFrame(parent, fg_color=DEEP_BG, corner_radius=0)
        row2.pack(fill="x", padx=24, pady=(10, 0))

        ctk.CTkLabel(
            row2, text="Stock:", font=ctk.CTkFont("Segoe UI", 10),
            text_color=TEXT_DIM
        ).pack(side="left")

        self._stock_var = ctk.StringVar()
        self._stock_combo = ctk.CTkComboBox(
            row2, variable=self._stock_var, state="readonly",
            width=420, font=ctk.CTkFont("Segoe UI", 10),
            fg_color=CARD_BG, border_color=BORDER,
            button_color=NEON_CYAN, button_hover_color=GLOW_CYAN,
            dropdown_fg_color=PANEL_BG, dropdown_hover_color=CARD_BG,
            dropdown_text_color=TEXT_BRIGHT, text_color=TEXT_BRIGHT,
            corner_radius=8)
        self._stock_combo.pack(side="left", padx=(6, 14))

        self._go_btn = ctk.CTkButton(
            row2, text="\u26A1  Analyze",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            fg_color=NEON_GREEN, hover_color="#00d470",
            text_color=DEEP_BG, corner_radius=10,
            width=130, height=32, cursor="hand2",
            command=self._on_analyze)
        self._go_btn.pack(side="left")
        self._go_btn.configure(state="disabled")

        # ── Row 3: Sort + Status ──────────────────────────────
        row3 = ctk.CTkFrame(parent, fg_color=DEEP_BG, corner_radius=0)
        row3.pack(fill="x", padx=24, pady=(10, 0))

        ctk.CTkLabel(
            row3, text="Sort:", font=ctk.CTkFont("Segoe UI", 10),
            text_color=TEXT_DIM
        ).pack(side="left")

        self._sort_var = ctk.StringVar(value=SORT_OPTIONS[0])
        self._sort_combo = ctk.CTkComboBox(
            row3, variable=self._sort_var, state="readonly",
            values=SORT_OPTIONS, width=260,
            font=ctk.CTkFont("Segoe UI", 10),
            fg_color=CARD_BG, border_color=BORDER,
            button_color=NEON_CYAN, button_hover_color=GLOW_CYAN,
            dropdown_fg_color=PANEL_BG, dropdown_hover_color=CARD_BG,
            dropdown_text_color=TEXT_BRIGHT, text_color=TEXT_BRIGHT,
            corner_radius=8, command=self._on_sort_change)
        self._sort_combo.pack(side="left", padx=(6, 18))

        self._status_var = ctk.StringVar(value="Loading industries...")
        self._status_label = ctk.CTkLabel(
            row3, textvariable=self._status_var,
            font=ctk.CTkFont("Consolas", 10),
            text_color=TEXT_DIM)
        self._status_label.pack(side="right")

        # ── Separator (neon line) ─────────────────────────────
        sep1 = ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0)
        sep1.pack(fill="x", padx=24, pady=(14, 0))

        # ── KPI Cards Bar ─────────────────────────────────────
        self._kpi_frame = ctk.CTkFrame(parent, fg_color=DEEP_BG, corner_radius=0)
        self._kpi_frame.pack(fill="x", padx=24, pady=(12, 0))
        self._kpi_labels = {}
        self._kpi_cards = {}

        kpi_defs = [
            ("industry", "INDUSTRY"),
            ("ind_size", "INDUSTRY SIZE"),
            ("mcap", "MARKET CAP"),
            ("price", "PRICE"),
            ("pe", "P/E RATIO"),
            ("signal", "VALUE SIGNAL"),
        ]

        for key, title in kpi_defs:
            card = ctk.CTkFrame(
                self._kpi_frame, fg_color=CARD_BG,
                corner_radius=12, border_width=1,
                border_color=BORDER)
            card.pack(side="left", padx=(0, 10), ipadx=12, ipady=6)

            ctk.CTkLabel(
                card, text=title,
                font=ctk.CTkFont("Consolas", 8),
                text_color=TEXT_MUTED
            ).pack(anchor="w", padx=8, pady=(4, 0))

            lbl = ctk.CTkLabel(
                card, text="\u2014",
                font=ctk.CTkFont("Consolas", 14, "bold"),
                text_color=TEXT_BRIGHT)
            lbl.pack(anchor="w", padx=8, pady=(0, 4))

            self._kpi_labels[key] = lbl
            self._kpi_cards[key] = card

        # ── Separator ─────────────────────────────────────────
        sep2 = ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0)
        sep2.pack(fill="x", padx=24, pady=(12, 0))

        # ── Charts Area (plain tk.Frame for matplotlib compat) ──
        self._chart_frame = tk.Frame(parent, bg=DEEP_BG)
        self._chart_frame.pack(fill="both", expand=True, padx=24, pady=(8, 4))

        tk.Label(
            self._chart_frame,
            text="Select an industry, load stocks, then analyze",
            font=("Segoe UI", 13), fg=TEXT_MUTED, bg=DEEP_BG
        ).pack(expand=True)

        # ── Separator ─────────────────────────────────────────
        sep3 = ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0)
        sep3.pack(fill="x", padx=24, pady=(4, 0))

        # ── Explanation Text Box ──────────────────────────────
        self._explain_frame = ctk.CTkFrame(parent, fg_color=DEEP_BG, corner_radius=0)
        self._explain_frame.pack(fill="x", padx=24, pady=(8, 14))

        ctk.CTkLabel(
            self._explain_frame, text="METRIC EXPLANATION",
            font=ctk.CTkFont("Consolas", 9, "bold"),
            text_color=TEXT_DIM
        ).pack(anchor="w")

        self._explain_text = ctk.CTkTextbox(
            self._explain_frame, height=100,
            font=ctk.CTkFont("Segoe UI", 9),
            fg_color=PANEL_BG, text_color=TEXT_BRIGHT,
            border_width=1, border_color=BORDER,
            corner_radius=8, wrap="word")
        self._explain_text.pack(fill="x", pady=(4, 0))
        self._explain_text.configure(state="disabled")
        self._update_explanation()

    # ── News Intelligence Panel ───────────────────────────────

    def _build_news_panel(self):
        """Build the right-side news intelligence panel (inside self._news_frame)."""
        # Header
        news_header = ctk.CTkFrame(self._news_frame, fg_color=PANEL_BG, corner_radius=0)
        news_header.pack(fill="x", padx=14, pady=(16, 8))

        ctk.CTkLabel(
            news_header, text="\U0001F4E1  NEWS INTELLIGENCE",
            font=ctk.CTkFont("Consolas", 12, "bold"),
            text_color=NEON_CYAN
        ).pack(anchor="w")

        ctk.CTkLabel(
            news_header, text="Sentiment-classified stock news",
            font=ctk.CTkFont("Segoe UI", 9),
            text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(2, 0))

        sep = ctk.CTkFrame(self._news_frame, fg_color=NEON_CYAN, height=1, corner_radius=0)
        sep.pack(fill="x", padx=14, pady=(0, 8))

        # Scrollable news list
        self._news_scroll = ctk.CTkScrollableFrame(
            self._news_frame, fg_color=PANEL_BG,
            corner_radius=0,
            scrollbar_button_color=CARD_BG,
            scrollbar_button_hover_color=TEXT_MUTED)
        self._news_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 10))

        # Placeholder
        self._news_placeholder = ctk.CTkLabel(
            self._news_scroll,
            text="Analyze a stock to see\nrelated news articles",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=TEXT_MUTED, justify="center")
        self._news_placeholder.pack(expand=True, pady=40)

    def _show_news_panel(self):
        if not self._news_panel_visible:
            self._news_frame.pack(side="right", fill="y", before=self._left_frame)
            self._news_frame.pack_propagate(False)  # keep fixed 320px width
            self._news_panel_visible = True

    def _populate_news(self, news_items):
        """Fill news panel with classified news cards."""
        for w in self._news_scroll.winfo_children():
            w.destroy()

        if not news_items:
            ctk.CTkLabel(
                self._news_scroll,
                text="No recent news found\nfor this stock",
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=TEXT_MUTED, justify="center"
            ).pack(expand=True, pady=40)
            return

        for item in news_items:
            sentiment = item.get("sentiment", "neutral")
            title = item.get("title", "No Title")
            source = item.get("source", "Unknown")
            date_str = item.get("date", "")

            # Sentiment colors
            if sentiment == "bullish":
                border_col = NEON_GREEN
                dot = "\U0001F7E2"
                label_text = "BULLISH"
                label_color = NEON_GREEN
            elif sentiment == "bearish":
                border_col = NEON_RED
                dot = "\U0001F534"
                label_text = "BEARISH"
                label_color = NEON_RED
            else:
                border_col = NEON_AMBER
                dot = "\U0001F7E1"
                label_text = "NEUTRAL"
                label_color = NEON_AMBER

            card = ctk.CTkFrame(
                self._news_scroll, fg_color=CARD_BG,
                corner_radius=10, border_width=1,
                border_color=border_col, cursor="hand2")
            card.pack(fill="x", padx=4, pady=(0, 8))

            # Sentiment badge
            badge_frame = ctk.CTkFrame(card, fg_color=CARD_BG, corner_radius=0)
            badge_frame.pack(fill="x", padx=10, pady=(8, 0))

            ctk.CTkLabel(
                badge_frame, text=f"{dot} {label_text}",
                font=ctk.CTkFont("Consolas", 8, "bold"),
                text_color=label_color
            ).pack(side="left")

            if date_str:
                ctk.CTkLabel(
                    badge_frame, text=date_str,
                    font=ctk.CTkFont("Consolas", 8),
                    text_color=TEXT_MUTED
                ).pack(side="right")

            # Title
            ctk.CTkLabel(
                card, text=title,
                font=ctk.CTkFont("Segoe UI", 9),
                text_color=TEXT_BRIGHT,
                wraplength=260, justify="left"
            ).pack(fill="x", padx=10, pady=(4, 2))

            # Source
            ctk.CTkLabel(
                card, text=f"via {source}",
                font=ctk.CTkFont("Segoe UI", 8),
                text_color=TEXT_MUTED
            ).pack(anchor="w", padx=10, pady=(0, 8))

            # Bind click on card and all its children
            news_data = dict(item)
            news_data["dot"] = dot
            news_data["label_text"] = label_text
            news_data["label_color"] = label_color
            news_data["border_col"] = border_col

            def _on_card_click(e, data=news_data):
                self._show_news_popup(data)

            card.bind("<Button-1>", _on_card_click)
            for child in card.winfo_children():
                child.bind("<Button-1>", _on_card_click)
                for grandchild in child.winfo_children():
                    grandchild.bind("<Button-1>", _on_card_click)

    def _show_news_popup(self, data):
        """Show a popup window with news summary and impact analysis."""
        popup = ctk.CTkToplevel(self)
        popup.title("News Detail")
        popup.configure(fg_color=DEEP_BG)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        # Size and center on parent
        pw, ph = 480, 420
        popup.geometry(f"{pw}x{ph}")
        self.update_idletasks()
        px = self.winfo_x() + (self.winfo_width() - pw) // 2
        py = self.winfo_y() + (self.winfo_height() - ph) // 2
        popup.geometry(f"+{px}+{py}")

        sentiment = data.get("sentiment", "neutral")
        title = data.get("title", "")
        summary = data.get("summary", "")
        source = data.get("source", "")
        date_str = data.get("date", "")
        impact = data.get("impact", "")
        dot = data.get("dot", "")
        label_text = data.get("label_text", "NEUTRAL")
        label_color = data.get("label_color", NEON_AMBER)
        border_col = data.get("border_col", NEON_AMBER)

        # ── Header bar with close button ──────────────────────
        header = ctk.CTkFrame(popup, fg_color=PANEL_BG, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header, text=f"{dot} {label_text}",
            font=ctk.CTkFont("Consolas", 12, "bold"),
            text_color=label_color
        ).pack(side="left", padx=16, pady=10)

        if date_str:
            ctk.CTkLabel(
                header, text=date_str,
                font=ctk.CTkFont("Consolas", 10),
                text_color=TEXT_MUTED
            ).pack(side="left", padx=(0, 10), pady=10)

        close_btn = ctk.CTkButton(
            header, text="\u2715", width=32, height=32,
            font=ctk.CTkFont("Consolas", 14),
            fg_color="transparent", hover_color=NEON_RED,
            text_color=TEXT_DIM, corner_radius=6,
            command=popup.destroy)
        close_btn.pack(side="right", padx=10, pady=6)

        # ── Accent line ───────────────────────────────────────
        ctk.CTkFrame(popup, fg_color=border_col, height=2,
                      corner_radius=0).pack(fill="x")

        # ── Content area ──────────────────────────────────────
        content = ctk.CTkFrame(popup, fg_color=DEEP_BG, corner_radius=0)
        content.pack(fill="both", expand=True, padx=20, pady=(16, 20))

        # Title
        ctk.CTkLabel(
            content, text=title,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=TEXT_BRIGHT,
            wraplength=430, justify="left"
        ).pack(anchor="w")

        ctk.CTkLabel(
            content, text=f"via {source}",
            font=ctk.CTkFont("Segoe UI", 9),
            text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(2, 10))

        # Summary (if available)
        if summary:
            ctk.CTkLabel(
                content, text="SUMMARY",
                font=ctk.CTkFont("Consolas", 9, "bold"),
                text_color=TEXT_DIM
            ).pack(anchor="w")

            ctk.CTkLabel(
                content, text=summary,
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=TEXT_BRIGHT,
                wraplength=430, justify="left"
            ).pack(anchor="w", pady=(4, 12))

        # Impact analysis
        if impact:
            impact_label = "WHY THIS MATTERS"
            ctk.CTkLabel(
                content, text=impact_label,
                font=ctk.CTkFont("Consolas", 9, "bold"),
                text_color=label_color
            ).pack(anchor="w")

            ctk.CTkLabel(
                content, text=impact,
                font=ctk.CTkFont("Segoe UI", 10),
                text_color=TEXT_BRIGHT,
                wraplength=430, justify="left"
            ).pack(anchor="w", pady=(4, 0))

        # Close on Escape key
        popup.bind("<Escape>", lambda e: popup.destroy())

        # Close on click outside — bind to root window after a short delay
        def _enable_outside_click():
            def _on_root_click(e):
                try:
                    # Check if click is outside the popup
                    x, y = e.x_root, e.y_root
                    px = popup.winfo_rootx()
                    py = popup.winfo_rooty()
                    pw = popup.winfo_width()
                    ph = popup.winfo_height()
                    if not (px <= x <= px + pw and py <= y <= py + ph):
                        popup.destroy()
                        self.unbind_all("<Button-1>")
                except Exception:
                    pass

            self.bind_all("<Button-1>", _on_root_click, add="+")
            popup.bind("<Destroy>", lambda e: self.unbind_all("<Button-1>"))

        popup.after(200, _enable_outside_click)
        popup.focus_force()

    # ══════════════════════════════════════════════════════════
    #  INDUSTRY LOADING
    # ══════════════════════════════════════════════════════════

    def _load_industries(self):
        def work():
            cached = load_industry_cache()
            if cached:
                self.after(0, lambda: self._on_industries_loaded(cached))
                return
            try:
                imap = build_industry_map()
                save_industry_cache(imap)
                self.after(0, lambda: self._on_industries_loaded(imap))
            except Exception as e:
                self.after(0, lambda: self._status_var.set(f"Error loading industries: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def _on_industries_loaded(self, imap):
        self._industry_map = imap
        sectors = sorted(imap.keys())
        self._sector_combo.configure(values=sectors)
        if sectors:
            self._sector_var.set(sectors[0])
            self._on_sector_change(sectors[0])
        self._status_var.set(f"Ready \u2014 {len(sectors)} sectors loaded")

    def _on_sector_change(self, choice=None):
        sector = self._sector_var.get()
        industries = self._industry_map.get(sector, [])
        self._industry_combo.configure(values=industries)
        if industries:
            self._industry_var.set(industries[0])

        # Reset stock state
        self._loaded_stocks = []
        self._stock_details = {}
        self._divergence_scores = {}
        self._names_to_symbols = {}
        self._stock_combo.configure(values=[])
        self._stock_var.set("")
        self._go_btn.configure(state="disabled")
        for key in self._kpi_labels:
            self._kpi_labels[key].configure(text="\u2014", text_color=TEXT_BRIGHT)
            self._kpi_cards[key].configure(border_color=BORDER)

        # Fetch sector data for Level 1 pie
        self._fetch_sector_data(sector)

    # ══════════════════════════════════════════════════════════
    #  SECTOR DATA FOR PIE LEVEL 1
    # ══════════════════════════════════════════════════════════

    def _fetch_sector_data(self, sector):
        if self._sector_data_loading:
            return
        self._sector_data_loading = True
        self._status_var.set(f"Loading sector overview for {sector}...")

        def work():
            try:
                operands = [
                    EquityQuery('eq', ['region', 'in']),
                    EquityQuery('eq', ['sector', sector]),
                    EquityQuery('is-in', ['exchange', 'NSI']),
                ]
                query = EquityQuery('and', operands)
                result = yf.screen(
                    query, sortField='intradaymarketcap',
                    sortAsc=False, size=250)
                quotes = result.get("quotes", [])
                industry_caps = {}
                for q in quotes:
                    ind = q.get("industry", "Unknown")
                    mcap = q.get("marketCap", 0) or 0
                    industry_caps[ind] = industry_caps.get(ind, 0) + mcap
                self.after(0, lambda: self._on_sector_data_loaded(sector, industry_caps))
            except Exception as e:
                self.after(0, lambda: self._on_sector_data_error(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _on_sector_data_loaded(self, sector, industry_caps):
        self._sector_data_loading = False
        if self._sector_var.get() != sector:
            return
        self._sector_data = industry_caps
        self._status_var.set(
            f"Sector overview: {len(industry_caps)} industries in {sector}")
        self._render_pie_level1()

    def _on_sector_data_error(self, err):
        self._sector_data_loading = False
        self._status_var.set(f"Sector overview error: {err}")

    # ══════════════════════════════════════════════════════════
    #  PIE CHART RENDERING & INTERACTION
    # ══════════════════════════════════════════════════════════

    def _get_chart_fig(self, figsize=(10.5, 7.0)):
        """Create a matplotlib figure with neon styling."""
        fig = Figure(figsize=figsize, dpi=96, facecolor=DEEP_BG)
        return fig

    def _neon_glow(self, ax):
        """Apply mplcyberpunk glow to an axes if available."""
        if HAS_CYBERPUNK:
            try:
                mplcyberpunk.make_lines_glow(ax)
            except Exception:
                pass

    def _style_axis(self, ax):
        """Apply neon terminal styling to a chart axis."""
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(colors=TEXT_DIM, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.grid(True, alpha=0.15, color=TEXT_MUTED)

    def _render_pie_level1(self):
        self._pie_level = 1
        for w in self._chart_frame.winfo_children():
            w.destroy()

        fig = self._get_chart_fig(figsize=(12, 7.5))
        ax_pie = fig.add_subplot(111)
        ax_pie.set_facecolor(DEEP_BG)

        items = sorted(self._sector_data.items(), key=lambda x: x[1], reverse=True)
        items = [(k, v) for k, v in items if v > 0]

        labels, sizes, colors, wedge_keys = [], [], [], []
        for i, (industry, mcap) in enumerate(items):
            if i < 12:
                short = industry if len(industry) <= 22 else industry[:20] + ".."
                labels.append(short)
                sizes.append(mcap)
                colors.append(CHART_COLORS[i % len(CHART_COLORS)])
                wedge_keys.append(industry)
            else:
                break

        if len(items) > 12:
            others_sum = sum(v for _, v in items[12:])
            labels.append("Others")
            sizes.append(others_sum)
            colors.append(TEXT_MUTED)
            wedge_keys.append(None)

        self._pie_wedge_keys = wedge_keys

        if sizes:
            selected_industry = self._industry_var.get()
            explode_list = [0.06 if wedge_keys[i] == selected_industry else 0
                            for i in range(len(sizes))]

            wedges, texts, autotexts = ax_pie.pie(
                sizes, labels=labels, colors=colors, explode=explode_list,
                autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
                startangle=140, pctdistance=0.80, labeldistance=1.12,
                textprops={"fontsize": 9, "color": TEXT_BRIGHT},
                wedgeprops={"edgecolor": DEEP_BG, "linewidth": 2})
            for at in autotexts:
                at.set_fontsize(8)
                at.set_color(DEEP_BG)
                at.set_fontweight("bold")
            self._pie_wedges = list(wedges)
        else:
            self._pie_wedges = []

        sector = self._sector_var.get()
        ax_pie.set_title(
            f"{sector} \u2014 Industries by Market Cap\n(click a slice to load stocks)",
            fontsize=13, color=NEON_CYAN, pad=16,
            fontfamily="Consolas", fontweight="bold")

        fig.tight_layout(pad=1.5)
        canvas = FigureCanvasTkAgg(fig, master=self._chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        canvas.mpl_connect('button_press_event', self._on_pie_click)
        canvas.mpl_connect('motion_notify_event', self._on_pie_hover)
        self._pie_canvas = canvas
        self._pie_fig = fig

    def _render_pie_only(self):
        self._pie_level = 2
        for w in self._chart_frame.winfo_children():
            w.destroy()

        fig = self._get_chart_fig(figsize=(12, 7.5))
        ax_pie = fig.add_subplot(111)
        ax_pie.set_facecolor(DEEP_BG)

        industry = self._industry_var.get()
        same_industry = [s for s, d in self._stock_details.items()
                         if d.get("industry") == industry]

        labels, sizes, colors, wedge_keys = [], [], [], []
        for i, t in enumerate(same_industry):
            d = self._stock_details.get(t, {})
            mcap = d.get("marketCap", 0)
            if mcap <= 0:
                continue
            short = d.get("name", t)
            if len(short) > 20:
                short = short[:18] + ".."
            labels.append(short)
            sizes.append(mcap)
            colors.append(CHART_COLORS[i % len(CHART_COLORS)])
            wedge_keys.append(t)

        if len(sizes) > 12:
            top_keys = wedge_keys[:12]
            top_labels = labels[:12]
            top_sizes = sizes[:12]
            top_colors = colors[:12]
            others_sum = sum(sizes[12:])
            top_labels.append("Others")
            top_sizes.append(others_sum)
            top_colors.append(TEXT_MUTED)
            top_keys.append(None)
            labels, sizes, colors, wedge_keys = top_labels, top_sizes, top_colors, top_keys

        self._pie_wedge_keys = wedge_keys

        if sizes:
            wedges, texts, autotexts = ax_pie.pie(
                sizes, labels=labels, colors=colors,
                autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
                startangle=140, pctdistance=0.80, labeldistance=1.12,
                textprops={"fontsize": 9, "color": TEXT_BRIGHT},
                wedgeprops={"edgecolor": DEEP_BG, "linewidth": 2})
            for at in autotexts:
                at.set_fontsize(8)
                at.set_color(DEEP_BG)
                at.set_fontweight("bold")
            self._pie_wedges = list(wedges)
        else:
            self._pie_wedges = []

        ax_pie.set_title(
            f"Market Share \u2014 {industry} (NSE)\n(click a stock to analyze)",
            fontsize=13, color=NEON_CYAN, pad=16,
            fontfamily="Consolas", fontweight="bold")

        fig.tight_layout(pad=1.5)
        canvas = FigureCanvasTkAgg(fig, master=self._chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        canvas.mpl_connect('button_press_event', self._on_pie_click)
        canvas.mpl_connect('motion_notify_event', self._on_pie_hover)
        self._pie_canvas = canvas
        self._pie_fig = fig

        # Back button
        back_btn = tk.Button(
            self._chart_frame, text="\u2190  Back to Sector View",
            font=("Segoe UI", 9), fg=NEON_CYAN, bg=CARD_BG,
            activebackground=BORDER, activeforeground=NEON_CYAN,
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._on_back_to_sector)
        back_btn.place(relx=0.0, rely=0.0, x=8, y=8)

    def _on_pie_click(self, event):
        if event.inaxes is None:
            return
        for i, wedge in enumerate(self._pie_wedges):
            if i >= len(self._pie_wedge_keys):
                break
            hit, _ = wedge.contains(event)
            if hit:
                key = self._pie_wedge_keys[i]
                if key is None:
                    return
                if self._pie_level == 1:
                    self._on_pie_industry_click(key)
                elif self._pie_level == 2:
                    self._on_pie_stock_click(key)
                return

    def _on_pie_industry_click(self, industry_name):
        if self._load_btn.cget("state") == "disabled":
            return
        industries = list(self._industry_combo.cget("values") if hasattr(self._industry_combo, 'cget') else [])
        # CTkComboBox stores values differently
        try:
            industries = self._industry_combo._values
        except AttributeError:
            industries = []

        if industry_name in industries:
            self._industry_var.set(industry_name)
        else:
            for ind in industries:
                if ind.startswith(industry_name[:15]):
                    self._industry_var.set(ind)
                    break
            else:
                self._status_var.set(f"Industry '{industry_name}' not in dropdown")
                return
        self._on_load_stocks()

    def _on_pie_stock_click(self, symbol):
        for label, sym in self._names_to_symbols.items():
            if sym == symbol:
                self._stock_var.set(label)
                self._on_analyze()
                return

    def _on_pie_hover(self, event):
        if self._pie_canvas is None:
            return
        if event.inaxes is None:
            self._pie_canvas.get_tk_widget().configure(cursor="")
            return
        for i, wedge in enumerate(self._pie_wedges):
            if i >= len(self._pie_wedge_keys):
                break
            hit, _ = wedge.contains(event)
            if hit and self._pie_wedge_keys[i] is not None:
                self._pie_canvas.get_tk_widget().configure(cursor="hand2")
                return
        self._pie_canvas.get_tk_widget().configure(cursor="")

    def _on_back_to_sector(self):
        self._pie_level = 1
        if self._sector_data:
            self._render_pie_level1()
        else:
            self._fetch_sector_data(self._sector_var.get())

    # ══════════════════════════════════════════════════════════
    #  STOCK LOADING VIA SCREENER
    # ══════════════════════════════════════════════════════════

    def _on_load_stocks(self):
        industry = self._industry_var.get()
        if not industry:
            return

        self._load_btn.configure(state="disabled")
        self._go_btn.configure(state="disabled")
        self._status_var.set(f"Screening NSE stocks in {industry}...")
        self._loaded_stocks = []
        self._stock_details = {}
        self._divergence_scores = {}
        self._names_to_symbols = {}
        self._stock_combo.configure(values=[])
        self._stock_var.set("")

        def work():
            try:
                operands = [
                    EquityQuery('eq', ['region', 'in']),
                    EquityQuery('eq', ['industry', industry]),
                    EquityQuery('is-in', ['exchange', 'NSI']),
                ]
                query = EquityQuery('and', operands)
                result = yf.screen(
                    query, sortField='intradaymarketcap',
                    sortAsc=False, size=100)
                quotes = result.get("quotes", [])
                total = result.get("total", 0)
                self.after(0, lambda: self._on_stocks_loaded(quotes, total, industry))
            except Exception as e:
                self.after(0, lambda: self._on_stock_load_error(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _on_stock_load_error(self, err):
        self._load_btn.configure(state="normal")
        self._status_var.set(f"Error: {err}")

    def _on_stocks_loaded(self, quotes, total, industry):
        self._loaded_stocks = quotes
        details = {}
        entries = []
        for q in quotes:
            sym = q.get("symbol", "")
            name = q.get("shortName", sym.replace(".NS", ""))
            mcap = q.get("marketCap", 0)
            price = q.get("regularMarketPrice", 0)
            pe = q.get("trailingPE", 0)
            pb = q.get("priceToBook", 0)
            div_yield = q.get("dividendYield", 0)
            ev_ebitda = q.get("enterpriseToEbitda", 0)
            fwd_pe = q.get("forwardPE", 0)

            details[sym] = {
                "name": name,
                "industry": industry,
                "sector": q.get("sector", ""),
                "marketCap": mcap or 0,
                "currentPrice": price or 0,
                "trailingPE": pe or 0,
                "forwardPE": fwd_pe or 0,
                "priceToBook": pb or 0,
                "dividendYield": (div_yield or 0) * 100 if div_yield and div_yield < 1 else (div_yield or 0),
                "enterpriseToEbitda": ev_ebitda or 0,
            }
            label = f"{name}  ({sym.replace('.NS', '')})"
            entries.append((label, sym))
            self._names_to_symbols[label] = sym

        self._stock_details = details

        entries.sort(key=lambda x: details.get(x[1], {}).get("marketCap", 0), reverse=True)
        labels = [e[0] for e in entries]
        self._stock_combo.configure(values=labels)
        if labels:
            self._stock_var.set(labels[0])

        self._load_btn.configure(state="normal")
        self._go_btn.configure(state="normal")
        self._status_var.set(
            f"{len(quotes)} stocks loaded (of {total} in {industry}) \u2014 computing value scores...")

        self._compute_divergence_scores(list(details.keys()))

        self._pie_level = 2
        self._render_pie_only()

    # ══════════════════════════════════════════════════════════
    #  VALUE DIVERGENCE SCORE COMPUTATION
    # ══════════════════════════════════════════════════════════

    def _compute_divergence_scores(self, symbols):
        self._computing_scores = True

        def work():
            scores = {}
            total = len(symbols)
            for i, sym in enumerate(symbols):
                try:
                    t = yf.Ticker(sym)
                    inc = t.income_stmt
                    rev_yearly = {}
                    if inc is not None and not inc.empty:
                        row = None
                        for lbl in ["Total Revenue", "Operating Revenue"]:
                            if lbl in inc.index:
                                row = inc.loc[lbl]
                                break
                        if row is not None:
                            for col in row.index:
                                yr = col.year if hasattr(col, "year") else int(str(col)[:4])
                                val = row[col]
                                if pd.notna(val):
                                    rev_yearly[yr] = float(val)

                    price_yearly = {}
                    hist = t.history(period="3y")
                    if hist is not None and not hist.empty:
                        hist.index = pd.to_datetime(hist.index)
                        for yr_group, group_df in hist.groupby(hist.index.year):
                            price_yearly[yr_group] = float(group_df["Close"].mean())

                    common_years = sorted(set(rev_yearly.keys()) & set(price_yearly.keys()))
                    if len(common_years) >= 2:
                        rev_vals = [rev_yearly[y] for y in common_years]
                        price_vals = [price_yearly[y] for y in common_years]
                        rev_base = rev_vals[0] if rev_vals[0] != 0 else 1
                        price_base = price_vals[0] if price_vals[0] != 0 else 1
                        rev_idx = [v / rev_base * 100 for v in rev_vals]
                        price_idx = [v / price_base * 100 for v in price_vals]
                        score = sum(r - p for r, p in zip(rev_idx, price_idx))
                        scores[sym] = score
                    else:
                        scores[sym] = -9999
                except Exception:
                    scores[sym] = -9999

                count = i + 1
                if count % 5 == 0 or count == total:
                    self.after(0, lambda c=count: self._status_var.set(
                        f"Computing value scores... {c}/{total}"))

            self.after(0, lambda: self._on_scores_computed(scores))

        threading.Thread(target=work, daemon=True).start()

    def _on_scores_computed(self, scores):
        self._divergence_scores = scores
        self._computing_scores = False
        n = len([s for s in scores.values() if s > -9999])
        self._status_var.set(
            f"{len(self._stock_details)} stocks loaded \u2014 {n} value scores computed")
        self._apply_sort()

    # ══════════════════════════════════════════════════════════
    #  SORTING
    # ══════════════════════════════════════════════════════════

    def _on_sort_change(self, choice=None):
        self._update_explanation()
        self._apply_sort()

    def _update_explanation(self):
        sort_key = self._sort_var.get()
        text = SORT_EXPLANATIONS.get(sort_key, "")
        self._explain_text.configure(state="normal")
        self._explain_text.delete("1.0", "end")
        self._explain_text.insert("1.0", text)
        self._explain_text.configure(state="disabled")

    def _apply_sort(self):
        if not self._stock_details:
            return

        sort_key = self._sort_var.get()
        symbols = list(self._stock_details.keys())

        if sort_key == "Value Divergence (default)":
            symbols.sort(key=lambda s: self._divergence_scores.get(s, -9999), reverse=True)
        elif sort_key == "Market Cap":
            symbols.sort(key=lambda s: self._stock_details[s].get("marketCap", 0), reverse=True)
        elif sort_key == "P/E Ratio (low first)":
            symbols.sort(key=lambda s: self._stock_details[s].get("trailingPE", 0) or 9999)
        elif sort_key == "P/B Ratio (low first)":
            symbols.sort(key=lambda s: self._stock_details[s].get("priceToBook", 0) or 9999)
        elif sort_key == "Dividend Yield (high first)":
            symbols.sort(key=lambda s: self._stock_details[s].get("dividendYield", 0) or 0, reverse=True)
        elif sort_key == "EV/EBITDA (low first)":
            symbols.sort(key=lambda s: self._stock_details[s].get("enterpriseToEbitda", 0) or 9999)

        entries = []
        new_map = {}
        for sym in symbols:
            d = self._stock_details[sym]
            name = d.get("name", sym)

            suffix = ""
            if sort_key == "Value Divergence (default)":
                score = self._divergence_scores.get(sym, -9999)
                if score > -9999:
                    suffix = f"  [VD: {score:+.0f}]"
                else:
                    suffix = "  [VD: N/A]"
            elif sort_key == "Market Cap":
                suffix = f"  [{fmt_inr(d.get('marketCap', 0))}]"
            elif sort_key == "P/E Ratio (low first)":
                pe = d.get("trailingPE", 0)
                suffix = f"  [P/E: {pe:.1f}]" if pe else "  [P/E: N/A]"
            elif sort_key == "P/B Ratio (low first)":
                pb = d.get("priceToBook", 0)
                suffix = f"  [P/B: {pb:.2f}]" if pb else "  [P/B: N/A]"
            elif sort_key == "Dividend Yield (high first)":
                dy = d.get("dividendYield", 0)
                suffix = f"  [Div: {dy:.2f}%]" if dy else "  [Div: 0%]"
            elif sort_key == "EV/EBITDA (low first)":
                ev = d.get("enterpriseToEbitda", 0)
                suffix = f"  [EV/E: {ev:.1f}]" if ev else "  [EV/E: N/A]"

            label = f"{name}  ({sym.replace('.NS', '')}){suffix}"
            entries.append(label)
            new_map[label] = sym

        self._names_to_symbols = new_map
        current = self._stock_var.get()
        self._stock_combo.configure(values=entries)

        if entries:
            current_sym = None
            for lbl, sym in self._names_to_symbols.items():
                if lbl == current:
                    current_sym = sym
                    break
            if current_sym:
                for lbl, sym in new_map.items():
                    if sym == current_sym:
                        self._stock_var.set(lbl)
                        break
            else:
                self._stock_var.set(entries[0])

    # ══════════════════════════════════════════════════════════
    #  ANALYZE
    # ══════════════════════════════════════════════════════════

    def _on_analyze(self):
        label = self._stock_var.get()
        symbol = self._names_to_symbols.get(label)
        if not symbol:
            return

        self._go_btn.configure(state="disabled")
        info = self._stock_details.get(symbol, {})
        name = info.get("name", symbol)
        self._status_var.set(f"Analyzing {name}...")

        industry = info.get("industry", "Unknown")

        # Update KPI cards with neon borders
        self._kpi_labels["industry"].configure(text=industry)
        self._kpi_cards["industry"].configure(border_color=NEON_CYAN)

        self._kpi_labels["mcap"].configure(text=fmt_inr(info.get("marketCap", 0)))
        self._kpi_cards["mcap"].configure(border_color=NEON_CYAN)

        price = info.get("currentPrice", 0)
        self._kpi_labels["price"].configure(
            text=f"\u20b9{price:,.2f}" if price else "\u2014")
        self._kpi_cards["price"].configure(border_color=NEON_CYAN)

        pe = info.get("trailingPE", 0)
        self._kpi_labels["pe"].configure(text=f"{pe:.1f}" if pe else "\u2014")
        self._kpi_cards["pe"].configure(border_color=NEON_CYAN)

        self._kpi_labels["signal"].configure(text="...", text_color=TEXT_DIM)
        self._kpi_cards["signal"].configure(border_color=BORDER)

        same_industry = [s for s, d in self._stock_details.items()
                         if d.get("industry") == industry]
        ind_size = sum(self._stock_details[s].get("marketCap", 0) for s in same_industry)
        self._kpi_labels["ind_size"].configure(text=fmt_inr(ind_size))
        self._kpi_cards["ind_size"].configure(border_color=NEON_CYAN)

        peers = [(s, self._stock_details[s].get("marketCap", 0))
                 for s in same_industry if s != symbol]
        peers.sort(key=lambda x: x[1], reverse=True)
        top_peers = [s for s, _ in peers[:5]]
        all_tickers = [symbol] + top_peers

        # Show news panel
        self._show_news_panel()
        self._populate_news([])  # clear while loading

        def work():
            revenue_data = {}
            for t in all_tickers:
                try:
                    inc = yf.Ticker(t).income_stmt
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
                                    yearly[yr] = float(val)
                            revenue_data[t] = yearly
                except Exception:
                    pass

            price_yearly = {}
            try:
                hist = yf.Ticker(symbol).history(period="3y")
                if hist is not None and not hist.empty:
                    hist.index = pd.to_datetime(hist.index)
                    for yr_group, group_df in hist.groupby(hist.index.year):
                        price_yearly[yr_group] = float(group_df["Close"].mean())
            except Exception:
                pass

            # Fetch news — use Google News RSS for Indian (.NS) stocks
            news_items = []
            try:
                stock_name = self._stock_details.get(symbol, {}).get("name", symbol.replace(".NS", ""))
                raw_articles = fetch_google_news(stock_name, count=10)
                for article in raw_articles:
                    title = article.get("title", "")
                    summary = article.get("summary", "")
                    source = article.get("source", "Unknown")
                    date_short = article.get("date", "")

                    sentiment, kw_hits = classify_sentiment(title)
                    impact = build_impact_note(sentiment, kw_hits, title)
                    news_items.append({
                        "title": title,
                        "summary": summary,
                        "source": source,
                        "date": date_short,
                        "sentiment": sentiment,
                        "impact": impact,
                    })
            except Exception:
                pass

            self.after(0, lambda: self._render_charts(
                symbol, same_industry, all_tickers,
                revenue_data, price_yearly, news_items))

        threading.Thread(target=work, daemon=True).start()

    # ══════════════════════════════════════════════════════════
    #  RENDER CHARTS (Neon Glow)
    # ══════════════════════════════════════════════════════════

    def _render_charts(self, selected, same_industry, chart_tickers,
                       revenue_data, price_yearly, news_items=None):
        for w in self._chart_frame.winfo_children():
            w.destroy()

        # Populate news panel
        if news_items is not None:
            self._populate_news(news_items)

        fig = self._get_chart_fig(figsize=(12, 9.5))
        gs = fig.add_gridspec(3, 2, height_ratios=[1.3, 0.8, 0.8],
                              hspace=0.38, wspace=0.3)

        # ── Row 1: Full-width Pie Chart ──────────────────────
        ax_pie = fig.add_subplot(gs[0, :])
        ax_pie.set_facecolor(DEEP_BG)

        labels, sizes, colors, explode_list, wedge_keys = [], [], [], [], []
        for i, t in enumerate(same_industry):
            d = self._stock_details.get(t, {})
            mcap = d.get("marketCap", 0)
            if mcap <= 0:
                continue
            short = d.get("name", t)
            if len(short) > 20:
                short = short[:18] + ".."
            labels.append(short)
            sizes.append(mcap)
            colors.append(CHART_COLORS[i % len(CHART_COLORS)])
            explode_list.append(0.06 if t == selected else 0)
            wedge_keys.append(t)

        if sizes:
            if len(sizes) > 12:
                top_labels = labels[:12]
                top_sizes = sizes[:12]
                top_colors = colors[:12]
                top_explode = explode_list[:12]
                top_keys = wedge_keys[:12]
                others_sum = sum(sizes[12:])
                top_labels.append("Others")
                top_sizes.append(others_sum)
                top_colors.append(TEXT_MUTED)
                top_explode.append(0)
                top_keys.append(None)
                labels, sizes, colors, explode_list = top_labels, top_sizes, top_colors, top_explode
                wedge_keys = top_keys

            wedges, texts, autotexts = ax_pie.pie(
                sizes, labels=labels, colors=colors, explode=explode_list,
                autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
                startangle=140, pctdistance=0.82, labeldistance=1.10,
                textprops={"fontsize": 9, "color": TEXT_BRIGHT},
                wedgeprops={"edgecolor": DEEP_BG, "linewidth": 2})
            for at in autotexts:
                at.set_fontsize(8)
                at.set_color(DEEP_BG)
                at.set_fontweight("bold")
            self._pie_wedges = list(wedges)
            self._pie_wedge_keys = wedge_keys
            self._pie_level = 2
        else:
            self._pie_wedges = []
            self._pie_wedge_keys = []

        industry = self._industry_var.get()
        ax_pie.set_title(f"Market Share \u2014 {industry} (NSE)",
                         fontsize=13, color=NEON_CYAN, pad=14,
                         fontfamily="Consolas", fontweight="bold")

        # ── Row 2-Left: Revenue vs Peers (Neon Glow) ──────────
        ax_rev = fig.add_subplot(gs[1, :])
        self._style_axis(ax_rev)

        if revenue_data:
            all_years = set()
            for yearly in revenue_data.values():
                all_years.update(yearly.keys())
            all_years = sorted(all_years)
            if len(all_years) > 3:
                all_years = all_years[-3:]

            for i, t in enumerate(chart_tickers):
                if t not in revenue_data:
                    continue
                yearly = revenue_data[t]
                years_present = [y for y in all_years if y in yearly]
                values = [yearly[y] / 1e7 for y in years_present]
                x_labels = [f"FY{str(y)[-2:]}" for y in years_present]
                color = CHART_COLORS[i % len(CHART_COLORS)]
                name = self._stock_details.get(t, {}).get("name", t)
                if len(name) > 16:
                    name = name[:14] + ".."
                lw = 2.5 if t == selected else 1.5
                marker = "o" if t == selected else "s"
                ax_rev.plot(x_labels, values, color=color, label=name,
                            linewidth=lw, marker=marker, markersize=5)

            self._neon_glow(ax_rev)
            ax_rev.legend(fontsize=7, facecolor=CARD_BG, edgecolor=BORDER,
                          labelcolor=TEXT_BRIGHT, loc="upper left")
            ax_rev.set_ylabel("Revenue (\u20b9 Cr)", fontsize=9, color=TEXT_DIM)
        else:
            ax_rev.text(0.5, 0.5, "No revenue data available",
                        ha="center", va="center", fontsize=10, color=TEXT_MUTED,
                        transform=ax_rev.transAxes)

        ax_rev.set_title("Revenue \u2014 Selected vs Top Peers",
                         fontsize=11, color=NEON_CYAN, pad=10,
                         fontfamily="Consolas", fontweight="bold")

        # ── Row 3: Value Divergence (Neon Glow) ───────────────
        ax_div = fig.add_subplot(gs[2, :])
        self._style_axis(ax_div)

        sel_revenue = revenue_data.get(selected, {})
        common_years = sorted(set(sel_revenue.keys()) & set(price_yearly.keys()))

        if len(common_years) >= 2:
            rev_vals = [sel_revenue[y] for y in common_years]
            price_vals = [price_yearly[y] for y in common_years]

            rev_base = rev_vals[0] if rev_vals[0] != 0 else 1
            price_base = price_vals[0] if price_vals[0] != 0 else 1
            rev_idx = [v / rev_base * 100 for v in rev_vals]
            price_idx = [v / price_base * 100 for v in price_vals]
            x_labels = [f"FY{str(y)[-2:]}" for y in common_years]
            x_pos = list(range(len(common_years)))

            ax_div.plot(x_pos, rev_idx, color=NEON_CYAN, linewidth=2.5,
                        marker="o", markersize=7, label="Revenue Index", zorder=3)
            ax_div.plot(x_pos, price_idx, color=NEON_GREEN, linewidth=2.5,
                        marker="D", markersize=7, label="Avg Price Index", zorder=3)

            self._neon_glow(ax_div)

            rev_arr = np.array(rev_idx)
            price_arr = np.array(price_idx)
            x_arr = np.array(x_pos)
            ax_div.fill_between(x_arr, rev_arr, price_arr,
                                where=rev_arr >= price_arr,
                                alpha=0.15, color=NEON_GREEN,
                                label="Undervalued zone", interpolate=True)
            ax_div.fill_between(x_arr, rev_arr, price_arr,
                                where=price_arr > rev_arr,
                                alpha=0.15, color=NEON_RED,
                                label="Overvalued zone", interpolate=True)

            ax_div.axhline(100, color=TEXT_MUTED, linewidth=0.8, linestyle="--", alpha=0.5)
            ax_div.set_xticks(x_pos)
            ax_div.set_xticklabels(x_labels)
            ax_div.legend(fontsize=8, facecolor=CARD_BG, edgecolor=BORDER,
                          labelcolor=TEXT_BRIGHT, loc="upper left")
            ax_div.set_ylabel("Indexed (Base = 100)", fontsize=9, color=TEXT_DIM)

            # Value Signal KPI
            rev_change = (rev_vals[-1] - rev_vals[-2]) / rev_vals[-2] * 100 if rev_vals[-2] != 0 else 0
            price_change = (price_vals[-1] - price_vals[-2]) / price_vals[-2] * 100 if price_vals[-2] != 0 else 0
            gap = rev_change - price_change

            if gap > 10:
                signal_text = "\u25B2 Undervalued"
                signal_color = NEON_GREEN
            elif gap < -10:
                signal_text = "\u25BC Overvalued"
                signal_color = NEON_RED
            else:
                signal_text = "\u25C6 Fair Value"
                signal_color = NEON_AMBER

            note = f"Rev {rev_change:+.1f}%  vs  Price {price_change:+.1f}%"
            ax_div.annotate(note,
                            xy=(x_pos[-1], max(rev_idx[-1], price_idx[-1]) + 2),
                            fontsize=8, color=TEXT_BRIGHT, ha="right",
                            bbox=dict(boxstyle="round,pad=0.3",
                                      facecolor=CARD_BG, edgecolor=BORDER, alpha=0.9))

            self._kpi_labels["signal"].configure(text=signal_text, text_color=signal_color)
            self._kpi_cards["signal"].configure(border_color=signal_color)

        elif len(common_years) == 1:
            ax_div.text(0.5, 0.5,
                        "Only 1 year of overlapping data \u2014 need at least 2 to compare trends",
                        ha="center", va="center", fontsize=10, color=TEXT_MUTED,
                        transform=ax_div.transAxes)
            self._kpi_labels["signal"].configure(text="\u2014", text_color=TEXT_DIM)
        else:
            ax_div.text(0.5, 0.5,
                        "No overlapping revenue & price data available",
                        ha="center", va="center", fontsize=10, color=TEXT_MUTED,
                        transform=ax_div.transAxes)
            self._kpi_labels["signal"].configure(text="\u2014", text_color=TEXT_DIM)

        name = self._stock_details.get(selected, {}).get("name", selected)
        ax_div.set_title(f"Value Divergence \u2014 {name}",
                         fontsize=11, color=NEON_CYAN, pad=12,
                         fontfamily="Consolas", fontweight="bold")

        fig.tight_layout(pad=2.0)
        canvas = FigureCanvasTkAgg(fig, master=self._chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        canvas.mpl_connect('button_press_event', self._on_pie_click)
        canvas.mpl_connect('motion_notify_event', self._on_pie_hover)
        self._pie_canvas = canvas
        self._pie_fig = fig

        # Back button
        back_btn = tk.Button(
            self._chart_frame, text="\u2190  Back to Sector View",
            font=("Segoe UI", 9), fg=NEON_CYAN, bg=CARD_BG,
            activebackground=BORDER, activeforeground=NEON_CYAN,
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._on_back_to_sector)
        back_btn.place(relx=0.0, rely=0.0, x=8, y=8)

        self._go_btn.configure(state="normal")
        n_peers = len(chart_tickers) - 1
        self._status_var.set(f"{name} \u2014 {n_peers} peer(s) charted")


if __name__ == "__main__":
    app = StockPicker()
    app.mainloop()
