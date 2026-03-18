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
    let pieOrder = [];        // symbols in pie chart order (mcap desc)

    // AbortControllers for race condition prevention (fixes #4, #5)
    let currentAnalyzeController = null;
    let currentSectorController = null;

    // Loading counter for nested show/hide (fix #9)
    let loadingCount = 0;

    // Modal focus management (fix #21)
    let lastModalTrigger = null;

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

        // Fix #8: Sentiment.init() failure should not kill the app
        try {
            await Sentiment.init();
        } catch (e) {
            console.warn('Sentiment init failed, continuing without it:', e);
        }

        // Load industries
        setStatus('Loading industries...');
        try {
            const resp = await apiFetch('/api/industries');
            industries = resp.sectors || {};
            populateSectors();
            setStatus('Ready');
        } catch (e) {
            // Fix #11: detect network errors
            if (e instanceof TypeError) {
                setStatus('No internet connection. Please check your network.');
            } else {
                setStatus('Failed to load industries: ' + e.message);
            }
        }

        // Mobile sidebar — start open so user can pick sector
        if (window.innerWidth <= 900) {
            document.getElementById('sidebar').classList.add('open');
        }

        // Event listeners
        document.getElementById('menu-btn').addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('open');
        });
        document.getElementById('sector-select').addEventListener('change', onSectorChange);
        // Fix #14: removed empty industry change listener
        document.getElementById('load-btn').addEventListener('click', onLoadStocks);
        document.getElementById('sort-select').addEventListener('change', onSortChange);
        document.getElementById('sort-info-btn').addEventListener('click', showSortInfo);
        document.getElementById('back-btn').addEventListener('click', onBackToSector);

        // Fix #19: news panel toggle uses CSS class instead of inline display
        document.getElementById('news-close').addEventListener('click', () => {
            document.getElementById('news-panel').classList.remove('visible');
        });

        // Fix #20 + #21: modal close uses e.target === e.currentTarget + focus management
        document.getElementById('sort-modal-close').addEventListener('click', () => {
            closeModal('sort-modal');
        });
        document.getElementById('news-modal-close').addEventListener('click', () => {
            closeModal('news-modal');
        });

        // Timeline buttons
        document.querySelectorAll('.tl-btn').forEach(btn => {
            btn.addEventListener('click', () => onPeriodChange(btn.dataset.period));
        });

        // Fix #20: Close modals on background click — use e.target === e.currentTarget
        ['sort-modal', 'news-modal'].forEach(id => {
            document.getElementById(id).addEventListener('click', (e) => {
                if (e.target === e.currentTarget) closeModal(id);
            });
        });

        // Fix #13: Escape key closes modals, arrow keys navigate stocks (with select guard)
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                ['sort-modal', 'news-modal'].forEach(id => closeModal(id));
            }
            // Fix #13: guard against arrow key conflict with form elements
            if (['SELECT', 'INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
            if (e.key === 'ArrowLeft') navigateStock(-1);
            if (e.key === 'ArrowRight') navigateStock(1);
        });

        // Sidebar overlay — close drawer on tap
        document.getElementById('sidebar-overlay')?.addEventListener('click', () => {
            document.getElementById('sidebar').classList.remove('open');
        });

        // News panel bottom-sheet drag (mobile)
        if (window.innerWidth <= 900) {
            initNewsDrag();
        }

        // Swipe navigation on charts
        initChartSwipe();

        // Arrow button clicks
        document.getElementById('swipe-prev').addEventListener('click', () => navigateStock(-1));
        document.getElementById('swipe-next').addEventListener('click', () => navigateStock(1));
    }

    // ── API HELPER (fixes #6, #7) ──────────────
    const apiCache = new Map();
    async function apiFetch(path, signal, ttlMs = 300000) {
        // Fix #7: client-side cache
        const cached = apiCache.get(path);
        if (cached && Date.now() - cached.time < ttlMs) return cached.data;

        const resp = await fetch(API_BASE + path, signal ? { signal } : {});
        if (!resp.ok) throw new Error(`API error ${resp.status}`);

        // Fix #6: handle non-JSON responses
        let data;
        try {
            data = await resp.json();
        } catch {
            throw new Error('Invalid response from server');
        }

        apiCache.set(path, { data, time: Date.now() });
        return data;
    }

    // ── POPULATE DROPDOWNS (fixes #1, #12) ─────
    function populateSectors() {
        const sel = document.getElementById('sector-select');
        // Fix #1 + #12: use createElement instead of innerHTML += to avoid XSS and quadratic perf
        sel.innerHTML = '';
        const defaultOpt = document.createElement('option');
        defaultOpt.value = '';
        defaultOpt.textContent = 'Select a sector';
        sel.appendChild(defaultOpt);
        for (const sector of Object.keys(industries).sort()) {
            const opt = document.createElement('option');
            opt.value = sector;
            opt.textContent = sector;
            sel.appendChild(opt);
        }
    }

    function populateIndustries(sector) {
        const sel = document.getElementById('industry-select');
        const list = industries[sector] || [];
        // Fix #1 + #12: use createElement instead of innerHTML +=
        sel.innerHTML = '';
        const defaultOpt = document.createElement('option');
        defaultOpt.value = '';
        defaultOpt.textContent = 'Select industry';
        sel.appendChild(defaultOpt);
        for (const ind of list) {
            const opt = document.createElement('option');
            opt.value = ind;
            opt.textContent = ind;
            sel.appendChild(opt);
        }
    }

    // ── SECTOR CHANGE → PIE LEVEL 1 (fix #5) ──
    async function onSectorChange() {
        const sector = document.getElementById('sector-select').value;
        if (!sector) {
            // Fix #10: restore empty state when sector selection is cleared
            showEmptyState();
            return;
        }

        // Fix #5: abort previous sector request
        if (currentSectorController) currentSectorController.abort();
        currentSectorController = new AbortController();
        const signal = currentSectorController.signal;

        populateIndustries(sector);
        document.getElementById('stock-list').innerHTML = '';
        stockList = [];
        stockDetails = {};

        hideEmptyState();
        showLoading('Loading sector data...');
        try {
            const resp = await apiFetch(`/api/screen?type=sector&value=${encodeURIComponent(sector)}`, signal);
            if (signal.aborted) return;
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
            document.getElementById('news-panel').classList.remove('visible');
            pieLevel = 1;

            Charts.renderPie('chart-pie', items, `Market Share \u2014 ${sector}`, (item) => {
                // Click pie slice → select that industry
                // Fix #15: verify industry dropdown value matches
                const indSel = document.getElementById('industry-select');
                indSel.value = item.label;
                if (indSel.value !== item.label) {
                    setStatus(`Industry "${item.label}" not found in dropdown`);
                    return;
                }
                onLoadStocks();
            });

            setStatus(`${sector} \u2014 ${stocks.length} stocks across ${Object.keys(indMap).length} industries`);
        } catch (e) {
            if (e.name === 'AbortError') return;
            // Fix #11: detect network errors
            if (e instanceof TypeError) {
                setStatus('No internet connection. Please check your network.');
            } else {
                setStatus('Error: ' + e.message);
            }
        } finally {
            // Fix #9: hideLoading in finally block
            hideLoading();
        }
    }

    // ── LOAD STOCKS ─────────────────────────────
    async function onLoadStocks() {
        const industry = document.getElementById('industry-select').value;
        if (!industry) {
            setStatus('Select an industry first');
            return;
        }

        hideEmptyState();
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
            pieOrder = pieItems.map(i => i.symbol);

            Charts.renderPie('chart-pie', pieItems, `Market Share \u2014 ${industry}`, (item) => {
                if (item.symbol) analyzeStock(item.symbol);
            });

            // Show industry KPIs
            const totalMcap = stockList.reduce((sum, s) => sum + (s.marketCap || 0), 0);
            setKPI('industry', industry);
            setKPI('ind-size', fmtInr(totalMcap));
            setKPI('mcap', `${stockList.length} stocks`);
            setKPI('price', '\u2014');
            setKPI('pe', '\u2014');
            setKPI('signal', '\u2014');

            // Show back button to return to sector pie
            document.getElementById('back-btn').style.display = 'block';
            document.getElementById('back-btn').textContent = '\u2190 Back to Sector';

            // Fetch industry news in background
            apiFetch(`/api/news?stock=${encodeURIComponent(industry)}`)
                .then(newsResp => showNews(newsResp.articles || [], {}))
                .catch(() => {});

            setStatus(`${industry} \u2014 ${stockList.length} stocks loaded \u2014 click a stock to analyze`);
        } catch (e) {
            // Fix #11: detect network errors
            if (e instanceof TypeError) {
                setStatus('No internet connection. Please check your network.');
            } else {
                setStatus('Error: ' + e.message);
            }
        } finally {
            // Fix #9: hideLoading in finally block
            hideLoading();
        }
    }

    // ── SORT (fix #3: divergence case) ─────────
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
                // Fix #3: implement divergence sort
                case 'divergence': {
                    const divA = (a.divergenceScore != null) ? a.divergenceScore : -(a.marketCap || 0);
                    const divB = (b.divergenceScore != null) ? b.divergenceScore : -(b.marketCap || 0);
                    return divB - divA; // higher divergence = more undervalued = first
                }
                default: return (b.marketCap || 0) - (a.marketCap || 0);
            }
        });

        renderStockList(sorted);
    }

    function onSortChange() { applySortAndRender(); }

    // Fix #2: renderStockList uses createElement + textContent instead of innerHTML
    function renderStockList(stocks) {
        const container = document.getElementById('stock-list');
        container.innerHTML = '';

        for (const s of stocks) {
            const div = document.createElement('div');
            div.className = 'stock-item' + (s.symbol === currentSymbol ? ' selected' : '');
            // Fix #18: use data-symbol attribute for selection comparison
            div.dataset.symbol = s.symbol;

            const nameSpan = document.createElement('span');
            nameSpan.className = 'name';
            nameSpan.textContent = s.name || s.symbol;

            const mcapSpan = document.createElement('span');
            mcapSpan.className = 'mcap';
            mcapSpan.textContent = fmtInr(s.marketCap);

            div.appendChild(nameSpan);
            div.appendChild(mcapSpan);
            div.addEventListener('click', () => analyzeStock(s.symbol));
            container.appendChild(div);
        }
    }

    // ── ANALYZE STOCK (fix #4: AbortController) ─
    async function analyzeStock(symbol) {
        // Fix #4: abort previous analyze request
        if (currentAnalyzeController) currentAnalyzeController.abort();
        currentAnalyzeController = new AbortController();
        const signal = currentAnalyzeController.signal;

        currentSymbol = symbol;

        // Immediately close sidebar on mobile for instant feedback
        if (window.innerWidth <= 900) {
            document.getElementById('sidebar').classList.remove('open');
        }

        // Fix #18: highlight in list using data-symbol attribute
        document.querySelectorAll('.stock-item').forEach(el => {
            el.classList.toggle('selected', el.dataset.symbol === symbol);
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
            // Fetch analyze + news in parallel, passing signal
            const [dataResp, newsResp] = await Promise.all([
                apiFetch(`/api/analyze?symbol=${encodeURIComponent(symbol)}&peers=${encodeURIComponent(peers.join(','))}`, signal),
                apiFetch(`/api/news?stock=${encodeURIComponent((info.name || symbol).replace('.NS', ''))}`, signal),
            ]);

            // Fix #4: check if aborted after awaits
            if (signal.aborted) return;

            analyzeData = dataResp;
            analyzeData.stockDetails = stockDetails;

            // Switch to full chart layout
            document.getElementById('chart-area').classList.remove('pie-only');
            document.getElementById('back-btn').style.display = 'block';
            document.getElementById('back-btn').textContent = '\u2190 Back to Industry';

            const allTickers = [symbol, ...peers];
            updateTimelineButtons();

            // Render all charts
            renderAllCharts(symbol, allTickers);

            // Update swipe indicator
            updateSwipeIndicator(symbol);

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

            setStatus(`${info.name || symbol} \u2014 ${peers.length} peer(s) charted`);
        } catch (e) {
            if (e.name === 'AbortError') return;
            // Fix #11: detect network errors
            if (e instanceof TypeError) {
                setStatus('No internet connection. Please check your network.');
            } else {
                setStatus('Error analyzing: ' + e.message);
            }
        } finally {
            // Fix #9: hideLoading in finally block
            hideLoading();
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

    // ── NEWS (fix #19: use CSS class .visible) ──
    function showNews(articles, financials) {
        const panel = document.getElementById('news-panel');
        const list = document.getElementById('news-list');
        // Fix #19: use CSS class instead of inline display
        panel.classList.add('visible');
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
                    <span class="sentiment-badge ${escHtml(sentiment)}">${escHtml(sentiment)}</span>
                    <span>${escHtml(article.source)} &middot; ${escHtml(article.date)}</span>
                </div>
            `;
            div.addEventListener('click', () => showNewsPopup(article.title, sentiment, impact));
            list.appendChild(div);
        }
    }

    function showNewsPopup(title, sentiment, impact) {
        document.getElementById('news-modal-badge').className = `sentiment-badge ${escHtml(sentiment)}`;
        document.getElementById('news-modal-badge').textContent = sentiment;
        document.getElementById('news-modal-title').textContent = title;
        document.getElementById('news-modal-impact').textContent = impact;
        openModal('news-modal');
    }

    // ── BACK BUTTON (fix #16: async + await) ────
    async function onBackToSector() {
        // Hide swipe indicator
        document.getElementById('swipe-indicator').style.display = 'none';

        // If viewing a stock → go back to industry pie
        if (analyzeData && currentSymbol) {
            document.getElementById('chart-area').classList.add('pie-only');
            analyzeData = null;
            currentSymbol = null;

            // Re-render industry stocks pie
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

                // Restore industry KPIs
                const totalMcap = stockList.reduce((sum, s) => sum + (s.marketCap || 0), 0);
                setKPI('industry', industry);
                setKPI('ind-size', fmtInr(totalMcap));
                setKPI('mcap', `${stockList.length} stocks`);
                setKPI('price', '\u2014');
                setKPI('pe', '\u2014');
                setKPI('signal', '\u2014');
            }

            document.getElementById('back-btn').textContent = '\u2190 Back to Sector';
            pieLevel = 2;
            setStatus(`${industry} \u2014 click a stock to analyze`);
            return;
        }

        // If viewing industry pie → go back to sector pie
        document.getElementById('chart-area').classList.add('pie-only');
        document.getElementById('back-btn').style.display = 'none';
        document.getElementById('news-panel').classList.remove('visible');
        stockList = [];
        stockDetails = {};
        document.getElementById('stock-list').innerHTML = '';

        const sector = document.getElementById('sector-select').value;
        if (sector) {
            // Fix #16: await the async call with catch
            try {
                await onSectorChange();
            } catch (e) {
                setStatus('Error returning to sector: ' + e.message);
            }
        }

        ['industry', 'ind-size', 'mcap', 'price', 'pe', 'signal'].forEach(k => setKPI(k, '\u2014'));
    }

    // ── SORT INFO MODAL ─────────────────────────
    function showSortInfo() {
        const key = document.getElementById('sort-select').value;
        document.getElementById('sort-modal-title').textContent = document.getElementById('sort-select').selectedOptions[0].textContent;
        document.getElementById('sort-modal-body').textContent = SORT_EXPLANATIONS[key] || '';
        openModal('sort-modal');
    }

    // ── MODAL HELPERS (fix #21: focus management) ─
    function openModal(id) {
        lastModalTrigger = document.activeElement;
        const modal = document.getElementById(id);
        modal.style.display = 'flex';
        // Move focus into modal
        const focusable = modal.querySelector('button, [tabindex], a, input, select, textarea');
        if (focusable) focusable.focus();
    }

    function closeModal(id) {
        const modal = document.getElementById(id);
        if (modal.style.display === 'none' && !modal.classList.contains('visible')) return;
        modal.style.display = 'none';
        // Fix #21: restore focus to trigger element
        if (lastModalTrigger && typeof lastModalTrigger.focus === 'function') {
            lastModalTrigger.focus();
            lastModalTrigger = null;
        }
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

    // Fix #25: fmtInr handles small values (Lakh tier) and negatives
    function fmtInr(value) {
        if (value == null || value === 0) return '\u2014';
        const negative = value < 0;
        const abs = Math.abs(value);
        const cr = abs / 1e7;
        let result;
        if (cr >= 1e5) result = `\u20b9${(cr / 1e5).toFixed(2)} L Cr`;
        else if (cr >= 1) result = `\u20b9${Math.round(cr).toLocaleString('en-IN')} Cr`;
        else if (abs >= 1e5) result = `\u20b9${(abs / 1e5).toFixed(2)} Lakh`;
        else result = `\u20b9${Math.round(abs).toLocaleString('en-IN')}`;
        return negative ? '-' + result : result;
    }

    // Fix #17: string-based escHtml instead of DOM-based
    function escHtml(str) {
        return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function setStatus(msg) {
        document.getElementById('status-bar').textContent = msg;
    }

    // Fix #9: loading counter for nested show/hide
    function showLoading(msg) {
        loadingCount++;
        document.getElementById('loading-text').textContent = msg || 'Loading...';
        document.getElementById('loading-overlay').style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function hideLoading() {
        if (loadingCount > 0) loadingCount--;
        if (loadingCount === 0) {
            document.getElementById('loading-overlay').style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    function hideEmptyState() {
        const el = document.getElementById('empty-state');
        if (el) el.style.display = 'none';
    }

    // Fix #10: restore empty state on reset
    function showEmptyState() {
        const el = document.getElementById('empty-state');
        if (el) el.style.display = '';
        document.getElementById('stock-list').innerHTML = '';
        document.getElementById('chart-area').classList.add('pie-only');
    }

    // ── SWIPE NAVIGATION (fixes #22, #23, #24) ──
    function initChartSwipe() {
        // Fix #24: add swipe to both #charts-left and #charts-right
        const targets = [
            document.getElementById('charts-left'),
            document.getElementById('charts-right'),
        ].filter(Boolean);

        for (const el of targets) {
            let startX = 0;
            let startY = 0;

            el.addEventListener('touchstart', (e) => {
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
            }, { passive: true });

            el.addEventListener('touchend', (e) => {
                const dx = e.changedTouches[0].clientX - startX;
                const dy = e.changedTouches[0].clientY - startY;

                // Only trigger if horizontal swipe > 60px and more horizontal than vertical
                if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
                    navigateStock(dx < 0 ? 1 : -1);
                }
            });
        }
    }

    function navigateStock(direction) {
        if (!currentSymbol || pieOrder.length < 2) return;
        const idx = pieOrder.indexOf(currentSymbol);
        if (idx === -1) return;

        const nextIdx = idx + direction;
        if (nextIdx < 0 || nextIdx >= pieOrder.length) return;

        analyzeStock(pieOrder[nextIdx]);
    }

    function updateSwipeIndicator(symbol) {
        const indicator = document.getElementById('swipe-indicator');
        if (pieOrder.length < 2) {
            indicator.style.display = 'none';
            return;
        }

        const idx = pieOrder.indexOf(symbol);
        if (idx === -1) {
            indicator.style.display = 'none';
            return;
        }

        const name = (stockDetails[symbol]?.name || symbol).substring(0, 20);
        document.getElementById('swipe-label').textContent = `${name}  (${idx + 1}/${pieOrder.length})`;
        document.getElementById('swipe-prev').style.visibility = idx === 0 ? 'hidden' : 'visible';
        document.getElementById('swipe-next').style.visibility = idx === pieOrder.length - 1 ? 'hidden' : 'visible';
        indicator.style.display = 'flex';
    }

    // Fix #22 + #23: news drag with passive:false on touchmove, cache offsetHeight
    function initNewsDrag() {
        const panel = document.getElementById('news-panel');
        const header = panel.querySelector('.news-header');
        let startY = 0;
        let cachedPanelHeight = 0;

        header.addEventListener('touchstart', (e) => {
            startY = e.touches[0].clientY;
            // Fix #23: cache offsetHeight on touchstart
            cachedPanelHeight = panel.offsetHeight;
            panel.style.transition = 'none';
        }, { passive: true });

        // Fix #22: use {passive: false} so we can preventDefault
        header.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const dy = e.touches[0].clientY - startY;
            if (panel.classList.contains('expanded')) {
                if (dy > 0) panel.style.transform = `translateY(${dy}px)`;
            } else {
                const baseOffset = cachedPanelHeight - 120;
                const newY = Math.max(0, baseOffset + dy);
                panel.style.transform = `translateY(${newY}px)`;
            }
        }, { passive: false });

        header.addEventListener('touchend', (e) => {
            panel.style.transition = 'transform 0.3s ease';
            const dy = e.changedTouches[0].clientY - startY;
            if (Math.abs(dy) > 60) {
                panel.classList.toggle('expanded', dy < 0);
            }
            panel.style.transform = '';
            startY = 0;
        });
    }

    return { init };
})();

// Boot
document.addEventListener('DOMContentLoaded', App.init);
