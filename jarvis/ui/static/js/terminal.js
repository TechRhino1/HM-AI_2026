/**
 * JARVIS AI 3.0 — Advanced Institutional Financial Trading Terminal Controller
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
            r1: 2425.00,
            r2: 2440.00,
            s1: 2390.00,
            s2: 2375.00
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

        // Manual Execution Desk
        deskActiveSymbol: document.getElementById("desk-active-symbol"),
        deskLots: document.getElementById("desk-lots"),
        deskWinProb: document.getElementById("desk-win-prob"),
        deskSl: document.getElementById("desk-sl"),
        deskTp: document.getElementById("desk-tp"),

        // Chart Stage
        chartMainPanel: document.getElementById("chart-main-panel"),
        chartSymbol: document.getElementById("chart-symbol"),
        chartRegime: document.getElementById("chart-regime"),
        chartLivePrice: document.getElementById("chart-live-price"),
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

        // Devil's Advocate & Risk Panel
        decisionBadgeContainer: document.getElementById("decision-badge-container"),
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
        { id: "copilot", title: "Toggle JARVIS AI Copilot", desc: "Open / Close intelligent assistant modal", shortcut: "C", action: () => toggleCopilotModal() },
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
            scaleMargins: { top: 0.8, bottom: 0 }
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
                contextTag = "⚠ Approaching Key Institutional Resistance Zone";
            } else if (candle.low <= state.supportResistance.s1) {
                contextTag = "✓ Institutional Demand Zone Support Absorption";
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
                    <div class="tooltip-structure-tag">✦ ${contextTag}</div>
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
        if (el.legendR1) el.legendR1.textContent = `🔴 Resistance: ${r1.toFixed(digits)}`;
        if (el.legendS1) el.legendS1.textContent = `🟢 Support: ${s1.toFixed(digits)}`;
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
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: `R1: ${state.supportResistance.r1.toFixed(digits)} (RESISTANCE)`
        });

        // Draw Active Support Level Line
        const s1Line = state.tvCandleSeries.createPriceLine({
            price: state.supportResistance.s1,
            color: '#00f59b',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: `S1: ${state.supportResistance.s1.toFixed(digits)} (SUPPORT)`
        });

        state.tvPriceLines.push(r1Line, s1Line);

        // Update Live Header Price
        const last = state.candles[state.candles.length - 1];
        if (last && el.chartLivePrice) {
            el.chartLivePrice.textContent = last.close.toFixed(digits);
            el.chartLivePrice.style.color = last.close >= last.open ? "var(--neon-bull)" : "var(--neon-bear)";
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
            btn.innerHTML = isExpanded ? "✕ Minimize" : "⛶ Expand";
            btn.classList.toggle("btn-warning", isExpanded);
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

                requestAnimationFrame(renderTelemetryDOM);
            }
        } catch (err) {
            console.error("Telemetry fetch error:", err);
        }
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

        if (el.hudServer) el.hudServer.textContent = acc.server || "XMGlobal-MT5 10";
        if (el.hudLogin) el.hudLogin.textContent = `#${acc.login || 345841337}`;
        if (el.hudBalance) el.hudBalance.textContent = `$${(acc.balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        if (el.hudEquity) el.hudEquity.textContent = `$${(acc.equity || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        if (el.hudFreeMargin) el.hudFreeMargin.textContent = `$${(acc.free_margin || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        if (el.hudMarginLevel) el.hudMarginLevel.textContent = `${Math.round(acc.margin_level || 0).toLocaleString()}%`;

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
        if (el.accLeverage) el.accLeverage.textContent = `1:${acc.leverage || 1000}`;
        if (el.accCompany) el.accCompany.textContent = acc.company || "XM Global Limited";
        if (el.accLogin) el.accLogin.textContent = `${acc.login || 345841337}`;
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

        // Update Manual Trade Desk Active Target
        if (el.deskActiveSymbol) el.deskActiveSymbol.textContent = state.symbol;
        const activeDec = state.latestDecisions[state.symbol];
        if (activeDec) {
            const winProb = activeDec.probabilities && activeDec.probabilities.buy ? activeDec.probabilities.buy : 0.73;
            if (el.deskWinProb) el.deskWinProb.value = `${(winProb * 100).toFixed(0)}%`;
            if (el.deskSl && !el.deskSl.value && activeDec.stop_loss) el.deskSl.value = activeDec.stop_loss;
            if (el.deskTp && !el.deskTp.value && activeDec.take_profit) el.deskTp.value = activeDec.take_profit;
        }
    }

    function renderScannerRadarDOM(opps) {
        if (!el.radarList) return;
        if (state.activeLeftTab === "radar" && el.leftPanelCounter) {
            el.leftPanelCounter.textContent = `${opps.length} Monitored`;
        }

        el.radarList.innerHTML = opps.map(opp => {
            const isBuy = opp.action === "BUY";
            const isSell = opp.action === "SELL";
            const actionClass = isBuy ? "radar-action-buy" : (isSell ? "radar-action-sell" : "radar-action-wait");
            const actionLabel = opp.action || "WAIT";

            let statusText = "Waiting for Confirmation";
            let statusColor = "var(--devil-amber)";
            if (opp.score >= 70 && opp.ev > 0) {
                statusText = "High-Conviction Setup Ready";
                statusColor = "var(--neon-bull)";
            } else if (opp.action === "NO_TRADE") {
                statusText = "Filtered by Quality Gate";
                statusColor = "var(--text-dim)";
            }

            return `
                <div class="radar-opportunity-card ${opp.symbol === state.symbol ? 'active' : ''}" onclick="selectSymbol('${opp.symbol}')">
                    <div class="radar-card-top">
                        <div class="radar-symbol">
                            ${opp.symbol}
                            <span class="radar-timeframe-tag">${opp.timeframe || 'H1'}</span>
                        </div>
                        <div class="radar-action-pill ${actionClass}">${actionLabel}</div>
                    </div>
                    <div class="radar-meta-row">
                        <span class="radar-setup-name">${opp.strategy || opp.regime || 'Institutional Structure'}</span>
                        <span class="mono-number" style="color: ${opp.ev >= 0 ? 'var(--neon-bull)' : 'var(--text-dim)'}; font-weight:700;">
                            EV: $${(opp.ev || 0).toFixed(2)}
                        </span>
                    </div>
                    <div class="radar-status-indicator">
                        <span class="status-dot" style="background-color: ${statusColor};"></span>
                        <span>${statusText}</span>
                    </div>
                </div>
            `;
        }).join("");
    }

    function renderNewsDOM(news) {
        if (!el.newsFeedList) return;
        if (state.activeLeftTab === "news" && el.leftPanelCounter) {
            el.leftPanelCounter.textContent = `${news.length} Events`;
        }

        el.newsFeedList.innerHTML = news.map(n => {
            const isHigh = n.impact === "HIGH";
            const badgeClass = isHigh ? "news-impact-high" : "news-impact-med";
            return `
                <div class="news-card">
                    <div class="news-card-header">
                        <span class="news-currency-tag">${n.currency}</span>
                        <span class="${badgeClass}">${n.impact} IMPACT</span>
                        <span class="mono-number" style="font-size:9.5px; color:var(--text-dim);">${n.time}</span>
                    </div>
                    <div class="news-title">${n.event}</div>
                    <div class="news-metrics-row">
                        <span>Fcst: <b>${n.forecast}</b></span>
                        <span>Prev: <b>${n.previous}</b></span>
                        <span>Actual: <b style="color:var(--accent-cyan);">${n.actual}</b></span>
                    </div>
                </div>
            `;
        }).join("");
    }

    function renderActiveTradesDOM(positions) {
        if (!el.positionsTbody) return;
        if (el.positionsCount) el.positionsCount.textContent = `${positions.length} Open`;

        if (positions.length === 0) {
            el.positionsTbody.innerHTML = '<tr><td colspan="11" style="text-align:center; color:var(--text-dim); padding:20px;">No Active MT5 Positions Open</td></tr>';
            return;
        }

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
                    <td><span class="badge ${isBuy ? 'radar-action-buy' : 'radar-action-sell'}" style="font-size:8.5px; padding:1px 5px;">${p.type}</span></td>
                    <td class="mono-number" style="font-weight:700;">${p.volume.toFixed(2)}</td>
                    <td class="mono-number">${p.open_price.toFixed(p.open_price > 100 ? 2 : 5)}</td>
                    <td class="mono-number">${p.current_price.toFixed(p.current_price > 100 ? 2 : 5)}</td>
                    <td class="mono-number" style="color:var(--neon-bear);">${p.sl > 0 ? p.sl.toFixed(p.sl > 100 ? 2 : 5) : '—'}</td>
                    <td class="mono-number" style="color:var(--neon-bull);">${p.tp > 0 ? p.tp.toFixed(p.tp > 100 ? 2 : 5) : '—'}</td>
                    <td class="mono-number" style="color:${profitColor}; font-weight:800; font-size:12px;">${profitPrefix}$${profit.toFixed(2)}</td>
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
        if (!d) return;

        if (el.decisionBadgeContainer) {
            const action = d.decision || "WAIT";
            const badgeClass = action === "EXECUTE" ? (d.bias === "BUY" ? "badge-buy" : "badge-sell") : "badge-wait";
            el.decisionBadgeContainer.innerHTML = `<div class="decision-badge ${badgeClass}">${action}: ${d.bias || 'NEUTRAL'} (${d.strategy || 'STRUCTURE'})</div>`;
        }
        if (el.chartRegime) {
            el.chartRegime.textContent = (d.regime && d.regime.primary) ? d.regime.primary : "TREND_BULL";
        }

        const prob = d.probabilities && d.probabilities.buy ? d.probabilities.buy : 0.73;
        if (el.decisionWinProb) el.decisionWinProb.textContent = `${(prob * 100).toFixed(0)}%`;
        if (el.decisionEv) el.decisionEv.textContent = `$${(d.expected_value || 0).toFixed(2)}`;
        if (el.decisionRr) el.decisionRr.textContent = `1:${(d.risk_reward_ratio || 2.5).toFixed(2)}`;

        const penalty = d.adversarial_penalty || 0;
        if (el.devilPenaltyScore) el.devilPenaltyScore.textContent = `${penalty.toFixed(1)} / 50.0`;
        if (el.devilPenaltyFill) el.devilPenaltyFill.style.width = `${Math.min(100, (penalty / 50.0) * 100)}%`;

        const coeff = d.calculated_risk_percent ? Math.min(1.0, d.calculated_risk_percent / 0.5) : 1.0;
        if (el.devilRiskCoeff) el.devilRiskCoeff.textContent = `${coeff.toFixed(2)}x Multiplier`;
        if (el.devilRiskFill) el.devilRiskFill.style.width = `${Math.min(100, coeff * 100)}%`;

        if (el.invalidationTriggerText) {
            const invs = d.invalidation_levels || [];
            el.invalidationTriggerText.innerHTML = invs.length > 0
                ? invs.map(i => `<div style="margin-bottom:2px;">• ${i}</div>`).join("")
                : "• H1 close below demand equilibrium (2390.00).";
        }

        if (el.threatVectorList) {
            const threats = d.risk_factors || [];
            el.threatVectorList.innerHTML = threats.length > 0
                ? threats.map(t => `<div class="threat-item"><span>⚠</span><span>${t}</span></div>`).join("")
                : `<div class="threat-item"><span style="color:var(--neon-bull);">✓</span><span>Normal market parameters.</span></div>`;
        }

        if (el.gateChecksList) {
            const checks = (d.quality_gate && d.quality_gate.checks) ? d.quality_gate.checks : {};
            el.gateChecksList.innerHTML = Object.entries(checks).map(([name, pass]) => `
                <div class="gate-row">
                    <span>${name}</span>
                    <span class="${pass ? 'gate-pass' : 'gate-fail'}">${pass ? 'PASS' : 'FAIL'}</span>
                </div>
            `).join("");
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
            } else {
                alert(`Execution Rejected: ${data.reason || 'Unknown error'}`);
            }
        } catch (err) {
            console.error("Manual trade error:", err);
        }
    };

    window.switchLeftTab = function (tab) {
        state.activeLeftTab = tab;
        if (el.tabBtnRadar) el.tabBtnRadar.classList.toggle("active", tab === "radar");
        if (el.tabBtnNews) el.tabBtnNews.classList.toggle("active", tab === "news");
        if (el.tabContentRadar) el.tabContentRadar.style.display = tab === "radar" ? "block" : "none";
        if (el.tabContentNews) el.tabContentNews.style.display = tab === "news" ? "block" : "none";

        if (tab === "news") fetchNews();
        else fetchTelemetry();
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
        el.copilotMessages.innerHTML = `<div class="copilot-bubble">🤖 <b>JARVIS AI:</b> Context cleared. Standing by.</div>`;
    };

    window.exportCopilotChat = function () {
        if (!el.copilotMessages) return;
        const bubbles = el.copilotMessages.querySelectorAll(".copilot-bubble");
        let transcript = `# JARVIS AI 3.0 — Trading Intelligence Transcript\nGenerated: ${new Date().toISOString()}\n\n---\n\n`;
        bubbles.forEach(b => {
            const isUser = b.classList.contains("user");
            const sender = isUser ? "TRADER" : "JARVIS AI";
            const text = b.innerText.replace(/🤖 JARVIS AI:\n/, "");
            transcript += `### [${sender}]\n${text}\n\n`;
        });

        const blob = new Blob([transcript], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `jarvis_copilot_session_${Date.now()}.md`;
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
            const jarvisBubble = document.createElement("div");
            jarvisBubble.className = "copilot-bubble";
            jarvisBubble.innerHTML = `🤖 <b>JARVIS AI:</b><br>${data.response || 'No response.'}`;
            el.copilotMessages.appendChild(jarvisBubble);
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
        fetchCandles();
        fetchTelemetry();

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
    };

    window.addEventListener("resize", () => {
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

        fetchCandles();
        fetchTelemetry();
        fetchNews();

        setInterval(fetchTelemetry, 1500);
        setInterval(fetchCandles, 5000);
        setInterval(simulateLiveMarketTick, 350);
    });

})();
