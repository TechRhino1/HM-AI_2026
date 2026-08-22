/**
 * JARVIS AI 3.0 â€” Advanced Institutional Financial Trading Terminal Controller
 * 
 * Features:
 * - TradingView Lightweight Charts v4 Integration (Live MT5 Candles + Volume + S/R Price Lines)
 * - TradingView Advanced Pro Real-Time Widget Switcher (Interactive Pine Script / Drawing Desk)
 * - Dynamic Active Support & Resistance Level Detection (R1/R2 & S1/S2)
 * - Fullscreen / Expand Chart Mode with Instant Responsive Re-scaling
 * - Smart Floating Tooltip with Structural AI Context
 * - High-Impact Macro Economic News Feed & Shock Calendar
 * - Live Position Close Actions (Individual 1-Click Close & Emergency Close All)
 * - High-Probability Opportunity Radar with 1-Click Manual Execution Desk
 * - Standalone Floating & Draggable Copilot Intelligence
 * - Global Spotlight Command Palette (Ctrl+K / Cmd+K)
 */

(function () {
    'use strict';

    // Terminal Application State
    const state = {
        symbol: "XAUUSD",
        timeframe: "H1",
        chartMode: "tv_live", // 'tv_live' or 'tv_pro'
        chartExpanded: false,
        candles: [],
        latestDecisions: {},
        radarOpportunities: [],
        positions: [],
        newsItems: [],
        account: null,
        executionMode: "LIVE",
        safeMode: false,
        copilotOpen: false,
        copilotMinimized: false,
        activeLeftTab: "radar",
        activeCommandIndex: 0,
        supportResistance: {
            r1: 0,
            r2: 0,
            s1: 0,
            s2: 0
        },
        tvChartInstance: null,
        tvCandleSeries: null,
        tvVolumeSeries: null,
        tvPriceLines: []
    };

    // DOM Elements Cache
    const el = {
        // Top HUD
        hudServer: document.getElementById("hud-server"),
        hudLogin: document.getElementById("hud-login"),
        hudBalance: document.getElementById("hud-balance"),
        hudEquity: document.getElementById("hud-equity"),
        hudFreeMargin: document.getElementById("hud-free-margin"),
        hudMarginLevel: document.getElementById("hud-margin-level"),
        hudSync: document.getElementById("hud-sync"),
        hudMarketStatus: document.getElementById("hud-market-status"),
        statusBadge: document.getElementById("status-badge"),
        execModeBadge: document.getElementById("exec-mode-badge"),

        // Account Details Panel (Left)
        accName: document.getElementById("acc-name"),
        accLeverage: document.getElementById("acc-leverage"),
        accCompany: document.getElementById("acc-company"),
        accLogin: document.getElementById("acc-login"),
        accBalance: document.getElementById("acc-balance"),
        accEquity: document.getElementById("acc-equity"),
        accProfit: document.getElementById("acc-profit"),
        accFreeMargin: document.getElementById("acc-free-margin"),

        // Left Panel Switcher
        tabBtnRadar: document.getElementById("tab-btn-radar"),
        tabBtnNews: document.getElementById("tab-btn-news"),
        tabContentRadar: document.getElementById("tab-content-radar"),
        tabContentNews: document.getElementById("tab-content-news"),
        leftPanelCounter: document.getElementById("left-panel-counter"),
        radarList: document.getElementById("radar-list"),
        newsFeedList: document.getElementById("news-feed-list"),

        // Right Panel Switcher
        tabBtnDesk: document.getElementById("tab-btn-desk"),
        tabBtnCognition: document.getElementById("tab-btn-cognition"),
        tabContentDesk: document.getElementById("tab-content-desk"),
        tabContentCognition: document.getElementById("tab-content-cognition"),

        // Manual Execution Desk & Summary Banner
        deskActiveSymbol: document.getElementById("desk-active-symbol"),
        deskMarketStatusBanner: document.getElementById("desk-market-status-banner"),
        deskMarketTitle: document.getElementById("desk-market-title"),
        deskMarketTime: document.getElementById("desk-market-time"),
        deskBannerTitle: document.getElementById("desk-banner-title"),
        deskBannerStatus: document.getElementById("desk-banner-status"),
        deskBannerEntry: document.getElementById("desk-banner-entry"),
        deskBannerSl: document.getElementById("desk-banner-sl"),
        deskBannerTp: document.getElementById("desk-banner-tp"),
        deskBannerRr: document.getElementById("desk-banner-rr"),
        deskBannerRisk: document.getElementById("desk-banner-risk"),
        deskBannerProb: document.getElementById("desk-banner-prob"),
        deskLots: document.getElementById("desk-lots"),
        deskWinProb: document.getElementById("desk-win-prob"),
        deskSl: document.getElementById("desk-sl"),
        deskTp: document.getElementById("desk-tp"),
        btnBuyAction: document.getElementById("btn-buy-action"),
        btnSellAction: document.getElementById("btn-sell-action"),

        // Chart Stage
        chartMainPanel: document.getElementById("chart-main-panel"),
        chartSymbol: document.getElementById("chart-symbol"),
        chartRegime: document.getElementById("chart-regime"),
        chartLivePrice: document.getElementById("chart-live-price"),
        chartMarketStatus: document.getElementById("chart-market-status"),
        tvLiveContainer: document.getElementById("tv-lightweight-chart-container"),
        tvProContainer: document.getElementById("tv-advanced-widget-container"),
        btnModeTvLive: document.getElementById("btn-mode-tv-live"),
        btnModeTvPro: document.getElementById("btn-mode-tv-pro"),
        btnExpandChart: document.getElementById("btn-expand-chart"),
        legendR1: document.getElementById("legend-r1"),
        legendS1: document.getElementById("legend-s1"),
        smartTooltip: document.getElementById("smart-chart-tooltip"),

        // Active Trades Table
        positionsTbody: document.getElementById("positions-tbody"),
        positionsCount: document.getElementById("pos-count"),

        // Trade History
        historyTbody: document.getElementById("history-tbody"),
        historyCount: document.getElementById("history-count"),

        // Devil's Advocate & Risk Panel
        planStrategyPill: document.getElementById("plan-strategy-pill"),
        planEntry: document.getElementById("plan-entry"),
        planSl: document.getElementById("plan-sl"),
        planTp: document.getElementById("plan-tp"),
        planRiskAmt: document.getElementById("plan-risk-amt"),
        planCalcLots: document.getElementById("plan-calc-lots"),
        btnBuyAction: document.getElementById("btn-buy-action"),
        btnSellAction: document.getElementById("btn-sell-action"),
        cognitionRr: document.getElementById("cognition-rr"),
        cognitionStrat: document.getElementById("cognition-strat"),
        gatePassCountTag: document.getElementById("gate-pass-count-tag"),
        decisionGateBadge: document.getElementById("decision-gate-badge"),
        decisionWinProb: document.getElementById("decision-win-prob"),
        decisionEv: document.getElementById("decision-ev"),
        decisionRr: document.getElementById("decision-rr"),
        devilPenaltyScore: document.getElementById("devil-penalty-score"),
        devilPenaltyFill: document.getElementById("devil-penalty-fill"),
        devilRiskCoeff: document.getElementById("devil-risk-coeff"),
        devilRiskFill: document.getElementById("devil-risk-fill"),
        invalidationTriggerText: document.getElementById("invalidation-trigger-text"),
        threatVectorList: document.getElementById("threat-vector-list"),
        gateChecksList: document.getElementById("gate-checks-list"),
        decisionRationaleCard: document.getElementById("decision-rationale-card"),
        decisionRationaleHeader: document.getElementById("decision-rationale-header"),
        decisionRationaleTitle: document.getElementById("decision-rationale-title"),
        decisionRationaleBadge: document.getElementById("decision-rationale-badge"),
        decisionRationaleContent: document.getElementById("decision-rationale-content"),

        // Copilot
        copilotWindow: document.getElementById("copilot-window"),
        copilotHeader: document.getElementById("copilot-header"),
        copilotMessages: document.getElementById("copilot-messages"),
        copilotInput: document.getElementById("copilot-input"),
        copilotFab: document.getElementById("copilot-fab"),

        // Command Palette
        cmdPaletteOverlay: document.getElementById("command-palette-overlay"),
        cmdPaletteInput: document.getElementById("command-palette-input"),
        cmdPaletteResults: document.getElementById("command-palette-results")
    };

    const commandRegistry = [
        { id: "xau", title: "Analyze Gold (XAUUSD)", desc: "Switch terminal view & load Gold desk", shortcut: "G", action: () => selectSymbol("XAUUSD") },
        { id: "eur", title: "Analyze Euro (EURUSD)", desc: "Switch terminal view & load EURUSD desk", shortcut: "E", action: () => selectSymbol("EURUSD") },
        { id: "gbp", title: "Analyze Pound (GBPUSD)", desc: "Switch terminal view & load GBPUSD desk", shortcut: "P", action: () => selectSymbol("GBPUSD") },
        { id: "jpy", title: "Analyze Yen (USDJPY)", desc: "Switch terminal view & load USDJPY desk", shortcut: "Y", action: () => selectSymbol("USDJPY") },
        { id: "btc", title: "Analyze Bitcoin (BTCUSD)", desc: "Switch terminal view & load BTCUSD desk", shortcut: "B", action: () => selectSymbol("BTCUSD") },
        { id: "expand", title: "Toggle Fullscreen Chart", desc: "Expand chart to fill full viewport", shortcut: "F", action: () => toggleExpandChart() },
        { id: "buy", title: "1-Click BUY Execution", desc: "Execute immediate LONG order on active symbol", shortcut: "B", action: () => executeManualTrade("BUY") },
        { id: "sell", title: "1-Click SELL Execution", desc: "Execute immediate SHORT order on active symbol", shortcut: "S", action: () => executeManualTrade("SELL") },
        { id: "close_all", title: "Close All Active Positions", desc: "Emergency kill-switch closing all open tickets", shortcut: "X", action: () => closeAllPositions() },
        { id: "news", title: "View Macro News Calendar", desc: "Switch left sidebar to High-Impact News feed", shortcut: "N", action: () => switchLeftTab("news") },
        { id: "radar", title: "View High-Probability Radar", desc: "Switch left sidebar to Setup Radar", shortcut: "R", action: () => switchLeftTab("radar") },
        { id: "desk", title: "View 1-Click Desk & Plan", desc: "Switch right panel to Trade Desk & Targets", shortcut: "D", action: () => switchRightTab("desk") },
        { id: "cognition", title: "View AI Cognition & Gates", desc: "Switch right panel to 14 Quality Gates & Analysis", shortcut: "A", action: () => switchRightTab("cognition") },
        { id: "copilot", title: "Toggle HM AI 4.0 Copilot", desc: "Open / Close intelligent assistant modal", shortcut: "C", action: () => toggleCopilotModal() },
        { id: "safe", title: "Toggle Emergency Safe Mode", desc: "Pause or unpause all autonomous executions", shortcut: "Esc", action: () => toggleSafeMode() },
        { id: "refresh", title: "Force Refresh Telemetry", desc: "Poll latest MT5 broker state immediately", shortcut: "F5", action: () => refreshData() }
    ];

    /* ==========================================================================
       1. TRADINGVIEW LIGHTWEIGHT CHARTS INITIALIZATION & S/R ENGINE
       ========================================================================== */

    function initTradingViewLightweightChart() {
        if (!el.tvLiveContainer) return;
        if (typeof LightweightCharts === "undefined") {
            console.warn("TradingView Lightweight Charts library not yet loaded. Retrying...");
            setTimeout(initTradingViewLightweightChart, 300);
            return;
        }

        el.tvLiveContainer.innerHTML = "";

        const width = el.tvLiveContainer.clientWidth || 600;
        const height = el.tvLiveContainer.clientHeight || 340;

        const chart = LightweightCharts.createChart(el.tvLiveContainer, {
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
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: "rgba(56, 189, 248, 0.5)", width: 1, style: 3 },
                horzLine: { color: "rgba(56, 189, 248, 0.5)", width: 1, style: 3 }
            },
            rightPriceScale: {
                borderColor: "rgba(51, 65, 85, 0.4)",
                scaleMargins: { top: 0.1, bottom: 0.25 }
            },
            timeScale: {
                borderColor: "rgba(51, 65, 85, 0.4)",
                timeVisible: true,
                secondsVisible: false
            }
        });

        // Candlestick Series
        const candleSeries = chart.addCandlestickSeries({
            upColor: "#00f59b",
            downColor: "#ff3b5c",
            borderUpColor: "#00f59b",
            borderDownColor: "#ff3b5c",
            wickUpColor: "#00f59b",
            wickDownColor: "#ff3b5c"
        });

        // Volume Histogram Series
        const volumeSeries = chart.addHistogramSeries({
            color: "#38bdf8",
            priceFormat: { type: "volume" },
            priceScaleId: "",
            scaleMargins: { top: 0.82, bottom: 0 },
            lastValueVisible: false,
            priceLineVisible: false
        });

        state.tvChartInstance = chart;
        state.tvCandleSeries = candleSeries;
        state.tvVolumeSeries = volumeSeries;

        // Subscribe to crosshair move for Smart Tooltip
        chart.subscribeCrosshairMove(param => {
            if (!param.time || !param.seriesData || !param.point) {
                if (el.smartTooltip) el.smartTooltip.style.display = "none";
                return;
            }

            const candle = param.seriesData.get(candleSeries);
            if (!candle) {
                if (el.smartTooltip) el.smartTooltip.style.display = "none";
                return;
            }

            const isBull = candle.close >= candle.open;
            const color = isBull ? "var(--neon-bull)" : "var(--neon-bear)";
            const digits = candle.close > 100 ? 2 : 5;

            let contextTag = "Standard Market Liquidity";
            if (candle.high >= state.supportResistance.r1) {
                contextTag = "âš  Approaching Key Institutional Resistance Zone";
            } else if (candle.low <= state.supportResistance.s1) {
                contextTag = "âœ“ Institutional Demand Zone Support Absorption";
            }

            const dateStr = typeof param.time === "number"
                ? new Date(param.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : String(param.time);

            if (el.smartTooltip) {
                el.smartTooltip.innerHTML = `
                    <div class="tooltip-header">
                        <span>${state.symbol} [${state.timeframe}]</span>
                        <span>${dateStr}</span>
                    </div>
                    <div class="tooltip-row"><span>Open:</span> <b>${candle.open.toFixed(digits)}</b></div>
                    <div class="tooltip-row"><span>High:</span> <b>${candle.high.toFixed(digits)}</b></div>
                    <div class="tooltip-row"><span>Low:</span> <b>${candle.low.toFixed(digits)}</b></div>
                    <div class="tooltip-row"><span>Close:</span> <b style="color:${color};">${candle.close.toFixed(digits)}</b></div>
                    <div class="tooltip-structure-tag">âœ¦ ${contextTag}</div>
                `;
                el.smartTooltip.style.display = "block";
                el.smartTooltip.style.left = `${Math.min(window.innerWidth - 220, param.point.x + 15)}px`;
                el.smartTooltip.style.top = `${Math.max(60, param.point.y - 40)}px`;
            }
        });

        renderTradingViewChartData();
    }

    function calculateSupportResistance(candles) {
        if (!candles || candles.length < 10) return;

        let highs = [];
        let lows = [];

        for (let i = 2; i < candles.length - 2; i++) {
            const cur = candles[i];
            // Swing High
            if (cur.high > candles[i - 1].high && cur.high > candles[i - 2].high &&
                cur.high > candles[i + 1].high && cur.high > candles[i + 2].high) {
                highs.push(cur.high);
            }
            // Swing Low
            if (cur.low < candles[i - 1].low && cur.low < candles[i - 2].low &&
                cur.low < candles[i + 1].low && cur.low < candles[i + 2].low) {
                lows.push(cur.low);
            }
        }

        const lastPrice = candles[candles.length - 1].close;
        const higherHighs = highs.filter(h => h > lastPrice).sort((a, b) => a - b);
        const lowerLows = lows.filter(l => l < lastPrice).sort((a, b) => b - a);

        const r1 = higherHighs.length > 0 ? higherHighs[0] : lastPrice * 1.012;
        const r2 = higherHighs.length > 1 ? higherHighs[1] : r1 * 1.015;
        const s1 = lowerLows.length > 0 ? lowerLows[0] : lastPrice * 0.988;
        const s2 = lowerLows.length > 1 ? lowerLows[1] : s1 * 0.985;

        state.supportResistance = { r1, r2, s1, s2 };

        const digits = lastPrice > 100 ? 2 : 5;
        if (el.legendR1) el.legendR1.textContent = `ðŸ”´ Resistance: ${r1.toFixed(digits)}`;
        if (el.legendS1) el.legendS1.textContent = `ðŸŸ¢ Support: ${s1.toFixed(digits)}`;
    }

    function renderTradingViewChartData() {
        if (!state.tvCandleSeries || !state.tvVolumeSeries || !state.candles || state.candles.length === 0) return;

        const formattedCandles = [];
        const formattedVolumes = [];

        state.candles.forEach(c => {
            const timeVal = typeof c.time === "number" ? c.time : Math.floor(new Date(c.time).getTime() / 1000);
            formattedCandles.push({
                time: timeVal,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close
            });
            formattedVolumes.push({
                time: timeVal,
                value: c.volume,
                color: c.close >= c.open ? "rgba(0, 245, 155, 0.35)" : "rgba(255, 59, 92, 0.35)"
            });
        });

        state.tvCandleSeries.setData(formattedCandles);
        state.tvVolumeSeries.setData(formattedVolumes);

        calculateSupportResistance(state.candles);

        // Clear existing Price Lines
        if (state.tvPriceLines && state.tvPriceLines.length > 0) {
            state.tvPriceLines.forEach(pl => state.tvCandleSeries.removePriceLine(pl));
            state.tvPriceLines = [];
        }

        const digits = state.candles[0].close > 100 ? 2 : 5;

        // Draw Active Resistance Level Line
        const r1Line = state.tvCandleSeries.createPriceLine({
            price: state.supportResistance.r1,
            color: '#ff3b5c',
            lineWidth: 1.5,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: `R1: ${state.supportResistance.r1.toFixed(digits)}`
        });

        // Draw Active Support Level Line
        const s1Line = state.tvCandleSeries.createPriceLine({
            price: state.supportResistance.s1,
            color: '#00f59b',
            lineWidth: 1.5,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: `S1: ${state.supportResistance.s1.toFixed(digits)}`
        });

        state.tvPriceLines.push(r1Line, s1Line);

        // Update Live Header Price
        const last = state.candles[state.candles.length - 1];
        if (last && el.chartLivePrice) {
            const sym = state.symbol || "XAUUSD";
            const statusObj = (state.marketStatuses && state.marketStatuses[sym]) || computeClientMarketStatus(sym);
            if (statusObj.is_open) {
                el.chartLivePrice.textContent = last.close.toFixed(digits);
                el.chartLivePrice.style.color = last.close >= last.open ? "var(--neon-bull)" : "var(--neon-bear)";
            } else {
                el.chartLivePrice.innerHTML = `${last.close.toFixed(digits)} <span style="font-size:9px; color:#ff5277; font-weight:800; margin-left:4px; padding:1px 4px; border-radius:2px; background:rgba(255,59,92,0.14);">CLOSED</span>`;
                el.chartLivePrice.style.color = "var(--text-secondary)";
            }
        }
    }

    function initTradingViewAdvancedWidget() {
        if (!el.tvProContainer) return;
        if (typeof TradingView === "undefined") return;

        el.tvProContainer.innerHTML = "";
        const widgetId = "tv_advanced_widget_frame";
        const div = document.createElement("div");
        div.id = widgetId;
        div.style.width = "100%";
        div.style.height = "100%";
        el.tvProContainer.appendChild(div);

        const tvSymbolMap = {
            "XAUUSD": "OANDA:XAUUSD",
            "EURUSD": "FX:EURUSD",
            "GBPUSD": "FX:GBPUSD",
            "USDJPY": "FX:USDJPY",
            "BTCUSD": "BINANCE:BTCUSDT"
        };
        const tvSym = tvSymbolMap[state.symbol] || `FX:${state.symbol}`;

        new TradingView.widget({
            container_id: widgetId,
            autosize: true,
            symbol: tvSym,
            interval: state.timeframe === "M5" ? "5" : (state.timeframe === "M15" ? "15" : (state.timeframe === "H4" ? "240" : (state.timeframe === "D1" ? "D" : "60"))),
            timezone: "Etc/UTC",
            theme: "dark",
            style: "1",
            locale: "en",
            toolbar_bg: "#080c14",
            enable_publishing: false,
            hide_side_toolbar: false,
            allow_symbol_change: true,
            details: true,
            hotlist: true,
            calendar: true,
            studies: ["Volume@tv-basicstudies", "MASimple@tv-basicstudies"]
        });
    }

    window.switchChartMode = function (mode) {
        state.chartMode = mode;
        if (el.btnModeTvLive) el.btnModeTvLive.classList.toggle("active", mode === "tv_live");
        if (el.btnModeTvPro) el.btnModeTvPro.classList.toggle("active", mode === "tv_pro");

        if (mode === "tv_live") {
            if (el.tvLiveContainer) el.tvLiveContainer.style.display = "block";
            if (el.tvProContainer) el.tvProContainer.style.display = "none";
            if (!state.tvChartInstance) initTradingViewLightweightChart();
            else {
                state.tvChartInstance.applyOptions({
                    width: el.tvLiveContainer.clientWidth,
                    height: el.tvLiveContainer.clientHeight
                });
                renderTradingViewChartData();
            }
        } else {
            if (el.tvLiveContainer) el.tvLiveContainer.style.display = "none";
            if (el.tvProContainer) el.tvProContainer.style.display = "block";
            initTradingViewAdvancedWidget();
        }
    };

    window.toggleExpandChart = function () {
        const panel = document.getElementById("chart-main-panel");
        const btn = document.getElementById("btn-expand-chart");
        if (!panel) return;

        const isExpanded = panel.classList.toggle("is-expanded");
        state.chartExpanded = isExpanded;

        if (btn) {
            btn.innerHTML = isExpanded ? "âœ• Minimize" : "â›¶ Expand";
            btn.classList.toggle("is-expanded-btn", isExpanded);
        }

        setTimeout(() => {
            if (state.tvChartInstance && el.tvLiveContainer) {
                state.tvChartInstance.applyOptions({
                    width: el.tvLiveContainer.clientWidth,
                    height: el.tvLiveContainer.clientHeight
                });
                state.tvChartInstance.timeScale().fitContent();
            }
            if (state.chartMode === "tv_pro") {
                initTradingViewAdvancedWidget();
            }
        }, 80);
    };

    /* ==========================================================================
       2. REAL-TIME DATA FETCHING & TELEMETRY
       ========================================================================== */

    async function fetchCandles() {
        try {
            const res = await fetch(`/api/candles?symbol=${state.symbol}&tf=${state.timeframe}`);
            const data = await res.json();
            if (data && data.candles) {
                state.candles = data.candles;
                if (state.chartMode === "tv_live") {
                    renderTradingViewChartData();
                }
            }
        } catch (err) {
            console.error("Candle fetch error:", err);
        }
    }

    async function fetchTelemetry() {
        try {
            const res = await fetch("/api/telemetry_state");
            const data = await res.json();
            if (data) {
                state.account = data.account;
                state.executionMode = data.execution_mode;
                state.safeMode = data.safe_mode;
                state.radarOpportunities = data.radar_opportunities || [];
                state.positions = data.positions || [];
                state.latestDecisions = data.latest_decisions || {};
                state.marketStatuses = data.market_statuses || {};
                state.activeMarketStatus = data.active_market_status || null;

                requestAnimationFrame(renderTelemetryDOM);
            }
        } catch (err) {
            console.error("Telemetry fetch error:", err);
        }
    }

        async function fetchHistory() {
        try {
            const res = await fetch('/api/history');
            const data = await res.json();
            if (Array.isArray(data)) {
                renderHistoryDOM(data);
            }
        } catch (err) {
            console.error('History fetch error:', err);
        }
    }

    /* ==========================================================================
       PRECISION FORMATTING & STATUS HELPERS (Requirements 8, 9)
       ========================================================================== */
    function formatPrice(val, symbol) {
        if (val === null || val === undefined || isNaN(val) || val === "" || val === 0) return "--";
        const num = Number(val);
        const s = (symbol || state.symbol || "").toUpperCase();
        if (s.includes("JPY")) {
            return num.toFixed(3);
        } else if (s.includes("XAU") || s.includes("GOLD") || s.includes("BTC") || s.includes("USDT") || num >= 500) {
            return num.toFixed(2);
        } else {
            return num.toFixed(5);
        }
    }

    function getStatusBadge(item) {
        if (!item) return { label: "NO SETUP", cssClass: "badge-no-setup", dotColor: "#475569" };
        const sym = item.symbol || state.symbol || "XAUUSD";
        const statusObj = (state.marketStatuses && state.marketStatuses[sym]) || computeClientMarketStatus(sym);
        
        if (!statusObj.is_open) {
            return { label: "🔒 CLOSED", cssClass: "badge-market-closed", dotColor: "#ff5277" };
        }

        const action = item.action || item.status_label || item.decision || "WAIT";
        const bias = item.bias || "NEUTRAL";
        const gatePassed = item.gate_passed !== undefined ? item.gate_passed : (item.quality_gate ? item.quality_gate.passed : false);
        const failing = item.failing_reasons || (item.quality_gate ? item.quality_gate.failing_reasons : []);
        
        if (action.includes("READY") || action === "BUY READY" || (item.decision === "EXECUTE" && bias === "BUY")) {
            return { label: "BUY READY", cssClass: "badge-ready-buy", dotColor: "var(--neon-bull)" };
        }
        if (action.includes("READY") || action === "SELL READY" || (item.decision === "EXECUTE" && bias === "SELL")) {
            return { label: "SELL READY", cssClass: "badge-ready-sell", dotColor: "var(--neon-bear)" };
        }
        if (action === "WAIT: BUY" || (item.decision === "WAIT" && bias === "BUY")) {
            return { label: "WAIT: BUY", cssClass: "badge-wait-buy", dotColor: "var(--devil-amber)" };
        }
        if (action === "WAIT: SELL" || (item.decision === "WAIT" && bias === "SELL")) {
            return { label: "WAIT: SELL", cssClass: "badge-wait-sell", dotColor: "var(--devil-amber)" };
        }
        if (action === "TRADE INVALIDATED" || failing.some(r => r.includes("Invalid") || r.includes("Devil") || r.includes("Adversarial"))) {
            return { label: "TRADE INVALIDATED", cssClass: "badge-invalidated", dotColor: "#c084fc" };
        }
        if (action === "NO TRADE" || item.decision === "NO_TRADE") {
            return { label: "NO TRADE", cssClass: "badge-no-trade", dotColor: "var(--text-dim)" };
        }
        return { label: "NO SETUP", cssClass: "badge-no-setup", dotColor: "#475569" };
    }

    function renderHistoryDOM(trades) {
        if (el.historyCount) el.historyCount.innerText = (trades ? trades.length : 0) + ' Executed';
        const tbody = el.historyTbody || document.getElementById('history-tbody');
        if (!tbody) return;
        if (!trades || trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:var(--text-dim); padding:16px;">No Recent History</td></tr>';
            return;
        }
        let html = '';
        for (const t of trades) {
            const isBuy = (t.action || t.type) === 'BUY';
            const sideClass = isBuy ? 'badge-ready-buy' : 'badge-ready-sell';
            const pnlVal = Number(t.realized_pnl !== undefined ? t.realized_pnl : (t.profit !== undefined ? t.profit : (t.expected_value || 0)));
            const pnlColor = pnlVal >= 0 ? 'var(--neon-bull)' : 'var(--neon-bear)';
            const pnlPrefix = pnlVal >= 0 ? '+' : '';
            const dtStr = t.timestamp ? t.timestamp.replace('T', ' ').substring(0, 19) : '--';
            const isManual = t.executor === 'MANUAL' || (t.regime === 'MANUAL_EXECUTION');
            const execBadge = isManual
                ? '<span class="badge-manual">👤 MANUAL</span>'
                : '<span class="badge-bot">🤖 BOT (AI)</span>';
            const ticketVal = t.ticket || t.id || '--';
            const volVal = Number(t.volume || t.lot_size || 0.01).toFixed(2);
            const slVal = t.sl || t.stop_loss || 0;
            const tpVal = t.tp || t.take_profit || 0;

            html += `<tr>
                <td style="color:var(--text-dim);">#${ticketVal}</td>
                <td><b style="color:#ffffff;">${t.symbol}</b></td>
                <td><span class="badge ${sideClass}" style="font-size:8.5px; padding:1px 5px;">${t.action || t.type}</span></td>
                <td>${execBadge}</td>
                <td class="mono-number" style="font-weight:700;">${volVal}</td>
                <td class="mono-number">${formatPrice(t.entry_price || t.open_price || 0, t.symbol)}</td>
                <td class="mono-number" style="color:var(--neon-bear);">${slVal > 0 ? formatPrice(slVal, t.symbol) : '—'}</td>
                <td class="mono-number" style="color:var(--neon-bull);">${tpVal > 0 ? formatPrice(tpVal, t.symbol) : '—'}</td>
                <td class="mono-number" style="color:${pnlColor}; font-weight:800; font-size:11px;">${pnlPrefix}$${pnlVal.toFixed(2)}</td>
                <td class="mono-number" style="color:var(--text-dim); font-size:9px;">${dtStr}</td>
            </tr>`;
        }
        tbody.innerHTML = html;
    }

    async function fetchNews() {
        try {
            const res = await fetch("/api/news");
            const data = await res.json();
            if (data && data.news) {
                state.newsItems = data.news;
                renderNewsDOM(data.news);
            }
        } catch (err) {
            console.error("News fetch error:", err);
        }
    }

    function simulateLiveMarketTick() {
        if (!state.candles || state.candles.length === 0 || state.chartMode !== "tv_live") return;
        const sym = state.symbol || "XAUUSD";
        const statusObj = (state.marketStatuses && state.marketStatuses[sym]) || computeClientMarketStatus(sym);
        // FREEZE CHART IF MARKET IS CLOSED: Do not simulate price movements on closed markets
        if (!statusObj.is_open) return;

        const last = state.candles[state.candles.length - 1];
        const volStep = (Math.random() - 0.495) * (last.close > 100 ? 0.35 : 0.00015);
        last.close = Math.max(last.low * 0.999, last.close + volStep);
        if (last.close > last.high) last.high = last.close;
        if (last.close < last.low) last.low = last.close;
        last.volume += Math.floor(Math.random() * 8) + 1;

        if (state.tvCandleSeries && state.tvVolumeSeries) {
            const timeVal = typeof last.time === "number" ? last.time : Math.floor(new Date(last.time).getTime() / 1000);
            state.tvCandleSeries.update({
                time: timeVal,
                open: last.open,
                high: last.high,
                low: last.low,
                close: last.close
            });
            state.tvVolumeSeries.update({
                time: timeVal,
                value: last.volume,
                color: last.close >= last.open ? "rgba(0, 245, 155, 0.35)" : "rgba(255, 59, 92, 0.35)"
            });
        }
    }

    /* ==========================================================================
       3. DOM RENDERING PIPELINE (MODULES A, B, C, NEWS, TRADE DESK)
       ========================================================================== */

    function renderTelemetryDOM() {
        const acc = state.account || {};

        if (el.hudServer) el.hudServer.textContent = acc.server || "Connecting...";
        if (el.hudLogin) el.hudLogin.textContent = acc.login ? `#${acc.login}` : "#--";
        if (el.hudBalance) el.hudBalance.textContent = `$${(acc.balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (el.hudEquity) el.hudEquity.textContent = `$${(acc.equity || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (el.hudFreeMargin) el.hudFreeMargin.textContent = `$${(acc.free_margin || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (el.hudMarginLevel) el.hudMarginLevel.textContent = acc.margin_level ? `${Math.round(acc.margin_level).toLocaleString()}%` : "--%";

        if (el.execModeBadge) el.execModeBadge.textContent = state.executionMode || "LIVE";
        if (el.statusBadge) {
            if (state.safeMode) {
                el.statusBadge.textContent = "SAFE MODE (PAUSED)";
                el.statusBadge.className = "badge badge-safe";
            } else {
                el.statusBadge.innerHTML = '<span class="pulse-dot"></span> OPERATIONAL';
                el.statusBadge.className = "badge badge-live";
            }
        }

        // Account Details Card
        if (el.accName) el.accName.textContent = acc.name || "Live MT5 Trader";
        if (el.accLeverage) el.accLeverage.textContent = acc.leverage ? `1:${acc.leverage}` : "--";
        if (el.accCompany) el.accCompany.textContent = acc.company || "Broker Gateway";
        if (el.accLogin) el.accLogin.textContent = acc.login ? `${acc.login}` : "--";
        if (el.accBalance) el.accBalance.textContent = `$${(acc.balance || 0).toFixed(2)}`;
        if (el.accEquity) el.accEquity.textContent = `$${(acc.equity || 0).toFixed(2)}`;

        const profit = acc.profit || 0;
        if (el.accProfit) {
            el.accProfit.textContent = `${profit >= 0 ? '+' : ''}$${profit.toFixed(2)}`;
            el.accProfit.style.color = profit >= 0 ? "var(--neon-bull)" : "var(--neon-bear)";
        }
        if (el.accFreeMargin) el.accFreeMargin.textContent = `$${(acc.free_margin || 0).toFixed(2)}`;

        // Render Sub-components
        renderScannerRadarDOM(state.radarOpportunities);
        renderActiveTradesDOM(state.positions);
        renderDevilAdvocateDOM(state.latestDecisions[state.symbol]);

        // Synchronize 1-Click Desk input values for active symbol
        if (el.deskActiveSymbol) el.deskActiveSymbol.textContent = state.symbol;
        const activeDec = state.latestDecisions[state.symbol];
        if (activeDec) {
            const winProb = activeDec.probabilities && activeDec.probabilities[activeDec.bias ? activeDec.bias.toLowerCase() : "buy"]
                ? activeDec.probabilities[activeDec.bias ? activeDec.bias.toLowerCase() : "buy"]
                : (activeDec.model_confidence || 0.50);
            if (el.deskWinProb) el.deskWinProb.value = `${Math.round(winProb * 100)}%`;
            const hasValidBracket = activeDec.stop_loss && activeDec.entry_price && (Math.abs(activeDec.stop_loss - activeDec.entry_price) > 1e-5);
            if (el.deskSl && document.activeElement !== el.deskSl && !el.deskSl.value) {
                el.deskSl.value = hasValidBracket ? formatPrice(activeDec.stop_loss, state.symbol) : "";
            }
            if (el.deskTp && document.activeElement !== el.deskTp && !el.deskTp.value) {
                el.deskTp.value = (hasValidBracket && activeDec.take_profit) ? formatPrice(activeDec.take_profit, state.symbol) : "";
            }
        }

        // Synchronize Global & Asset Market Open/Closed Status
        updateMarketStatusDisplay(state.symbol);
    }

    function computeClientMarketStatus(symbol) {
        const sym = (symbol || "XAUUSD").toUpperCase();
        if (sym.includes("BTC") || sym.includes("ETH") || sym.includes("SOL") || sym.includes("CRYPTO")) {
            return {
                is_open: true,
                market_type: "CRYPTO_24_7",
                status: "OPEN",
                status_text: "Continuous 24/7 Crypto Trading",
                next_open_ist: "Always Open",
                countdown_formatted: "Live 24/7"
            };
        }
        const now = new Date();
        const utcDay = now.getUTCDay(); // 0=Sun, 5=Fri, 6=Sat
        const utcHour = now.getUTCHours();
        const utcMin = now.getUTCMinutes();
        const utcSec = now.getUTCSeconds();

        let isClosed = false;
        if (utcDay === 5 && utcHour >= 21) isClosed = true;
        else if (utcDay === 6) isClosed = true;
        else if (utcDay === 0 && utcHour < 21) isClosed = true;

        if (isClosed) {
            let daysToAdd = (7 - utcDay) % 7;
            if (utcDay === 0) daysToAdd = 0;
            const nextOpenUtc = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + daysToAdd, 21, 0, 0));
            const diffMs = Math.max(0, nextOpenUtc.getTime() - now.getTime());
            const totalSec = Math.floor(diffMs / 1000);
            const days = Math.floor(totalSec / 86400);
            const hours = Math.floor((totalSec % 86400) / 3600);
            const mins = Math.floor((totalSec % 3600) / 60);
            const secs = totalSec % 60;

            const istOffset = 5.5 * 3600 * 1000;
            const istDate = new Date(nextOpenUtc.getTime() + istOffset);
            const daysShort = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
            const monthsShort = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            const formattedIst = `${daysShort[istDate.getUTCDay()]} ${monthsShort[istDate.getUTCMonth()]} ${istDate.getUTCDate()}, 02:30 AM IST`;

            const cdStr = days > 0 ? `${days}d ${hours}h ${mins}m ${secs}s` : `${hours}h ${mins}m ${secs}s`;

            return {
                is_open: false,
                market_type: "FOREX_METALS_24_5",
                status: "CLOSED_WEEKEND",
                status_text: `Market is closed for the weekend. Re-opens ${formattedIst}`,
                next_open_ist: formattedIst,
                countdown_formatted: cdStr,
                reason: "Global Forex & Spot Metals markets are closed on weekends."
            };
        } else {
            return {
                is_open: true,
                market_type: "FOREX_METALS_24_5",
                status: "OPEN",
                status_text: "Market is Open (24/5)",
                next_open_ist: "Currently Open",
                countdown_formatted: "Open"
            };
        }
    }

    function updateMarketStatusDisplay(symbol) {
        const sym = symbol || state.symbol || "XAUUSD";
        const statusObj = (state.marketStatuses && state.marketStatuses[sym]) || computeClientMarketStatus(sym);

        // 1. Top Global HUD Tile
        if (el.hudMarketStatus) {
            el.hudMarketStatus.textContent = statusObj.is_open ? "OPEN (24/5)" : "CLOSED (WEEKEND)";
            el.hudMarketStatus.style.color = statusObj.is_open ? "var(--neon-bull)" : "var(--neon-bear)";
        }

        // 2. Chart Header Status Pill
        if (el.chartMarketStatus) {
            if (statusObj.is_open) {
                el.chartMarketStatus.className = "market-status-pill market-open";
                el.chartMarketStatus.innerHTML = `🟢 OPEN (24/5)`;
                el.chartMarketStatus.title = statusObj.status_text;
            } else {
                el.chartMarketStatus.className = "market-status-pill market-closed";
                el.chartMarketStatus.innerHTML = `🔴 CLOSED (WEEKEND) — Re-opens <b>${statusObj.next_open_ist || 'Mon 02:30 AM IST'}</b> (<span id="mkt-countdown-val">${statusObj.countdown_formatted}</span>)`;
                el.chartMarketStatus.title = statusObj.reason || statusObj.status_text;
            }
        }

        // 3. Trade Desk Execution Warning Banner
        if (el.deskMarketStatusBanner) {
            if (statusObj.is_open) {
                el.deskMarketStatusBanner.style.display = "none";
            } else {
                el.deskMarketStatusBanner.style.display = "flex";
                if (el.deskMarketTitle) el.deskMarketTitle.textContent = `🔒 ${sym} MARKET IS CLOSED`;
                if (el.deskMarketTime) el.deskMarketTime.textContent = `Re-opens: ${statusObj.next_open_ist} (in ${statusObj.countdown_formatted})`;
            }
        }

        // 4. Chart Stage Controls Label
        if (el.btnModeTvLive) {
            el.btnModeTvLive.textContent = statusObj.is_open ? "⚡ Live MT5" : "📊 MT5 Close (Frozen)";
        }
    }

    function tickMarketCountdown() {
        updateMarketStatusDisplay(state.symbol);
    }

    let _lastRadarSnapshot = "";
    function renderScannerRadarDOM(opps) {
        if (!el.radarList) return;
        const currentSymStatus = (state.marketStatuses && state.marketStatuses[state.symbol]) || computeClientMarketStatus(state.symbol);
        
        if (state.activeLeftTab === "radar" && el.leftPanelCounter) {
            el.leftPanelCounter.textContent = currentSymStatus.is_open ? `${opps.length} Monitored` : `🔒 CLOSED | ${opps.length} Monitored`;
        }

        if (!opps || opps.length === 0) {
            el.radarList.innerHTML = `<div style="text-align:center; color:var(--text-dim); padding:16px;">Scanning monitored instruments...</div>`;
            _lastRadarSnapshot = "";
            return;
        }

        // Institutional Multi-Factor Priority Ranking:
        // 1. Open / Live markets (e.g. BTCUSD continuous 24/7) rank ABOVE closed weekend markets
        // 2. Action Conviction: READY > WAIT > NO_TRADE > CLOSED
        // 3. AI Win Probability: highest win rate first
        // 4. Mathematical Expected Value (EV)
        const sortedOpps = [...opps].sort((a, b) => {
            const symA = a.symbol || "XAUUSD";
            const symB = b.symbol || "XAUUSD";
            const statusA = (state.marketStatuses && state.marketStatuses[symA]) || computeClientMarketStatus(symA);
            const statusB = (state.marketStatuses && state.marketStatuses[symB]) || computeClientMarketStatus(symB);
            
            if (statusA.is_open !== statusB.is_open) {
                return statusA.is_open ? -1 : 1;
            }
            
            const getConviction = (item) => {
                const act = item.action || item.status_label || "";
                if (act.includes("READY")) return 3;
                if (act.includes("WAIT")) return 2;
                if (act.includes("NO TRADE") || act.includes("INVALID")) return 1;
                return 0;
            };
            const convA = getConviction(a);
            const convB = getConviction(b);
            if (convA !== convB) {
                return convB - convA;
            }
            
            const probA = Number(a.win_prob || a.score || 0);
            const probB = Number(b.win_prob || b.score || 0);
            if (probA !== probB) {
                return probB - probA;
            }
            
            const evA = Number(a.ev || 0);
            const evB = Number(b.ev || 0);
            return evB - evA;
        });

        const snapshot = JSON.stringify({ activeSym: state.symbol, data: sortedOpps, mktOpen: currentSymStatus.is_open });
        if (snapshot === _lastRadarSnapshot) {
            return; // Zero DOM thrashing when data is unchanged
        }
        _lastRadarSnapshot = snapshot;

        el.radarList.innerHTML = sortedOpps.map(opp => {
            const sym = opp.symbol || "XAUUSD";
            const symStatus = (state.marketStatuses && state.marketStatuses[sym]) || computeClientMarketStatus(sym);
            const isMarketClosed = !symStatus.is_open;
            const badge = getStatusBadge(opp);
            const isActive = opp.symbol === state.symbol;
            const hasValidBracket = opp.stop_loss && opp.entry_price && (Math.abs(opp.stop_loss - opp.entry_price) > 1e-5);
            const entryStr = formatPrice(opp.entry_price, opp.symbol);
            const slStr = hasValidBracket ? formatPrice(opp.stop_loss, opp.symbol) : "—";
            const tpStr = (hasValidBracket && opp.take_profit && Math.abs(opp.take_profit - opp.entry_price) > 1e-5) ? formatPrice(opp.take_profit, opp.symbol) : "—";
            const rrStr = (hasValidBracket && opp.risk_reward_ratio) ? `1:${Number(opp.risk_reward_ratio).toFixed(2)}` : "--";
            const evVal = Number(opp.ev || 0);
            const evStr = `${evVal >= 0 ? '+' : ''}$${evVal.toFixed(2)}`;
            const probStr = opp.win_prob ? `${opp.win_prob}%` : (opp.score ? `${opp.score}%` : "--%");
            const strategyName = opp.strategy || "MARKET_STRUCTURE";

            const gateLabel = isMarketClosed 
                ? `<b style="color:#ff5277;">🔒 WEEKEND CLOSE</b>`
                : (opp.gate_passed ? '<b style="color:var(--neon-bull);">GATE PASS (14/14)</b>' : '<b style="color:var(--devil-amber);">GATE WAIT</b>');

            const evLabel = isMarketClosed
                ? `<span class="mono-number" style="color: var(--text-dim); font-size:9.5px;">Re-opens ${symStatus.next_open_ist ? symStatus.next_open_ist.split(',')[0] : 'Mon'}</span>`
                : `<span class="mono-number" style="color: ${evVal >= 0 ? 'var(--neon-bull)' : 'var(--neon-bear)'}; font-weight:700;">EV: ${evStr}</span>`;

            return `
                <div class="radar-opportunity-card ${isActive ? 'active' : ''}" onclick="selectSymbol('${opp.symbol}')">
                    <div class="radar-card-top">
                        <div class="radar-symbol">
                            ${opp.symbol}
                            <span class="radar-timeframe-tag">${opp.timeframe || 'H1'}</span>
                        </div>
                        <div class="radar-action-pill ${badge.cssClass}">${badge.label}</div>
                    </div>
                    <div class="radar-meta-row">
                        <span class="radar-setup-name">${strategyName}</span>
                        ${evLabel}
                    </div>
                    <div class="radar-plan-chip">
                        <span>E: <b>${entryStr}</b></span>
                        <span style="color:var(--neon-bear);">SL: <b>${slStr}</b></span>
                        <span style="color:var(--neon-bull);">TP: <b>${tpStr}</b></span>
                        <span>R:R: <b>${rrStr}</b></span>
                    </div>
                    <div class="radar-status-indicator">
                        <span class="status-dot" style="background-color: ${badge.dotColor};"></span>
                        <span style="display:flex; justify-content:space-between; width:100%;">
                            <span>Prob: <b style="color:var(--text-primary);">${probStr}</b></span>
                            <span>${gateLabel}</span>
                        </span>
                    </div>
                </div>
            `;
        }).join("");
    }

    function renderNewsDOM(news) {
        if (!el.newsFeedList) return;
        window.RAW_NEWS_FEED = news || [];
        if (!news || news.length === 0) {
            el.newsFeedList.innerHTML = '<div style="text-align:center; color:var(--text-dim); padding:20px; font-size:11px;">Scanning live institutional macro calendar...</div>';
            if (state.activeLeftTab === "news" && el.leftPanelCounter) {
                el.leftPanelCounter.textContent = "0 Events";
            }
            return;
        }

        const liveCount = news.filter(n => n.is_live).length;
        if (state.activeLeftTab === "news" && el.leftPanelCounter) {
            el.leftPanelCounter.textContent = liveCount > 0 ? `${liveCount} LIVE | ${news.length} Events` : `${news.length} Events`;
        }

        el.newsFeedList.innerHTML = news.map((n, idx) => {
            const isMostRecent = Boolean(n.is_most_recent || idx === 0);
            const isLive = Boolean(n.is_live);
            const isUpcoming = Boolean(n.is_upcoming);
            const isHigh = n.impact === "HIGH";
            const isMed = n.impact === "MEDIUM";
            
            let cardClass = "news-card";
            let statusPillClass = "news-status-past";
            let statusText;
            if (isLive) {
                cardClass += " news-card-live";
                statusPillClass = "news-status-live";
                statusText = n.status_badge || "🔴 LIVE NOW";
            } else if (isMostRecent) {
                cardClass += " news-card-recent";
                statusPillClass = "news-status-recent";
                statusText = n.status_badge || "⚡ LATEST RELEASE (ENDED)";
            } else if (isUpcoming) {
                cardClass += " news-card-upcoming";
                statusPillClass = "news-status-upcoming";
                statusText = n.status_badge || `⏳ ${n.time}`;
            } else {
                cardClass += " news-card-past";
                statusPillClass = "news-status-past";
                statusText = n.status_badge || "✓ ENDED";
            }

            let impactBadgeClass = "news-impact-low";
            if (isHigh) impactBadgeClass = "news-impact-high";
            else if (isMed) impactBadgeClass = "news-impact-med";

            // Shock alert banner
            let shockBannerHtml = "";
            if (isLive) {
                shockBannerHtml = `<div class="news-shock-banner live">⚡ <b>VOLATILITY SHOCK ACTIVE:</b> High spread expansion & slippage risk</div>`;
            } else if (isMostRecent && !isLive && n.actual && n.actual !== "—" && n.actual !== "Upcoming") {
                shockBannerHtml = `<div class="news-shock-banner upcoming" style="background:rgba(56,189,248,0.12); color:var(--accent-cyan); border-color:var(--accent-cyan);">⚡ <b>LATEST MACRO REPORT:</b> Actual: ${n.actual} vs Forecast: ${n.forecast} (Prev: ${n.previous})</div>`;
            } else if (isUpcoming && isHigh) {
                shockBannerHtml = `<div class="news-shock-banner upcoming">⏳ <b>APPROACHING HIGH IMPACT:</b> Expect liquidity volatility on ${n.currency}</div>`;
            }

            // Affected pairs tags
            let affectedHtml = "";
            if (n.affected_pairs && n.affected_pairs.length > 0) {
                affectedHtml = `
                    <div class="news-affected-row">
                        <span style="color:var(--text-dim);">Impacts:</span>
                        ${n.affected_pairs.slice(0, 4).map(p => `<span class="news-affected-tag">${p}</span>`).join("")}
                    </div>
                `;
            }

            const actualStyle = isLive 
                ? "color:#ff3b5c; font-weight:800;" 
                : (isMostRecent 
                    ? "color:var(--accent-cyan); font-weight:800;" 
                    : (n.actual && n.actual !== "Upcoming" && n.actual !== "—" ? "color:var(--neon-bull); font-weight:700;" : "color:var(--text-dim);"));

            const istDisplay = n.time_ist ? `🇮🇳 ${n.time_ist}` : `🇮🇳 ${n.time}`;

            return `
                <div class="${cardClass}" onclick="openNewsDetailModal(${idx})" title="Click to view deep shock analysis and Indian Standard Time schedule">
                    <div class="news-card-header">
                        <div style="display:flex; align-items:center; gap:4px;">
                            <span class="news-currency-tag">${n.currency}</span>
                            <span class="${impactBadgeClass}">${n.impact}</span>
                        </div>
                        <span class="news-status-pill ${statusPillClass}">${statusText}</span>
                    </div>

                    <div class="news-card-title">${n.event}</div>

                    <div class="news-meta-row">
                        <span class="news-time-ist">${istDisplay}</span>
                        <span class="news-countdown-text">${n.status_badge || ''}</span>
                    </div>

                    ${shockBannerHtml}

                    <div class="news-metrics-grid">
                        <div class="news-metric-col">
                            <span class="news-metric-label">Actual</span>
                            <span class="news-metric-value" style="${actualStyle}">${n.actual || "—"}</span>
                        </div>
                        <div class="news-metric-col">
                            <span class="news-metric-label">Forecast</span>
                            <span class="news-metric-value">${n.forecast || "—"}</span>
                        </div>
                        <div class="news-metric-col">
                            <span class="news-metric-label">Previous</span>
                            <span class="news-metric-value">${n.previous || "—"}</span>
                        </div>
                    </div>

                    ${affectedHtml}
                </div>
            `;
        }).join("");
    }

    function openNewsDetailModal(idx) {
        const feed = window.RAW_NEWS_FEED || [];
        const item = feed[idx];
        if (!item) return;

        const modal = document.getElementById("macro-news-modal");
        if (!modal) return;

        // Set Currency, Impact, Status
        const currEl = document.getElementById("mn-modal-curr");
        const impactEl = document.getElementById("mn-modal-impact");
        const statusEl = document.getElementById("mn-modal-status");
        if (currEl) currEl.textContent = item.currency;
        if (impactEl) {
            impactEl.textContent = item.impact;
            impactEl.className = item.impact === "HIGH" ? "news-impact-high" : (item.impact === "MEDIUM" ? "news-impact-med" : "news-impact-low");
        }
        if (statusEl) {
            statusEl.textContent = item.is_live ? "🔴 LIVE NOW" : (item.is_most_recent ? (item.status_badge || "⚡ LATEST RELEASE (ENDED)") : (item.is_upcoming ? `⏳ ${item.status_badge || item.time}` : (item.status_badge || "✓ ENDED")));
            statusEl.className = item.is_live ? "news-status-pill news-status-live" : (item.is_most_recent ? "news-status-pill news-status-recent" : (item.is_upcoming ? "news-status-pill news-status-upcoming" : "news-status-pill news-status-past"));
        }

        // Title & Category
        const titleEl = document.getElementById("mn-modal-title");
        const catEl = document.getElementById("mn-modal-category");
        if (titleEl) titleEl.textContent = item.event;
        if (catEl) catEl.textContent = item.category || "Institutional Macroeconomic Telemetry";

        // Timing Ribbon (IST & UTC)
        const timeIstEl = document.getElementById("mn-modal-time-ist");
        const timeUtcEl = document.getElementById("mn-modal-time-utc");
        const diffEl = document.getElementById("mn-modal-diff");
        if (timeIstEl) timeIstEl.textContent = item.time_ist || item.time;
        if (timeUtcEl) timeUtcEl.textContent = item.time_utc || "UTC Reference";
        if (diffEl) {
            diffEl.textContent = item.is_live 
                ? `🔴 LIVE ACTIVE (Ends ${item.live_end_ist || ''})` 
                : (item.is_past ? `✓ Ended at ${item.live_end_ist || item.time_ist}` : (item.status_badge || `⏳ Upcoming`));
        }

        // Metrics Grid
        const actEl = document.getElementById("mn-modal-actual");
        const fcstEl = document.getElementById("mn-modal-forecast");
        const prevEl = document.getElementById("mn-modal-previous");
        const devEl = document.getElementById("mn-modal-deviation");
        if (actEl) {
            actEl.textContent = item.actual || "—";
            actEl.style.color = item.is_live ? "#ff3b5c" : (item.actual && item.actual !== "Upcoming" && item.actual !== "—" ? "var(--neon-bull)" : "var(--accent-cyan)");
        }
        if (fcstEl) fcstEl.textContent = item.forecast || "—";
        if (prevEl) prevEl.textContent = item.previous || "—";
        if (devEl) {
            devEl.textContent = item.deviation_summary || "In Line";
            devEl.style.color = (item.deviation_summary && item.deviation_summary.includes("+")) ? "var(--neon-bull)" : ((item.deviation_summary && item.deviation_summary.includes("-")) ? "#ff3b5c" : "var(--accent-cyan)");
        }

        // Bias & Shock Analysis
        const biasEl = document.getElementById("mn-modal-bias");
        const impactDescEl = document.getElementById("mn-modal-impact-desc");
        if (biasEl) biasEl.textContent = item.direction_bias || `DIRECTIONAL MOMENTUM ON ${item.currency}`;
        if (impactDescEl) impactDescEl.textContent = item.impact_analysis || item.shock_alert;

        // Description
        const descEl = document.getElementById("mn-modal-desc");
        if (descEl) descEl.textContent = item.description || "Comprehensive macroeconomic release parsed by HM AI 4.0 Institutional Decision Engine.";

        // Affected Pairs
        const pairsEl = document.getElementById("mn-modal-pairs");
        if (pairsEl) {
            const pairs = item.affected_pairs || ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"];
            pairsEl.innerHTML = pairs.map(p => `<span class="news-affected-tag" style="font-size:11px; padding:3px 8px;">${p}</span>`).join("");
        }

        // Warning Box
        const warnEl = document.getElementById("mn-modal-warning");
        if (warnEl) warnEl.textContent = item.execution_warning || item.shock_alert;

        modal.style.display = "flex";
        modal.classList.add("active");
    }

    function closeNewsDetailModal() {
        const modal = document.getElementById("macro-news-modal");
        if (modal) {
            modal.style.display = "none";
            modal.classList.remove("active");
        }
    }

    window.openNewsDetailModal = openNewsDetailModal;
    window.closeNewsDetailModal = closeNewsDetailModal;

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeNewsDetailModal();
        }
    });

    let _lastPositionsSnapshot = "";
    function renderActiveTradesDOM(positions) {
        if (!el.positionsTbody) return;
        if (el.positionsCount) el.positionsCount.textContent = `${positions.length} Open`;

        if (positions.length === 0) {
            el.positionsTbody.innerHTML = '<tr><td colspan="11" style="text-align:center; color:var(--text-dim); padding:16px;">No Active MT5 Positions Open</td></tr>';
            _lastPositionsSnapshot = "";
            return;
        }

        const snapshot = JSON.stringify(positions);
        if (snapshot === _lastPositionsSnapshot) {
            return; // Skip DOM update if positions are identical
        }
        _lastPositionsSnapshot = snapshot;

        el.positionsTbody.innerHTML = positions.map(p => {
            const isBuy = p.type === "BUY";
            const profit = p.profit || 0;
            const profitColor = profit >= 0 ? "var(--neon-bull)" : "var(--neon-bear)";
            const profitPrefix = profit >= 0 ? "+" : "";

            let progressPct = 50;
            if (p.sl && p.tp && p.sl !== p.tp) {
                const total = Math.abs(p.tp - p.sl);
                const currentDist = isBuy ? (p.current_price - p.sl) : (p.sl - p.current_price);
                progressPct = Math.max(5, Math.min(95, (currentDist / total) * 100));
            }

            return `
                <tr>
                    <td style="color:var(--text-dim);">#${p.ticket}</td>
                    <td><b style="color:#ffffff;">${p.symbol}</b></td>
                    <td><span class="badge ${isBuy ? 'badge-ready-buy' : 'badge-ready-sell'}" style="font-size:8.5px; padding:1px 5px;">${p.type}</span></td>
                    <td class="mono-number" style="font-weight:700;">${p.volume.toFixed(2)}</td>
                    <td class="mono-number">${formatPrice(p.open_price, p.symbol)}</td>
                    <td class="mono-number">${formatPrice(p.current_price, p.symbol)}</td>
                    <td class="mono-number" style="color:var(--neon-bear);">${p.sl > 0 ? formatPrice(p.sl, p.symbol) : '—'}</td>
                    <td class="mono-number" style="color:var(--neon-bull);">${p.tp > 0 ? formatPrice(p.tp, p.symbol) : '—'}</td>
                    <td class="mono-number" style="color:${profitColor}; font-weight:800; font-size:11.5px;">${profitPrefix}$${profit.toFixed(2)}</td>
                    <td>
                        <div class="position-progress-wrap">
                            <div class="progress-track">
                                <div class="progress-fill" style="width:${progressPct}%;"></div>
                            </div>
                            <div class="progress-labels">
                                <span>SL</span>
                                <span>TP</span>
                            </div>
                        </div>
                    </td>
                    <td>
                        <button class="btn-close-pos" onclick="closePosition(${p.ticket})">Close</button>
                    </td>
                </tr>
            `;
        }).join("");
    }

    function renderDevilAdvocateDOM(d) {
        const sym = state.symbol;
        if (el.deskActiveSymbol) el.deskActiveSymbol.textContent = sym;
        if (el.chartSymbol) el.chartSymbol.textContent = sym;

        const symStatus = (state.marketStatuses && state.marketStatuses[sym]) || computeClientMarketStatus(sym);
        const isMarketClosed = !symStatus.is_open;

        // Enable or disable 1-click execution buttons based on market open status
        if (el.btnBuyAction) {
            el.btnBuyAction.disabled = isMarketClosed;
            el.btnBuyAction.style.opacity = isMarketClosed ? "0.35" : "1.0";
            el.btnBuyAction.style.cursor = isMarketClosed ? "not-allowed" : "pointer";
        }
        if (el.btnSellAction) {
            el.btnSellAction.disabled = isMarketClosed;
            el.btnSellAction.style.opacity = isMarketClosed ? "0.35" : "1.0";
            el.btnSellAction.style.cursor = isMarketClosed ? "not-allowed" : "pointer";
        }

        if (!d) {
            if (el.planStrategyPill) el.planStrategyPill.textContent = "SYNTHESIZING...";
            if (el.planEntry) el.planEntry.textContent = "--";
            if (el.planSl) el.planSl.textContent = "--";
            if (el.planTp) el.planTp.textContent = "--";
            if (el.decisionRr) el.decisionRr.textContent = "--";
            if (el.cognitionRr) el.cognitionRr.textContent = "--";
            if (el.cognitionStrat) el.cognitionStrat.textContent = "--";
            if (el.planRiskAmt) el.planRiskAmt.textContent = "--";
            if (el.planCalcLots) el.planCalcLots.textContent = "--";
            if (el.decisionWinProb) el.decisionWinProb.textContent = "--%";
            if (el.decisionEv) el.decisionEv.textContent = "--";
            if (el.decisionGateBadge) {
                el.decisionGateBadge.textContent = isMarketClosed ? "🔒 MARKET CLOSED" : "EVALUATING...";
                el.decisionGateBadge.style.color = isMarketClosed ? "#ff5277" : "var(--text-dim)";
            }
            if (el.gatePassCountTag) el.gatePassCountTag.textContent = isMarketClosed ? "PAUSED" : "-- / 14";
            if (el.deskBannerTitle) el.deskBannerTitle.textContent = `${sym} — PENDING ANALYSIS`;
            if (el.deskBannerStatus) {
                el.deskBannerStatus.textContent = isMarketClosed ? "🔒 CLOSED" : "SCANNING";
                el.deskBannerStatus.className = isMarketClosed ? "radar-action-pill badge-market-closed" : "radar-action-pill badge-no-setup";
            }
            if (el.deskBannerEntry) el.deskBannerEntry.textContent = "--";
            if (el.deskBannerSl) el.deskBannerSl.textContent = "--";
            if (el.deskBannerTp) el.deskBannerTp.textContent = "--";
            if (el.deskBannerRr) el.deskBannerRr.textContent = "--";
            if (el.deskBannerRisk) el.deskBannerRisk.textContent = "--%";
            if (el.deskBannerProb) el.deskBannerProb.textContent = "--%";
            if (el.devilPenaltyScore) el.devilPenaltyScore.textContent = "0.0 / 50.0";
            if (el.devilPenaltyFill) el.devilPenaltyFill.style.width = "0%";
            if (el.devilRiskCoeff) el.devilRiskCoeff.textContent = "1.00x";
            if (el.devilRiskFill) el.devilRiskFill.style.width = "100%";
            return;
        }

        const badge = getStatusBadge(d);
        const hasValidBracket = d.stop_loss && d.entry_price && (Math.abs(d.stop_loss - d.entry_price) > 1e-5);
        const entryStr = formatPrice(d.entry_price, sym);
        const slStr = hasValidBracket ? formatPrice(d.stop_loss, sym) : "--";
        const tpStr = (hasValidBracket && d.take_profit && Math.abs(d.take_profit - d.entry_price) > 1e-5) ? formatPrice(d.take_profit, sym) : "--";
        const rrStr = (hasValidBracket && d.risk_reward_ratio) ? `1:${Number(d.risk_reward_ratio).toFixed(2)}` : "--";
        const probVal = d.probabilities && d.probabilities[d.bias ? d.bias.toLowerCase() : "buy"] 
            ? d.probabilities[d.bias ? d.bias.toLowerCase() : "buy"] 
            : (d.model_confidence || 0.50);
        const probPct = Math.round(probVal * 100);
        const evVal = d.expected_value || 0;
        const evStr = `${evVal >= 0 ? '+' : ''}$${evVal.toFixed(2)}`;
        const riskPct = d.calculated_risk_percent || 0.50;
        const stratName = d.strategy || "MARKET_STRUCTURE";

        // 1. Update 1-Click Execution Desk Summary Banner
        if (el.deskBannerTitle) el.deskBannerTitle.textContent = `${sym} — ${d.bias || 'WAIT'} / ${d.bias === 'SELL' ? 'SHORT' : (d.bias === 'BUY' ? 'LONG' : 'MONITOR')}`;
        if (el.deskBannerStatus) {
            el.deskBannerStatus.textContent = badge.label;
            el.deskBannerStatus.className = `radar-action-pill ${badge.cssClass}`;
        }
        if (el.deskBannerEntry) el.deskBannerEntry.textContent = entryStr;
        if (el.deskBannerSl) el.deskBannerSl.textContent = slStr;
        if (el.deskBannerTp) el.deskBannerTp.textContent = tpStr;
        if (el.deskBannerRr) el.deskBannerRr.textContent = rrStr;
        if (el.deskBannerRisk) el.deskBannerRisk.textContent = `${riskPct.toFixed(2)}%`;
        if (el.deskBannerProb) el.deskBannerProb.textContent = `${probPct}%`;

        // 2. Populate Trade Plan Card
        if (el.planStrategyPill) el.planStrategyPill.textContent = stratName;
        if (el.planEntry) el.planEntry.textContent = entryStr;
        if (el.planSl) el.planSl.textContent = slStr;
        if (el.planTp) el.planTp.textContent = tpStr;
        if (el.decisionRr) el.decisionRr.textContent = rrStr;
        if (el.planRiskAmt) {
            const bal = state.account ? (state.account.balance || 0) : 0;
            const riskDollars = bal * (riskPct / 100);
            el.planRiskAmt.textContent = riskDollars > 0 ? `$${riskDollars.toFixed(2)}` : "--";
        }
        if (el.planCalcLots) {
            el.planCalcLots.textContent = `${(el.deskLots ? el.deskLots.value : '0.01')} Lots`;
        }

        // 3. Populate AI Validation & Cognition Metrics
        if (el.decisionWinProb) el.decisionWinProb.textContent = `${probPct}%`;
        if (el.decisionEv) {
            el.decisionEv.textContent = evStr;
            el.decisionEv.style.color = evVal >= 0 ? "var(--accent-cyan)" : "var(--neon-bear)";
        }
        if (el.cognitionRr) el.cognitionRr.textContent = rrStr;
        if (el.cognitionStrat) el.cognitionStrat.textContent = stratName;
        if (el.chartRegime) {
            el.chartRegime.textContent = (d.regime && d.regime.primary) ? d.regime.primary : ((d.regime && typeof d.regime === "string") ? d.regime : "MONITORING");
        }

        const checks = (d.quality_gate && d.quality_gate.checks) ? { ...d.quality_gate.checks } : {};
        if (isMarketClosed) {
            checks["Market Session Open"] = false;
        }
        const passCount = Object.values(checks).filter(Boolean).length;
        const totalCount = Object.keys(checks).length || 14;
        const isGatePassed = !isMarketClosed && (d.quality_gate ? d.quality_gate.passed : (d.execution_authorized || false));
        
        if (el.gatePassCountTag) {
            el.gatePassCountTag.textContent = isMarketClosed ? "PAUSED (CLOSED)" : `${passCount} / ${totalCount} PASS`;
            el.gatePassCountTag.style.color = isMarketClosed ? "#ff5277" : (passCount === totalCount ? "var(--neon-bull)" : "var(--devil-amber)");
        }

        if (el.decisionGateBadge) {
            if (isMarketClosed) {
                el.decisionGateBadge.textContent = "🔒 MARKET CLOSED (WEEKEND)";
                el.decisionGateBadge.style.color = "#ff5277";
            } else if (isGatePassed) {
                el.decisionGateBadge.textContent = `GATE PASSED (${passCount}/${totalCount} PASS)`;
                el.decisionGateBadge.style.color = "var(--neon-bull)";
            } else {
                const failCount = totalCount - passCount;
                el.decisionGateBadge.textContent = `GATE WAITING (${failCount} of ${totalCount} Failed)`;
                el.decisionGateBadge.style.color = "var(--devil-amber)";
            }
        }

        // Gauges
        const penalty = d.adversarial_penalty || 0;
        if (el.devilPenaltyScore) el.devilPenaltyScore.textContent = `${penalty.toFixed(1)} / 50.0`;
        if (el.devilPenaltyFill) {
            el.devilPenaltyFill.style.width = `${Math.min(100, (penalty / 50.0) * 100)}%`;
            el.devilPenaltyFill.style.background = penalty > 25 ? "var(--neon-bear)" : (penalty > 15 ? "var(--devil-amber)" : "var(--neon-bull)");
        }

        const coeff = d.calculated_risk_percent ? Math.min(1.0, d.calculated_risk_percent / 0.5) : 1.0;
        if (el.devilRiskCoeff) el.devilRiskCoeff.textContent = `${coeff.toFixed(2)}x Multiplier`;
        if (el.devilRiskFill) el.devilRiskFill.style.width = `${Math.min(100, coeff * 100)}%`;

        // 4. Decision Rationale: Closed Market vs Waiting vs Authorized
        if (el.decisionRationaleCard && el.decisionRationaleContent) {
            const action = isMarketClosed ? "MARKET_CLOSED" : (d.decision || (badge.label.includes("READY") ? "EXECUTE" : (badge.label.includes("WAIT") ? "WAIT" : "NO_TRADE")));
            const waitingReasons = d.waiting_reasons || [];
            const rejectionReasons = d.rejection_reasons || [];
            const failingChecks = d.quality_gate ? (d.quality_gate.failing_reasons || []) : [];
            
            if (isMarketClosed) {
                if (el.decisionRationaleHeader) el.decisionRationaleHeader.className = "section-card-header closed";
                if (el.decisionRationaleTitle) el.decisionRationaleTitle.textContent = "🔒 Session Intermission: Weekend Close";
                if (el.decisionRationaleBadge) {
                    el.decisionRationaleBadge.textContent = "MARKET CLOSED";
                    el.decisionRationaleBadge.style.color = "#ff5277";
                }
                el.decisionRationaleContent.innerHTML = `
                    <div class="rationale-item" style="color:#ff5277; display:flex; gap:5px;">
                        <span class="icon">🔒</span>
                        <span>Trading session is closed for the weekend. Live execution and automated order dispatch are halted until session re-opens on <b>${symStatus.next_open_ist || 'Monday'}</b>.</span>
                    </div>
                    <div class="rationale-item" style="color:var(--text-secondary); margin-top:4px; display:flex; gap:5px;">
                        <span class="icon">📐</span>
                        <span>Pre-market structural levels, targets, and hypotheses are preserved for trade planning only.</span>
                    </div>
                `;
            } else if (action === "EXECUTE" || badge.label.includes("READY")) {
                if (el.decisionRationaleHeader) el.decisionRationaleHeader.className = "section-card-header emerald";
                if (el.decisionRationaleTitle) el.decisionRationaleTitle.textContent = "⚡ Decision Rationale: Trade Authorized";
                if (el.decisionRationaleBadge) {
                    el.decisionRationaleBadge.textContent = "ALL GATES PASSED";
                    el.decisionRationaleBadge.style.color = "var(--neon-bull)";
                }
                el.decisionRationaleContent.innerHTML = `
                    <div class="rationale-item ready">
                        <span class="icon">✓</span>
                        <span>All 14 Institutional Quality Gates, risk parameters, and EV edge hurdles passed. Setup authorized for live execution.</span>
                    </div>
                `;
            } else if (action === "WAIT" || badge.label.includes("WAIT")) {
                if (el.decisionRationaleHeader) el.decisionRationaleHeader.className = "section-card-header amber";
                if (el.decisionRationaleTitle) el.decisionRationaleTitle.textContent = "⏳ Decision Rationale: Waiting For Setup Triggers";
                if (el.decisionRationaleBadge) {
                    el.decisionRationaleBadge.textContent = "PENDING TRIGGER";
                    el.decisionRationaleBadge.style.color = "var(--devil-amber)";
                }
                const reasons = waitingReasons.length > 0 ? waitingReasons : failingChecks.map(c => `Awaiting quality gate check: ${c}`);
                if (reasons.length === 0) reasons.push("Awaiting structural candle close and liquidity sweep confirmation.");
                
                el.decisionRationaleContent.innerHTML = reasons.map(r => `
                    <div class="rationale-item wait">
                        <span class="icon">⏳</span>
                        <span>${r}</span>
                    </div>
                `).join("");
            } else {
                // NO_TRADE or TRADE INVALIDATED or REJECTED
                if (el.decisionRationaleHeader) el.decisionRationaleHeader.className = "section-card-header";
                if (el.decisionRationaleTitle) el.decisionRationaleTitle.textContent = "🚫 Decision Rationale: Rejection Causes";
                if (el.decisionRationaleBadge) {
                    el.decisionRationaleBadge.textContent = badge.label === "TRADE INVALIDATED" ? "INVALIDATED" : "REJECTED";
                    el.decisionRationaleBadge.style.color = "var(--neon-bear)";
                }
                const reasons = rejectionReasons.length > 0 ? rejectionReasons : failingChecks.map(c => `Failed quality check: ${c}`);
                if (reasons.length === 0) reasons.push("No actionable institutional market structure or viable directional edge.");
                
                el.decisionRationaleContent.innerHTML = reasons.map(r => `
                    <div class="rationale-item reject">
                        <span class="icon">✕</span>
                        <span>${r}</span>
                    </div>
                `).join("");
            }
        }

        // 5. Invalidation Conditions ("What Would Change My Mind")
        if (el.invalidationTriggerText) {
            const invs = d.invalidation_levels || [];
            if (invs.length > 0) {
                el.invalidationTriggerText.innerHTML = invs.map(i => `<div style="margin-bottom:3px;">• ${i}</div>`).join("");
            } else {
                const triggerSide = d.bias === 'BUY' ? 'demand support' : 'supply resistance';
                el.invalidationTriggerText.innerHTML = `<div>• H1 close violating ${triggerSide} (${slStr}).</div><div>• Bearish structural displacement breaking swing structure.</div>`;
            }
        }

        // 6. Threat Assessment Vectors
        if (el.threatVectorList) {
            const threats = d.risk_factors || [];
            if (threats.length > 0) {
                el.threatVectorList.innerHTML = threats.map(t => `<div class="threat-vector-item"><span style="color:var(--devil-amber);">⚠</span><span>${t}</span></div>`).join("");
            } else {
                el.threatVectorList.innerHTML = `<div class="threat-vector-item"><span style="color:var(--neon-bull);">✓</span><span>Normal institutional market parameters.</span></div>`;
            }
        }

        // 7. Quality Gate Checks Grid
        if (el.gateChecksList) {
            el.gateChecksList.innerHTML = Object.entries(checks).map(([name, pass]) => {
                let badgeHtml = `<span class="gate-check-fail">⏳ WAIT</span>`;
                if (name === "Market Session Open") {
                    badgeHtml = pass ? `<span class="gate-check-pass">✓ OPEN</span>` : `<span style="color:#ff5277; font-weight:700;">🔒 CLOSED</span>`;
                } else if (pass) {
                    badgeHtml = `<span class="gate-check-pass">✓ PASS</span>`;
                }
                return `
                    <div class="gate-check-row">
                        <span>${name}</span>
                        ${badgeHtml}
                    </div>
                `;
            }).join("");
        }
    }

    /* ==========================================================================
       4. ACTION HANDLERS: CLOSE POSITIONS & MANUAL 1-CLICK DESK
       ========================================================================== */

    window.closePosition = async function (ticket) {
        if (!confirm(`Confirm close position #${ticket}?`)) return;
        try {
            const res = await fetch("/api/action/close_position", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ticket })
            });
            const data = await res.json();
            if (data.status === "CLOSED") {
                fetchTelemetry();
            } else {
                alert(`Close failed: ${data.reason || 'Unknown error'}`);
            }
        } catch (err) {
            console.error("Close position error:", err);
        }
    };

    window.closeAllPositions = async function () {
        if (!confirm("EMERGENCY KILL-SWITCH: Close ALL active positions immediately?")) return;
        try {
            const res = await fetch("/api/action/close_all_positions", { method: "POST" });
            const data = await res.json();
            alert(`Closed ${data.closed_count || 0} positions.`);
            fetchTelemetry();
        } catch (err) {
            console.error("Close all error:", err);
        }
    };

    window.executeManualTrade = async function (action) {
        const sym = state.symbol;
        const lots = parseFloat(el.deskLots ? el.deskLots.value : 0.01) || 0.01;
        const sl = parseFloat(el.deskSl ? el.deskSl.value : 0.0) || 0.0;
        const tp = parseFloat(el.deskTp ? el.deskTp.value : 0.0) || 0.0;

        if (!confirm(`Confirm 1-Click Manual Execution: ${action} ${lots} ${sym}?`)) return;

        try {
            const res = await fetch("/api/action/manual_trade", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ symbol: sym, action, lots, sl, tp })
            });
            const data = await res.json();
            if (data.status === "FILLED") {
                alert(`Order FILLED: Ticket #${data.ticket} ${action} ${lots} ${sym} @ ${data.price}`);
                fetchTelemetry();
                if (typeof fetchHistory === "function") fetchHistory();
            } else {
                alert(`Execution Rejected: ${data.reason || data.error || data.comment || 'Broker rejection or invalid parameters'}`);
            }
        } catch (err) {
            console.error("Manual trade error:", err);
        }
    };

    window.switchLeftTab = function (tab) {
        state.activeLeftTab = tab;
        if (el.tabBtnRadar) el.tabBtnRadar.classList.toggle("active", tab === "radar");
        if (el.tabBtnNews) el.tabBtnNews.classList.toggle("active", tab === "news");
        if (el.tabContentRadar) el.tabContentRadar.style.display = tab === "radar" ? "flex" : "none";
        if (el.tabContentNews) el.tabContentNews.style.display = tab === "news" ? "flex" : "none";

        if (tab === "news") fetchNews();
        else fetchTelemetry();
    };

    window.switchRightTab = function (tab) {
        state.activeRightTab = tab;
        if (el.tabBtnDesk) el.tabBtnDesk.classList.toggle("active", tab === "desk");
        if (el.tabBtnCognition) el.tabBtnCognition.classList.toggle("active", tab === "cognition");
        if (el.tabContentDesk) el.tabContentDesk.style.display = tab === "desk" ? "flex" : "none";
        if (el.tabContentCognition) el.tabContentCognition.style.display = tab === "cognition" ? "flex" : "none";
    };

    /* ==========================================================================
       5. DRAGGABLE COPILOT & COMMAND PALETTE
       ========================================================================== */

    function initCopilotInteractivity() {
        if (!el.copilotHeader || !el.copilotWindow) return;

        let isDragging = false;
        let startX = 0, startY = 0, initialLeft = 0, initialTop = 0;

        el.copilotHeader.addEventListener("mousedown", e => {
            if (e.target.closest("button")) return;
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            const rect = el.copilotWindow.getBoundingClientRect();
            initialLeft = rect.left;
            initialTop = rect.top;
            document.body.style.cursor = "move";
        });

        window.addEventListener("mousemove", e => {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            const newLeft = Math.max(10, Math.min(window.innerWidth - 410, initialLeft + dx));
            const newTop = Math.max(60, Math.min(window.innerHeight - 320, initialTop + dy));
            el.copilotWindow.style.left = `${newLeft}px`;
            el.copilotWindow.style.top = `${newTop}px`;
            el.copilotWindow.style.right = "auto";
        });

        window.addEventListener("mouseup", () => {
            if (isDragging) {
                isDragging = false;
                document.body.style.cursor = "default";
            }
        });
    }

    window.toggleCopilotModal = function (forceOpen) {
        if (!el.copilotWindow) return;
        const isOpen = el.copilotWindow.style.display === "flex";
        const target = forceOpen !== undefined ? forceOpen : !isOpen;
        state.copilotOpen = target;
        state.copilotMinimized = false;

        el.copilotWindow.style.display = target ? "flex" : "none";
        if (el.copilotFab) el.copilotFab.style.display = "none";
        if (target && el.copilotInput) setTimeout(() => el.copilotInput.focus(), 50);
    };

    window.toggleCopilotMinimize = function (minimize) {
        if (!el.copilotWindow || !el.copilotFab) return;
        const target = minimize !== undefined ? minimize : !state.copilotMinimized;
        state.copilotMinimized = target;

        if (target) {
            el.copilotWindow.style.display = "none";
            el.copilotFab.style.display = "flex";
        } else {
            el.copilotWindow.style.display = "flex";
            el.copilotFab.style.display = "none";
            if (el.copilotInput) setTimeout(() => el.copilotInput.focus(), 50);
        }
    };

    window.clearCopilotChat = function () {
        if (!el.copilotMessages) return;
        el.copilotMessages.innerHTML = `<div class="copilot-bubble">🤖 <b>HM AI 4.0:</b> Context cleared. Standing by.</div>`;
    };

    window.exportCopilotChat = function () {
        if (!el.copilotMessages) return;
        const bubbles = el.copilotMessages.querySelectorAll(".copilot-bubble");
        let transcript = `# HM AI 4.0 — Trading Intelligence Transcript\nGenerated: ${new Date().toISOString()}\n\n---\n\n`;
        bubbles.forEach(b => {
            const isUser = b.classList.contains("user");
            const sender = isUser ? "TRADER" : "HM AI 4.0";
            const text = b.innerText.replace(/🤖 HM AI 4.0:\n/, "").replace(/🤖 JARVIS AI:\n/, "");
            transcript += `### [${sender}]\n${text}\n\n`;
        });

        const blob = new Blob([transcript], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `hm_ai_copilot_session_${Date.now()}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    window.sendChatMessage = async function () {
        if (!el.copilotInput) return;
        const query = el.copilotInput.value.trim();
        if (!query) return;

        const userBubble = document.createElement("div");
        userBubble.className = "copilot-bubble user";
        userBubble.textContent = query;
        el.copilotMessages.appendChild(userBubble);
        el.copilotInput.value = "";
        el.copilotMessages.scrollTop = el.copilotMessages.scrollHeight;

        try {
            const res = await fetch("/api/copilot/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query })
            });
            const data = await res.json();
            const aiBubble = document.createElement("div");
            aiBubble.className = "copilot-bubble";
            aiBubble.innerHTML = `🤖 <b>HM AI 4.0:</b><br>${data.response || 'No response.'}`;
            el.copilotMessages.appendChild(aiBubble);
            el.copilotMessages.scrollTop = el.copilotMessages.scrollHeight;
        } catch (err) {
            console.error("Copilot error:", err);
        }
    };

    window.handleChatKey = function (e) {
        if (e.key === "Enter") window.sendChatMessage();
    };

    function initCommandPalette() {
        window.addEventListener("keydown", e => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                toggleCommandPalette();
            } else if (e.key === "/" && document.activeElement.tagName !== "INPUT") {
                e.preventDefault();
                toggleCommandPalette(true);
            } else if (e.key === "Escape") {
                toggleCommandPalette(false);
            }
        });

        if (el.cmdPaletteInput) {
            el.cmdPaletteInput.addEventListener("input", () => {
                const q = el.cmdPaletteInput.value.toLowerCase().trim();
                renderCommandResults(q);
            });

            el.cmdPaletteInput.addEventListener("keydown", e => {
                const items = el.cmdPaletteResults.querySelectorAll(".command-item");
                if (e.key === "ArrowDown") {
                    e.preventDefault();
                    state.activeCommandIndex = (state.activeCommandIndex + 1) % items.length;
                    updateCommandSelection(items);
                } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    state.activeCommandIndex = (state.activeCommandIndex - 1 + items.length) % items.length;
                    updateCommandSelection(items);
                } else if (e.key === "Enter") {
                    e.preventDefault();
                    if (items[state.activeCommandIndex]) items[state.activeCommandIndex].click();
                }
            });
        }
    }

    window.toggleCommandPalette = function (forceOpen) {
        if (!el.cmdPaletteOverlay) return;
        const isOpen = el.cmdPaletteOverlay.style.display === "flex";
        const target = forceOpen !== undefined ? forceOpen : !isOpen;
        el.cmdPaletteOverlay.style.display = target ? "flex" : "none";
        if (target && el.cmdPaletteInput) {
            el.cmdPaletteInput.value = "";
            renderCommandResults("");
            setTimeout(() => el.cmdPaletteInput.focus(), 50);
        }
    };

    function renderCommandResults(query) {
        if (!el.cmdPaletteResults) return;
        const filtered = commandRegistry.filter(c => 
            c.title.toLowerCase().includes(query) || c.desc.toLowerCase().includes(query) || c.id.toLowerCase().includes(query)
        );
        state.activeCommandIndex = 0;
        el.cmdPaletteResults.innerHTML = filtered.map((c, i) => `
            <div class="command-item ${i === 0 ? 'selected' : ''}" onclick="executeCommand('${c.id}')">
                <div>
                    <b>${c.title}</b>
                    <div style="font-size:10px; color:var(--text-dim);">${c.desc}</div>
                </div>
                <span class="command-item-badge">${c.shortcut}</span>
            </div>
        `).join("");
    }

    function updateCommandSelection(items) {
        items.forEach((it, idx) => {
            it.classList.toggle("selected", idx === state.activeCommandIndex);
            if (idx === state.activeCommandIndex) it.scrollIntoView({ block: "nearest" });
        });
    }

    window.executeCommand = function (id) {
        const cmd = commandRegistry.find(c => c.id === id);
        if (cmd) cmd.action();
        toggleCommandPalette(false);
    };

    /* ==========================================================================
       6. GLOBAL INITIALIZATION
       ========================================================================== */

    window.selectSymbol = function (sym) {
        state.symbol = sym;
        if (el.chartSymbol) el.chartSymbol.textContent = sym;
        if (el.deskActiveSymbol) el.deskActiveSymbol.textContent = sym;

        // Reset & immediate re-bind of 1-Click Execution Desk inputs to new symbol's decision
        const activeDec = state.latestDecisions[sym];
        if (activeDec) {
            const hasValidBracket = activeDec.stop_loss && activeDec.entry_price && (Math.abs(activeDec.stop_loss - activeDec.entry_price) > 1e-5);
            if (el.deskSl) el.deskSl.value = hasValidBracket ? formatPrice(activeDec.stop_loss, sym) : "";
            if (el.deskTp) el.deskTp.value = (hasValidBracket && activeDec.take_profit) ? formatPrice(activeDec.take_profit, sym) : "";
            const winProb = activeDec.probabilities && activeDec.probabilities[activeDec.bias ? activeDec.bias.toLowerCase() : "buy"]
                ? activeDec.probabilities[activeDec.bias ? activeDec.bias.toLowerCase() : "buy"]
                : (activeDec.model_confidence || 0.73);
            if (el.deskWinProb) el.deskWinProb.value = `${Math.round(winProb * 100)}%`;
            renderDevilAdvocateDOM(activeDec);
        } else {
            if (el.deskSl) el.deskSl.value = "";
            if (el.deskTp) el.deskTp.value = "";
        }

        updateMarketStatusDisplay(sym);
        renderScannerRadarDOM(state.radarOpportunities);
        fetchCandles();
        fetchTelemetry();

        if (window.innerWidth <= 900 && state.activeMobileView === "radar") {
            switchMobileView("chart");
        }

        if (state.chartMode === "tv_pro") {
            initTradingViewAdvancedWidget();
        }
    };

    window.setTimeframe = function (tf) {
        state.timeframe = tf;
        document.querySelectorAll(".tf-btn").forEach(btn => {
            btn.classList.toggle("active", btn.textContent === tf);
        });
        fetchCandles();

        if (state.chartMode === "tv_pro") {
            initTradingViewAdvancedWidget();
        }
    };

    window.toggleSafeMode = async function () {
        try {
            const res = await fetch("/api/action/toggle_safe_mode", { method: "POST" });
            const data = await res.json();
            state.safeMode = data.safe_mode;
            fetchTelemetry();
        } catch (err) {
            console.error("Safe mode error:", err);
        }
    };

    window.refreshData = function () {
        fetchCandles();
        fetchTelemetry();
        fetchNews();
        updateMarketStatusDisplay(state.symbol);
    };

    window.switchMobileView = function (view) {
        state.activeMobileView = view;

        const btnChart = document.getElementById("mob-btn-chart");
        const btnRadar = document.getElementById("mob-btn-radar");
        const btnCognition = document.getElementById("mob-btn-cognition");
        const btnOrders = document.getElementById("mob-btn-orders");
        const btnAll = document.getElementById("mob-btn-all");

        if (btnChart) btnChart.classList.toggle("active", view === "chart");
        if (btnRadar) btnRadar.classList.toggle("active", view === "radar");
        if (btnCognition) btnCognition.classList.toggle("active", view === "cognition");
        if (btnOrders) btnOrders.classList.toggle("active", view === "orders");
        if (btnAll) btnAll.classList.toggle("active", view === "all");

        const leftPanel = document.getElementById("panel-left");
        const middlePanel = document.getElementById("panel-middle");
        const rightPanel = document.getElementById("panel-right");
        const chartPanel = document.getElementById("chart-main-panel");
        const posSection = document.getElementById("section-positions");
        const histSection = document.getElementById("section-history");

        if (window.innerWidth <= 900) {
            if (view === "chart") {
                if (leftPanel) leftPanel.style.display = "none";
                if (middlePanel) {
                    middlePanel.style.display = "flex";
                    if (chartPanel) chartPanel.style.display = "flex";
                    if (posSection) posSection.style.display = "none";
                    if (histSection) histSection.style.display = "none";
                }
                if (rightPanel) {
                    rightPanel.style.display = "flex";
                    switchRightTab("desk");
                }
            } else if (view === "radar") {
                if (leftPanel) leftPanel.style.display = "flex";
                if (middlePanel) middlePanel.style.display = "none";
                if (rightPanel) rightPanel.style.display = "none";
            } else if (view === "cognition") {
                if (leftPanel) leftPanel.style.display = "none";
                if (middlePanel) middlePanel.style.display = "none";
                if (rightPanel) {
                    rightPanel.style.display = "flex";
                    switchRightTab("cognition");
                }
            } else if (view === "orders") {
                if (leftPanel) leftPanel.style.display = "none";
                if (middlePanel) {
                    middlePanel.style.display = "flex";
                    if (chartPanel) chartPanel.style.display = "none";
                    if (posSection) posSection.style.display = "flex";
                    if (histSection) histSection.style.display = "flex";
                }
                if (rightPanel) rightPanel.style.display = "none";
            } else if (view === "all") {
                if (leftPanel) leftPanel.style.display = "flex";
                if (middlePanel) {
                    middlePanel.style.display = "flex";
                    if (chartPanel) chartPanel.style.display = "flex";
                    if (posSection) posSection.style.display = "flex";
                    if (histSection) histSection.style.display = "flex";
                }
                if (rightPanel) rightPanel.style.display = "flex";
            }
        } else {
            // Restore desktop multi-column view
            if (leftPanel) leftPanel.style.display = "flex";
            if (middlePanel) {
                middlePanel.style.display = "flex";
                if (chartPanel) chartPanel.style.display = "flex";
                if (posSection) posSection.style.display = "flex";
                if (histSection) histSection.style.display = "flex";
            }
            if (rightPanel) rightPanel.style.display = "flex";
        }

        setTimeout(() => {
            if (state.tvChartInstance && el.tvLiveContainer) {
                state.tvChartInstance.applyOptions({
                    width: el.tvLiveContainer.clientWidth || (window.innerWidth - 20),
                    height: el.tvLiveContainer.clientHeight || 300
                });
            }
        }, 80);
    };

    window.addEventListener("resize", () => {
        if (window.innerWidth > 900) {
            const leftPanel = document.getElementById("panel-left");
            const middlePanel = document.getElementById("panel-middle");
            const rightPanel = document.getElementById("panel-right");
            const chartPanel = document.getElementById("chart-main-panel");
            const posSection = document.getElementById("section-positions");
            const histSection = document.getElementById("section-history");
            if (leftPanel) leftPanel.style.display = "flex";
            if (middlePanel) {
                middlePanel.style.display = "flex";
                if (chartPanel) chartPanel.style.display = "flex";
                if (posSection) posSection.style.display = "flex";
                if (histSection) histSection.style.display = "flex";
            }
            if (rightPanel) rightPanel.style.display = "flex";
        } else {
            if (state.activeMobileView) {
                switchMobileView(state.activeMobileView);
            }
        }

        if (state.tvChartInstance && el.tvLiveContainer) {
            state.tvChartInstance.applyOptions({
                width: el.tvLiveContainer.clientWidth,
                height: el.tvLiveContainer.clientHeight
            });
        }
    });

    document.addEventListener("DOMContentLoaded", () => {
        initTradingViewLightweightChart();
        initCopilotInteractivity();
        initCommandPalette();

        updateMarketStatusDisplay(state.symbol);
        fetchCandles();
        fetchTelemetry();
        fetchNews();

        if (window.innerWidth <= 900) {
            switchMobileView("chart");
        }

        setInterval(fetchTelemetry, 1500);
        setInterval(fetchHistory, 5000);
        setInterval(fetchNews, 10000);
        fetchHistory();
        setInterval(fetchCandles, 5000);
        setInterval(simulateLiveMarketTick, 350);
        setInterval(tickMarketCountdown, 1000);
    });

})();


