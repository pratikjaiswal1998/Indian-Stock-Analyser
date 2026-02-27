/* ── Theme Toggle ─────────────────────────────── */
const Theme = (() => {
    let isDark = true;

    function init() {
        const saved = localStorage.getItem('theme');
        if (saved === 'light') {
            isDark = false;
            document.body.classList.replace('dark', 'light');
            document.getElementById('theme-icon').textContent = '\u2600\uFE0F';
            document.getElementById('theme-switch').checked = true;
        }

        document.getElementById('theme-switch').addEventListener('change', toggle);
    }

    function toggle() {
        isDark = !isDark;
        document.body.classList.replace(isDark ? 'light' : 'dark', isDark ? 'dark' : 'light');
        document.getElementById('theme-icon').textContent = isDark ? '\uD83C\uDF19' : '\u2600\uFE0F';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');

        // Re-render charts with new theme
        if (typeof Charts !== 'undefined' && Charts.reRenderAll) {
            Charts.reRenderAll();
        }
    }

    function dark() { return isDark; }

    function plotlyLayout() {
        return {
            paper_bgcolor: isDark ? '#0a0e1a' : '#f0f2f5',
            plot_bgcolor: isDark ? '#111827' : '#ffffff',
            font: { color: isDark ? '#e2e8f0' : '#1a1a2e', family: 'Consolas, monospace' },
            gridcolor: isDark ? 'rgba(71,85,105,0.3)' : 'rgba(200,205,213,0.5)',
        };
    }

    return { init, toggle, dark, plotlyLayout };
})();
