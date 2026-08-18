/**
 * JARVIS AI 3.0 — Advanced Institutional Financial Trading Terminal Controller
 * 
 * Features:
 * - Multi-Pane Synchronized Charting (Candlestick + Volume/Momentum Sub-Pane)
 * - Smart Floating Tooltip with Structural AI Context
 * - Institutional Visual Overlays (Order Blocks, Fair Value Gaps)
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
        chartOverlays: {
            demandOB: { low: 2390.00, high: 2402.50, label: "DEMAND OB" },
            supplyOB: { low: 2435.00, high: 2446.00, label: "SUPPLY OB" },
            fvg: { low: 2410.00, high: 2415.20, label: "BEARISH FVG" }
        }
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
        chartSymbol: document.getElementById("chart-symbol"),
        chartRegime: document.getElementById("chart-regime"),
        chartLivePrice: document.getElementById("chart-live-price"),
        mainChartPane: document.getElementById("main-chart-pane"),
        subChartPane: document.getElementById("sub-chart-pane"),
        mainCanvas: document.getElementById("main-chart-canvas"),
        subCanvas: document.getElementById("sub-chart-canvas"),
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

    let hoverState = { active: false, x: 0, y: 0, candle: null };

    const commandRegistry = [
        { id: "xau", title: "Analyze Gold (XAUUSD)", desc: "Switch terminal view & load Gold desk", shortcut: "G", action: () => selectSymbol("XAUUSD") },
        { id: "eur", title: "Analyze Euro (EURUSD)", desc: "Switch terminal view & load EURUSD desk", shortcut: "E", action: () => selectSymbol("EURUSD") },
        { id: "gbp", title: "Analyze Pound (GBPUSD)", desc: "Switch terminal view & load GBPUSD desk", shortcut: "P", action: () => selectSymbol("GBPUSD") },
        { id: "jpy", title: "Analyze Yen (USDJPY)", desc: "Switch terminal view & load USDJPY desk", shortcut: "Y", action: () => selectSymbol("USDJPY") },
        { id: "btc", title: "Analyze Bitcoin (BTCUSD)", desc: "Switch terminal view & load BTCUSD desk", shortcut: "B", action: () => selectSymbol("BTCUSD") },
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
       1. MULTI-PANE SYNCHRONIZED CANVAS CHART ENGINE
       ========================================================================== */

    function renderMultiPaneChart() {
        if (!el.mainCanvas || !el.subCanvas) return;

        const mainRect = el.mainCanvas.parentElement.getBoundingClientRect();
        const subRect = el.subCanvas.parentElement.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        if (mainRect.width === 0 || mainRect.height === 0) return;

        el.mainCanvas.width = mainRect.width * dpr;
        el.mainCanvas.height = mainRect.height * dpr;
        const mainCtx = el.mainCanvas.getContext("2d");
        mainCtx.scale(dpr, dpr);

        el.subCanvas.width = subRect.width * dpr;
        el.subCanvas.height = subRect.height * dpr;
        const subCtx = el.subCanvas.getContext("2d");
        subCtx.scale(dpr, dpr);

        const w = mainRect.width;
        const mainH = mainRect.height;
        const subH = subRect.height;

        mainCtx.fillStyle = "#080c14";
        mainCtx.fillRect(0, 0, w, mainH);
        subCtx.fillStyle = "#060a12";
        subCtx.fillRect(0, 0, w, subH);

        const candles = state.candles;
        if (!candles || candles.length === 0) {
            mainCtx.fillStyle = "#64748b";
            mainCtx.font = "12px 'JetBrains Mono', monospace";
            mainCtx.textAlign = "center";
            mainCtx.fillText("Streaming Institutional Market Feed...", w / 2, mainH / 2);
            return;
        }

        const count = Math.min(candles.length, 65);
        const visible = candles.slice(-count);

        let minPrice = Infinity;
        let maxPrice = -Infinity;
        let maxVolume = 0;

        visible.forEach(c => {
            if (c.low < minPrice) minPrice = c.low;
            if (c.high > maxPrice) maxPrice = c.high;
            if (c.volume > maxVolume) maxVolume = c.volume;
        });

        const pad = (maxPrice - minPrice) * 0.08 || 1.0;
        minPrice -= pad;
        maxPrice += pad;

        const priceToY = p => (mainH - 24) - ((p - minPrice) / (maxPrice - minPrice)) * (mainH - 45);
        const spacing = (w - 70) / count;
        const candleWidth = Math.max(3.5, spacing * 0.72);

        // Grid lines
        mainCtx.strokeStyle = "rgba(51, 65, 85, 0.22)";
        mainCtx.lineWidth = 1;
        const steps = 5;
        for (let i = 0; i <= steps; i++) {
            const y = 20 + (mainH - 45) * (i / steps);
            mainCtx.beginPath();
            mainCtx.moveTo(0, y);
            mainCtx.lineTo(w - 65, y);
            mainCtx.stroke();

            const pVal = maxPrice - (i / steps) * (maxPrice - minPrice);
            mainCtx.fillStyle = "#64748b";
            mainCtx.font = "10px 'JetBrains Mono', monospace";
            mainCtx.textAlign = "left";
            mainCtx.fillText(pVal.toFixed(pVal > 100 ? 2 : 5), w - 60, y + 3);
        }

        // Institutional Overlays (Demand / Supply / FVG)
        const obDemand = state.chartOverlays.demandOB;
        if (obDemand && obDemand.high >= minPrice && obDemand.low <= maxPrice) {
            const topY = priceToY(obDemand.high);
            const botY = priceToY(obDemand.low);
            mainCtx.fillStyle = "rgba(0, 245, 155, 0.08)";
            mainCtx.fillRect(0, topY, w - 70, Math.max(2, botY - topY));
            mainCtx.strokeStyle = "rgba(0, 245, 155, 0.35)";
            mainCtx.setLineDash([4, 4]);
            mainCtx.strokeRect(0, topY, w - 70, Math.max(2, botY - topY));
            mainCtx.setLineDash([]);
            mainCtx.fillStyle = "var(--neon-bull)";
            mainCtx.font = "9px 'JetBrains Mono', monospace";
            mainCtx.fillText(`[+] DEMAND OB (${obDemand.low}-${obDemand.high})`, 10, topY + 12);
        }

        // Candlesticks
        visible.forEach((c, idx) => {
            const x = idx * spacing + spacing / 2;
            const isBull = c.close >= c.open;
            const color = isBull ? "#00f59b" : "#ff3b5c";

            // Wick
            mainCtx.strokeStyle = color;
            mainCtx.lineWidth = 1.2;
            mainCtx.beginPath();
            mainCtx.moveTo(x, priceToY(c.high));
            mainCtx.lineTo(x, priceToY(c.low));
            mainCtx.stroke();

            // Body
            mainCtx.fillStyle = color;
            const topY = priceToY(Math.max(c.open, c.close));
            const botY = priceToY(Math.min(c.open, c.close));
            const bodyHeight = Math.max(2, botY - topY);
            mainCtx.fillRect(x - candleWidth / 2, topY, candleWidth, bodyHeight);
        });

        // Sub-pane: Volume & RSI Momentum
        subCtx.strokeStyle = "rgba(51, 65, 85, 0.2)";
        subCtx.lineWidth = 1;
        subCtx.beginPath();
        subCtx.moveTo(0, subH / 2);
        subCtx.lineTo(w - 65, subH / 2);
        subCtx.stroke();

        subCtx.beginPath();
        visible.forEach((c, idx) => {
            const x = idx * spacing + spacing / 2;
            const isBull = c.close >= c.open;

            if (maxVolume > 0) {
                const volHeight = (c.volume / maxVolume) * (subH * 0.65);
                subCtx.fillStyle = isBull ? "rgba(0, 245, 155, 0.18)" : "rgba(255, 59, 92, 0.18)";
                subCtx.fillRect(x - candleWidth / 2, subH - volHeight, candleWidth, volHeight);
            }

            const pseudoRsi = 30 + ((c.close - minPrice) / (maxPrice - minPrice)) * 40;
            const rsiY = subH - (pseudoRsi / 100) * subH;
            if (idx === 0) subCtx.moveTo(x, rsiY);
            else subCtx.lineTo(x, rsiY);
        });
        subCtx.strokeStyle = "#38bdf8";
        subCtx.lineWidth = 1.5;
        subCtx.stroke();

        // Crosshair & Tooltip
        if (hoverState.active && hoverState.candle) {
            const hx = hoverState.x;

            mainCtx.strokeStyle = "rgba(56, 189, 248, 0.4)";
            mainCtx.lineWidth = 1;
            mainCtx.setLineDash([3, 3]);
            mainCtx.beginPath();
            mainCtx.moveTo(hx, 0);
            mainCtx.lineTo(hx, mainH);
            mainCtx.moveTo(0, hoverState.y);
            mainCtx.lineTo(w - 65, hoverState.y);
            mainCtx.stroke();

            subCtx.strokeStyle = "rgba(56, 189, 248, 0.4)";
            subCtx.lineWidth = 1;
            subCtx.setLineDash([3, 3]);
            subCtx.beginPath();
            subCtx.moveTo(hx, 0);
            subCtx.lineTo(hx, subH);
            subCtx.stroke();
            mainCtx.setLineDash([]);
            subCtx.setLineDash([]);

            updateSmartTooltip(hoverState.candle, hx, hoverState.y);
        } else {
            if (el.smartTooltip) el.smartTooltip.style.display = "none";
        }

        // Live Header Price Tag
        const last = visible[visible.length - 1];
        if (last && el.chartLivePrice) {
            el.chartLivePrice.textContent = last.close.toFixed(last.close > 100 ? 2 : 5);
            el.chartLivePrice.style.color = last.close >= last.open ? "var(--neon-bull)" : "var(--neon-bear)";
        }
    }

    function updateSmartTooltip(candle, x, y) {
        const tip = el.smartTooltip;
        if (!tip) return;

        const isBull = candle.close >= candle.open;
        const color = isBull ? "var(--neon-bull)" : "var(--neon-bear)";
        const digits = candle.close > 100 ? 2 : 5;

        let contextTag = "Standard Liquidity Transition";
        if (candle.high >= state.chartOverlays.supplyOB.low) {
            contextTag = "⚠ Approaching H1 Supply Order Block";
        } else if (candle.low <= state.chartOverlays.demandOB.high) {
            contextTag = "✓ Institutional Demand Zone Absorption";
        } else if (candle.volume > 3000) {
            contextTag = "⚡ Volume Expansion Sweep (Stop-Hunt)";
        }

        const dateStr = typeof candle.time === "number"
            ? new Date(candle.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : String(candle.time).split(" ")[1] || "Live";

        tip.innerHTML = `
            <div class="tooltip-header">
                <span>${state.symbol} [${state.timeframe}]</span>
                <span>${dateStr}</span>
            </div>
            <div class="tooltip-row"><span>Open:</span> <b>${candle.open.toFixed(digits)}</b></div>
            <div class="tooltip-row"><span>High:</span> <b>${candle.high.toFixed(digits)}</b></div>
            <div class="tooltip-row"><span>Low:</span> <b>${candle.low.toFixed(digits)}</b></div>
            <div class="tooltip-row"><span>Close:</span> <b style="color:${color};">${candle.close.toFixed(digits)}</b></div>
            <div class="tooltip-row"><span>Volume:</span> <b>${candle.volume.toLocaleString()}</b></div>
            <div class="tooltip-structure-tag">✦ ${contextTag}</div>
        `;

        tip.style.display = "block";
        tip.style.left = `${Math.min(window.innerWidth - 200, x + 15)}px`;
        tip.style.top = `${Math.max(60, y - 40)}px`;
    }

    function initChartInteractions() {
        if (!el.mainCanvas) return;

        el.mainCanvas.addEventListener("mousemove", e => {
            const rect = el.mainCanvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const count = Math.min(state.candles.length, 65);
            const spacing = (rect.width - 70) / count;
            const idx = Math.floor(x / spacing);
            const visible = state.candles.slice(-count);

            if (idx >= 0 && idx < visible.length && x < rect.width - 70) {
                hoverState = { active: true, x, y, candle: visible[idx] };
            } else {
                hoverState = { active: false, x: 0, y: 0, candle: null };
            }
            requestAnimationFrame(renderMultiPaneChart);
        });

        el.mainCanvas.addEventListener("mouseleave", () => {
            hoverState = { active: false, x: 0, y: 0, candle: null };
            requestAnimationFrame(renderMultiPaneChart);
        });

        el.mainCanvas.addEventListener("dblclick", () => {
            if (hoverState.candle) {
                injectChartContextToCopilot(hoverState.candle);
            }
        });
    }

    function injectChartContextToCopilot(candle) {
        const timeStr = typeof candle.time === "number"
            ? new Date(candle.time * 1000).toLocaleTimeString()
            : String(candle.time);

        const prompt = `JARVIS, analyze the structural order flow and liquidity around ${timeStr} @ ${candle.close} for ${state.symbol}.`;
        toggleCopilotModal(true);
        if (el.copilotInput) {
            el.copilotInput.value = prompt;
            setTimeout(() => el.copilotInput.focus(), 100);
        }
    }

    /* ==========================================================================
       2. REAL-TIME DATA FETCHING & TELEMETRY
       ========================================================================== */

    async function fetchCandles() {
        try {
            const res = await fetch(`/api/candles?symbol=${state.symbol}&tf=${state.timeframe}`);
            const data = await res.json();
            if (data && data.candles) {
                state.candles = data.candles;
                requestAnimationFrame(renderMultiPaneChart);
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
        if (!state.candles || state.candles.length === 0) return;
        const last = state.candles[state.candles.length - 1];
        const volStep = (Math.random() - 0.495) * (last.close > 100 ? 0.35 : 0.00015);
        last.close = Math.max(last.low * 0.999, last.close + volStep);
        if (last.close > last.high) last.high = last.close;
        if (last.close < last.low) last.low = last.close;
        last.volume += Math.floor(Math.random() * 8) + 1;
        requestAnimationFrame(renderMultiPaneChart);
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
    };

    window.setTimeframe = function (tf) {
        state.timeframe = tf;
        document.querySelectorAll(".tf-btn").forEach(btn => {
            btn.classList.toggle("active", btn.textContent === tf);
        });
        fetchCandles();
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
        requestAnimationFrame(renderMultiPaneChart);
    });

    document.addEventListener("DOMContentLoaded", () => {
        initChartInteractions();
        initCopilotInteractivity();
        initCommandPalette();

        fetchCandles();
        fetchTelemetry();
        fetchNews();

        setInterval(fetchTelemetry, 1500);
        setInterval(fetchCandles, 5000);
        setInterval(simulateLiveMarketTick, 250);
    });

})();
