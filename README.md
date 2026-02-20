# Indian Stock Analyser

A desktop NSE stock screener with value-based analysis, interactive charts, and real-time news intelligence. Built with Python, customtkinter, and matplotlib.

## Features

### Sector & Industry Screener
- Browse all NSE sectors and industries via cascading dropdowns
- Powered by yfinance's `EquityQuery` screener API
- Weekly industry cache for faster startup (auto-refreshes every 7 days)

### Interactive Drilldown Pie Charts
- **Level 1**: Sector overview showing all industries by market cap — click any slice to drill down
- **Level 2**: Industry breakdown showing individual stocks by market cap — click any stock to analyze
- Full-width pie charts with neon glow effects and hover cursors

### Stock Analysis Dashboard
- **Market Share Pie** — selected stock highlighted (exploded slice) among industry peers
- **Revenue vs Peers** — line chart comparing revenue trends against top 5 peers (last 3 fiscal years)
- **Value Divergence** — proprietary scoring that indexes revenue growth vs price growth to base 100, with undervalued/overvalued zone shading

### Value Divergence Scoring
Compares a stock's revenue trajectory against its price trajectory over 2-3 years. If revenue grew 40% but price only grew 10%, the divergence score is positive — signaling potential undervaluation. Computed in background threads for all loaded stocks.

### 6 Sort Modes
Each sort mode shows inline metric values in the stock dropdown:
- Value Divergence (default)
- Market Cap
- P/E Ratio (low first)
- P/B Ratio (low first)
- Dividend Yield (high first)
- EV/EBITDA (low first)

Each mode includes a detailed explanation panel describing what the metric means, how it works, and when to use it.

### News Intelligence Panel
- Real-time news via Google News RSS (works for all NSE stocks)
- Sentiment classification using multi-word phrase matching + word-boundary regex
- Negation-aware scoring (e.g., "no revenue growth" correctly flips to bearish)
- Phrases weighted 2x over single keywords to reduce false positives
- Three classifications: BULLISH (green), BEARISH (red), NEUTRAL (amber)
- Click any news card for a detail popup with impact analysis

### KPI Dashboard
Six live metric cards updated on each analysis:
- Industry name
- Industry total market cap
- Stock market cap
- Current price
- P/E ratio
- Value signal (Undervalued / Fair Value / Overvalued)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI Framework | customtkinter (dark mode) |
| Charts | matplotlib + mplcyberpunk (neon glow) |
| Data | yfinance (screener + financials + price history) |
| News | Google News RSS (no API key needed) |
| Sentiment | Regex word-boundary matching + phrase detection |
| Packaging | PyInstaller (--onedir, --collect-all customtkinter) |

## Installation

### From Source
```bash
pip install yfinance customtkinter matplotlib mplcyberpunk numpy pandas
python stock_picker.py
```

### Build Executable
```bash
pip install pyinstaller
pyinstaller --onedir --windowed --collect-all customtkinter --name StockPicker stock_picker.py
```
The exe will be in `dist/StockPicker/StockPicker.exe`.

> **Note**: customtkinter requires `--onedir` mode (not `--onefile`).

## Requirements

- Python 3.10+
- Windows (tested on Windows 11)
- Internet connection (for yfinance data and Google News)

## License

MIT License - see [LICENSE](LICENSE) for details.
