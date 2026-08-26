/**
 * JARVIS AI 3.0 — AI BREAKOUT STOCK SCREENER & STOCK INTELLIGENCE CONTROLLER
 * Independent client-side application controller for institutional equity screening.
 */

(function () {
    'use strict';

    // Application State
    const state = {
        stocks: [],
        filteredStocks: [],
        watchlist: new Set(JSON.parse(localStorage.getItem("jarvis_stock_watchlist") || '["NVDA", "AAPL", "PLTR", "TSLA"]')),
        activeSymbol: "NVDA",
        activeTimeframe: "1D",
        filters: {
            market: "all",
            sector: "all",
            timeframe: "1D",
            minProb: 0,
            breakoutType: "all",
            searchQuery: "",
            showWatchlistOnly: false,
            sortBy: "probability",
            sortDir: "desc"
        },
        chartInstance: null,
        candleSeries: null,
        volumeSeries: null,
        chartPriceLines: [],
        dossierOpen: false,
        autoScanInterval: 30,
        countdown: 30,
        audioEnabled: true,
        currentDossier: null,
        heatmapOpen: false
    };

    // DOM Elements Cache
    const el = {
        searchInput: document.getElementById("stock-search-input"),
        autocompleteDropdown: document.getElementById("search-autocomplete"),
        screenerTableBody: document.getElementById("screener-table-tbody"),
        tableCountBadge: document.getElementById("table-count-badge"),
        statTotalScanned: document.getElementById("stat-total-scanned"),
        statHighProbCount: document.getElementById("stat-high-prob-count"),
        statSqueezeCount: document.getElementById("stat-squeeze-count"),
        tickerTrack: document.getElementById("alert-ticker-track"),
        
        // Auto-Scan & Audio
        audioBtn: document.getElementById("btn-audio-toggle"),
        audioIcon: document.getElementById("audio-icon"),
        scanIntervalSelect: document.getElementById("auto-scan-interval"),
        scanCountdown: document.getElementById("scan-countdown"),

        // Sector Heatmap
        heatmapSection: document.getElementById("sector-heatmap-section"),
        heatmapGrid: document.getElementById("sector-heatmap-grid"),

        // Dossier Modal
        dossierModal: document.getElementById("stock-dossier-modal"),
        dossierTicker: document.getElementById("dossier-ticker"),
        dossierGradeBadge: document.getElementById("dossier-grade-badge"),
        dossierCompany: document.getElementById("dossier-company"),
        dossierSector: document.getElementById("dossier-sector"),
        dossierLivePrice: document.getElementById("dossier-live-price"),
        dossierChangeBadge: document.getElementById("dossier-change-badge"),
        dossierProbVal: document.getElementById("dossier-prob-val"),
        dossierProbFill: document.getElementById("dossier-prob-fill"),
        dossierSqueezeBadge: document.getElementById("dossier-squeeze-badge"),
        dossierRecBadge: document.getElementById("dossier-rec-badge"),
        dossierRiskRating: document.getElementById("dossier-risk-rating"),

        // Position Size Calculator
        calcEquity: document.getElementById("calc-equity-input"),
        calcRiskPct: document.getElementById("calc-risk-pct-input"),
        calcShares: document.getElementById("calc-out-shares"),
        calcCapital: document.getElementById("calc-out-capital"),
        calcLoss: document.getElementById("calc-out-loss"),
        calcProfit: document.getElementById("calc-out-profit"),
        calcRrTag: document.getElementById("calc-rr-tag"),

        // Order Flow
        flowBuyerText: document.getElementById("flow-buyer-text"),
        flowSellerText: document.getElementById("flow-seller-text"),
        flowBuyerBar: document.getElementById("flow-buyer-bar"),
        flowCmf: document.getElementById("flow-cmf"),
        flowObv: document.getElementById("flow-obv"),
        flowRsSpy: document.getElementById("flow-rs-spy"),

        // Monte Carlo
        mcTp1Prob: document.getElementById("mc-tp1-prob"),
        mcTp2Prob: document.getElementById("mc-tp2-prob"),
        mcVar: document.getElementById("mc-var"),
        mcRange: document.getElementById("mc-range"),
        
        // Trade Plan
        planEntry: document.getElementById("plan-entry"),
        planSl: document.getElementById("plan-sl"),
        planTp1: document.getElementById("plan-tp1"),
        planTp2: document.getElementById("plan-tp2"),
        planTp3: document.getElementById("plan-tp3"),
        planRr: document.getElementById("plan-rr"),
        
        // Technicals
        techRsi: document.getElementById("tech-rsi"),
        techMacd: document.getElementById("tech-macd"),
        techAdx: document.getElementById("tech-adx"),
        techAtr: document.getElementById("tech-atr"),
        techRvol: document.getElementById("tech-rvol"),
        techBbWidth: document.getElementById("tech-bb-width"),
        
        // S/R Table
        srR3: document.getElementById("sr-r3"),
        srR2: document.getElementById("sr-r2"),
        srR1: document.getElementById("sr-r1"),
        srPivot: document.getElementById("sr-pivot"),
        srS1: document.getElementById("sr-s1"),
        srS2: document.getElementById("sr-s2"),
        srS3: document.getElementById("sr-s3"),
        
        // Multi-TF Grid
        multiTfGrid: document.getElementById("multi-tf-grid"),
        newsContainer: document.getElementById("dossier-news-list"),
        chartContainer: document.getElementById("dossier-tv-chart"),
        
        // AI Recommended Buy Now Grid
        aiBuyNowGrid: document.getElementById("ai-buy-now-grid"),

        // Head-to-Head Compare Modal
        compareModal: document.getElementById("stock-compare-modal"),
        compareSelectA: document.getElementById("compare-select-a"),
        compareSelectB: document.getElementById("compare-select-b"),
        compareContainer: document.getElementById("compare-results-container")
    };

    /* ==========================================================================
       1. DATA FETCHING & API INTERACTION
       ========================================================================== */

    async function fetchScreenerData() {
        try {
            const params = new URLSearchParams({
                market: state.filters.market,
                sector: state.filters.sector,
                tf: state.filters.timeframe,
                min_prob: state.filters.minProb,
                type: state.filters.breakoutType,
                sort_by: state.filters.sortBy,
                sort_dir: state.filters.sortDir
            });

            const res = await fetch(`/api/stocks/screener?${params.toString()}`);
            const data = await res.json();
            if (data && data.stocks) {
                state.stocks = data.stocks;
                renderScreenerTableDOM();
                updateQuickStats();
                if (data.ai_recommended_buys && el.aiBuyNowGrid) {
                    renderAiBuyNowDOM(data.ai_recommended_buys);
                }
            }
        } catch (err) {
            console.error("Screener fetch error:", err);
        }
    }

    async function fetchAlerts() {
        try {
            const res = await fetch("/api/stocks/alerts");
            const data = await res.json();
            if (data && data.alerts) {
                renderAlertTickerDOM(data.alerts);
            }
        } catch (err) {
            console.error("Alerts fetch error:", err);
        }
    }

    async function fetchStockDossier(symbol) {
        try {
            const res = await fetch(`/api/stocks/details?symbol=${symbol}&tf=${state.activeTimeframe}`);
            const data = await res.json();
            if (data) {
                renderDossierDOM(data);
            }
        } catch (err) {
            console.error("Stock details fetch error:", err);
        }
    }

    /* ==========================================================================
       2. DOM RENDERING PIPELINE
       ========================================================================== */

    function renderAiBuyNowDOM(buys) {
        if (!el.aiBuyNowGrid || !buys || buys.length === 0) return;

        let html = "";
        buys.forEach(b => {
            const grade = b.grade_badge || "A";
            let gradeClass = "badge-grade-a";
            if (grade === "A+") gradeClass = "badge-grade-a-plus";
            else if (grade === "B") gradeClass = "badge-grade-b";

            const changeSign = b.change_pct >= 0 ? "+" : "";

            html += `
            <div class="buy-now-card" onclick="window.openStockDossier('${b.symbol}')">
                <div class="buy-now-card-top">
                    <div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <span class="buy-now-sym">${b.symbol}</span>
                            <span class="${gradeClass}">${b.setup_grade}</span>
                        </div>
                        <div class="buy-now-comp">${b.name}</div>
                    </div>
                    <div class="buy-now-price-box">
                        <div class="buy-now-price">$${Number(b.price).toFixed(2)}</div>
                        <span class="buy-now-gain-tag">${changeSign}${Number(b.change_pct).toFixed(2)}%</span>
                    </div>
                </div>

                <div style="display:flex; align-items:center; justify-content:space-between; font-size:11px;">
                    <span style="font-weight:800; color:var(--accent-cyan); font-family:var(--font-mono);">
                        🔥 ${b.breakout_probability}% AI Prob
                    </span>
                    <span style="font-weight:700; color:var(--neon-bull); font-family:var(--font-mono);">
                        Est. Gain: +${b.expected_gain_pct}%
                    </span>
                </div>

                <div class="buy-now-plan-grid">
                    <div class="buy-now-plan-item">
                        <span class="buy-now-plan-lbl">Entry Zone</span>
                        <span class="buy-now-plan-val" style="color:var(--accent-cyan);">$${Number(b.entry_zone).toFixed(2)}</span>
                    </div>
                    <div class="buy-now-plan-item">
                        <span class="buy-now-plan-lbl">Target (TP)</span>
                        <span class="buy-now-plan-val" style="color:var(--neon-bull);">$${Number(b.take_profit_2).toFixed(2)}</span>
                    </div>
                    <div class="buy-now-plan-item">
                        <span class="buy-now-plan-lbl">Stop Loss</span>
                        <span class="buy-now-plan-val" style="color:var(--neon-bear);">$${Number(b.stop_loss).toFixed(2)}</span>
                    </div>
                </div>

                <div class="buy-now-catalyst-text">
                    ${b.ai_catalyst}
                </div>

                <button class="btn-buy-now-cta" onclick="event.stopPropagation(); window.openStockDossier('${b.symbol}')">
                    <span>⚡</span> Buy Now Setup Dossier ➔
                </button>
            </div>`;
        });

        el.aiBuyNowGrid.innerHTML = html;
    }

    function renderScreenerTableDOM() {
        if (!el.screenerTableBody) return;

        let list = state.stocks.slice();

        // Client-side search filter
        const q = state.filters.searchQuery.toLowerCase().trim();
        if (q) {
            list = list.filter(s => s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q));
        }

        // Watchlist filter
        if (state.filters.showWatchlistOnly) {
            list = list.filter(s => state.watchlist.has(s.symbol));
        }

        state.filteredStocks = list;
        if (el.tableCountBadge) el.tableCountBadge.textContent = `${list.length} Stocks`;

        if (list.length === 0) {
            if (q) {
                el.screenerTableBody.innerHTML = `
                    <tr>
                        <td colspan="10" style="text-align:center; padding:35px 20px; color:var(--text-secondary);">
                            <div style="font-size:14px; font-weight:800; margin-bottom:6px; color:#ffffff;">
                                No pre-scanned stocks matching "<span style="color:var(--accent-cyan);">${q.toUpperCase()}</span>" in current filter.
                            </div>
                            <div style="font-size:12px; color:var(--text-dim); margin-bottom:14px;">
                                You can launch immediate real-time AI quantitative analysis, multi-timeframe trends, and interactive chart for <b>${q.toUpperCase()}</b>:
                            </div>
                            <button class="btn-analyze-action" style="padding:8px 20px; font-size:12px; display:inline-flex; align-items:center; gap:6px;" onclick="window.selectSearchResult('${q.toUpperCase()}')">
                                <span>⚡</span> Run AI Intelligence Dossier on [${q.toUpperCase()}] ➔
                            </button>
                        </td>
                    </tr>`;
            } else {
                el.screenerTableBody.innerHTML = `
                    <tr>
                        <td colspan="10" style="text-align:center; padding:30px; color:var(--text-dim);">
                            No stocks matched the active breakout filters. Try broadening your criteria.
                        </td>
                    </tr>`;
            }
            return;
        }

        let html = "";
        list.forEach((st, idx) => {
            const isStarred = state.watchlist.has(st.symbol);
            const isSelected = (st.symbol === state.activeSymbol);
            const changeColor = st.change_pct >= 0 ? "var(--neon-bull)" : "var(--neon-bear)";
            const changeSign = st.change_pct >= 0 ? "+" : "";
            
            // Breakout Prob Meter
            let probColorClass = "prob-low";
            if (st.breakout_probability >= 78) probColorClass = "prob-high";
            else if (st.breakout_probability >= 60) probColorClass = "prob-med";

            // Squeeze Badge
            let squeezeBadge = '<span style="color:var(--text-dim); font-size:11px;">Normal</span>';
            if (st.is_squeeze || st.squeeze_status.includes("EXTREME")) {
                squeezeBadge = '<span class="badge badge-squeeze-extreme">🔥 COILING SQUEEZE</span>';
            } else if (st.squeeze_status.includes("FIRED")) {
                squeezeBadge = '<span class="badge badge-squeeze-fired">⚡ FIRED BULLISH</span>';
            }

            // Recommendation Badge
            let recClass = "badge-rec-pullback";
            if (st.recommendation.includes("STRONG")) recClass = "badge-rec-strong";

            // Grade Badge Class
            const grade = st.grade_badge || "A";
            let gradeClass = "badge-grade-a";
            if (grade === "A+") gradeClass = "badge-grade-a-plus";
            else if (grade === "B") gradeClass = "badge-grade-b";
            else if (grade === "C") gradeClass = "badge-grade-c";

            // RS Badge
            const rsVal = Number(st.rs_vs_spy || 0);
            const rsBadgeClass = rsVal >= 0 ? "badge-rs-lead" : "badge-rs-lag";
            const rsSign = rsVal >= 0 ? "+" : "";

            // CMF Color
            const cmfVal = Number(st.cmf_20 || 0);
            const cmfColor = cmfVal > 0 ? "var(--neon-bull)" : (cmfVal < 0 ? "var(--neon-bear)" : "var(--text-dim)");
            const cmfSign = cmfVal > 0 ? "+" : "";

            // Timing Horizon Badge
            const tBadge = st.timing_badge || "UPCOMING";
            let timingBadgeHtml = '<span class="badge-timing-upcoming">⏳ Upcoming (1-3D)</span>';
            if (tBadge === "THIS_WEEK") {
                timingBadgeHtml = '<span class="badge-timing-weekly">📅 This Week (5-10D)</span>';
            } else if (tBadge === "ACTIVE") {
                timingBadgeHtml = '<span class="badge-timing-active">⚡ Active Today</span>';
            } else if (tBadge === "WATCH") {
                timingBadgeHtml = '<span class="badge-timing-watch">Watch Base</span>';
            }

            html += `
            <tr class="${isSelected ? 'active-row' : ''}" onclick="window.openStockDossier('${st.symbol}')">
                <td>
                    <button class="btn-star-watch ${isStarred ? 'starred' : ''}" onclick="event.stopPropagation(); window.toggleWatchlist('${st.symbol}')">
                        ${isStarred ? '★' : '☆'}
                    </button>
                </td>
                <td><span class="${gradeClass}">${st.setup_grade || 'GRADE A'}</span></td>
                <td>
                    <div class="stock-sym-cell">
                        <div class="stock-sym-name">
                            <span class="stock-ticker">${st.symbol}</span>
                            <span class="stock-comp-name">${st.name}</span>
                        </div>
                    </div>
                </td>
                <td>${timingBadgeHtml}</td>
                <td class="mono-num" style="color:#ffffff; font-size:13px;">$${Number(st.price).toFixed(2)}</td>
                <td class="mono-num" style="color:${changeColor}; font-weight:800;">${changeSign}${Number(st.change_pct).toFixed(2)}%</td>
                <td>
                    <div class="prob-meter-wrapper">
                        <div class="prob-meter-bar">
                            <div class="prob-meter-fill ${probColorClass}" style="width:${st.breakout_probability}%;"></div>
                        </div>
                        <span class="mono-num" style="font-weight:800; color:#ffffff; font-size:12px;">${st.breakout_probability}%</span>
                    </div>
                </td>
                <td>${squeezeBadge}</td>
                <td>
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span class="mono-num" style="color:${cmfColor}; font-size:11px; font-weight:800;">CMF: ${cmfSign}${cmfVal.toFixed(2)}</span>
                        <span style="font-size:10px; color:var(--text-dim);">${st.buyer_pressure_pct || 50}% Buyers</span>
                    </div>
                </td>
                <td><span class="badge ${rsBadgeClass}">${rsSign}${rsVal.toFixed(1)}% vs SPY</span></td>
                <td>
                    <span class="${st.earnings_warning === 'HIGH_VOLATILITY_WARNING' ? 'badge-earnings-warn' : (st.earnings_warning === 'UPCOMING_SOON' ? 'badge-earnings-soon' : 'badge-earnings-clear')}">
                        ${st.earnings_badge || '✅ Clear'}
                    </span>
                </td>
                <td><span class="badge ${recClass}">${st.recommendation}</span></td>
                <td>
                    <button class="btn-analyze-action" onclick="event.stopPropagation(); window.openStockDossier('${st.symbol}')">
                        Dossier ➔
                    </button>
                </td>
            </tr>`;
        });

        el.screenerTableBody.innerHTML = html;
    }

    function updateQuickStats() {
        if (!state.stocks || state.stocks.length === 0) return;
        if (el.statTotalScanned) el.statTotalScanned.textContent = state.stocks.length;
        
        const highProb = state.stocks.filter(s => s.breakout_probability >= 75).length;
        if (el.statHighProbCount) el.statHighProbCount.textContent = highProb;
        
        const squeeze = state.stocks.filter(s => s.is_squeeze || s.squeeze_status.includes("SQUEEZE")).length;
        if (el.statSqueezeCount) el.statSqueezeCount.textContent = squeeze;
    }

    function renderAlertTickerDOM(alerts) {
        if (!el.tickerTrack || !alerts || alerts.length === 0) return;
        let html = "";
        alerts.forEach(a => {
            html += `
            <div class="ticker-alert-pill" onclick="window.openStockDossier('${a.symbol}')">
                <b style="color:#ffffff;">${a.symbol}</b>
                <span style="color:${a.change_pct >= 0 ? 'var(--neon-bull)' : 'var(--neon-bear)'};">${a.change_pct >= 0 ? '+' : ''}${a.change_pct}%</span>
                <span class="ticker-prob-badge">${a.probability}% Prob</span>
                <span style="color:var(--text-dim); font-size:10px;">${a.time_ago}</span>
            </div>`;
        });
        el.tickerTrack.innerHTML = html;
    }

    /* ==========================================================================
       3. STOCK DOSSIER MODAL & CHART RENDERING
       ========================================================================== */

    function renderDossierDOM(data) {
        if (!data) return;
        state.activeSymbol = data.symbol;

        if (el.dossierTicker) el.dossierTicker.textContent = data.symbol;
        if (el.dossierGradeBadge) {
            const grade = data.grade_badge || "A";
            el.dossierGradeBadge.textContent = data.setup_grade || "GRADE A";
            if (grade === "A+") el.dossierGradeBadge.className = "badge-grade-a-plus";
            else if (grade === "B") el.dossierGradeBadge.className = "badge-grade-b";
            else if (grade === "C") el.dossierGradeBadge.className = "badge-grade-c";
            else el.dossierGradeBadge.className = "badge-grade-a";
        }
        if (el.dossierCompany) el.dossierCompany.textContent = `${data.name} • ${data.sector} • Cap: ${data.market_cap}`;
        if (el.dossierLivePrice) el.dossierLivePrice.textContent = `$${Number(data.current_price).toFixed(2)}`;
        
        if (el.dossierChangeBadge) {
            const chg = Number(data.change_pct);
            el.dossierChangeBadge.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}% ($${Number(data.change_val).toFixed(2)})`;
            el.dossierChangeBadge.style.color = chg >= 0 ? "var(--neon-bull)" : "var(--neon-bear)";
            el.dossierChangeBadge.style.borderColor = chg >= 0 ? "rgba(0,245,155,0.4)" : "rgba(255,59,92,0.4)";
        }

        // AI Gauge
        if (el.dossierProbVal) el.dossierProbVal.textContent = `${data.breakout_probability}%`;
        if (el.dossierProbFill) {
            el.dossierProbFill.style.width = `${data.breakout_probability}%`;
            el.dossierProbFill.className = `prob-meter-fill ${data.breakout_probability >= 78 ? 'prob-high' : 'prob-med'}`;
        }
        if (el.dossierSqueezeBadge) el.dossierSqueezeBadge.textContent = data.squeeze_status;
        if (el.dossierRecBadge) el.dossierRecBadge.textContent = data.recommendation;
        if (el.dossierRiskRating) el.dossierRiskRating.textContent = `Risk: ${data.risk_level}`;

        // Order Flow & Smart Money
        const flow = data.order_flow || {};
        if (el.flowBuyerText) el.flowBuyerText.textContent = `Buyers: ${flow.buyer_pressure_pct || 50}%`;
        if (el.flowSellerText) el.flowSellerText.textContent = `Sellers: ${flow.seller_pressure_pct || 50}%`;
        if (el.flowBuyerBar) el.flowBuyerBar.style.width = `${flow.buyer_pressure_pct || 50}%`;
        if (el.flowCmf) {
            const cVal = Number(flow.cmf_20 || 0);
            el.flowCmf.textContent = `${cVal >= 0 ? '+' : ''}${cVal.toFixed(2)}`;
            el.flowCmf.style.color = cVal > 0 ? "var(--neon-bull)" : (cVal < 0 ? "var(--neon-bear)" : "var(--text-dim)");
        }
        if (el.flowObv) el.flowObv.textContent = flow.obv_trend || "ACCUMULATION";
        if (el.flowRsSpy) {
            const rsVal = Number(flow.rs_vs_spy || 0);
            el.flowRsSpy.textContent = `${rsVal >= 0 ? '+' : ''}${rsVal.toFixed(2)}% (${flow.rs_label || 'Leading'})`;
            el.flowRsSpy.style.color = rsVal >= 0 ? "var(--neon-amber)" : "var(--neon-bear)";
        }

        // Monte Carlo Statistical Model
        const mc = data.monte_carlo || {};
        if (el.mcTp1Prob) el.mcTp1Prob.textContent = `${mc.tp1_probability_pct || 75}%`;
        if (el.mcTp2Prob) el.mcTp2Prob.textContent = `${mc.tp2_probability_pct || 55}%`;
        if (el.mcVar) el.mcVar.textContent = `-${mc.value_at_risk_95_pct || 3.5}%`;
        if (el.mcRange) el.mcRange.textContent = `$${mc.lower_corridor_5pct || data.current_price * 0.95} — $${mc.upper_corridor_95pct || data.current_price * 1.1}`;

        // Trade Plan
        const plan = data.trade_setup || {};
        if (el.planEntry) el.planEntry.textContent = `$${Number(plan.entry_zone || data.current_price).toFixed(2)}`;
        if (el.planSl) el.planSl.textContent = `$${Number(plan.stop_loss || 0).toFixed(2)}`;
        if (el.planTp1) el.planTp1.textContent = `$${Number(plan.take_profit_1 || 0).toFixed(2)}`;
        if (el.planTp2) el.planTp2.textContent = `$${Number(plan.take_profit_2 || 0).toFixed(2)}`;
        if (el.planTp3) el.planTp3.textContent = `$${Number(plan.take_profit_3 || 0).toFixed(2)}`;
        if (el.planRr) el.planRr.textContent = plan.risk_reward_ratio || "1:2.8";

        // Technicals
        const tech = data.technicals || {};
        if (el.techRsi) el.techRsi.textContent = tech.rsi_14 || "--";
        if (el.techMacd) el.techMacd.textContent = `${tech.macd_hist >= 0 ? '+' : ''}${tech.macd_hist || 0}`;
        if (el.techAdx) el.techAdx.textContent = tech.adx || "--";
        if (el.techAtr) el.techAtr.textContent = `$${tech.atr_14 || 0}`;
        if (el.techRvol) el.techRvol.textContent = `${data.rvol}x`;
        if (el.techBbWidth) el.techBbWidth.textContent = `${tech.bb_width_pct}%`;

        // S/R Table
        const sr = data.support_resistance || {};
        if (el.srR3) el.srR3.textContent = `$${Number(sr.r3 || 0).toFixed(2)}`;
        if (el.srR2) el.srR2.textContent = `$${Number(sr.r2 || 0).toFixed(2)}`;
        if (el.srR1) el.srR1.textContent = `$${Number(sr.r1 || 0).toFixed(2)}`;
        if (el.srPivot) el.srPivot.textContent = `$${Number(sr.pivot || 0).toFixed(2)}`;
        if (el.srS1) el.srS1.textContent = `$${Number(sr.s1 || 0).toFixed(2)}`;
        if (el.srS2) el.srS2.textContent = `$${Number(sr.s2 || 0).toFixed(2)}`;
        if (el.srS3) el.srS3.textContent = `$${Number(sr.s3 || 0).toFixed(2)}`;

        // Multi-Timeframe Alignment Matrix
        if (el.multiTfGrid && data.multi_timeframe) {
            let mHtml = "";
            const tfs = ["1M", "5M", "15M", "1H", "4H", "1D", "1W"];
            tfs.forEach(tfKey => {
                const item = data.multi_timeframe[tfKey] || { bias: "NEUTRAL", strength: 50 };
                let biasClass = "bias-neut";
                if (item.bias === "BULLISH") biasClass = "bias-bull";
                else if (item.bias === "BEARISH") biasClass = "bias-bear";

                mHtml += `
                <div class="matrix-tf-cell">
                    <span class="matrix-tf-name">${tfKey}</span>
                    <span class="matrix-bias-tag ${biasClass}">${item.bias}</span>
                    <span style="font-size:9px; color:var(--text-dim);">${item.strength}%</span>
                </div>`;
            });
            el.multiTfGrid.innerHTML = mHtml;
        }

        // News Feed
        if (el.newsContainer && data.news) {
            let nHtml = "";
            data.news.forEach(n => {
                let sentColor = "var(--text-dim)";
                if (n.sentiment === "BULLISH") sentColor = "var(--neon-bull)";
                else if (n.sentiment === "BEARISH") sentColor = "var(--neon-bear)";

                nHtml += `
                <div class="news-item-row">
                    <div class="news-item-top">
                        <span class="news-source">${n.source}</span>
                        <span style="color:${sentColor}; font-weight:800; font-size:10px;">${n.sentiment} (${Math.round(n.sentiment_score * 100)}%)</span>
                        <span class="news-time">${n.time_ago}</span>
                    </div>
                    <div class="news-headline">${n.headline}</div>
                    <div class="news-summary">${n.summary}</div>
                </div>`;
            });
            el.newsContainer.innerHTML = nHtml;
        }

        // Render TradingView Chart
        initDossierChart(data.candles, data.support_resistance);

        // Store state & update live position sizing calculator
        state.currentDossier = data;
        window.updatePositionCalculator();

        // Display Modal
        if (el.dossierModal) {
            el.dossierModal.style.display = "flex";
            state.dossierOpen = true;
        }
    }

    function initDossierChart(candles, sr) {
        if (!el.chartContainer || !candles || candles.length === 0) return;
        if (typeof LightweightCharts === "undefined") return;

        el.chartContainer.innerHTML = "";

        const width = el.chartContainer.clientWidth || 650;
        const height = el.chartContainer.clientHeight || 380;

        const chart = LightweightCharts.createChart(el.chartContainer, {
            width: width,
            height: height,
            layout: {
                background: { color: "#080c14" },
                textColor: "#94a3b8",
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace"
            },
            grid: {
                vertLines: { color: "rgba(51, 65, 85, 0.2)" },
                horzLines: { color: "rgba(51, 65, 85, 0.2)" }
            },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            rightPriceScale: {
                borderColor: "rgba(51, 65, 85, 0.4)",
                scaleMargins: { top: 0.1, bottom: 0.25 }
            },
            timeScale: {
                borderColor: "rgba(51, 65, 85, 0.4)",
                timeVisible: true
            }
        });

        const candleSeries = chart.addCandlestickSeries({
            upColor: "#00f59b",
            downColor: "#ff3b5c",
            borderUpColor: "#00f59b",
            borderDownColor: "#ff3b5c",
            wickUpColor: "#00f59b",
            wickDownColor: "#ff3b5c"
        });

        const volumeSeries = chart.addHistogramSeries({
            color: "#38bdf8",
            priceFormat: { type: "volume" },
            priceScaleId: "",
            scaleMargins: { top: 0.82, bottom: 0 },
            lastValueVisible: false,
            priceLineVisible: false
        });

        const sorted = candles.map(c => ({
            time: typeof c.time === "number" ? c.time : Math.floor(new Date(c.time).getTime() / 1000),
            open: Number(c.open),
            high: Number(c.high),
            low: Number(c.low),
            close: Number(c.close)
        })).sort((a, b) => a.time - b.time);

        const vols = candles.map(c => ({
            time: typeof c.time === "number" ? c.time : Math.floor(new Date(c.time).getTime() / 1000),
            value: Number(c.volume || 0),
            color: c.close >= c.open ? "rgba(0, 245, 155, 0.35)" : "rgba(255, 59, 92, 0.35)"
        })).sort((a, b) => a.time - b.time);

        candleSeries.setData(sorted);
        volumeSeries.setData(vols);
        chart.timeScale().fitContent();

        // Draw S/R Lines
        if (sr) {
            if (sr.r1 > 0) {
                candleSeries.createPriceLine({
                    price: sr.r1,
                    color: "#ff2a5f",
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    title: `R1: $${sr.r1.toFixed(2)}`
                });
            }
            if (sr.s1 > 0) {
                candleSeries.createPriceLine({
                    price: sr.s1,
                    color: "#00f59b",
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    title: `S1: $${sr.s1.toFixed(2)}`
                });
            }
        }

        // Auto-resize
        if (window.ResizeObserver) {
            const ro = new ResizeObserver(entries => {
                for (const entry of entries) {
                    if (entry.contentRect && entry.contentRect.width > 0 && entry.contentRect.height > 0) {
                        chart.applyOptions({
                            width: entry.contentRect.width,
                            height: entry.contentRect.height
                        });
                    }
                }
            });
            ro.observe(el.chartContainer);
        }

        state.chartInstance = chart;
        state.candleSeries = candleSeries;
        state.volumeSeries = volumeSeries;
    }

/* ==========================================================================
   4. POSITION SIZE & RISK CALCULATOR
   ========================================================================== */

window.updatePositionCalculator = function () {
    if (!state.currentDossier) return;
    const d = state.currentDossier;
    const equity = parseFloat(el.calcEquity ? el.calcEquity.value : 10000) || 10000;
    const riskPct = parseFloat(el.calcRiskPct ? el.calcRiskPct.value : 1.0) || 1.0;

    const entry = Number(d.trade_setup ? d.trade_setup.entry_zone : d.current_price) || d.current_price;
    const sl = Number(d.trade_setup ? d.trade_setup.stop_loss : (entry * 0.96)) || (entry * 0.96);
    const tp = Number(d.trade_setup ? d.trade_setup.take_profit_2 : (entry * 1.10)) || (entry * 1.10);

    const riskDollar = Math.max(1, equity * (riskPct / 100.0));
    const perShareRisk = Math.max(0.01, Math.abs(entry - sl));
    const shares = Math.max(1, Math.floor(riskDollar / perShareRisk));

    const totalCapital = shares * entry;
    const actualRisk = shares * perShareRisk;
    const actualProfit = shares * Math.abs(tp - entry);
    const rrRatio = (actualProfit / actualRisk).toFixed(2);

    if (el.calcShares) el.calcShares.textContent = `${shares.toLocaleString()} sh`;
    if (el.calcCapital) el.calcCapital.textContent = `$${totalCapital.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}`;
    if (el.calcLoss) el.calcLoss.textContent = `-$${actualRisk.toFixed(2)}`;
    if (el.calcProfit) el.calcProfit.textContent = `+$${actualProfit.toFixed(2)}`;
    if (el.calcRrTag) el.calcRrTag.textContent = `R:R 1:${rrRatio}`;
};

window.copyBrokerOrder = function () {
    if (!state.currentDossier) return;
    const d = state.currentDossier;
    const equity = parseFloat(el.calcEquity ? el.calcEquity.value : 10000) || 10000;
    const riskPct = parseFloat(el.calcRiskPct ? el.calcRiskPct.value : 1.0) || 1.0;

    const entry = Number(d.trade_setup ? d.trade_setup.entry_zone : d.current_price) || d.current_price;
    const sl = Number(d.trade_setup ? d.trade_setup.stop_loss : (entry * 0.96)) || (entry * 0.96);
    const tp = Number(d.trade_setup ? d.trade_setup.take_profit_2 : (entry * 1.10)) || (entry * 1.10);

    const riskDollar = Math.max(1, equity * (riskPct / 100.0));
    const perShareRisk = Math.max(0.01, Math.abs(entry - sl));
    const shares = Math.max(1, Math.floor(riskDollar / perShareRisk));

    const orderText = `BUY ${shares} ${d.symbol} @ $${entry.toFixed(2)} | SL: $${sl.toFixed(2)} | TP: $${tp.toFixed(2)} | MaxRisk: $${(shares * perShareRisk).toFixed(2)}`;

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(orderText).then(() => {
            const btn = document.getElementById("btn-copy-broker-order");
            if (btn) {
                const orig = btn.innerHTML;
                btn.innerHTML = `<span>✅</span> Order Copied to Clipboard!`;
                btn.style.background = "var(--neon-bull)";
                btn.style.color = "#000000";
                setTimeout(() => {
                    btn.innerHTML = orig;
                    btn.style.background = "";
                    btn.style.color = "";
                }, 2000);
            }
        });
    } else {
        prompt("Copy Broker Order Ticket:", orderText);
    }
};

/* ==========================================================================
   5. SECTOR CAPITAL ROTATION HEATMAP CONTROLLER
   ========================================================================== */

window.toggleSectorHeatmap = function () {
    if (!el.heatmapSection) return;
    state.heatmapOpen = !state.heatmapOpen;
    el.heatmapSection.style.display = state.heatmapOpen ? "flex" : "none";
    if (state.heatmapOpen) {
        fetchSectorHeatmap();
    }
};

async function fetchSectorHeatmap() {
    if (!el.heatmapGrid) return;
    try {
        const res = await fetch("/api/stocks/heatmap");
        const data = await res.json();
        if (data && data.sectors) {
            renderSectorHeatmapDOM(data.sectors);
        }
    } catch (err) {
        console.error("Heatmap fetch error:", err);
    }
}

function renderSectorHeatmapDOM(sectors) {
    if (!el.heatmapGrid) return;
    let html = "";
    sectors.forEach(sec => {
        const isPos = sec.avg_change_pct >= 0;
        const tileClass = isPos ? "heatmap-tile-inflow" : "heatmap-tile-outflow";
        const flowBadgeClass = sec.rotation_status.includes("INFLOW") || sec.rotation_status.includes("ACCUMULATION") ? "flow-inflow" : (sec.rotation_status.includes("OUTFLOW") ? "flow-outflow" : "flow-neutral");

        html += `
        <div class="heatmap-tile ${tileClass}" onclick="window.filterByHeatmapSector('${sec.sector}')">
            <div class="heatmap-tile-top">
                <span class="heatmap-sec-name">${sec.sector}</span>
                <span class="heatmap-chg mono-num" style="color:${isPos ? 'var(--neon-bull)' : 'var(--neon-bear)'};">
                    ${isPos ? '+' : ''}${sec.avg_change_pct}%
                </span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:10px;">
                <span class="heatmap-flow-badge ${flowBadgeClass}">${sec.rotation_status.replace('_', ' ')}</span>
                <span style="color:var(--text-dim);">CMF: <b>${sec.avg_cmf > 0 ? '+' : ''}${sec.avg_cmf}</b></span>
            </div>
            <div style="font-size:10px; color:var(--text-secondary); margin-top:2px;">
                Top Leader: <b style="color:var(--accent-cyan);">${sec.top_leader_symbol} (${sec.top_leader_change > 0 ? '+' : ''}${sec.top_leader_change}%)</b>
            </div>
        </div>`;
    });
    el.heatmapGrid.innerHTML = html;
}

window.filterByHeatmapSector = function (sec) {
    window.setSectorFilter(sec, null);
};

/* ==========================================================================
   6. EXPORT CSV & TRADINGVIEW WATCHLIST
   ========================================================================== */

window.exportCsv = function () {
    const url = `/api/stocks/export_csv?market=${encodeURIComponent(state.filters.market)}&sector=${encodeURIComponent(state.filters.sector)}`;
    window.location.href = url;
};

window.copyTradingViewList = function () {
    if (!state.filteredStocks || state.filteredStocks.length === 0) return;
    const list = state.filteredStocks.map(s => `NASDAQ:${s.symbol}`).join(", ");
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(list).then(() => {
            alert(`📋 Copied ${state.filteredStocks.length} tickers for TradingView Watchlist!`);
        });
    } else {
        prompt("TradingView Watchlist Tickers:", list);
    }
};

/* ==========================================================================
   7. HEAD-TO-HEAD COMPARATIVE RADAR
   ========================================================================== */

window.openCompareModal = function () {
    if (el.compareModal) {
        el.compareModal.style.display = "flex";
        window.runComparison();
    }
};

window.closeCompareModal = function () {
    if (el.compareModal) el.compareModal.style.display = "none";
};

window.runComparison = async function () {
    if (!el.compareContainer) return;
    const sym1 = el.compareSelectA ? el.compareSelectA.value : "NVDA";
    const sym2 = el.compareSelectB ? el.compareSelectB.value : "AMD";

    el.compareContainer.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-dim);">Analyzing multi-factor quant radar for ${sym1} vs ${sym2}...</div>`;

    try {
        const res = await fetch(`/api/stocks/compare?sym1=${sym1}&sym2=${sym2}`);
        const data = await res.json();
        if (data && data.stock_a && data.stock_b) {
            renderCompareResultsDOM(data);
        }
    } catch (err) {
        el.compareContainer.innerHTML = `<div style="color:var(--neon-bear); text-align:center; padding:20px;">Failed to load comparison: ${err.message}</div>`;
    }
};

function renderCompareResultsDOM(data) {
    const a = data.stock_a;
    const b = data.stock_b;
    const winner = data.ai_winner;

    let html = `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
        <!-- Stock A Card -->
        <div style="background:var(--bg-card); border:1px solid ${winner === a.symbol ? 'var(--neon-bull)' : 'var(--border-subtle)'}; border-radius:8px; padding:14px; display:flex; flex-direction:column; gap:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-size:18px; font-weight:900; color:#ffffff;">${a.symbol}</span>
                    <div style="font-size:11px; color:var(--text-dim);">${a.name}</div>
                </div>
                ${winner === a.symbol ? '<span class="badge" style="background:rgba(0,245,155,0.15); color:var(--neon-bull); border:1px solid var(--neon-bull);">🏆 AI PREFERRED</span>' : ''}
            </div>
            <div style="font-size:20px; font-weight:900; font-family:var(--font-mono); color:#ffffff;">$${Number(a.current_price).toFixed(2)}</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; font-size:11px;">
                <div>Breakout Prob: <b style="color:var(--neon-bull);">${a.breakout_probability}%</b></div>
                <div>Grade: <b>${a.setup_grade}</b></div>
                <div>CMF 20: <b>${a.order_flow.cmf_20 > 0 ? '+' : ''}${a.order_flow.cmf_20}</b></div>
                <div>RS vs SPY: <b>${a.order_flow.rs_vs_spy > 0 ? '+' : ''}${a.order_flow.rs_vs_spy}%</b></div>
                <div>RVOL: <b>${a.rvol}x</b></div>
                <div>R:R Ratio: <b>${a.trade_setup.risk_reward_ratio}</b></div>
            </div>
            <button class="btn-analyze-action" style="margin-top:6px; width:100%;" onclick="window.closeCompareModal(); window.openStockDossier('${a.symbol}')">Open ${a.symbol} Dossier ➔</button>
        </div>

        <!-- Stock B Card -->
        <div style="background:var(--bg-card); border:1px solid ${winner === b.symbol ? 'var(--neon-bull)' : 'var(--border-subtle)'}; border-radius:8px; padding:14px; display:flex; flex-direction:column; gap:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-size:18px; font-weight:900; color:#ffffff;">${b.symbol}</span>
                    <div style="font-size:11px; color:var(--text-dim);">${b.name}</div>
                </div>
                ${winner === b.symbol ? '<span class="badge" style="background:rgba(0,245,155,0.15); color:var(--neon-bull); border:1px solid var(--neon-bull);">🏆 AI PREFERRED</span>' : ''}
            </div>
            <div style="font-size:20px; font-weight:900; font-family:var(--font-mono); color:#ffffff;">$${Number(b.current_price).toFixed(2)}</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; font-size:11px;">
                <div>Breakout Prob: <b style="color:var(--neon-bull);">${b.breakout_probability}%</b></div>
                <div>Grade: <b>${b.setup_grade}</b></div>
                <div>CMF 20: <b>${b.order_flow.cmf_20 > 0 ? '+' : ''}${b.order_flow.cmf_20}</b></div>
                <div>RS vs SPY: <b>${b.order_flow.rs_vs_spy > 0 ? '+' : ''}${b.order_flow.rs_vs_spy}%</b></div>
                <div>RVOL: <b>${b.rvol}x</b></div>
                <div>R:R Ratio: <b>${b.trade_setup.risk_reward_ratio}</b></div>
            </div>
            <button class="btn-analyze-action" style="margin-top:6px; width:100%;" onclick="window.closeCompareModal(); window.openStockDossier('${b.symbol}')">Open ${b.symbol} Dossier ➔</button>
        </div>
    </div>`;

    el.compareContainer.innerHTML = html;
}

/* ==========================================================================
   8. AUDIO ALERTS & AUTO-SCAN COUNTDOWN ENGINE
   ========================================================================== */

function playBreakoutChime() {
    if (!state.audioEnabled) return;
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const now = ctx.currentTime;
        
        // Oscillator 1 (587.33 Hz - D5)
        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = "sine";
        osc1.frequency.setValueAtTime(587.33, now);
        gain1.gain.setValueAtTime(0.08, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(now);
        osc1.stop(now + 0.35);

        // Oscillator 2 (880.00 Hz - A5)
        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = "sine";
        osc2.frequency.setValueAtTime(880.0, now + 0.15);
        gain2.gain.setValueAtTime(0.12, now + 0.15);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(now + 0.15);
        osc2.stop(now + 0.55);
    } catch (e) {}
}

window.toggleAudioAlerts = function () {
    state.audioEnabled = !state.audioEnabled;
    if (el.audioBtn) {
        el.audioBtn.innerHTML = `<span id="audio-icon">${state.audioEnabled ? '🔊' : '🔇'}</span> Audio: ${state.audioEnabled ? 'ON' : 'OFF'}`;
        el.audioBtn.style.color = state.audioEnabled ? "var(--accent-cyan)" : "var(--text-dim)";
    }
    if (state.audioEnabled) playBreakoutChime();
};

window.setAutoScanInterval = function (seconds) {
    state.autoScanInterval = parseInt(seconds, 10);
    state.countdown = state.autoScanInterval;
    if (el.scanCountdown) {
        el.scanCountdown.textContent = state.autoScanInterval > 0 ? `${state.countdown}s` : "OFF";
    }
};

function startAutoScanTicker() {
    setInterval(() => {
        if (state.autoScanInterval <= 0) return;
        state.countdown--;
        if (state.countdown <= 0) {
            state.countdown = state.autoScanInterval;
            fetchScreenerData();
            fetchAlerts();
        }
        if (el.scanCountdown) {
            el.scanCountdown.textContent = `${state.countdown}s`;
        }
    }, 1000);
}

/* ==========================================================================
   9. GLOBAL WINDOW ACTIONS
   ========================================================================== */

window.openStockDossier = function (symbol) {
    state.activeSymbol = symbol;
    fetchStockDossier(symbol);
};

window.closeStockDossier = function () {
    if (el.dossierModal) el.dossierModal.style.display = "none";
    state.dossierOpen = false;
};

window.toggleWatchlist = function (symbol) {
    if (state.watchlist.has(symbol)) {
        state.watchlist.delete(symbol);
    } else {
        state.watchlist.add(symbol);
    }
    localStorage.setItem("jarvis_stock_watchlist", JSON.stringify(Array.from(state.watchlist)));
    renderScreenerTableDOM();
};

window.setSectorFilter = function (sector, btn) {
    state.filters.sector = sector;
    document.querySelectorAll(".sector-pill").forEach(p => p.classList.remove("active"));
    if (btn) btn.classList.add("active");
    fetchScreenerData();
};

window.setTimeframeFilter = function (tf, btn) {
    state.filters.timeframe = tf;
    state.activeTimeframe = tf;
    document.querySelectorAll(".tf-pill").forEach(p => p.classList.remove("active"));
    if (btn) btn.classList.add("active");
    fetchScreenerData();
};

window.setProbFilter = function (minProb, btn) {
    state.filters.minProb = minProb;
    document.querySelectorAll(".prob-pill").forEach(p => p.classList.remove("active"));
    if (btn) btn.classList.add("active");
    fetchScreenerData();
};

window.setTypeFilter = function (bType, btn) {
    state.filters.breakoutType = bType;
    document.querySelectorAll(".type-pill").forEach(p => p.classList.remove("active", "active-squeeze"));
    if (btn) {
        btn.classList.add("active");
        if (bType === "squeeze") btn.classList.add("active-squeeze");
    }
    fetchScreenerData();
};

window.toggleWatchlistOnly = function (btn) {
    state.filters.showWatchlistOnly = !state.filters.showWatchlistOnly;
    if (btn) btn.classList.toggle("active", state.filters.showWatchlistOnly);
    renderScreenerTableDOM();
};

window.sortTableBy = function (columnKey) {
    if (state.filters.sortBy === columnKey) {
        state.filters.sortDir = (state.filters.sortDir === "asc") ? "desc" : "asc";
    } else {
        state.filters.sortBy = columnKey;
        state.filters.sortDir = "desc";
    }
    fetchScreenerData();
};

window.setDossierTf = function (tf, btn) {
    state.activeTimeframe = tf;
    document.querySelectorAll(".stock-tf-btn").forEach(b => b.classList.remove("active"));
    if (btn) btn.classList.add("active");
    fetchStockDossier(state.activeSymbol);
};

/* ==========================================================================
   10. SEARCH AUTOCOMPLETE CONTROLLER
   ========================================================================== */

function initSearchController() {
    if (!el.searchInput) return;

    let debounceTimer = null;
    
    async function doSearch(query) {
        if (query.trim().length > 0) {
            try {
                const res = await fetch(`/api/stocks/search?q=${encodeURIComponent(query)}`);
                const data = await res.json();
                if (data && data.results && el.autocompleteDropdown) {
                    renderAutocompleteDOM(data.results);
                }
            } catch (err) {}
        } else if (el.autocompleteDropdown) {
            el.autocompleteDropdown.style.display = "none";
        }
    }

    el.searchInput.addEventListener("input", (e) => {
        const query = e.target.value;
        state.filters.searchQuery = query;
        renderScreenerTableDOM();

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => doSearch(query), 120);
    });

    el.searchInput.addEventListener("focus", (e) => {
        if (e.target.value.trim().length > 0) {
            doSearch(e.target.value);
        }
    });

    el.searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            const query = e.target.value.trim().toUpperCase();
            if (query.length > 0) {
                if (el.autocompleteDropdown && el.autocompleteDropdown.children.length > 0) {
                    const firstItem = el.autocompleteDropdown.children[0];
                    const sym = firstItem.getAttribute("data-symbol") || query;
                    window.selectSearchResult(sym);
                } else {
                    window.selectSearchResult(query);
                }
            }
        } else if (e.key === "Escape") {
            if (el.autocompleteDropdown) el.autocompleteDropdown.style.display = "none";
        }
    });

    document.addEventListener("click", (e) => {
        if (el.autocompleteDropdown && !el.searchInput.contains(e.target) && !el.autocompleteDropdown.contains(e.target)) {
            el.autocompleteDropdown.style.display = "none";
        }
    });
}

