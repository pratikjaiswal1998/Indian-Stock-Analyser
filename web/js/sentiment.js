/* ── Client-side Sentiment Classifier ─────────── */
/* Port of the desktop app's hybrid 3-layer system */
const Sentiment = (() => {
    let lmPos = new Set();
    let lmNeg = new Set();
    let loaded = false;

    const BULLISH_PHRASES = [
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
    ];

    const BEARISH_PHRASES = [
        "net loss", "revenue decline", "revenue miss", "profit decline",
        "profit falls", "profit drops", "profit dropped", "profit fell",
        "profit slumps", "profit plunges", "profit tumbles",
        "share price drop", "shares drop", "shares fall", "shares fell",
        "shares tumble", "shares plunge", "shares slide", "shares sink",
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
    ];

    const EXTRA_BULLISH = new Set([
        "bullish", "rally", "rallies", "rallied", "soars", "soared",
        "surges", "surged", "jumps", "jumped", "climbs", "climbed",
        "rises", "risen", "beats", "buyback", "outperform", "outperformed",
        "upgrade", "upgraded", "milestone", "recovery", "boost", "boosted",
    ]);

    const EXTRA_BEARISH = new Set([
        "bearish", "crash", "crashed", "plunge", "plunged", "plunges",
        "tumble", "tumbled", "tumbles", "slump", "slumped", "slumps",
        "plummets", "plummeted", "tanks", "tanked", "sinks", "sank",
        "slides", "slid", "falls", "fell", "fall", "drops", "dropped",
        "drop", "underperform", "underperformed",
    ]);

    const NEGATION_PREFIXES = ["no ", "not ", "without ", "lack of ", "failed to ", "unable to "];

    async function init() {
        try {
            const resp = await fetch('data/lm_dictionary.json');
            const data = await resp.json();
            lmPos = new Set(data.positive || []);
            lmNeg = new Set(data.negative || []);
            loaded = true;
        } catch (e) {
            console.warn('LM dictionary not loaded:', e);
        }
    }

    function classify(text) {
        if (!text) return { sentiment: 'neutral', keywords: [] };
        const lower = text.toLowerCase();
        let bullScore = 0, bearScore = 0;
        const bullHits = [], bearHits = [];

        // Phase 1: Phrases (weight 3)
        for (const phrase of BULLISH_PHRASES) {
            if (lower.includes(phrase)) {
                const idx = lower.indexOf(phrase);
                const before = lower.substring(Math.max(0, idx - 15), idx);
                const negated = NEGATION_PREFIXES.some(n => before.includes(n));
                if (negated) { bearScore += 3; bearHits.push('not ' + phrase); }
                else { bullScore += 3; bullHits.push(phrase); }
            }
        }
        for (const phrase of BEARISH_PHRASES) {
            if (lower.includes(phrase)) {
                const idx = lower.indexOf(phrase);
                const before = lower.substring(Math.max(0, idx - 15), idx);
                const negated = NEGATION_PREFIXES.some(n => before.includes(n));
                if (negated) { bullScore += 3; bullHits.push('no ' + phrase); }
                else { bearScore += 3; bearHits.push(phrase); }
            }
        }

        // Phase 2: LM dictionary + extras (weight 1)
        const allPos = new Set([...lmPos, ...EXTRA_BULLISH]);
        const allNeg = new Set([...lmNeg, ...EXTRA_BEARISH]);
        const words = lower.match(/[a-z]+/g) || [];
        for (const word of words) {
            if (allPos.has(word)) {
                bullScore += 1;
                if (!bullHits.includes(word) && bullHits.length < 6) bullHits.push(word);
            } else if (allNeg.has(word)) {
                bearScore += 1;
                if (!bearHits.includes(word) && bearHits.length < 6) bearHits.push(word);
            }
        }

        const diff = bullScore - bearScore;
        if (diff >= 2) return { sentiment: 'bullish', keywords: bullHits };
        if (diff <= -2) return { sentiment: 'bearish', keywords: bearHits };
        if (bullScore > 0 && bearScore === 0) return { sentiment: 'bullish', keywords: bullHits };
        if (bearScore > 0 && bullScore === 0) return { sentiment: 'bearish', keywords: bearHits };
        return { sentiment: 'neutral', keywords: [...bullHits, ...bearHits] };
    }

    function buildImpact(sentiment, keywords, title, financials) {
        let finLine = '';
        if (financials) {
            const parts = [];
            if (financials.revenue_cr != null) {
                let s = `Revenue: \u20b9${Number(financials.revenue_cr).toLocaleString('en-IN')} Cr`;
                if (financials.revenue_growth != null) s += ` (${financials.revenue_growth > 0 ? '+' : ''}${financials.revenue_growth}% YoY)`;
                parts.push(s);
            }
            if (financials.net_profit_cr != null) {
                let s = `Net Profit: \u20b9${Number(financials.net_profit_cr).toLocaleString('en-IN')} Cr`;
                if (financials.profit_growth != null) s += ` (${financials.profit_growth > 0 ? '+' : ''}${financials.profit_growth}% YoY)`;
                parts.push(s);
            }
            if (financials.pe) parts.push(`P/E: ${financials.pe}`);
            if (financials.mcap_cr) {
                const m = financials.mcap_cr;
                parts.push(m >= 1e5 ? `MCap: \u20b9${(m/1e5).toFixed(2)} L Cr` : `MCap: \u20b9${Number(m).toLocaleString('en-IN')} Cr`);
            }
            if (parts.length) finLine = '\n\n\uD83D\uDCCA Key Financials: ' + parts.join('  |  ');
        }

        const triggers = keywords.slice(0, 4).map(k => k.charAt(0).toUpperCase() + k.slice(1)).join(', ');

        if (sentiment === 'bullish') {
            return triggers
                ? `This news signals positive momentum. Key triggers: ${triggers}. Such developments typically indicate business growth, improved financials, or market confidence.${finLine}`
                : 'This news has a positive tone that could support investor confidence.' + finLine;
        }
        if (sentiment === 'bearish') {
            return triggers
                ? `This news raises caution. Key concerns: ${triggers}. These factors may indicate operational challenges, financial stress, or governance issues.${finLine}`
                : 'This news has a negative tone that warrants caution for investors.' + finLine;
        }
        return triggers
            ? `This news contains mixed signals (${triggers}) and does not clearly lean positive or negative. Monitor for follow-up developments.${finLine}`
            : 'This news is neutral and does not strongly indicate either positive or negative impact.' + finLine;
    }

    return { init, classify, buildImpact };
})();
