/* ── Main App Logic ───────────────────────────── */
const App = (() => {
    // Same domain on Vercel — use empty string for relative paths
    const API_BASE = '';

    // State
    let industries = {};
    let stockList = [];       // full stock objects from screener
    let stockDetails = {};    // keyed by symbol
    let currentSymbol = null;
    let analyzeData = null;   // last fetched analyze response
    let currentPeriod = '1y';
    let pieLevel = 0;         // 0=none, 1=sector, 2=industry

    const SORT_EXPLANATIONS = {
        divergence: "Value Divergence compares a stock's revenue growth to its price growth. Higher score = more undervalued (revenue grew faster than price).",
        mcap: "Market Capitalization is the total market value of a company. Larger = more established.",
        pe: "P/E Ratio measures how much you pay per rupee of earnings. Lower = potentially cheaper.",
        pb: "P/B Ratio compares stock price to book value. Below 1.0 could signal undervaluation.",
        dividend: "Dividend Yield is annual dividend as % of stock price. Higher = more cash income.",
        ev: "EV/EBITDA measures total company value relative to operating earnings. Lower = potentially cheaper.",
    };

    // ── INIT ────────────────────────────────────
    async function init() {
        Theme.init();
        await Sentiment.init();

        // Load industries
        setStatus('Loading industries...');
        try {
            const resp = await apiFetch('/api/industries');
            industries = resp.sectors || {};
            populateSectors();
            setStatus('Ready');
        } catch (e) {
            setStatus('Failed to load industries: ' + e.message);
        }

        // Event listeners
        document.getElementById('sector-select').addEventListener('change', onSectorChange);
        document.getElementById('industry-select').addEventListener('change', () => {});
        document.getElementById('load-btn').addEventListener('click', onLoadStocks);
        document.getElementById('sort-select').addEventListener('change', onSortChange);
        document.getElementById('sort-info-btn').addEventListener('click', showSortInfo);
        document.getElementById('back-btn').addEventListener('click', onBackToSector);
        document.getElementById('news-close').addEventListener('click', () => {
            document.getElementById('news-panel').style.display = 'none';
        });
        document.getElementById('sort-modal-close').addEventListener('click', () => {
            document.getElementById('sort-modal').style.display = 'none';
        });
        document.getElementById('news-modal-close').addEventListener('click', () => {
            document.getElementById('news-modal').style.display = 'none';
        });

        // Timeline buttons
        document.querySelectorAll('.tl-btn').forEach(btn => {
            btn.addEventListener('click', () => onPeriodChange(btn.dataset.period));
        });

        // Close modals on background click
        ['sort-modal', 'news-modal'].forEach(id => {
            document.getElementById(id).addEventListener('click', (e) => {
                if (e.target.classList.contains('modal')) e.target.style.display = 'none';
            });
        });
    }

    // ── API HELPER ──────────────────────────────
    async function apiFetch(path) {
        const resp = await fetch(API_BASE + path);
        if (!resp.ok) throw new Error(`API error ${resp.status}`);
        return resp.json();
    }

    // ── POPULATE DROPDOWNS ──────────────────────
    function populateSectors() {
        const sel = document.getElementById('sector-select');
        sel.innerHTML = '<option value="">Select a sector</option>';
        for (const sector of Object.keys(industries).sort()) {
            sel.innerHTML += `<option value="${sector}">${sector}</option>`;
        }
    }

    function populateIndustries(sector) {
        const sel = document.getElementById('industry-select');
        const list = industries[sector] || [];
        sel.innerHTML = '<option value="">Select industry</option>';
        for (const ind of list) {
            sel.innerHTML += `<option value="${ind}">${ind}</option>`;
        }
    }

    // ── SECTOR CHANGE → PIE LEVEL 1 ────────────
    async function onSectorChange() {
        const sector = document.getElementById('sector-select').value;
        if (!sector) return;

        populateIndustries(sector);
        document.getElementById('stock-list').innerHTML = '';
        stockList = [];
        stockDetails = {};

        showLoading('Loading sector data...');
        try {
            const resp = await apiFetch(`/api/screen?type=sector&value=${encodeURIComponent(sector)}`);
            const stocks = resp.stocks || [];

            // Group by industry for pie
            const indMap = {};
            for (const s of stocks) {
                const ind = s.industry || 'Other';
                indMap[ind] = (indMap[ind] || 0) + (s.marketCap || 0);
            }

            const items = Object.entries(indMap)
                .map(([label, value]) => ({ label, value: value / 1e7 }))
                .filter(i => i.value > 0)
                .sort((a, b) => b.value - a.value);

            document.getElementById('chart-area').classList.add('pie-only');
            document.getElementById('back-btn').style.display = 'none';
            pieLevel = 1;

            Charts.renderPie('chart-pie', items, `Market Share \u2014 ${sector}`, (item) => {
                // Click pie slice → select that industry
                document.getElementById('industry-select').value = item.label;
                onLoadStocks();
            });

            hideLoading();
            setStatus(`${sector} \u2014 ${stocks.length} stocks across ${Object.keys(indMap).length} industries`);
        } catch (e) {
            hideLoading();
            setStatus('Error: ' + e.message);
        }
    }

    // ── LOAD STOCKS ─────────────────────────────
    async function onLoadStocks() {
        const industry = document.getElementById('industry-select').value;
        if (!industry) {
            setStatus('Select an industry first');
            return;
        }

        showLoading('Screening stocks...');
        try {
            const resp = await apiFetch(`/api/screen?type=industry&value=${encodeURIComponent(industry)}`);
            stockList = resp.stocks || [];

            // Build details map
            stockDetails = {};
            for (const s of stockList) {
                stockDetails[s.symbol] = {
                    name: s.name,
                    industry: s.industry,
                    marketCap: s.marketCap,
                    currentPrice: s.currentPrice,
                    trailingPE: s.trailingPE,
                    priceToBook: s.priceToBook,
                    dividendYield: s.dividendYield,
                    evToEbitda: s.evToEbitda,
                };
            }

            applySortAndRender();

            // Pie level 2 — industry stocks by mcap
            const pieItems = stockList
                .filter(s => s.marketCap > 0)
                .map(s => ({ label: (s.name || s.symbol).substring(0, 18), value: s.marketCap / 1e7, symbol: s.symbol }))
                .sort((a, b) => b.value - a.value)
                .slice(0, 15);

            document.getElementById('chart-area').classList.add('pie-only');
            pieLevel = 2;

            Charts.renderPie('chart-pie', pieItems, `Market Share \u2014 ${industry}`, (item) => {
                if (item.symbol) analyzeStock(item.symbol);
            });

            hideLoading();
            setStatus(`${industry} \u2014 ${stockList.length} stocks loaded`);
        } catch (e) {
            hideLoading();
            setStatus('Error: ' + e.message);
        }
    }

    // ── SORT ────────────────────────────────────
    function applySortAndRender() {
        const sortKey = document.getElementById('sort-select').value;
        const sorted = [...stockList];

        sorted.sort((a, b) => {
            switch (sortKey) {
                case 'mcap': return (b.marketCap || 0) - (a.marketCap || 0);
                case 'pe': return (a.trailingPE || 9999) - (b.trailingPE || 9999);
                case 'pb': return (a.priceToBook || 9999) - (b.priceToBook || 9999);
                case 'dividend': return (b.dividendYield || 0) - (a.dividendYield || 0);
                case 'ev': return (a.evToEbitda || 9999) - (b.evToEbitda || 9999);
                default: return (b.marketCap || 0) - (a.marketCap || 0);
            }
        });

        renderStockList(sorted);
    }

    function onSortChange() { applySortAndRender(); }

    function renderStockList(stocks) {
        const container = document.getElementById('stock-list');
        container.innerHTML = '';

        for (const s of stocks) {
            const div = document.createElement('div');
            div.className = 'stock-item' + (s.symbol === currentSymbol ? ' selected' : '');
            const mcapStr = fmtInr(s.marketCap);
            div.innerHTML = `<span class="name">${s.name || s.symbol}</span><span class="mcap">${mcapStr}</span>`;
            div.addEventListener('click', () => analyzeStock(s.symbol));
            container.appendChild(div);
        }
    }

    // ── ANALYZE STOCK ───────────────────────────
    async function analyzeStock(symbol) {
        currentSymbol = symbol;

        // Highlight in list
        document.querySelectorAll('.stock-item').forEach(el => el.classList.remove('selected'));
        document.querySelectorAll('.stock-item').forEach(el => {
            if (el.querySelector('.name').textContent === (stockDetails[symbol]?.name || symbol)) {
                el.classList.add('selected');
            }
        });

        const info = stockDetails[symbol] || {};
        setKPI('industry', info.industry || '\u2014');
        setKPI('mcap', fmtInr(info.marketCap));
        setKPI('price', info.currentPrice ? `\u20b9${Number(info.currentPrice).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '\u2014');
        setKPI('pe', info.trailingPE ? info.trailingPE.toFixed(1) : '\u2014');
        setKPI('signal', '...');

        // Industry size
        const sameInd = stockList.filter(s => s.industry === info.industry);
        const indSize = sameInd.reduce((sum, s) => sum + (s.marketCap || 0), 0);
        setKPI('ind-size', fmtInr(indSize));

        // Peers
        const peers = sameInd
            .filter(s => s.symbol !== symbol)
            .sort((a, b) => (b.marketCap || 0) - (a.marketCap || 0))
            .slice(0, 5)
            .map(s => s.symbol);

        showLoading('Analyzing...');

        try {
            // Fetch analyze + news in parallel
            const [dataResp, newsResp] = await Promise.all([
                apiFetch(`/api/analyze?symbol=${encodeURIComponent(symbol)}&peers=${encodeURIComponent(peers.join(','))}`),
                apiFetch(`/api/news?stock=${encodeURIComponent((info.name || symbol).replace('.NS', ''))}`),
            ]);

            analyzeData = dataResp;
            analyzeData.stockDetails = stockDetails;

            // Switch to full chart layout
            document.getElementById('chart-area').classList.remove('pie-only');
            document.getElementById('back-btn').style.display = 'block';

            const allTickers = [symbol, ...peers];
            currentPeriod = '1y';
            updateTimelineButtons();

            // Render all charts
            renderAllCharts(symbol, allTickers);

            // Render pie (industry)
            const industry = info.industry;
            const pieStocks = sameInd
                .filter(s => s.marketCap > 0)
                .map(s => ({ label: (s.name || s.symbol).substring(0, 18), value: s.marketCap / 1e7, symbol: s.symbol }))
                .sort((a, b) => b.value - a.value)
                .slice(0, 15);
            Charts.renderPie('chart-pie', pieStocks, `Market Share \u2014 ${industry}`, (item) => {
                if (item.symbol) analyzeStock(item.symbol);
            });

            // News panel
            showNews(newsResp.articles || [], dataResp.financials || {});

            hideLoading();
            setStatus(`${info.name || symbol} \u2014 ${peers.length} peer(s) charted`);
        } catch (e) {
            hideLoading();
            setStatus('Error analyzing: ' + e.message);
        }
    }

    function renderAllCharts(symbol, allTickers) {
        const d = analyzeData;

        Charts.renderRevenue('chart-revenue', {
            selected: symbol,
            chartTickers: allTickers,
            annualRevenue: d.annual_revenue,
            quarterlyRevenue: d.quarterly_revenue,
            stockDetails,
        }, currentPeriod);

        const divResult = Charts.renderDivergence('chart-divergence', {
            selected: symbol,
            annualRevenue: d.annual_revenue,
            quarterlyRevenue: d.quarterly_revenue,
            priceYearly: d.price_yearly,
            priceQuarterly: d.price_quarterly,
            stockDetails,
        }, currentPeriod);

        if (divResult?.signal) {
            setKPI('signal', divResult.signal.text);
            document.querySelector('#kpi-signal .kpi-value').style.color = divResult.signal.color;
        }

        Charts.renderCandlestick('chart-candle', {
            ohlc: d.ohlc,
            symbol,
            stockDetails,
        }, currentPeriod);
    }

    // ── TIMELINE ────────────────────────────────
    function onPeriodChange(period) {
        currentPeriod = period;
        updateTimelineButtons();

        if (analyzeData && currentSymbol) {
            const info = stockDetails[currentSymbol] || {};
            const sameInd = stockList.filter(s => s.industry === info.industry);
            const peers = sameInd
                .filter(s => s.symbol !== currentSymbol)
                .sort((a, b) => (b.marketCap || 0) - (a.marketCap || 0))
                .slice(0, 5)
                .map(s => s.symbol);
            renderAllCharts(currentSymbol, [currentSymbol, ...peers]);
        }
    }

    function updateTimelineButtons() {
        document.querySelectorAll('.tl-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.period === currentPeriod);
        });
    }

    // ── NEWS ────────────────────────────────────
    function showNews(articles, financials) {
        const panel = document.getElementById('news-panel');
        const list = document.getElementById('news-list');
        panel.style.display = 'flex';
        list.innerHTML = '';

        if (articles.length === 0) {
            list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px;">No recent news found</div>';
            return;
        }

        for (const article of articles) {
            const { sentiment, keywords } = Sentiment.classify(article.title);
            const impact = Sentiment.buildImpact(sentiment, keywords, article.title, financials);

            const div = document.createElement('div');
            div.className = 'news-item';
            div.innerHTML = `
                <div class="news-title">${escHtml(article.title)}</div>
                <div class="news-meta">
                    <span class="sentiment-badge ${sentiment}">${sentiment}</span>
                    <span>${escHtml(article.source)} &middot; ${escHtml(article.date)}</span>
                </div>
            `;
            div.addEventListener('click', () => showNewsPopup(article.title, sentiment, impact));
            list.appendChild(div);
        }
    }

    function showNewsPopup(title, sentiment, impact) {
        document.getElementById('news-modal-badge').className = `sentiment-badge ${sentiment}`;
        document.getElementById('news-modal-badge').textContent = sentiment;
        document.getElementById('news-modal-title').textContent = title;
        document.getElementById('news-modal-impact').textContent = impact;
        document.getElementById('news-modal').style.display = 'flex';
    }

    // ── BACK BUTTON ─────────────────────────────
    function onBackToSector() {
        document.getElementById('chart-area').classList.add('pie-only');
        document.getElementById('back-btn').style.display = 'none';
        document.getElementById('news-panel').style.display = 'none';
        analyzeData = null;
        currentSymbol = null;

        // Re-render industry pie
        const industry = document.getElementById('industry-select').value;
        if (industry && stockList.length > 0) {
            const pieItems = stockList
                .filter(s => s.marketCap > 0)
                .map(s => ({ label: (s.name || s.symbol).substring(0, 18), value: s.marketCap / 1e7, symbol: s.symbol }))
                .sort((a, b) => b.value - a.value)
                .slice(0, 15);
            Charts.renderPie('chart-pie', pieItems, `Market Share \u2014 ${industry}`, (item) => {
                if (item.symbol) analyzeStock(item.symbol);
            });
        }

        // Reset KPIs
        ['industry', 'ind-size', 'mcap', 'price', 'pe', 'signal'].forEach(k => setKPI(k, '\u2014'));
    }

    // ── SORT INFO MODAL ─────────────────────────
    function showSortInfo() {
        const key = document.getElementById('sort-select').value;
        document.getElementById('sort-modal-title').textContent = document.getElementById('sort-select').selectedOptions[0].textContent;
        document.getElementById('sort-modal-body').textContent = SORT_EXPLANATIONS[key] || '';
        document.getElementById('sort-modal').style.display = 'flex';
    }

    // ── HELPERS ─────────────────────────────────
    function setKPI(id, value) {
        const el = document.querySelector(`#kpi-${id} .kpi-value`);
        if (el) {
            el.textContent = value;
            el.style.color = '';
        }
        const card = document.getElementById(`kpi-${id}`);
        if (card && value !== '\u2014') card.classList.add('active');
        else if (card) card.classList.remove('active');
    }

    function fmtInr(value) {
        if (!value || value === 0) return '\u2014';
        const cr = value / 1e7;
        if (cr >= 1e5) return `\u20b9${(cr / 1e5).toFixed(2)} L Cr`;
        if (cr >= 1) return `\u20b9${Math.round(cr).toLocaleString('en-IN')} Cr`;
        return `\u20b9${Math.round(value).toLocaleString('en-IN')}`;
    }

    function escHtml(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }

    function setStatus(msg) {
        document.getElementById('status-bar').textContent = msg;
    }

    function showLoading(msg) {
        document.getElementById('loading-text').textContent = msg || 'Loading...';
        document.getElementById('loading-overlay').style.display = 'flex';
    }

    function hideLoading() {
        document.getElementById('loading-overlay').style.display = 'none';
    }

    return { init };
})();

// Boot
document.addEventListener('DOMContentLoaded', App.init);