function renderAutocompleteDOM(results) {
    if (!el.autocompleteDropdown) return;
    if (results.length === 0) {
        el.autocompleteDropdown.style.display = "none";
        return;
    }

    let html = "";
    results.forEach(r => {
        html += `
        <div class="autocomplete-item" data-symbol="${r.symbol}" onclick="window.selectSearchResult('${r.symbol}')">
            <div style="display:flex; align-items:center;">
                <span class="autocomplete-sym">${r.symbol}</span>
                <span class="autocomplete-name">${r.name}</span>
            </div>
            <span style="font-size:10px; color:var(--text-dim);">${r.sector}</span>
        </div>`;
    });

    el.autocompleteDropdown.innerHTML = html;
    el.autocompleteDropdown.style.display = "block";
}

window.selectSearchResult = function (symbol) {
    if (el.searchInput) el.searchInput.value = symbol;
    if (el.autocompleteDropdown) el.autocompleteDropdown.style.display = "none";
    state.filters.searchQuery = symbol;
    renderScreenerTableDOM();
    window.openStockDossier(symbol);
};

/* ==========================================================================
   11. MOBILE DOCK NAVIGATION CONTROLLER
   ========================================================================== */

window.switchMobileStocksView = function (view) {
    const btnSetups = document.getElementById("mob-btn-setups");
    const btnScreener = document.getElementById("mob-btn-screener");
    const btnHeatmap = document.getElementById("mob-btn-heatmap");
    const btnAll = document.getElementById("mob-btn-all");

    if (btnSetups) btnSetups.classList.toggle("active", view === "setups");
    if (btnScreener) btnScreener.classList.toggle("active", view === "screener");
    if (btnHeatmap) btnHeatmap.classList.toggle("active", view === "heatmap");
    if (btnAll) btnAll.classList.toggle("active", view === "all");

    const secBuyNow = document.getElementById("section-buy-now");
    const secScreener = document.getElementById("section-screener");
    const secHeatmap = document.getElementById("sector-heatmap-section");
    const secControls = document.querySelector(".controls-deck");

    if (window.innerWidth <= 900) {
        if (view === "setups") {
            if (secBuyNow) secBuyNow.style.display = "flex";
            if (secControls) secControls.style.display = "none";
            if (secScreener) secScreener.style.display = "none";
            if (secHeatmap) secHeatmap.style.display = "none";
        } else if (view === "screener") {
            if (secBuyNow) secBuyNow.style.display = "none";
            if (secControls) secControls.style.display = "flex";
            if (secScreener) secScreener.style.display = "block";
            if (secHeatmap) secHeatmap.style.display = "none";
        } else if (view === "heatmap") {
            if (secBuyNow) secBuyNow.style.display = "none";
            if (secControls) secControls.style.display = "none";
            if (secScreener) secScreener.style.display = "none";
            if (secHeatmap) {
                secHeatmap.style.display = "flex";
                if (!state.heatmapLoaded) fetchHeatmapData();
            }
        } else if (view === "all") {
            if (secBuyNow) secBuyNow.style.display = "flex";
            if (secControls) secControls.style.display = "flex";
            if (secScreener) secScreener.style.display = "block";
            if (secHeatmap) secHeatmap.style.display = "none";
        }
    }
};

/* ==========================================================================
   12. GLOBAL INITIALIZATION
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    initSearchController();
    fetchScreenerData();
    fetchAlerts();
    startAutoScanTicker();
    if (window.innerWidth <= 900) {
        window.switchMobileStocksView("setups");
    }
});

window.addEventListener("resize", () => {
    if (window.innerWidth <= 900) {
        window.switchMobileStocksView(state.activeMobileView || "setups");
    } else {
        const secBuyNow = document.getElementById("section-buy-now");
        const secScreener = document.getElementById("section-screener");
        const secHeatmap = document.getElementById("sector-heatmap-section");
        const secControls = document.querySelector(".controls-deck");
        if (secBuyNow) secBuyNow.style.display = "block";
        if (secControls) secControls.style.display = "block";
        if (secScreener) secScreener.style.display = "block";
        if (secHeatmap) secHeatmap.style.display = state.heatmapVisible ? "block" : "none";
    }
});

})();

