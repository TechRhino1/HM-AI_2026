/**
 * JARVIS AI 3.0 — India Markets (NSE/BSE & F&O Intelligence) Client Controller
 */

(function () {
    'use strict';

    // Application State
    const state = {
        stocks: [],
        filteredStocks: [],
        activeSymbol: "NIFTY",
        activeTimeframe: "1D",
        filters: {
            sector: "all",
            market: "all",
            cpr: "all",
            minProb: 0,
            searchQuery: "",
            sortBy: "probability",
            sortDir: "desc"
        },
        chartInstance: null,
        candleSeries: null,
        volumeSeries: null,
        dossierOpen: false,
        currentDossier: null,
        strategyBias: "BULLISH",
        autoScanInterval: 30,
        countdown: 30,
        heatmapOpen: false
    };

    // DOM Elements Cache
    const el = {
        searchInput: document.getElementById("india-search-input"),
        autocompleteDropdown: document.getElementById("india-search-autocomplete"),
        indicesTrack: document.getElementById("indices-track"),
        screenerTableBody: document.getElementById("screener-table-tbody"),
        tableCountBadge: document.getElementById("table-count-badge"),
        aiBuyNowGrid: document.getElementById("ai-buy-now-grid"),
        heatmapSection: document.getElementById("sector-heatmap-section"),
        heatmapGrid: document.getElementById("sector-heatmap-grid"),
        scanCountdown: document.getElementById("scan-countdown"),

        // FII / DII Ribbon
        fiiCashVal: document.getElementById("fii-cash-val"),
        diiCashVal: document.getElementById("dii-cash-val"),
        fiiLongVal: document.getElementById("fii-long-val"),
        niftyPcrVal: document.getElementById("nifty-pcr-val"),

        // Dossier Modal
        dossierModal: document.getElementById("india-dossier-modal"),
        dossierTicker: document.getElementById("dossier-ticker"),
        dossierGradeBadge: document.getElementById("dossier-grade-badge"),
        dossierOppState: document.getElementById("dossier-opp-state"),
        dossierCompany: document.getElementById("dossier-company"),
        dossierLivePrice: document.getElementById("dossier-live-price"),
        dossierChangeBadge: document.getElementById("dossier-change-badge"),
        dossierProbVal: document.getElementById("dossier-prob-val"),
        dossierProbFill: document.getElementById("dossier-prob-fill"),
        dossierCprTag: document.getElementById("dossier-cpr-tag"),
        dossierCamH4: document.getElementById("dossier-cam-h4"),
        dossierVwapTag: document.getElementById("dossier-vwap-tag"),
        dossierLotSize: document.getElementById("dossier-lot-size"),
        dossierOptSym: document.getElementById("dossier-opt-sym"),
        chartContainer: document.getElementById("dossier-tv-chart"),
        multiTfGrid: document.getElementById("multi-tf-grid"),
        newsContainer: document.getElementById("dossier-news-list"),

        // Trade Plan
        planEntry: document.getElementById("plan-entry"),
        planSl: document.getElementById("plan-sl"),
        planTp1: document.getElementById("plan-tp1"),
        planTp2: document.getElementById("plan-tp2"),
        planRr: document.getElementById("plan-rr"),

        // Position Calculator
        calcEquity: document.getElementById("calc-equity-input"),
        calcRiskPct: document.getElementById("calc-risk-pct-input"),
        calcLots: document.getElementById("calc-out-lots"),
        calcShares: document.getElementById("calc-out-shares"),
        calcCapital: document.getElementById("calc-out-capital"),
        calcLoss: document.getElementById("calc-out-loss"),
        calcProfit: document.getElementById("calc-out-profit"),
        calcRrTag: document.getElementById("calc-rr-tag"),

        // CPR breakdown
        cprTcVal: document.getElementById("cpr-tc-val"),
        cprPVal: document.getElementById("cpr-p-val"),
        cprBcVal: document.getElementById("cpr-bc-val"),
        cprWidthVal: document.getElementById("cpr-width-val"),

        // Option Chain Modal
        optModal: document.getElementById("india-opt-modal"),
        optChainTicker: document.getElementById("opt-chain-ticker"),
        optChainSpotInfo: document.getElementById("opt-chain-spot-info"),
        optMaxPainBadge: document.getElementById("opt-max-pain-badge"),
        optPcrBadge: document.getElementById("opt-pcr-badge"),
        optChainTbody: document.getElementById("opt-chain-tbody"),

        // Strategy Builder Modal
        stratModal: document.getElementById("india-strategy-modal"),
        stratModalTicker: document.getElementById("strat-modal-ticker"),
        stratPayloadContainer: document.getElementById("strategy-payload-container")
    };

    /* ==========================================================================
       1. DATA FETCHING & TELEMETRY
       ========================================================================== */

    async function fetchIndicesTelemetry() {
        try {
            const res = await fetch("/api/india/indices");
            const data = await res.json();
            if (data && data.indices && el.indicesTrack) {
                renderIndicesTrackDOM(data.indices);
            }
        } catch (err) {
            console.error("Indices fetch error:", err);
        }
    }

    async function fetchFiiDiiData() {
        try {
            const res = await fetch("/api/india/fii_dii");
            const data = await res.json();
            if (data) {
                if (el.fiiCashVal) el.fiiCashVal.textContent = `+₹${data.fii_cash_net_cr.toLocaleString()} Cr`;
                if (el.diiCashVal) el.diiCashVal.textContent = `+₹${data.dii_cash_net_cr.toLocaleString()} Cr`;
                if (el.fiiLongVal) el.fiiLongVal.textContent = `${data.fii_index_futures_long_pct}%`;
                if (el.niftyPcrVal) el.niftyPcrVal.textContent = `${data.fii_index_options_pcr} (Bullish Floor)`;
            }
        } catch (err) {
            console.error("FII/DII fetch error:", err);
        }
    }

    async function fetchScannerData() {
        try {
            const params = new URLSearchParams({
                sector: state.filters.sector,
                market: state.filters.market,
                cpr: state.filters.cpr,
                min_prob: state.filters.minProb,
                sort_by: state.filters.sortBy,
                sort_dir: state.filters.sortDir
            });

            const res = await fetch(`/api/india/scanner?${params.toString()}`);
            const data = await res.json();
            if (data && data.stocks) {
                state.stocks = data.stocks;
                renderScreenerTableDOM();
                if (data.ai_recommended_buys && el.aiBuyNowGrid) {
                    renderAiBuyNowDOM(data.ai_recommended_buys);
                }
            }
        } catch (err) {
            console.error("Scanner fetch error:", err);
        }
    }

    async function fetchStockDossier(symbol) {
        try {
            const res = await fetch(`/api/india/details?symbol=${symbol}&tf=${state.activeTimeframe}`);
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

    function renderIndicesTrackDOM(indices) {
        let html = "";
        indices.forEach(idx => {
            const isPos = idx.change_pct >= 0;
            const chgColor = isPos ? "var(--neon-bull)" : "var(--neon-bear)";
            const chgSign = isPos ? "+" : "";

            html += `
            <div class="index-pill" onclick="window.openIndiaDossier('${idx.symbol}')">
                <b style="color:#ffffff;">${idx.symbol}</b>
                <span class="mono-num" style="color:#ffffff;">₹${Number(idx.price).toLocaleString(undefined, {minimumFractionDigits:2})}</span>
                <span class="mono-num" style="color:${chgColor}; font-weight:800;">${chgSign}${idx.change_pct}%</span>
                <span class="badge ${idx.cpr_width === 'NARROW_CPR' ? 'badge-cpr-narrow' : 'badge-cpr-wide'}">
                    ${idx.cpr_width === 'NARROW_CPR' ? '⚡ Narrow CPR' : 'Wide CPR'}
                </span>
            </div>`;
        });
        el.indicesTrack.innerHTML = html;
    }

    function renderAiBuyNowDOM(buys) {
        if (!el.aiBuyNowGrid || !buys || buys.length === 0) return;

        let html = "";
        buys.forEach(b => {
            const isPos = b.change_pct >= 0;
            const chgSign = isPos ? "+" : "";

            html += `
            <div class="buy-now-card" onclick="window.openIndiaDossier('${b.symbol}')">
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <span style="font-size:16px; font-weight:900; color:#ffffff;">${b.symbol}</span>
                            <span class="badge-grade-a-plus">${b.grade_badge || 'A+'}</span>
                        </div>
                        <div style="font-size:11px; color:var(--text-dim);">${b.name}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:15px; font-weight:900; font-family:var(--font-mono); color:#ffffff;">₹${Number(b.price).toLocaleString(undefined, {minimumFractionDigits:2})}</div>
                        <span style="font-size:11px; font-weight:800; color:${isPos ? 'var(--neon-bull)' : 'var(--neon-bear)'};">${chgSign}${b.change_pct}%</span>
                    </div>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px;">
                    <span style="color:var(--accent-cyan); font-weight:800; font-family:var(--font-mono);">
                        🔥 ${b.breakout_probability}% AI Probability
                    </span>
                    <span style="color:var(--neon-bull); font-weight:800; font-family:var(--font-mono);">
                        Est. Gain: +${b.expected_gain_pct}%
                    </span>
                </div>

                <div class="buy-now-plan-grid">
                    <div>
                        <div style="color:var(--text-dim); font-size:9px;">Entry Trigger</div>
                        <div style="font-weight:800; color:var(--accent-cyan); font-family:var(--font-mono);">₹${Number(b.entry_zone).toFixed(2)}</div>
                    </div>
                    <div>
                        <div style="color:var(--text-dim); font-size:9px;">Target (TP2)</div>
                        <div style="font-weight:800; color:var(--neon-bull); font-family:var(--font-mono);">₹${Number(b.take_profit_2).toFixed(2)}</div>
                    </div>
                    <div>
                        <div style="color:var(--text-dim); font-size:9px;">Stop Loss</div>
                        <div style="font-weight:800; color:var(--neon-bear); font-family:var(--font-mono);">₹${Number(b.stop_loss).toFixed(2)}</div>
                    </div>
                </div>

                <button class="btn-buy-now-cta" onclick="event.stopPropagation(); window.openIndiaDossier('${b.symbol}')">
                    <span>⚡</span> Open NSE Intelligence Dossier ➔
                </button>
            </div>`;
        });

        el.aiBuyNowGrid.innerHTML = html;
    }

    function renderScreenerTableDOM() {
        if (!el.screenerTableBody) return;

        let list = state.stocks.filter(s => !s.is_index && s.sector !== "Indices");

        // Search query filter
        const q = state.filters.searchQuery.toLowerCase().trim();
        if (q) {
            list = list.filter(s => s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q));
        }

        state.filteredStocks = list;
        if (el.tableCountBadge) el.tableCountBadge.textContent = `${list.length} Corporate Stocks Analyzed`;

        if (list.length === 0) {
            el.screenerTableBody.innerHTML = `
                <tr>
                    <td colspan="13" style="text-align:center; padding:35px 20px; color:var(--text-secondary);">
                        No Indian equities/indices matched the current filter. Try resetting criteria.
                    </td>
                </tr>`;
            return;
        }

        let html = "";
        list.forEach(st => {
            const isPos = st.change_pct >= 0;
            const chgColor = isPos ? "var(--neon-bull)" : "var(--neon-bear)";
            const chgSign = isPos ? "+" : "";

            let gradeBadge = "badge-grade-a";
            if (st.grade_badge === "A+") gradeBadge = "badge-grade-a-plus";
            else if (st.grade_badge === "B") gradeBadge = "badge-grade-a";

            const cprClass = st.cpr.width_classification === "NARROW_CPR" ? "badge-cpr-narrow" : "badge-cpr-wide";
            const cprText = st.cpr.width_classification === "NARROW_CPR" ? "⚡ Narrow CPR" : "Wide CPR";

            html += `
            <tr onclick="window.openIndiaDossier('${st.symbol}')">
                <td><span class="${gradeBadge}">${st.setup_grade || 'GRADE A'}</span></td>
                <td>
                    <div>
                        <b style="font-size:13px; color:#ffffff;">${st.symbol}</b>
                        <div style="font-size:10px; color:var(--text-dim);">${st.name}</div>
                    </div>
                </td>
                <td>
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span class="badge ${cprClass}">${cprText} (${st.cpr.width_pct}%)</span>
                        <span style="font-size:10px; color:var(--text-dim);">P: ₹${st.cpr.pivot}</span>
                    </div>
                </td>
                <td class="mono-num" style="color:var(--neon-bull); font-weight:800;">₹${st.camarilla.h4_breakout}</td>
                <td class="mono-num" style="color:${st.vwap_dist_pct >= 0 ? 'var(--neon-bull)' : 'var(--neon-bear)'};">
                    ₹${st.vwap} (${st.vwap_dist_pct >= 0 ? '+' : ''}${st.vwap_dist_pct}%)
                </td>
                <td class="mono-num" style="color:#ffffff; font-size:13px; font-weight:800;">₹${Number(st.price).toLocaleString(undefined, {minimumFractionDigits:2})}</td>
                <td class="mono-num" style="color:${chgColor}; font-weight:800;">${chgSign}${st.change_pct}%</td>
                <td>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <div style="flex:1; height:6px; background:rgba(30,41,59,0.8); border-radius:3px; overflow:hidden;">
                            <div style="width:${st.breakout_probability}%; height:100%; background:var(--neon-bull);"></div>
                        </div>
                        <span class="mono-num" style="font-weight:800; color:#ffffff; font-size:11px;">${st.breakout_probability}%</span>
                    </div>
                </td>
                <td class="mono-num" style="color:var(--accent-cyan); font-weight:800;">${st.rvol}x</td>
                <td class="mono-num" style="color:var(--text-secondary);">${st.lot_size} sh</td>
                <td><span class="badge badge-strong-buy">${st.opportunity_state}</span></td>
                <td><span style="font-size:11px; font-weight:700; color:var(--text-secondary);">${st.recommendation}</span></td>
                <td style="text-align:right;">
                    <div style="display:inline-flex; gap:4px;" onclick="event.stopPropagation();">
                        <button class="btn-action-tool" style="padding:3px 8px; font-size:10px;" onclick="window.openIndiaDossier('${st.symbol}')">Dossier ➔</button>
                        <button class="btn-action-tool" style="padding:3px 8px; font-size:10px; border-color:var(--neon-bull);" onclick="window.openOptionChainModal('${st.symbol}')">F&O ⚡</button>
                    </div>
                </td>
            </tr>`;
        });

        el.screenerTableBody.innerHTML = html;
    }

    /* ==========================================================================
       3. STOCK DOSSIER MODAL & CHART RENDERING
       ========================================================================== */

    function renderDossierDOM(data) {
        if (!data) return;
        state.activeSymbol = data.symbol;
        state.currentDossier = data;

        if (el.dossierTicker) el.dossierTicker.textContent = data.symbol;
        if (el.dossierOptSym) el.dossierOptSym.textContent = data.symbol;
        if (el.dossierCompany) el.dossierCompany.textContent = `${data.name} • ${data.sector} • ${data.market_cap}`;
        if (el.dossierLivePrice) el.dossierLivePrice.textContent = `₹${Number(data.current_price).toLocaleString(undefined, {minimumFractionDigits:2})}`;
        
        if (el.dossierChangeBadge) {
            const isPos = data.change_pct >= 0;
            el.dossierChangeBadge.textContent = `${isPos ? '+' : ''}${data.change_pct}% (${isPos ? '+₹' : '-₹'}${Math.abs(data.change_val)})`;
            el.dossierChangeBadge.style.color = isPos ? "var(--neon-bull)" : "var(--neon-bear)";
        }

        if (el.dossierProbVal) el.dossierProbVal.textContent = `${data.breakout_probability}%`;
        if (el.dossierProbFill) el.dossierProbFill.style.width = `${data.breakout_probability}%`;
        if (el.dossierCprTag) el.dossierCprTag.textContent = data.cpr.width_label;
        if (el.dossierCamH4) el.dossierCamH4.textContent = `₹${data.camarilla.h4_breakout}`;
        if (el.dossierVwapTag) el.dossierVwapTag.textContent = `${data.vwap_structure.distance_from_vwap_pct >= 0 ? '+' : ''}${data.vwap_structure.distance_from_vwap_pct}% vs VWAP`;
        if (el.dossierLotSize) el.dossierLotSize.textContent = `${data.lot_size} Shares`;

        // Trade Plan
        const plan = data.trade_setup || {};
        if (el.planEntry) el.planEntry.textContent = `₹${Number(plan.entry_zone || data.current_price).toFixed(2)}`;
        if (el.planSl) el.planSl.textContent = `₹${Number(plan.stop_loss || 0).toFixed(2)}`;
        if (el.planTp1) el.planTp1.textContent = `₹${Number(plan.take_profit_1 || 0).toFixed(2)}`;
        if (el.planTp2) el.planTp2.textContent = `₹${Number(plan.take_profit_2 || 0).toFixed(2)}`;
        if (el.planRr) el.planRr.textContent = plan.risk_reward_ratio || "1:2.25";

        // CPR breakdown
        if (el.cprTcVal) el.cprTcVal.textContent = `₹${data.cpr.tc}`;
        if (el.cprPVal) el.cprPVal.textContent = `₹${data.cpr.pivot}`;
        if (el.cprBcVal) el.cprBcVal.textContent = `₹${data.cpr.bc}`;
        if (el.cprWidthVal) el.cprWidthVal.textContent = `${data.cpr.width_pct}% (${data.cpr.width_classification})`;

        // Multi-TF Grid
        if (el.multiTfGrid && data.multi_timeframe) {
            let mHtml = "";
            const tfs = ["5M", "15M", "1H", "1D", "1W"];
            tfs.forEach(tfKey => {
                const item = data.multi_timeframe[tfKey] || { bias: "NEUTRAL", strength: 50 };
                const isBull = item.bias === "BULLISH";
                mHtml += `
                <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border-subtle); border-radius:4px; padding:6px; text-align:center;">
                    <div style="font-size:10px; color:var(--text-dim);">${tfKey}</div>
                    <div style="font-weight:800; font-size:11px; color:${isBull ? 'var(--neon-bull)' : 'var(--neon-bear)'};">${item.bias}</div>
                    <div style="font-size:9px; color:var(--text-dim);">${item.strength}%</div>
                </div>`;
            });
            el.multiTfGrid.innerHTML = mHtml;
        }

        // News Feed
        if (el.newsContainer && data.news) {
            let nHtml = "";
            data.news.forEach(n => {
                nHtml += `
                <div style="border-bottom:1px solid rgba(51,65,85,0.2); padding-bottom:6px; margin-bottom:6px;">
                    <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--text-dim);">
                        <span>${n.source}</span>
                        <span style="color:var(--neon-bull); font-weight:800;">${n.sentiment}</span>
                    </div>
                    <div style="font-size:11px; font-weight:700; color:#ffffff; margin-top:2px;">${n.headline}</div>
                </div>`;
            });
            el.newsContainer.innerHTML = nHtml;
        }

        // Render Chart
        initDossierChart(data.candles, data.cpr, data.camarilla);

        // Update position size calculator
        window.updatePositionCalculator();

        if (el.dossierModal) {
            el.dossierModal.style.display = "flex";
            state.dossierOpen = true;
        }
    }

    function initDossierChart(candles, cpr, camarilla) {
        if (!el.chartContainer || !candles || candles.length === 0) return;
        if (typeof LightweightCharts === "undefined") return;

        el.chartContainer.innerHTML = "";

        const width = el.chartContainer.clientWidth || 550;
        const height = el.chartContainer.clientHeight || 320;

        const chart = LightweightCharts.createChart(el.chartContainer, {
            width: width,
            height: height,
            layout: {
                background: { color: "#060a14" },
                textColor: "#94a3b8",
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace"
            },
            grid: {
                vertLines: { color: "rgba(51, 65, 85, 0.2)" },
                horzLines: { color: "rgba(51, 65, 85, 0.2)" }
            },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            rightPriceScale: { borderColor: "rgba(51, 65, 85, 0.4)" },
            timeScale: { borderColor: "rgba(51, 65, 85, 0.4)", timeVisible: true }
        });

        const candleSeries = chart.addCandlestickSeries({
            upColor: "#00f59b",
            downColor: "#ff3b5c",
            borderUpColor: "#00f59b",
            borderDownColor: "#ff3b5c",
            wickUpColor: "#00f59b",
            wickDownColor: "#ff3b5c"
        });

        const sorted = candles.map(c => ({
            time: typeof c.time === "number" ? c.time : Math.floor(new Date(c.time).getTime() / 1000),
            open: Number(c.open),
            high: Number(c.high),
            low: Number(c.low),
            close: Number(c.close)
        })).sort((a, b) => a.time - b.time);

        candleSeries.setData(sorted);
        chart.timeScale().fitContent();

        // Draw CPR Pivot lines
        if (cpr) {
            candleSeries.createPriceLine({
                price: cpr.tc,
                color: "#00d4ff",
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                title: `CPR TC: ₹${cpr.tc}`
            });
            candleSeries.createPriceLine({
                price: cpr.pivot,
                color: "#fbbf24",
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                title: `CPR Pivot: ₹${cpr.pivot}`
            });
            candleSeries.createPriceLine({
                price: cpr.bc,
                color: "#00d4ff",
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                title: `CPR BC: ₹${cpr.bc}`
            });
        }

        // Draw Camarilla H4 breakout line
        if (camarilla && camarilla.h4_breakout) {
            candleSeries.createPriceLine({
                price: camarilla.h4_breakout,
                color: "#00f59b",
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                title: `Cam H4 Breakout: ₹${camarilla.h4_breakout}`
            });
        }

        state.chartInstance = chart;
        state.candleSeries = candleSeries;
    }

    /* ==========================================================================
       4. POSITION SIZE & BROKER ORDER GENERATOR
       ========================================================================== */

    window.updatePositionCalculator = function () {
        if (!state.currentDossier) return;
        const d = state.currentDossier;
        const equity = parseFloat(el.calcEquity ? el.calcEquity.value : 500000) || 500000;
        const riskPct = parseFloat(el.calcRiskPct ? el.calcRiskPct.value : 1.0) || 1.0;

        const entry = Number(d.trade_setup ? d.trade_setup.entry_zone : d.current_price) || d.current_price;
        const sl = Number(d.trade_setup ? d.trade_setup.stop_loss : (entry * 0.98)) || (entry * 0.98);
        const tp = Number(d.trade_setup ? d.trade_setup.take_profit_2 : (entry * 1.05)) || (entry * 1.05);
        const lotSize = d.lot_size || 100;

        const riskBudgetInr = Math.max(100, equity * (riskPct / 100.0));
        const perShareRisk = Math.max(0.05, Math.abs(entry - sl));
        const perLotRisk = perShareRisk * lotSize;

        const rawLots = Math.floor(riskBudgetInr / perLotRisk);
        const lots = Math.max(1, rawLots);
        const shares = lots * lotSize;

        const totalCapital = shares * entry;
        const actualRisk = shares * perShareRisk;
        const actualProfit = shares * Math.abs(tp - entry);
        const rrRatio = (actualProfit / actualRisk).toFixed(2);

        if (el.calcLots) el.calcLots.textContent = `${lots} Lots`;
        if (el.calcShares) el.calcShares.textContent = `${shares.toLocaleString()} sh`;
        if (el.calcCapital) el.calcCapital.textContent = `₹${totalCapital.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}`;
        if (el.calcLoss) el.calcLoss.textContent = `-₹${actualRisk.toFixed(2)}`;
        if (el.calcProfit) el.calcProfit.textContent = `+₹${actualProfit.toFixed(2)}`;
        if (el.calcRrTag) el.calcRrTag.textContent = `R:R 1:${rrRatio}`;
    };

    window.copyBrokerOrder = function () {
        if (!state.currentDossier) return;
        const d = state.currentDossier;
        const equity = parseFloat(el.calcEquity ? el.calcEquity.value : 500000) || 500000;
        const riskPct = parseFloat(el.calcRiskPct ? el.calcRiskPct.value : 1.0) || 1.0;

        const entry = Number(d.trade_setup ? d.trade_setup.entry_zone : d.current_price) || d.current_price;
        const sl = Number(d.trade_setup ? d.trade_setup.stop_loss : (entry * 0.98)) || (entry * 0.98);
        const tp = Number(d.trade_setup ? d.trade_setup.take_profit_2 : (entry * 1.05)) || (entry * 1.05);
        const lotSize = d.lot_size || 100;

        const riskBudgetInr = Math.max(100, equity * (riskPct / 100.0));
        const perShareRisk = Math.max(0.05, Math.abs(entry - sl));
        const lots = Math.max(1, Math.floor(riskBudgetInr / (perShareRisk * lotSize)));
        const shares = lots * lotSize;

        const ticket = `BUY ${shares} ${d.symbol} (CNC/NRML) @ ₹${entry.toFixed(2)} | SL: ₹${sl.toFixed(2)} | TP: ₹${tp.toFixed(2)} | MaxRisk: ₹${(shares * perShareRisk).toFixed(2)}`;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(ticket).then(() => {
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
            prompt("Zerodha / Upstox Order Ticket:", ticket);
        }
    };

    /* ==========================================================================
       5. OPTION CHAIN CONTROLLER
       ========================================================================== */

    window.openOptionChainModal = async function (symbol) {
        const sym = symbol || state.activeSymbol || "NIFTY";
        if (el.optModal) {
            el.optModal.style.display = "flex";
            if (el.optChainTicker) el.optChainTicker.textContent = sym;
            if (el.optChainTbody) {
                el.optChainTbody.innerHTML = `<tr><td colspan="11" style="text-align:center; padding:30px; color:var(--text-dim);">Fetching live ${sym} Option Chain and calculating Greeks...</td></tr>`;
            }

            try {
                const res = await fetch(`/api/india/option_chain?symbol=${sym}`);
                const data = await res.json();
                if (data && data.chain) {
                    renderOptionChainDOM(data);
                }
            } catch (err) {
                if (el.optChainTbody) el.optChainTbody.innerHTML = `<tr><td colspan="11" style="color:var(--neon-bear); text-align:center; padding:20px;">Option Chain error: ${err.message}</td></tr>`;
            }
        }
    };

    window.closeOptionChainModal = function () {
        if (el.optModal) el.optModal.style.display = "none";
    };

    function renderOptionChainDOM(data) {
        if (!el.optChainTbody) return;

        if (el.optChainSpotInfo) {
            el.optChainSpotInfo.textContent = `Spot: ₹${Number(data.spot_price).toFixed(2)} • ATM Strike: ${data.atm_strike} • Lot Size: ${data.lot_size} • Expiry: ${data.expiry}`;
        }
        if (el.optMaxPainBadge) el.optMaxPainBadge.textContent = `Max Pain: ${data.max_pain_strike}`;
        if (el.optPcrBadge) el.optPcrBadge.textContent = `PCR: ${data.pcr.pcr_oi} (${data.pcr.sentiment})`;

        let html = "";
        data.chain.forEach(row => {
            const isAtm = row.is_atm;
            const rowClass = isAtm ? "atm-strike-row" : "";
            const call = row.call;
            const put = row.put;

            const callItm = call.is_itm ? "itm-call" : "";
            const putItm = put.is_itm ? "itm-put" : "";

            html += `
            <tr class="${rowClass}">
                <!-- CALLS -->
                <td class="${callItm}" style="color:${call.oi_change_pct >= 0 ? 'var(--neon-bull)' : 'var(--neon-bear)'}; font-weight:700;">
                    ${call.oi_change_pct >= 0 ? '+' : ''}${call.oi_change_pct}%
                </td>
                <td class="${callItm}">${call.oi.toLocaleString()}</td>
                <td class="${callItm}" style="color:var(--text-dim);">${call.volume.toLocaleString()}</td>
                <td class="${callItm}">${call.iv}%</td>
                <td class="${callItm}" style="color:#ffffff; font-weight:800;">₹${call.ltp}</td>

                <!-- STRIKE -->
                <td class="strike-cell">${row.strike}</td>

                <!-- PUTS -->
                <td class="${putItm}" style="color:#ffffff; font-weight:800;">₹${put.ltp}</td>
                <td class="${putItm}">${put.iv}%</td>
                <td class="${putItm}" style="color:var(--text-dim);">${put.volume.toLocaleString()}</td>
                <td class="${putItm}">${put.oi.toLocaleString()}</td>
                <td class="${putItm}" style="color:${put.oi_change_pct >= 0 ? 'var(--neon-bull)' : 'var(--neon-bear)'}; font-weight:700;">
                    ${put.oi_change_pct >= 0 ? '+' : ''}${put.oi_change_pct}%
                </td>
            </tr>`;
        });

        el.optChainTbody.innerHTML = html;
    }

    /* ==========================================================================
       6. AI DEFINED-RISK STRATEGY BUILDER
       ========================================================================== */

    window.openAiStrategyModal = async function (symbol) {
        const sym = symbol || state.activeSymbol || "NIFTY";
        if (el.stratModal) {
            el.stratModal.style.display = "flex";
            if (el.stratModalTicker) el.stratModalTicker.textContent = sym;
            fetchAiStrategy(sym, state.strategyBias);
        }
    };

    window.closeAiStrategyModal = function () {
        if (el.stratModal) el.stratModal.style.display = "none";
    };

    window.setStrategyBias = function (bias, btn) {
        state.strategyBias = bias;
        document.querySelectorAll(".strat-bias-btn").forEach(b => b.classList.remove("active"));
        if (btn) btn.classList.add("active");
        fetchAiStrategy(state.activeSymbol, bias);
    };

    async function fetchAiStrategy(symbol, bias) {
        if (!el.stratPayloadContainer) return;
        el.stratPayloadContainer.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-dim);">Optimizing defined-risk ${bias} options spread for ${symbol}...</div>`;

        try {
            const res = await fetch(`/api/india/options_ai?symbol=${symbol}&bias=${bias}`);
            const data = await res.json();
            if (data && data.legs) {
                renderStrategyDOM(data);
            }
        } catch (err) {
            el.stratPayloadContainer.innerHTML = `<div style="color:var(--neon-bear); text-align:center; padding:20px;">Strategy generation error: ${err.message}</div>`;
        }
    }

    function renderStrategyDOM(data) {
        let legsHtml = "";
        data.legs.forEach(leg => {
            const isBuy = leg.action === "BUY";
            legsHtml += `
            <div style="background:var(--bg-elevated); border:1px solid var(--border-subtle); border-radius:6px; padding:10px 12px; display:flex; justify-content:space-between; align-items:center;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="badge ${isBuy ? 'badge-strong-buy' : 'badge-prime'}">${leg.action}</span>
                    <b style="color:#ffffff; font-size:13px;">${leg.strike} ${leg.type}</b>
                    <span style="font-size:11px; color:var(--text-dim);">(${leg.expiry})</span>
                </div>
                <div class="mono-num" style="font-size:13px; font-weight:800; color:#ffffff;">
                    ₹${leg.price} (Lot: ${leg.lot_size})
                </div>
            </div>`;
        });

        el.stratPayloadContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:12px;">
            <div style="background:linear-gradient(135deg, rgba(0,245,155,0.08), rgba(0,212,255,0.08)); border:1px solid var(--border-bright); border-radius:8px; padding:12px;">
                <div style="font-size:15px; font-weight:900; color:#ffffff;">${data.strategy_name}</div>
                <div style="font-size:12px; color:var(--text-dim); margin-top:4px;">${data.rationale}</div>
            </div>

            <div style="display:flex; flex-direction:column; gap:8px;">
                ${legsHtml}
            </div>

            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:8px; margin-top:6px;">
                <div class="kpi-item">
                    <span class="kpi-label">Max Profit</span>
                    <span class="kpi-val text-bull">+₹${data.max_profit_inr.toLocaleString()}</span>
                </div>
                <div class="kpi-item">
                    <span class="kpi-label">Max Risk / Loss</span>
                    <span class="kpi-val text-bear">-₹${data.max_loss_inr.toLocaleString()}</span>
                </div>
                <div class="kpi-item">
                    <span class="kpi-label">Risk:Reward</span>
                    <span class="kpi-val text-gold">${data.risk_reward_ratio}</span>
                </div>
                <div class="kpi-item">
                    <span class="kpi-label">Prob of Profit</span>
                    <span class="kpi-val text-cyan">${data.probability_of_profit_pct}%</span>
                </div>
                <div class="kpi-item">
                    <span class="kpi-label">Margin Required</span>
                    <span class="kpi-val text-white">₹${data.estimated_margin_inr.toLocaleString()}</span>
                </div>
            </div>
        </div>`;
    }

    /* ==========================================================================
       7. SECTOR ROTATION HEATMAP CONTROLLER
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
            const res = await fetch("/api/india/heatmap");
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
            html += `
            <div class="heatmap-tile" onclick="window.setSectorFilter('${sec.sector}', null)">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="color:#ffffff; font-size:12px;">${sec.sector}</b>
                    <span class="mono-num" style="color:${isPos ? 'var(--neon-bull)' : 'var(--neon-bear)'}; font-weight:800;">
                        ${isPos ? '+' : ''}${sec.avg_change_pct}%
                    </span>
                </div>
                <div style="font-size:10px; color:var(--text-dim); margin-top:4px;">
                    Top Leader: <b style="color:var(--neon-bull);">${sec.top_leader_symbol} (${sec.top_leader_change > 0 ? '+' : ''}${sec.top_leader_change}%)</b>
                </div>
            </div>`;
        });
        el.heatmapGrid.innerHTML = html;
    }

    /* ==========================================================================
       8. GLOBAL WINDOW ACTIONS
       ========================================================================== */

    window.openIndiaDossier = function (symbol) {
        state.activeSymbol = symbol;
        fetchStockDossier(symbol);
    };

    window.closeIndiaDossier = function () {
        if (el.dossierModal) el.dossierModal.style.display = "none";
        state.dossierOpen = false;
    };

    window.getCurrentDossierSymbol = function () {
        return state.activeSymbol || "NIFTY";
    };

    window.setSectorFilter = function (sector, btn) {
        state.filters.sector = sector;
        document.querySelectorAll(".sector-pill").forEach(p => p.classList.remove("active"));
        if (btn) btn.classList.add("active");
        fetchScannerData();
    };

    window.setCprFilter = function (cprType, btn) {
        state.filters.cpr = cprType;
        document.querySelectorAll(".cpr-pill").forEach(p => p.classList.remove("active"));
        if (btn) btn.classList.add("active");
        fetchScannerData();
    };

    window.setProbFilter = function (minProb, btn) {
        state.filters.minProb = minProb;
        document.querySelectorAll(".prob-pill").forEach(p => p.classList.remove("active"));
        if (btn) btn.classList.add("active");
        fetchScannerData();
    };

    window.sortTableBy = function (columnKey) {
        if (state.filters.sortBy === columnKey) {
            state.filters.sortDir = (state.filters.sortDir === "asc") ? "desc" : "asc";
        } else {
            state.filters.sortBy = columnKey;
            state.filters.sortDir = "desc";
        }
        fetchScannerData();
    };

    window.setDossierTf = function (tf, btn) {
        state.activeTimeframe = tf;
        document.querySelectorAll(".stock-tf-btn").forEach(b => b.classList.remove("active"));
        if (btn) btn.classList.add("active");
        fetchStockDossier(state.activeSymbol);
    };

    window.exportIndiaCsv = function () {
        window.location.href = `/api/india/export_csv?sector=${encodeURIComponent(state.filters.sector)}`;
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
                fetchScannerData();
                fetchIndicesTelemetry();
                fetchFiiDiiData();
            }
            if (el.scanCountdown) {
                el.scanCountdown.textContent = `${state.countdown}s`;
            }
        }, 1000);
    }

    /* ==========================================================================
       9. SEARCH CONTROLLER
       ========================================================================== */

    function initSearchController() {
        if (!el.searchInput) return;

        let debounceTimer = null;

        async function doSearch(query) {
            if (query.trim().length > 0) {
                try {
                    const res = await fetch(`/api/india/search?q=${encodeURIComponent(query)}`);
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

        el.searchInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                const query = e.target.value.trim().toUpperCase();
                if (query.length > 0) {
                    window.openIndiaDossier(query);
                    if (el.autocompleteDropdown) el.autocompleteDropdown.style.display = "none";
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
            <div class="autocomplete-item" onclick="window.selectSearchResult('${r.symbol}')">
                <div>
                    <b style="color:#ffffff;">${r.symbol}</b>
                    <span style="font-size:10px; color:var(--text-dim); margin-left:6px;">${r.name}</span>
                </div>
                <span style="font-size:10px; color:var(--neon-saffron);">${r.sector}</span>
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
        window.openIndiaDossier(symbol);
    };

    /* ==========================================================================
       10. INITIALIZATION
       ========================================================================== */

    document.addEventListener("DOMContentLoaded", () => {
        initSearchController();
        fetchIndicesTelemetry();
        fetchFiiDiiData();
        fetchScannerData();
        startAutoScanTicker();
    });

})();
