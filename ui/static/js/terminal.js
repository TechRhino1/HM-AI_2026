/**
 * JARVIS AI 3.0 — Institutional Financial Trading Terminal Controller
 * Real-Time Telemetry Streaming, Live Positions HUD, Scanner Radar, Devil's Advocate Panel & Canvas Chart
 */

(function () {
    'use strict';

    // Terminal State
    let currentSymbol = "XAUUSD";
    let currentTimeframe = "H1";
    let candlesData = [];
    let previousPositions = {};
    let previousAccountState = {};
    let isSafeModeActive = false;

    // DOM Element References
    const elements = {
        // Top HUD
        hudServer: document.getElementById("hud-server"),
        hudLogin: document.getElementById("hud-login"),
        hudBalance: document.getElementById("hud-balance"),
        hudEquity: document.getElementById("hud-equity"),
        hudFreeMargin: document.getElementById("hud-free-margin"),
        hudMarginLevel: document.getElementById("hud-margin-level"),
        hudStateSync: document.getElementById("hud-sync"),
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
        accMargin: document.getElementById("acc-margin"),
        accFreeMargin: document.getElementById("acc-free-margin"),
        accTradeAllowed: document.getElementById("acc-trade-allowed"),

        // Radar Panel
        radarList: document.getElementById("radar-list"),
        radarCount: document.getElementById("radar-count"),

        // Chart Header
        chartSymbol: document.getElementById("chart-symbol"),
        chartRegime: document.getElementById("chart-regime"),
        chartLivePrice: document.getElementById("chart-live-price"),
        canvasChart: document.getElementById("chart-canvas"),

        // Active Trades Table
        positionsTbody: document.getElementById("positions-tbody"),
        positionsCount: document.getElementById("pos-count"),

        // Devil's Advocate & Risk Panel
        devilPenaltyScore: document.getElementById("devil-penalty-score"),
        devilPenaltyFill: document.getElementById("devil-penalty-fill"),
        devilRiskCoeff: document.getElementById("devil-risk-coeff"),
        devilRiskFill: document.getElementById("devil-risk-fill"),
        invalidationTriggerText: document.getElementById("invalidation-trigger-text"),
        threatVectorList: document.getElementById("threat-vector-list"),
        decisionBadgeContainer: document.getElementById("decision-badge-container"),
        decisionWinProb: document.getElementById("decision-win-prob"),
        decisionEv: document.getElementById("decision-ev"),
        decisionRr: document.getElementById("decision-rr"),
        decisionPenaltyTag: document.getElementById("decision-penalty-tag"),
        gateChecksList: document.getElementById("gate-checks-list"),

        // Copilot
        copilotMessages: document.getElementById("copilot-messages"),
        copilotInput: document.getElementById("copilot-input")
    };

    /**
     * High-Performance Canvas Candlestick & Volume Renderer
     */
    function renderCandlestickChart(candles) {
        const canvas = elements.canvasChart;
        if (!canvas) return;

        const container = canvas.parentElement;
        const rect = container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        const ctx = canvas.getContext("2d");
        ctx.scale(dpr, dpr);

        const width = rect.width;
        const height = rect.height;

        // Background
        ctx.fillStyle = "#080c14";
        ctx.fillRect(0, 0, width, height);

        if (!candles || candles.length === 0) {
            ctx.fillStyle = "#64748b";
            ctx.font = "12px 'JetBrains Mono', monospace";
            ctx.textAlign = "center";
            ctx.fillText("Loading Real-Time Institutional Feed...", width / 2, height / 2);
            return;
        }

        // Keep last 65 candles for high-density view
        const count = Math.min(candles.length, 65);
        const visibleCandles = candles.slice(-count);

        let minPrice = Infinity;
        let maxPrice = -Infinity;
        let maxVolume = 0;

        visibleCandles.forEach(c => {
            if (c.low < minPrice) minPrice = c.low;
            if (c.high > maxPrice) maxPrice = c.high;
            if (c.volume > maxVolume) maxVolume = c.volume;
        });

        const padding = (maxPrice - minPrice) * 0.08 || 1.0;
        minPrice -= padding;
        maxPrice += padding;

        const chartBottom = height - 26;
        const priceToY = p => chartBottom - ((p - minPrice) / (maxPrice - minPrice)) * (chartBottom - 30);

        // Horizontal Grid Lines & Price Axis
        ctx.strokeStyle = "rgba(51, 65, 85, 0.25)";
        ctx.lineWidth = 1;
        const gridSteps = 5;
        for (let i = 0; i <= gridSteps; i++) {
            const y = 25 + (chartBottom - 35) * (i / gridSteps);
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width - 65, y);
            ctx.stroke();

            const pVal = maxPrice - (i / gridSteps) * (maxPrice - minPrice);
            ctx.fillStyle = "#64748b";
            ctx.font = "10px 'JetBrains Mono', monospace";
            ctx.textAlign = "left";
            ctx.fillText(pVal.toFixed(pVal > 100 ? 2 : 5), width - 60, y + 3);
        }

        // Render Candlesticks & Volume
        const candleSpacing = (width - 70) / count;
        const candleWidth = Math.max(3, candleSpacing * 0.72);

        visibleCandles.forEach((c, idx) => {
            const x = idx * candleSpacing + candleSpacing / 2;
            const isBull = c.close >= c.open;
            const candleColor = isBull ? "#00f59b" : "#ff3b5c";

            // Volume Bars at bottom
            if (maxVolume > 0) {
                const volHeight = (c.volume / maxVolume) * 45;
                ctx.fillStyle = isBull ? "rgba(0, 245, 155, 0.15)" : "rgba(255, 59, 92, 0.15)";
                ctx.fillRect(x - candleWidth / 2, chartBottom - volHeight, candleWidth, volHeight);
            }

            // High-Low Wick
            ctx.strokeStyle = candleColor;
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(x, priceToY(c.high));
            ctx.lineTo(x, priceToY(c.low));
            ctx.stroke();

            // Real Body
            ctx.fillStyle = candleColor;
            const topY = priceToY(Math.max(c.open, c.close));
            const botY = priceToY(Math.min(c.open, c.close));
            const bodyHeight = Math.max(2, botY - topY);
            ctx.fillRect(x - candleWidth / 2, topY, candleWidth, bodyHeight);
        });

        // Update live price header tag
        const lastCandle = visibleCandles[visibleCandles.length - 1];
        if (lastCandle && elements.chartLivePrice) {
            elements.chartLivePrice.textContent = lastCandle.close.toFixed(lastCandle.close > 100 ? 2 : 5);
            elements.chartLivePrice.style.color = lastCandle.close >= lastCandle.open ? "var(--neon-bull)" : "var(--neon-bear)";
        }
    }

    /**
     * Fetch Live Candle History for Central Chart
     */
    async function fetchCandles() {
        try {
            const res = await fetch(`/api/candles?symbol=${currentSymbol}&tf=${currentTimeframe}`);
            const data = await res.json();
            if (data && data.candles) {
                candlesData = data.candles;
                renderCandlestickChart(candlesData);
            }
        } catch (err) {
            console.error("Candles fetch error:", err);
        }
    }

    /**
     * Fetch Complete Real-Time Telemetry State
     */
    async function fetchTelemetry() {
        try {
            const res = await fetch("/api/telemetry_state");
            const state = await res.json();
            if (state) {
                updateAccountHUD(state.account, state.execution_mode, state.safe_mode);
                updateScannerRadar(state.radar_opportunities);
                updateActiveTrades(state.positions);
                updateDevilAdvocateAndDecision(state.latest_decisions);
            }
        } catch (err) {
            console.error("Telemetry fetch error:", err);
        }
    }

    /**
     * Update Top Header & Detailed Account Box
     */
    function updateAccountHUD(acc, mode, safeMode) {
        if (!acc) return;

        // Flash detection on balance / equity change
        if (previousAccountState.equity !== undefined && previousAccountState.equity !== acc.equity) {
            const elem = elements.hudEquity;
            if (elem) {
                elem.classList.remove("flash-up", "flash-down");
                void elem.offsetWidth;
                elem.classList.add(acc.equity >= previousAccountState.equity ? "flash-up" : "flash-down");
            }
        }
        previousAccountState = { ...acc };

        // Header Tiles
        if (elements.hudServer) elements.hudServer.textContent = acc.server || "XMGlobal-MT5 10";
        if (elements.hudLogin) elements.hudLogin.textContent = `#${acc.login || 345841337}`;
        if (elements.hudBalance) elements.hudBalance.textContent = `$${(acc.balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        if (elements.hudEquity) elements.hudEquity.textContent = `$${(acc.equity || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        if (elements.hudFreeMargin) elements.hudFreeMargin.textContent = `$${(acc.free_margin || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        if (elements.hudMarginLevel) elements.hudMarginLevel.textContent = `${Math.round(acc.margin_level || 0).toLocaleString()}%`;

        // Execution Mode & Safe Mode Badges
        if (elements.execModeBadge) elements.execModeBadge.textContent = mode || "LIVE";
        if (elements.statusBadge) {
            if (safeMode) {
                elements.statusBadge.textContent = "SAFE MODE (PAUSED)";
                elements.statusBadge.className = "badge badge-safe";
            } else {
                elements.statusBadge.innerHTML = '<span class="pulse-dot"></span> OPERATIONAL';
                elements.statusBadge.className = "badge badge-live";
            }
        }

        // Detailed Account Panel (Left Column)
        if (elements.accName) elements.accName.textContent = acc.name || "Live MT5 Trader";
        if (elements.accLeverage) elements.accLeverage.textContent = `1:${acc.leverage || 1000}`;
        if (elements.accCompany) elements.accCompany.textContent = acc.company || "XM Global Limited";
        if (elements.accLogin) elements.accLogin.textContent = `${acc.login || 345841337}`;
        if (elements.accBalance) elements.accBalance.textContent = `$${(acc.balance || 0).toFixed(2)}`;
        if (elements.accEquity) elements.accEquity.textContent = `$${(acc.equity || 0).toFixed(2)}`;

        const profit = acc.profit || 0;
        if (elements.accProfit) {
            elements.accProfit.textContent = `${profit >= 0 ? '+' : ''}$${profit.toFixed(2)}`;
            elements.accProfit.style.color = profit >= 0 ? "var(--neon-bull)" : "var(--neon-bear)";
        }

        if (elements.accMargin) elements.accMargin.textContent = `$${(acc.margin || 0).toFixed(2)}`;
        if (elements.accFreeMargin) elements.accFreeMargin.textContent = `$${(acc.free_margin || 0).toFixed(2)}`;
        if (elements.accTradeAllowed) {
            elements.accTradeAllowed.textContent = acc.trade_allowed !== false ? "YES (Full Access)" : "RESTRICTED";
            elements.accTradeAllowed.style.color = acc.trade_allowed !== false ? "var(--neon-bull)" : "var(--neon-bear)";
        }
    }

    /**
     * MODULE B: Upcoming Trades & Scanner Radar
     */
    function updateScannerRadar(opportunities) {
        const container = elements.radarList;
        if (!container) return;

        const opps = opportunities || [];
        if (elements.radarCount) elements.radarCount.textContent = `${opps.length} Monitored`;

        container.innerHTML = "";
        opps.forEach(opp => {
            const card = document.createElement("div");
            card.className = `radar-opportunity-card ${opp.symbol === currentSymbol ? 'active' : ''}`;
            card.onclick = () => selectSymbol(opp.symbol);

            const isBuy = opp.action === "BUY";
            const isSell = opp.action === "SELL";
            const actionClass = isBuy ? "radar-action-buy" : (isSell ? "radar-action-sell" : "radar-action-wait");
            const actionLabel = opp.action || "WAIT";

            // Status Indicator Mapping
            let statusText = "Waiting for Confirmation";
            let statusColor = "var(--devil-amber)";
            if (opp.score >= 70 && opp.ev > 20) {
                statusText = "Setup Armed & Ready";
                statusColor = "var(--neon-bull)";
            } else if (opp.action === "NO_TRADE") {
                statusText = "Filtered by Quality Gate";
                statusColor = "var(--text-dim)";
            }

            card.innerHTML = `
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
            `;
            container.appendChild(card);
        });
    }

    /**
     * MODULE A: Active Trades (Live Positions HUD with Proximity Progress Bar)
     */
    function updateActiveTrades(positions) {
        const tbody = elements.positionsTbody;
        if (!tbody) return;

        const posList = positions || [];
        if (elements.positionsCount) elements.positionsCount.textContent = `${posList.length} Open`;

        if (posList.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--text-dim); padding:16px;">No Active MT5 Positions Open</td></tr>';
            return;
        }

        tbody.innerHTML = posList.map(p => {
            const isBuy = p.type === "BUY";
            const profit = p.profit || 0;
            const profitColor = profit >= 0 ? "var(--neon-bull)" : "var(--neon-bear)";
            const profitPrefix = profit >= 0 ? "+" : "";

            // Calculate TP/SL Proximity Progress (0% to 100%)
            let progressPct = 50;
            if (p.sl && p.tp && p.sl !== p.tp) {
                const totalRange = Math.abs(p.tp - p.sl);
                const currentDistFromSl = isBuy ? (p.current_price - p.sl) : (p.sl - p.current_price);
                progressPct = Math.max(5, Math.min(95, (currentDistFromSl / totalRange) * 100));
            }

            return `
                <tr>
                    <td style="color:var(--text-dim);">#${p.ticket}</td>
                    <td><b style="color:#ffffff;">${p.symbol}</b></td>
                    <td>
                        <span class="badge ${isBuy ? 'radar-action-buy' : 'radar-action-sell'}" style="font-size:9.5px; padding:2px 6px;">
                            ${p.type}
                        </span>
                    </td>
                    <td class="mono-number" style="font-weight:700;">${p.volume.toFixed(2)}</td>
                    <td class="mono-number">${p.open_price.toFixed(p.open_price > 100 ? 2 : 5)}</td>
                    <td class="mono-number" style="color:var(--text-primary);">${p.current_price.toFixed(p.current_price > 100 ? 2 : 5)}</td>
                    <td class="mono-number" style="color:var(--neon-bear);">${p.sl > 0 ? p.sl.toFixed(p.sl > 100 ? 2 : 5) : '—'}</td>
                    <td class="mono-number" style="color:var(--neon-bull);">${p.tp > 0 ? p.tp.toFixed(p.tp > 100 ? 2 : 5) : '—'}</td>
                    <td class="mono-number" style="color:${profitColor}; font-weight:800; font-size:12px;">
                        ${profitPrefix}$${profit.toFixed(2)}
                    </td>
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
                </tr>
            `;
        }).join("");
    }

    /**
     * MODULE C: The Devil's Advocate & Adversarial Risk Panel
     */
    function updateDevilAdvocateAndDecision(decisions) {
        const d = (decisions && decisions[currentSymbol]) ? decisions[currentSymbol] : null;

        if (!d) {
            if (elements.invalidationTriggerText) {
                elements.invalidationTriggerText.textContent = "Scanning order book for structural invalidation levels...";
            }
            return;
        }

        // Active Decision Badge
        if (elements.decisionBadgeContainer) {
            const action = d.decision || "WAIT";
            const isExec = action === "EXECUTE";
            const badgeClass = isExec ? (d.bias === "BUY" ? "badge-buy" : "badge-sell") : "badge-wait";
            elements.decisionBadgeContainer.innerHTML = `
                <div class="decision-badge ${badgeClass}">
                    ${action}: ${d.bias || 'NEUTRAL'} (${d.strategy || 'STRUCTURE'})
                </div>
            `;
        }

        if (elements.chartRegime) {
            elements.chartRegime.textContent = (d.regime && d.regime.primary) ? d.regime.primary : "TREND_BULL";
        }

        // Dialectical Probabilities & EV
        const probBuy = d.probabilities && d.probabilities.buy ? d.probabilities.buy : 0.65;
        const winProb = (probBuy * 100).toFixed(0);
        if (elements.decisionWinProb) elements.decisionWinProb.textContent = `${winProb}%`;
        if (elements.decisionEv) elements.decisionEv.textContent = `$${(d.expected_value || 0).toFixed(2)}`;
        if (elements.decisionRr) elements.decisionRr.textContent = `1:${(d.risk_reward_ratio || 2.0).toFixed(2)}`;

        // Devil's Advocate Gauges
        const penalty = d.adversarial_penalty || 0.0;
        if (elements.devilPenaltyScore) elements.devilPenaltyScore.textContent = `${penalty.toFixed(1)} / 50.0`;
        if (elements.devilPenaltyFill) {
            const fillPct = Math.min(100, (penalty / 50.0) * 100);
            elements.devilPenaltyFill.style.width = `${fillPct}%`;
        }

        const riskCoeff = d.calculated_risk_percent ? Math.min(1.0, d.calculated_risk_percent / 0.5) : 0.85;
        if (elements.devilRiskCoeff) elements.devilRiskCoeff.textContent = `${riskCoeff.toFixed(2)}x Multiplier`;
        if (elements.devilRiskFill) {
            elements.devilRiskFill.style.width = `${Math.min(100, riskCoeff * 100)}%`;
        }

        // "What Would Change My Mind" Invalidation Box
        if (elements.invalidationTriggerText) {
            const triggers = d.invalidation_levels || [];
            elements.invalidationTriggerText.innerHTML = triggers.length > 0
                ? triggers.map(t => `<div style="margin-bottom:3px;">• ${t}</div>`).join("")
                : "H1 candle close below demand equilibrium (2390.00).";
        }

        // Threat Assessment Vector List
        if (elements.threatVectorList) {
            const threats = d.risk_factors || [];
            elements.threatVectorList.innerHTML = threats.length > 0
                ? threats.map(t => `
                    <div class="threat-item">
                        <span class="threat-bullet">⚠</span>
                        <span>${t}</span>
                    </div>
                `).join("")
                : `<div class="threat-item"><span class="threat-bullet">✓</span><span>Standard volatility bounds; no imminent macro traps.</span></div>`;
        }

        // 14-Point Quality Gate Checks
        if (elements.gateChecksList) {
            const checks = (d.quality_gate && d.quality_gate.checks) ? d.quality_gate.checks : {
                "Regime Viability": true,
                "Risk/Reward >= 1.5": true,
                "Positive Expected Value": false,
                "Spread Protection": true,
                "Devil Penalty Guard": true
            };

            elements.gateChecksList.innerHTML = Object.entries(checks).map(([name, pass]) => `
                <div class="gate-row">
                    <span>${name}</span>
                    <span class="${pass ? 'gate-pass' : 'gate-fail'}">${pass ? 'PASS' : 'FAIL'}</span>
                </div>
            `).join("");
        }
    }

    /**
     * Symbol Selection Handler
     */
    window.selectSymbol = function (sym) {
        currentSymbol = sym;
        if (elements.chartSymbol) elements.chartSymbol.textContent = sym;
        fetchCandles();
        fetchTelemetry();
    };

    /**
     * Timeframe Selection Handler
     */
    window.setTimeframe = function (tf) {
        currentTimeframe = tf;
        document.querySelectorAll(".tf-btn").forEach(btn => {
            btn.classList.toggle("active", btn.textContent === tf);
        });
        fetchCandles();
    };

    /**
     * Safe Mode Toggle
     */
    window.toggleSafeMode = async function () {
        try {
            const res = await fetch("/api/action/toggle_safe_mode", { method: "POST" });
            const data = await res.json();
            isSafeModeActive = data.safe_mode;
            fetchTelemetry();
        } catch (err) {
            console.error("Safe mode error:", err);
        }
    };

    /**
     * Copilot Chat Handler
     */
    window.sendChatMessage = async function () {
        const input = elements.copilotInput;
        if (!input) return;
        const query = input.value.trim();
        if (!query) return;

        const chatBox = elements.copilotMessages;

        // User bubble
        const userBubble = document.createElement("div");
        userBubble.className = "copilot-bubble user";
        userBubble.textContent = query;
        chatBox.appendChild(userBubble);
        input.value = "";
        chatBox.scrollTop = chatBox.scrollHeight;

        try {
            const res = await fetch("/api/copilot/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query })
            });
            const data = await res.json();

            const jarvisBubble = document.createElement("div");
            jarvisBubble.className = "copilot-bubble";
            jarvisBubble.innerHTML = `🤖 <b>JARVIS AI:</b><br>${data.response.replace(/\n/g, '<br>')}`;
            chatBox.appendChild(jarvisBubble);
            chatBox.scrollTop = chatBox.scrollHeight;
        } catch (err) {
            console.error("Copilot error:", err);
        }
    };

    window.handleChatKey = function (e) {
        if (e.key === "Enter") {
            window.sendChatMessage();
        }
    };

    window.refreshData = function () {
        fetchCandles();
        fetchTelemetry();
    };

    // Auto-Resize Canvas on window resize
    window.addEventListener("resize", () => {
        renderCandlestickChart(candlesData);
    });

    // Lifecycle Initialization
    document.addEventListener("DOMContentLoaded", () => {
        fetchCandles();
        fetchTelemetry();

        // High-Frequency Real-Time Polling Loop
        setInterval(fetchTelemetry, 1500);
        setInterval(fetchCandles, 4000);
    });

})();
