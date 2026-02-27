/* ── Plotly Chart Rendering ────────────────────── */
const Charts = (() => {
    const COLORS = [
        '#00f0ff', '#00ff88', '#ffaa00', '#ff006e', '#a78bfa',
        '#38bdf8', '#fb923c', '#e879f9', '#22d3ee', '#facc15',
        '#f472b6', '#34d399',
    ];

    let lastPieData = null;
    let lastRevenueData = null;
    let lastDivergenceData = null;
    let lastCandleData = null;

    function _layout(overrides = {}) {
        const t = Theme.plotlyLayout();
        return Object.assign({
            paper_bgcolor: t.paper_bgcolor,
            plot_bgcolor: t.plot_bgcolor,
            font: t.font,
            margin: { l: 50, r: 20, t: 40, b: 40 },
            xaxis: { gridcolor: t.gridcolor, zerolinecolor: t.gridcolor },
            yaxis: { gridcolor: t.gridcolor, zerolinecolor: t.gridcolor },
            showlegend: true,
            legend: { font: { size: 10 }, bgcolor: 'rgba(0,0,0,0)' },
        }, overrides);
    }

    function _config() {
        return { responsive: true, displayModeBar: false };
    }

    // ── PIE CHART ──────────────────────────────
    function renderPie(containerId, items, title, onClick) {
        lastPieData = { containerId, items, title, onClick };
        const labels = items.map(i => i.label);
        const values = items.map(i => i.value);
        const colors = items.map((_, i) => COLORS[i % COLORS.length]);

        const trace = {
            type: 'pie',
            labels, values,
            marker: { colors, line: { color: Theme.dark() ? '#0a0e1a' : '#f0f2f5', width: 2 } },
            textinfo: 'label+percent',
            textfont: { size: 10 },
            hovertemplate: '%{label}<br>\u20b9%{value:,.0f} Cr<br>%{percent}<extra></extra>',
            hole: 0.0,
        };

        const layout = _layout({
            title: { text: title, font: { size: 13, color: '#00f0ff' } },
            margin: { l: 20, r: 20, t: 50, b: 20 },
            showlegend: false,
        });

        Plotly.newPlot(containerId, [trace], layout, _config()).then(() => {
            if (onClick) {
                document.getElementById(containerId).on('plotly_click', (data) => {
                    if (data.points && data.points[0]) {
                        const idx = data.points[0].pointNumber;
                        onClick(items[idx], idx);
                    }
                });
            }
        });
    }

    // ── REVENUE CHART ──────────────────────────
    function renderRevenue(containerId, data, period) {
        lastRevenueData = { containerId, data, period };
        const { selected, chartTickers, annualRevenue, quarterlyRevenue, stockDetails } = data;
        const useQuarterly = ['1mo', '3mo', '6mo', '1y'].includes(period);

        const maxPts = { '1mo': 2, '3mo': 3, '6mo': 4, '1y': 5, '2y': 2, '3y': 3, '4y': 4 };
        const nPts = maxPts[period] || 3;

        const traces = [];

        if (useQuarterly && quarterlyRevenue && Object.keys(quarterlyRevenue).length > 0) {
            // Gather all quarter keys
            let allKeys = new Set();
            for (const t of chartTickers) {
                if (quarterlyRevenue[t]) Object.keys(quarterlyRevenue[t]).forEach(k => allKeys.add(k));
            }
            let sortedKeys = [...allKeys].sort();
            if (sortedKeys.length > nPts) sortedKeys = sortedKeys.slice(-nPts);

            chartTickers.forEach((t, i) => {
                const qdata = quarterlyRevenue[t] || {};
                const keysPresent = sortedKeys.filter(k => qdata[k] != null);
                if (keysPresent.length === 0) return;
                const vals = keysPresent.map(k => qdata[k] / 1e7);
                const labels = keysPresent.map(k => {
                    const [yr, q] = k.split('-Q');
                    return `Q${q}'${yr.slice(-2)}`;
                });
                const name = (stockDetails[t]?.name || t).substring(0, 16);
                traces.push({
                    x: labels, y: vals, type: 'scatter', mode: 'lines+markers',
                    name, line: { color: COLORS[i % COLORS.length], width: t === selected ? 3 : 1.5 },
                    marker: { size: t === selected ? 7 : 5 },
                });
            });
        } else if (annualRevenue) {
            let allYears = new Set();
            for (const t of chartTickers) {
                if (annualRevenue[t]) Object.keys(annualRevenue[t]).forEach(y => allYears.add(y));
            }
            let sortedYears = [...allYears].sort();
            if (sortedYears.length > nPts) sortedYears = sortedYears.slice(-nPts);

            chartTickers.forEach((t, i) => {
                const yearly = annualRevenue[t] || {};
                const yrsPresent = sortedYears.filter(y => yearly[y] != null);
                if (yrsPresent.length === 0) return;
                const vals = yrsPresent.map(y => yearly[y] / 1e7);
                const labels = yrsPresent.map(y => `FY${String(y).slice(-2)}`);
                const name = (stockDetails[t]?.name || t).substring(0, 16);
                traces.push({
                    x: labels, y: vals, type: 'scatter', mode: 'lines+markers',
                    name, line: { color: COLORS[i % COLORS.length], width: t === selected ? 3 : 1.5 },
                    marker: { size: t === selected ? 7 : 5 },
                });
            });
        }

        const gran = (useQuarterly && quarterlyRevenue && Object.keys(quarterlyRevenue).length > 0) ? 'Quarterly' : 'Annual';
        const pLabel = period.toUpperCase().replace('MO', 'M');
        const layout = _layout({
            title: { text: `Revenue \u2014 Selected vs Peers (${pLabel}, ${gran})`, font: { size: 12, color: '#00f0ff' } },
            yaxis: { title: 'Revenue (\u20b9 Cr)', gridcolor: Theme.plotlyLayout().gridcolor },
            margin: { l: 60, r: 10, t: 35, b: 30 },
            legend: { font: { size: 9 }, x: 0, y: 1.15, orientation: 'h' },
        });

        if (traces.length > 0) {
            Plotly.newPlot(containerId, traces, layout, _config());
        } else {
            Plotly.newPlot(containerId, [], _layout({
                title: { text: 'No revenue data available', font: { size: 12, color: '#64748b' } },
                xaxis: { visible: false }, yaxis: { visible: false },
            }), _config());
        }
    }

    // ── DIVERGENCE CHART ───────────────────────
    function renderDivergence(containerId, data, period) {
        lastDivergenceData = { containerId, data, period };
        const { selected, annualRevenue, quarterlyRevenue, priceYearly, priceQuarterly, stockDetails } = data;
        const useQuarterly = ['1mo', '3mo', '6mo', '1y'].includes(period);
        const maxPts = { '1mo': 2, '3mo': 3, '6mo': 4, '1y': 5, '2y': 2, '3y': 3, '4y': 4 };
        const nPts = maxPts[period] || 3;

        let revVals = [], priceVals = [], xLabels = [];
        let hasData = false;

        if (useQuarterly && quarterlyRevenue?.[selected] && priceQuarterly) {
            const selQRev = quarterlyRevenue[selected];
            let commonKeys = Object.keys(selQRev).filter(k => priceQuarterly[k] != null).sort();
            if (commonKeys.length > nPts) commonKeys = commonKeys.slice(-nPts);
            if (commonKeys.length >= 2) {
                revVals = commonKeys.map(k => selQRev[k]);
                priceVals = commonKeys.map(k => priceQuarterly[k]);
                xLabels = commonKeys.map(k => { const [yr, q] = k.split('-Q'); return `Q${q}'${yr.slice(-2)}`; });
                hasData = true;
            }
        }

        if (!hasData && annualRevenue?.[selected] && priceYearly) {
            const selRev = annualRevenue[selected];
            let commonYrs = Object.keys(selRev).filter(y => priceYearly[y] != null).sort();
            if (commonYrs.length > nPts) commonYrs = commonYrs.slice(-nPts);
            if (commonYrs.length >= 2) {
                revVals = commonYrs.map(y => selRev[y]);
                priceVals = commonYrs.map(y => priceYearly[y]);
                xLabels = commonYrs.map(y => `FY${String(y).slice(-2)}`);
                hasData = true;
            }
        }

        if (!hasData) {
            Plotly.newPlot(containerId, [], _layout({
                title: { text: 'Not enough overlapping data', font: { size: 12, color: '#64748b' } },
                xaxis: { visible: false }, yaxis: { visible: false },
            }), _config());
            return { signal: null };
        }

        // Index to 100
        const revBase = revVals[0] || 1;
        const priceBase = priceVals[0] || 1;
        const revIdx = revVals.map(v => v / revBase * 100);
        const priceIdx = priceVals.map(v => v / priceBase * 100);

        const traces = [
            {
                x: xLabels, y: revIdx, type: 'scatter', mode: 'lines+markers',
                name: 'Revenue Index', line: { color: '#00f0ff', width: 2.5 },
                marker: { size: 7, symbol: 'circle' },
            },
            {
                x: xLabels, y: priceIdx, type: 'scatter', mode: 'lines+markers',
                name: 'Avg Price Index', line: { color: '#00ff88', width: 2.5 },
                marker: { size: 7, symbol: 'diamond' },
            },
        ];

        // Fill between
        traces.push({
            x: [...xLabels, ...xLabels.slice().reverse()],
            y: [...revIdx, ...priceIdx.slice().reverse()],
            type: 'scatter', fill: 'toself',
            fillcolor: 'rgba(0, 255, 136, 0.08)',
            line: { color: 'transparent' },
            showlegend: false, hoverinfo: 'skip',
        });

        const pLabel = period.toUpperCase().replace('MO', 'M');
        const name = (stockDetails[selected]?.name || selected).substring(0, 20);
        const layout = _layout({
            title: { text: `Value Divergence \u2014 ${name} (${pLabel})`, font: { size: 12, color: '#00f0ff' } },
            yaxis: { title: 'Indexed (100)', gridcolor: Theme.plotlyLayout().gridcolor },
            margin: { l: 50, r: 10, t: 35, b: 30 },
            legend: { font: { size: 9 }, x: 0, y: 1.15, orientation: 'h' },
            shapes: [{ type: 'line', y0: 100, y1: 100, x0: 0, x1: 1, xref: 'paper',
                       line: { color: '#475569', width: 1, dash: 'dash' } }],
        });

        Plotly.newPlot(containerId, traces, layout, _config());

        // Compute signal
        const n = revVals.length;
        const revChange = revVals[n-2] !== 0 ? (revVals[n-1] - revVals[n-2]) / revVals[n-2] * 100 : 0;
        const priceChange = priceVals[n-2] !== 0 ? (priceVals[n-1] - priceVals[n-2]) / priceVals[n-2] * 100 : 0;
        const gap = revChange - priceChange;

        let signal;
        if (gap > 10) signal = { text: '\u25B2 Undervalued', color: '#00ff88' };
        else if (gap < -10) signal = { text: '\u25BC Overvalued', color: '#ff3366' };
        else signal = { text: '\u25C6 Fair Value', color: '#ffaa00' };

        return { signal, revChange, priceChange };
    }

    // ── CANDLESTICK CHART ──────────────────────
    function renderCandlestick(containerId, data, period) {
        lastCandleData = { containerId, data, period };
        const { ohlc, symbol, stockDetails } = data;

        if (!ohlc || ohlc.length === 0) {
            Plotly.newPlot(containerId, [], _layout({
                title: { text: 'No price history available', font: { size: 12, color: '#64748b' } },
                xaxis: { visible: false }, yaxis: { visible: false },
            }), _config());
            return;
        }

        // Filter by period
        const periodDays = { '1mo': 30, '3mo': 90, '6mo': 180, '1y': 365, '2y': 730, '3y': 1095, '4y': 1460 };
        const days = periodDays[period] || 365;
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - days);
        const cutoff = cutoffDate.toISOString().split('T')[0];

        let filtered = ohlc.filter(d => d.date >= cutoff);
        if (filtered.length === 0) filtered = ohlc;

        // Weekly resample for >1Y
        if (days > 365) {
            filtered = _weeklyResample(filtered);
        }

        const trace = {
            type: 'candlestick',
            x: filtered.map(d => d.date),
            open: filtered.map(d => d.open),
            high: filtered.map(d => d.high),
            low: filtered.map(d => d.low),
            close: filtered.map(d => d.close),
            increasing: { line: { color: Theme.dark() ? '#00ff88' : '#16a34a' } },
            decreasing: { line: { color: Theme.dark() ? '#ff3366' : '#dc2626' } },
        };

        const name = (stockDetails[symbol]?.name || symbol).substring(0, 20);
        const pLabel = period.toUpperCase().replace('MO', 'M');
        const layout = _layout({
            title: { text: `Price Action \u2014 ${name} (${pLabel})`, font: { size: 12, color: '#00f0ff' } },
            xaxis: { rangeslider: { visible: false }, gridcolor: Theme.plotlyLayout().gridcolor },
            yaxis: { title: 'Price (\u20b9)', gridcolor: Theme.plotlyLayout().gridcolor },
            margin: { l: 55, r: 10, t: 35, b: 30 },
            showlegend: false,
        });

        Plotly.newPlot(containerId, [trace], layout, _config());
    }

    function _weeklyResample(data) {
        if (data.length === 0) return data;
        const weeks = {};
        for (const d of data) {
            const dt = new Date(d.date);
            const weekStart = new Date(dt);
            weekStart.setDate(dt.getDate() - dt.getDay());
            const key = weekStart.toISOString().split('T')[0];
            if (!weeks[key]) {
                weeks[key] = { date: key, open: d.open, high: d.high, low: d.low, close: d.close };
            } else {
                weeks[key].high = Math.max(weeks[key].high, d.high);
                weeks[key].low = Math.min(weeks[key].low, d.low);
                weeks[key].close = d.close;
            }
        }
        return Object.values(weeks).sort((a, b) => a.date.localeCompare(b.date));
    }

    // ── RE-RENDER ALL (on theme change) ────────
    function reRenderAll() {
        if (lastPieData) renderPie(lastPieData.containerId, lastPieData.items, lastPieData.title, lastPieData.onClick);
        if (lastRevenueData) renderRevenue(lastRevenueData.containerId, lastRevenueData.data, lastRevenueData.period);
        if (lastDivergenceData) renderDivergence(lastDivergenceData.containerId, lastDivergenceData.data, lastDivergenceData.period);
        if (lastCandleData) renderCandlestick(lastCandleData.containerId, lastCandleData.data, lastCandleData.period);
    }

    return { renderPie, renderRevenue, renderDivergence, renderCandlestick, reRenderAll, COLORS };
})();
