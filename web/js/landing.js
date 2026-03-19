/* ── Landing Page — Live Market Dashboard ────── */
const Landing = (() => {

    function fmtInr(value) {
        if (value == null || value === 0) return '\u2014';
        const abs = Math.abs(value);
        const cr = abs / 1e7;
        let result;
        if (cr >= 1e5) result = '\u20b9' + (cr / 1e5).toFixed(2) + ' L Cr';
        else if (cr >= 1) result = '\u20b9' + Math.round(cr).toLocaleString('en-IN') + ' Cr';
        else if (abs >= 1e5) result = '\u20b9' + (abs / 1e5).toFixed(2) + ' Lakh';
        else result = '\u20b9' + Math.round(abs).toLocaleString('en-IN');
        return value < 0 ? '-' + result : result;
    }

    function escHtml(str) {
        return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    async function init() {
        Theme.init();
        try {
            const resp = await fetch('/api/market-overview');
            if (!resp.ok) throw new Error('API ' + resp.status);
            const data = await resp.json();
            renderStats(data);
            renderHeatmap(data.sectors || []);
            renderMovers(data.topGainers || [], data.topLosers || []);
        } catch (e) {
            console.warn('Market overview failed:', e);
            // Remove skeletons, show fallback
            document.querySelectorAll('.lp-skeleton').forEach(el => {
                el.classList.remove('lp-skeleton');
                el.textContent = '\u2014';
            });
        }
    }

    function renderStats(data) {
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) {
                el.textContent = val;
                el.classList.remove('lp-skeleton');
            }
        };
        setVal('lp-stat-mcap', fmtInr(data.totalMarketCap));
        setVal('lp-stat-stocks', (data.totalStocks || 0).toLocaleString('en-IN'));
        setVal('lp-stat-pe', data.avgPE ? data.avgPE.toFixed(1) : '\u2014');
        setVal('lp-stat-sectors', (data.sectors || []).length + '');
    }

    function renderHeatmap(sectors) {
        const container = document.getElementById('lp-heatmap-grid');
        if (!container || sectors.length === 0) return;

        const maxMcap = Math.max(...sectors.map(s => s.totalMarketCap || 0));

        for (const sector of sectors) {
            const cell = document.createElement('a');
            cell.href = 'app.html?sector=' + encodeURIComponent(sector.name);
            cell.className = 'lp-heatmap-cell';

            // Estimate sector direction from top stocks' price change
            let avgChange = 0;
            const tops = sector.topStocks || [];
            if (tops.length > 0) {
                const changes = tops.map(s => s.priceChangePercent || 0);
                avgChange = changes.reduce((a, b) => a + b, 0) / changes.length;
            }

            // Color intensity based on change magnitude
            const intensity = Math.min(Math.abs(avgChange) / 3, 1); // cap at 3%
            if (avgChange > 0) {
                cell.style.borderColor = 'rgba(0, 255, 136, ' + (0.2 + intensity * 0.6) + ')';
                cell.style.background = 'rgba(0, 255, 136, ' + (0.03 + intensity * 0.08) + ')';
            } else if (avgChange < 0) {
                cell.style.borderColor = 'rgba(255, 51, 102, ' + (0.2 + intensity * 0.6) + ')';
                cell.style.background = 'rgba(255, 51, 102, ' + (0.03 + intensity * 0.08) + ')';
            }

            // Size weight for grid
            const weight = maxMcap > 0 ? (sector.totalMarketCap || 0) / maxMcap : 0.5;
            cell.style.setProperty('--cell-weight', weight.toFixed(2));

            const nameEl = document.createElement('div');
            nameEl.className = 'lp-heatmap-name';
            nameEl.textContent = sector.name;
            cell.appendChild(nameEl);

            const mcapEl = document.createElement('div');
            mcapEl.className = 'lp-heatmap-mcap';
            mcapEl.textContent = fmtInr(sector.totalMarketCap);
            cell.appendChild(mcapEl);

            const metaEl = document.createElement('div');
            metaEl.className = 'lp-heatmap-meta';
            const parts = [];
            parts.push(sector.stockCount + ' stocks');
            if (sector.medianPE) parts.push('P/E ' + sector.medianPE.toFixed(1));
            metaEl.textContent = parts.join(' \u00b7 ');
            cell.appendChild(metaEl);

            if (avgChange !== 0) {
                const changeEl = document.createElement('div');
                changeEl.className = 'lp-heatmap-change ' + (avgChange > 0 ? 'lp-change-up' : 'lp-change-down');
                changeEl.textContent = (avgChange > 0 ? '+' : '') + avgChange.toFixed(2) + '%';
                cell.appendChild(changeEl);
            }

            container.appendChild(cell);
        }
    }

    function renderMovers(gainers, losers) {
        renderMoverList('lp-gainers-list', gainers.slice(0, 5), true);
        renderMoverList('lp-losers-list', losers.slice(0, 5), false);
    }

    function renderMoverList(containerId, stocks, isGainer) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';

        if (stocks.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'lp-mover-empty';
            empty.textContent = 'No data available';
            container.appendChild(empty);
            return;
        }

        for (const s of stocks) {
            const row = document.createElement('a');
            row.href = 'app.html?symbol=' + encodeURIComponent(s.symbol);
            row.className = 'lp-mover-row';

            const left = document.createElement('div');
            left.className = 'lp-mover-left';

            const name = document.createElement('div');
            name.className = 'lp-mover-name';
            name.textContent = (s.name || s.symbol).substring(0, 24);
            left.appendChild(name);

            const sector = document.createElement('div');
            sector.className = 'lp-mover-sector';
            sector.textContent = s.sector || '';
            left.appendChild(sector);

            row.appendChild(left);

            const right = document.createElement('div');
            right.className = 'lp-mover-right';

            const price = document.createElement('div');
            price.className = 'lp-mover-price';
            price.textContent = s.currentPrice ? '\u20b9' + Number(s.currentPrice).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '\u2014';
            right.appendChild(price);

            const change = document.createElement('div');
            const pct = s.priceChangePercent || 0;
            change.className = 'lp-mover-change ' + (isGainer ? 'lp-change-up' : 'lp-change-down');
            change.textContent = (pct > 0 ? '+' : '') + pct.toFixed(2) + '%';
            right.appendChild(change);

            row.appendChild(right);
            container.appendChild(row);
        }
    }

    return { init };
})();

document.addEventListener('DOMContentLoaded', Landing.init);
