/**
 * JARVIS AI 3.0 — India F&O Options & Derivatives Terminal Client Controller
 * Renders live interactive payoff curves (Sensibull/Opstra algorithm), strike-wise OI bar visualizers,
 * multi-leg strategy builder, and Zerodha/Upstox basket orders.
 */

(function () {
    'use strict';

    // Application State
    const state = {
        symbol: "NIFTY",
        spotPrice: 24850.0,
        lotSize: 25,
        atmStrike: 24850,
        strikeStep: 50,
        expiry: "CURRENT",
        daysToExpiry: 4.0,
        daysToTarget: 0.0,
        simulatedSpot: 24850.0,
        chainData: null,
        payoffChart: null,
        oiChart: null,
        legs: [
            { action: "BUY", type: "CE", strike: 24850, price: 185.0, lots: 1 },
            { action: "SELL", type: "CE", strike: 24950, price: 110.0, lots: 1 }
        ]
    };

    // DOM Elements Cache
    const el = {
        searchInput: document.getElementById("opt-search-input"),
        autocompleteDropdown: document.getElementById("opt-search-autocomplete"),
        expirySelect: document.getElementById("opt-expiry-select"),
        
        // Spot KPIs
        spotPriceVal: document.getElementById("spot-price-val"),
        atmStrikeVal: document.getElementById("atm-strike-val"),
        maxPainVal: document.getElementById("max-pain-val"),
        pcrVal: document.getElementById("pcr-val"),
        straddlePremVal: document.getElementById("straddle-prem-val"),
        ivRankVal: document.getElementById("iv-rank-val"),
        lotSizeVal: document.getElementById("lot-size-val"),
        chainUndTag: document.getElementById("chain-und-tag"),

        // Sliders
        sliderDays: document.getElementById("slider-days"),
        sliderDaysVal: document.getElementById("slider-days-val"),
        sliderSpot: document.getElementById("slider-spot"),
        sliderSpotVal: document.getElementById("slider-spot-val"),

        // Canvas
        payoffCanvas: document.getElementById("payoff-canvas"),
        oiBarCanvas: document.getElementById("oi-bar-canvas"),

        // Legs Table & KPIs
        legsTbody: document.getElementById("legs-tbody"),
        stratMaxProfit: document.getElementById("strat-max-profit"),
        stratMaxLoss: document.getElementById("strat-max-loss"),
        stratBreakeven: document.getElementById("strat-breakeven"),
        stratPop: document.getElementById("strat-pop"),
        stratNetCost: document.getElementById("strat-net-cost"),
        stratMargin: document.getElementById("strat-margin"),

        // Portfolio Greeks
        portDelta: document.getElementById("port-delta"),
        portGamma: document.getElementById("port-gamma"),
        portTheta: document.getElementById("port-theta"),
        portVega: document.getElementById("port-vega"),

        // Option Chain Table
        fullChainTbody: document.getElementById("full-chain-tbody"),

        // AI Multi-Leg Spreads Grid
        aiOptRecGrid: document.getElementById("ai-opt-rec-grid"),

        // AI Single Entry Option Buying Signals Grid
        aiSingleSignalsGrid: document.getElementById("ai-single-signals-grid")
    };

    /* ==========================================================================
       1. DATA FETCHING & API INTERACTION
       ========================================================================== */

    async function fetchSingleOptionSignals() {
        if (!el.aiSingleSignalsGrid) return;
        try {
            const res = await fetch('/api/india/options/single_signals?limit=12');
            const data = await res.json();
            if (data && data.signals && data.signals.length > 0) {
                state.allSingleSignals = data.signals;
                renderSingleSignalsDOM(data.signals);
            }
        } catch (err) {
            console.error("Single option signals fetch error:", err);
        }
    }

    function renderSingleSignalsDOM(signals) {
        if (!el.aiSingleSignalsGrid || !signals || signals.length === 0) return;

        let html = "";
        signals.forEach((s, idx) => {
            const isCall = s.option_type === "CE";
            const cardClass = isCall ? "sig-call" : "sig-put";
            const pillClass = isCall ? "ce" : "pe";
            const tpGain = s.trade_plan.expected_gain_pct;
            const slLoss = s.trade_plan.max_loss_pct;

            html += `
            <div class="single-sig-card ${cardClass}" onclick="window.loadSingleSignalByIndex(${idx})">
                <div class="sig-card-top-row">
                    <div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <span class="sig-contract-name">${s.contract_symbol}</span>
                            <span class="sig-type-pill ${pillClass}">🟢 ${s.action_label}</span>
                        </div>
                        <div style="font-size:10px; color:var(--text-dim); margin-top:2px;">
                            ${s.name} • Expiry: ${s.expiry} • Lot: ${s.lot_size}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <span class="badge-grade-a-plus">🔥 ${s.conviction_score}% POP</span>
                        <div style="font-size:10px; color:var(--text-dim); margin-top:2px;">Spot: ₹${Number(s.spot_price).toLocaleString()}</div>
                    </div>
                </div>

                <div class="sig-plan-grid">
                    <div>
                        <div class="sig-plan-item-lbl">Entry Zone</div>
                        <div class="sig-plan-item-val text-cyan">₹${s.trade_plan.entry_premium}</div>
                    </div>
                    <div>
                        <div class="sig-plan-item-lbl">Target (TP1)</div>
                        <div class="sig-plan-item-val text-bull">₹${s.trade_plan.target_1_premium} <span style="font-size:9px;">(+${tpGain}%)</span></div>
                    </div>
                    <div>
                        <div class="sig-plan-item-lbl">Target (TP2)</div>
                        <div class="sig-plan-item-val text-gold">₹${s.trade_plan.target_2_premium}</div>
                    </div>
                    <div>
                        <div class="sig-plan-item-lbl">Stop Loss</div>
                        <div class="sig-plan-item-val text-bear">₹${s.trade_plan.stop_loss_premium} <span style="font-size:9px;">(-${slLoss}%)</span></div>
                    </div>
                </div>

                <div class="sig-capital-row">
                    <span>Capital Required (1 Lot): <b class="text-white">₹${Number(s.trade_plan.capital_required_per_lot_inr).toLocaleString()}</b></span>
                    <span>R:R: <b class="text-bull">${s.trade_plan.risk_reward}</b></span>
                    <span>Delta: <b class="text-cyan">${s.greeks.delta}</b></span>
                </div>

                <div class="sig-rationale-box">
                    ${s.rationale}
                </div>

                <div class="sig-card-actions">
                    <button class="btn-sig-load" onclick="event.stopPropagation(); window.loadSingleSignalByIndex(${idx})">
                        ⚡ Load into Payoff & Chart
                    </button>
                    <button class="btn-sig-order" onclick="event.stopPropagation(); window.copySingleOrderTicketByIndex(${idx})">
                        📋 Copy Order Ticket
                    </button>
                </div>
            </div>`;
        });

        el.aiSingleSignalsGrid.innerHTML = html;
    }

    window.filterSingleSignals = function (filterType, btn) {
        document.querySelectorAll(".sig-filter-btn").forEach(b => b.classList.remove("active"));
        if (btn) btn.classList.add("active");

        if (!state.allSingleSignals) return;

        let filtered = state.allSingleSignals;
        if (filterType === "CE") {
            filtered = state.allSingleSignals.filter(s => s.option_type === "CE");
        } else if (filterType === "PE") {
            filtered = state.allSingleSignals.filter(s => s.option_type === "PE");
        } else if (filterType === "INDEX") {
            filtered = state.allSingleSignals.filter(s => s.is_index);
        } else if (filterType === "EQUITY") {
            filtered = state.allSingleSignals.filter(s => !s.is_index);
        }

        renderSingleSignalsDOM(filtered);
    };

    window.loadSingleSignalByIndex = function (idx) {
        if (!state.allSingleSignals || !state.allSingleSignals[idx]) return;
        const sig = state.allSingleSignals[idx];

        // Switch underlying
        state.symbol = sig.symbol;
        document.querySelectorAll(".und-pill").forEach(p => {
            if (p.textContent.trim().toUpperCase().includes(sig.symbol)) {
                p.classList.add("active");
            } else {
                p.classList.remove("active");
            }
        });

        // Set single leg in strategy builder
        state.legs = [{
            action: "BUY",
            type: sig.option_type,
            strike: sig.strike,
            price: sig.trade_plan.entry_premium,
            lots: 1
        }];

        fetchOptionChain(sig.symbol);
    };

    window.copySingleOrderTicketByIndex = function (idx) {
        if (!state.allSingleSignals || !state.allSingleSignals[idx]) return;
        const sig = state.allSingleSignals[idx];
        const ticket = sig.broker_order_ticket;
        const ticketJson = JSON.stringify(ticket, null, 2);

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(ticketJson).then(() => {
                alert(`📋 Copied Order Ticket for ${sig.contract_symbol} (Entry ₹${sig.trade_plan.entry_premium}, SL ₹${sig.trade_plan.stop_loss_premium}, TP ₹${sig.trade_plan.target_1_premium})!`);
            });
        } else {
            prompt("Broker Order Ticket JSON:", ticketJson);
        }
    };

    async function fetchOptionRecommendations() {
        if (!el.aiOptRecGrid) return;
        try {
            const res = await fetch('/api/india/options/recommendations');
            const data = await res.json();
            if (data && data.recommendations && data.recommendations.length > 0) {
                renderOptionRecommendationsDOM(data.recommendations);
            }
        } catch (err) {
            console.error("Option recommendations fetch error:", err);
        }
    }

    function renderOptionRecommendationsDOM(recs) {
        if (!el.aiOptRecGrid || !recs || recs.length === 0) return;

        let html = "";
        recs.forEach((r, idx) => {
            const isBull = r.bias === "BULLISH";
            const isBear = r.bias === "BEARISH";
            const dirColor = isBull ? "var(--neon-bull)" : (isBear ? "var(--neon-bear)" : "var(--neon-gold)");
            const dirText = isBull ? "🟢 Bullish" : (isBear ? "🔴 Bearish" : "⚖️ Delta-Neutral");

            html += `
            <div class="opt-rec-card" onclick="window.loadRecommendedStrategyByIndex(${idx})">
                <div class="opt-rec-top-row">
                    <div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <span class="opt-rec-sym">${r.symbol}</span>
                            <span class="badge badge-nse">${r.badge}</span>
                        </div>
                        <div class="opt-rec-strat-name">${r.strategy_name}</div>
                    </div>
                    <div style="text-align:right;">
                        <span style="font-size:10px; font-weight:800; color:${dirColor};">${dirText}</span>
                        <div style="font-size:10px; color:var(--text-dim);">₹${Number(r.spot_price).toLocaleString()}</div>
                    </div>
                </div>

                <div class="opt-rec-legs-text">
                    ⚡ ${r.legs_desc}
                </div>

                <div class="opt-rec-kpis">
                    <div>
                        <div class="opt-rec-kpi-lbl">Max Profit</div>
                        <div class="opt-rec-kpi-val text-bull">+₹${Number(r.max_profit_inr).toLocaleString()}</div>
                    </div>
                    <div>
                        <div class="opt-rec-kpi-lbl">Max Loss</div>
                        <div class="opt-rec-kpi-val text-bear">-₹${Math.abs(Number(r.max_loss_inr)).toLocaleString()}</div>
                    </div>
                    <div>
                        <div class="opt-rec-kpi-lbl">Win Prob (POP)</div>
                        <div class="opt-rec-kpi-val text-cyan">${r.pop_pct}%</div>
                    </div>
                </div>

                <button class="btn-load-opt-strat" onclick="event.stopPropagation(); window.loadRecommendedStrategyByIndex(${idx})">
                    ⚡ Load Strategy in Payoff & Option Chain
                </button>
            </div>`;
        });

        el.aiOptRecGrid.innerHTML = html;
        state.cachedOptionRecs = recs;
    }

    window.loadRecommendedStrategyByIndex = function (idx) {
        if (!state.cachedOptionRecs || !state.cachedOptionRecs[idx]) return;
        const rec = state.cachedOptionRecs[idx];
        
        // Switch underlying
        state.symbol = rec.symbol;
        document.querySelectorAll(".und-pill").forEach(p => {
            if (p.textContent.trim().toUpperCase().includes(rec.symbol)) {
                p.classList.add("active");
            } else {
                p.classList.remove("active");
            }
        });

        state.legs = rec.legs.map(l => ({
            action: l.action,
            type: l.type,
            strike: l.strike,
            price: l.price,
            lots: l.lots || 1
        }));

        fetchOptionChain(rec.symbol);
    };

    async function fetchOptionChain(symbol) {
        try {
            const res = await fetch(`/api/india/options/chain?symbol=${symbol}`);
            const data = await res.json();
            if (data && data.chain) {
                state.chainData = data;
                state.spotPrice = data.spot_price;
                state.lotSize = data.lot_size;
                state.atmStrike = data.atm_strike;
                state.strikeStep = data.strike_step;
                state.simulatedSpot = data.spot_price;
                state.daysToExpiry = data.expiry_schedule ? data.expiry_schedule.days_to_expiry : 4.0;

                updateSpotKPIs(data);
                renderOptionChainDOM(data);
                renderOiBarChart(data);
                
                // Initialize default legs if first load
                if (state.legs.length === 0 || state.legs[0].strike !== data.atm_strike) {
                    window.applyPresetStrategy("BULLISH");
                } else {
                    recalculatePayoff();
                }
            }
        } catch (err) {
            console.error("Option chain fetch error:", err);
        }
    }

    /* ==========================================================================
       2. KPI & OPTION CHAIN DOM RENDERING
       ========================================================================== */

    function updateSpotKPIs(data) {
        if (el.spotPriceVal) el.spotPriceVal.textContent = `₹${Number(data.spot_price).toLocaleString(undefined, {minimumFractionDigits:2})}`;
        if (el.atmStrikeVal) el.atmStrikeVal.textContent = data.atm_strike.toLocaleString();
        if (el.maxPainVal) el.maxPainVal.textContent = data.max_pain_strike.toLocaleString();
        if (el.pcrVal) el.pcrVal.textContent = `${data.pcr.pcr_oi} (${data.pcr.sentiment})`;
        if (el.straddlePremVal && data.atm_straddle) {
            el.straddlePremVal.textContent = `₹${data.atm_straddle.combined_premium} (±${data.atm_straddle.expected_move_pct}%)`;
        }
        if (el.ivRankVal) el.ivRankVal.textContent = `${data.iv_rank} (IV Rank)`;
        if (el.lotSizeVal) el.lotSizeVal.textContent = `${data.lot_size} Qty`;
        if (el.chainUndTag) el.chainUndTag.textContent = data.symbol;

        if (el.sliderSpot) {
            el.sliderSpot.min = Math.floor(data.spot_price * 0.85);
            el.sliderSpot.max = Math.ceil(data.spot_price * 1.15);
            el.sliderSpot.value = data.spot_price;
            if (el.sliderSpotVal) el.sliderSpotVal.textContent = `₹${Number(data.spot_price).toFixed(2)}`;
        }
    }

    function renderOptionChainDOM(data) {
        if (!el.fullChainTbody) return;

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
                <td class="${callItm} trade-btns-cell">
                    <button class="btn-opt-trade-b" title="Buy Call (Long CE)" onclick="window.addLegFromChain('BUY', 'CE', ${row.strike}, ${call.ltp})">B</button>
                    <button class="btn-opt-trade-s" title="Sell / Write Call (Short CE)" onclick="window.addLegFromChain('SELL', 'CE', ${row.strike}, ${call.ltp})">S</button>
                </td>
                <td class="${callItm}">${call.delta}</td>
                <td class="${callItm}">${call.iv}%</td>
                <td class="${callItm}" style="color:${call.oi_change_pct >= 0 ? 'var(--neon-bull)' : 'var(--neon-bear)'};">${call.oi_change_pct >= 0 ? '+' : ''}${call.oi_change_pct}%</td>
                <td class="${callItm}">${call.oi.toLocaleString()}</td>
                <td class="${callItm}" style="color:#ffffff; font-weight:800;">₹${call.ltp}</td>

                <!-- STRIKE -->
                <td class="strike-cell">${row.strike}</td>

                <!-- PUTS -->
                <td class="${putItm}" style="color:#ffffff; font-weight:800;">₹${put.ltp}</td>
                <td class="${putItm}">${put.oi.toLocaleString()}</td>
                <td class="${putItm}" style="color:${put.oi_change_pct >= 0 ? 'var(--neon-bull)' : 'var(--neon-bear)'};">${put.oi_change_pct >= 0 ? '+' : ''}${put.oi_change_pct}%</td>
                <td class="${putItm}">${put.iv}%</td>
                <td class="${putItm}">${put.delta}</td>
                <td class="${putItm} trade-btns-cell">
                    <button class="btn-opt-trade-b" title="Buy Put (Long PE)" onclick="window.addLegFromChain('BUY', 'PE', ${row.strike}, ${put.ltp})">B</button>
                    <button class="btn-opt-trade-s" title="Sell / Write Put (Short PE)" onclick="window.addLegFromChain('SELL', 'PE', ${row.strike}, ${put.ltp})">S</button>
                </td>
            </tr>`;
        });

        el.fullChainTbody.innerHTML = html;
    }

    /* ==========================================================================
       3. INTERACTIVE MULTI-LEG PAYOFF DIAGRAM & MATH
       ========================================================================== */

    async function recalculatePayoff() {
        renderLegsTableDOM();

        try {
            const legsPayload = encodeURIComponent(JSON.stringify(state.legs));
            const res = await fetch(`/api/india/options/payoff?symbol=${state.symbol}&days_to_target=${state.daysToTarget}&legs=${legsPayload}`);
            const data = await res.json();
            if (data && data.curve_expiry) {
                updatePayoffKPIs(data);
                renderPayoffChart(data);
            }
        } catch (err) {
            console.error("Payoff calculation error:", err);
        }
    }

    function renderLegsTableDOM() {
        if (!el.legsTbody) return;

        let html = "";
        state.legs.forEach((leg, idx) => {
            const isBuy = leg.action.toUpperCase() === "BUY";
            const isCall = leg.type.toUpperCase() === "CE";

            html += `
            <tr>
                <td>
                    <select onchange="window.updateLegField(${idx}, 'action', this.value)">
                        <option value="BUY" ${isBuy ? 'selected' : ''}>BUY</option>
                        <option value="SELL" ${!isBuy ? 'selected' : ''}>SELL</option>
                    </select>
                </td>
                <td>
                    <select onchange="window.updateLegField(${idx}, 'type', this.value)">
                        <option value="CE" ${isCall ? 'selected' : ''}>CE</option>
                        <option value="PE" ${!isCall ? 'selected' : ''}>PE</option>
                    </select>
                </td>
                <td>
                    <input type="number" value="${leg.strike}" step="${state.strikeStep}" style="width:75px;" onchange="window.updateLegField(${idx}, 'strike', parseFloat(this.value))">
                </td>
                <td>
                    <input type="number" value="${leg.price}" step="0.5" style="width:65px;" onchange="window.updateLegField(${idx}, 'price', parseFloat(this.value))">
                </td>
                <td>
                    <input type="number" value="${leg.lots || 1}" min="1" max="50" style="width:45px;" onchange="window.updateLegField(${idx}, 'lots', parseInt(this.value, 10))">
                </td>
                <td style="color:${isCall ? 'var(--neon-bull)' : 'var(--neon-bear)'};">${isCall ? '+0.48' : '-0.52'}</td>
                <td style="color:var(--neon-bear);">-₹18.5</td>
                <td>
                    <button class="btn-remove-leg" onclick="window.removeLeg(${idx})">✕</button>
                </td>
            </tr>`;
        });

        el.legsTbody.innerHTML = html;
    }

    function updatePayoffKPIs(data) {
        if (el.stratMaxProfit) el.stratMaxProfit.textContent = `+₹${Number(data.max_profit_inr).toLocaleString(undefined, {minimumFractionDigits:2})}`;
        if (el.stratMaxLoss) el.stratMaxLoss.textContent = `-₹${Math.abs(Number(data.max_loss_inr)).toLocaleString(undefined, {minimumFractionDigits:2})}`;
        if (el.stratBreakeven) {
            el.stratBreakeven.textContent = data.breakevens && data.breakevens.length > 0 ? data.breakevens.join(", ") : "None";
        }
        if (el.stratPop) el.stratPop.textContent = `${data.probability_of_profit_pct}%`;
        if (el.stratNetCost) {
            const cost = data.net_debit_or_credit_inr;
            el.stratNetCost.textContent = `${cost >= 0 ? 'Debit' : 'Credit'} ₹${Math.abs(cost).toLocaleString(undefined, {minimumFractionDigits:2})}`;
        }
        if (el.stratMargin) {
            let marginHtml = `₹${Number(data.estimated_margin_inr).toLocaleString(undefined, {minimumFractionDigits:2})}`;
            if (data.margin_breakdown && data.margin_breakdown.hedge_benefit_inr > 0) {
                marginHtml += ` <span class="badge-benefit" title="SEBI Margin Relief for Hedged Positions">Save ₹${Number(data.margin_breakdown.hedge_benefit_inr).toLocaleString()}</span>`;
            }
            el.stratMargin.innerHTML = marginHtml;
        }

        if (data.portfolio_greeks) {
            const g = data.portfolio_greeks;
            if (el.portDelta) el.portDelta.textContent = `${g.net_delta > 0 ? '+' : ''}${g.net_delta}`;
            if (el.portGamma) el.portGamma.textContent = `${g.net_gamma > 0 ? '+' : ''}${g.net_gamma}`;
            if (el.portTheta) el.portTheta.textContent = `${g.net_theta_day_inr >= 0 ? '+' : ''}₹${g.net_theta_day_inr}/day`;
            if (el.portVega) el.portVega.textContent = `${g.net_vega_inr >= 0 ? '+' : ''}₹${g.net_vega_inr}`;
        }
    }

    function renderPayoffChart(data) {
        if (!el.payoffCanvas || typeof Chart === "undefined") return;

        const ctx = el.payoffCanvas.getContext("2d");
        if (state.payoffChart) {
            state.payoffChart.destroy();
        }

        const labels = data.spot_grid;
        const expiryData = data.curve_expiry;
        const targetData = data.curve_target;

        state.payoffChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "P&L at Expiry",
                        data: expiryData,
                        borderColor: "#00f59b",
                        borderWidth: 2.5,
                        fill: {
                            target: { value: 0 },
                            above: "rgba(0, 245, 155, 0.12)",
                            below: "rgba(255, 59, 92, 0.12)"
                        },
                        tension: 0.1,
                        pointRadius: 0
                    },
                    {
                        label: "P&L at Target Date",
                        data: targetData,
                        borderColor: "#00d4ff",
                        borderWidth: 2,
                        borderDash: [4, 4],
                        fill: false,
                        tension: 0.2,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                scales: {
                    x: {
                        grid: { color: "rgba(51, 65, 85, 0.2)" },
                        ticks: { color: "#94a3b8", font: { family: "'JetBrains Mono', monospace", size: 10 } }
                    },
                    y: {
                        grid: { color: "rgba(51, 65, 85, 0.2)" },
                        ticks: {
                            color: "#94a3b8",
                            font: { family: "'JetBrains Mono', monospace", size: 10 },
                            callback: (val) => `₹${val}`
                        }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ₹${ctx.raw.toLocaleString()}`
                        }
                    }
                }
            }
        });
    }

    /* ==========================================================================
       4. STRIKE-WISE OI BAR CHART (CHART.JS)
       ========================================================================== */

    function renderOiBarChart(data) {
        if (!el.oiBarCanvas || typeof Chart === "undefined" || !data.chain) return;

        const ctx = el.oiBarCanvas.getContext("2d");
        if (state.oiChart) {
            state.oiChart.destroy();
        }

        const labels = data.chain.map(r => r.strike);
        const callOIs = data.chain.map(r => r.call.oi);
        const putOIs = data.chain.map(r => r.put.oi);

        state.oiChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Call OI (CE)",
                        data: callOIs,
                        backgroundColor: "rgba(255, 59, 92, 0.65)",
                        borderColor: "#ff3b5c",
                        borderWidth: 1
                    },
                    {
                        label: "Put OI (PE)",
                        data: putOIs,
                        backgroundColor: "rgba(0, 245, 155, 0.65)",
                        borderColor: "#00f59b",
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: "#94a3b8", font: { family: "'JetBrains Mono', monospace", size: 9 } }
                    },
                    y: {
                        grid: { color: "rgba(51, 65, 85, 0.2)" },
                        ticks: { color: "#94a3b8", font: { family: "'JetBrains Mono', monospace", size: 9 } }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    /* ==========================================================================
       5. STRATEGY PRESETS & ACTIONS
       ========================================================================== */

    window.selectUnderlying = function (sym, btn) {
        state.symbol = sym;
        document.querySelectorAll(".und-pill").forEach(p => p.classList.remove("active"));
        if (btn) btn.classList.add("active");
        state.legs = [];
        fetchOptionChain(sym);
    };

    window.applyPresetStrategy = async function (presetType) {
        document.querySelectorAll(".preset-btn").forEach(btn => {
            const oc = btn.getAttribute("onclick") || "";
            if (oc.includes(presetType)) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });

        try {
            const res = await fetch(`/api/india/options_ai?symbol=${state.symbol}&bias=${presetType}`);
            const data = await res.json();
            if (data && data.legs && data.legs.length > 0) {
                state.legs = data.legs.map(l => ({
                    action: l.action.toUpperCase(),
                    type: l.type.toUpperCase(),
                    strike: parseFloat(l.strike),
                    price: parseFloat(l.price),
                    lots: parseInt(l.lots || 1, 10)
                }));
                recalculatePayoff();
                return;
            }
        } catch (err) {
            console.error("Preset strategy fetch error:", err);
        }

        // Local algorithmic fallback
        const spot = state.spotPrice;
        const step = state.strikeStep;
        const atm = state.atmStrike;

        if (presetType === "BUY_CALL") {
            state.legs = [{ action: "BUY", type: "CE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 }];
        } else if (presetType === "BUY_PUT") {
            state.legs = [{ action: "BUY", type: "PE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 }];
        } else if (presetType === "BULL_PUT_SPREAD") {
            state.legs = [
                { action: "BUY", type: "PE", strike: atm - (3 * step), price: 18.0, lots: 1 },
                { action: "SELL", type: "PE", strike: atm - (1 * step), price: 48.0, lots: 1 }
            ];
        } else if (presetType === "BEAR_CALL_SPREAD") {
            state.legs = [
                { action: "SELL", type: "CE", strike: atm + (1 * step), price: 50.0, lots: 1 },
                { action: "BUY", type: "CE", strike: atm + (3 * step), price: 16.0, lots: 1 }
            ];
        } else if (presetType === "SHORT_STRANGLE") {
            state.legs = [
                { action: "SELL", type: "PE", strike: atm - (2 * step), price: 35.0, lots: 1 },
                { action: "SELL", type: "CE", strike: atm + (2 * step), price: 38.0, lots: 1 }
            ];
        } else if (presetType === "IRON_BUTTERFLY") {
            state.legs = [
                { action: "BUY", type: "PE", strike: atm - (3 * step), price: 18.0, lots: 1 },
                { action: "SELL", type: "PE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 },
                { action: "SELL", type: "CE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 },
                { action: "BUY", type: "CE", strike: atm + (3 * step), price: 19.0, lots: 1 }
            ];
        } else if (presetType === "LONG_STRADDLE") {
            state.legs = [
                { action: "BUY", type: "CE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 },
                { action: "BUY", type: "PE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 }
            ];
        } else if (presetType === "BULL_CALL_SPREAD" || presetType === "BULLISH") {
            state.legs = [
                { action: "BUY", type: "CE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 },
                { action: "SELL", type: "CE", strike: atm + (2 * step), price: roundTo50(spot * 0.008), lots: 1 }
            ];
        } else if (presetType === "BEAR_PUT_SPREAD" || presetType === "BEARISH") {
            state.legs = [
                { action: "BUY", type: "PE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 },
                { action: "SELL", type: "PE", strike: atm - (2 * step), price: roundTo50(spot * 0.008), lots: 1 }
            ];
        } else if (presetType === "SHORT_STRADDLE") {
            state.legs = [
                { action: "SELL", type: "CE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 },
                { action: "SELL", type: "PE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 }
            ];
        } else {
            state.legs = [
                { action: "BUY", type: "PE", strike: atm - (4 * step), price: 12.0, lots: 1 },
                { action: "SELL", type: "PE", strike: atm - (2 * step), price: 42.0, lots: 1 },
                { action: "SELL", type: "CE", strike: atm + (2 * step), price: 45.0, lots: 1 },
                { action: "BUY", type: "CE", strike: atm + (4 * step), price: 14.0, lots: 1 }
            ];
        }
        recalculatePayoff();
    };

    window.quickAddAtm = function (action, type) {
        if (!state.chainData || !state.chainData.chain) return;
        const atm = state.atmStrike;
        const isCall = type.toUpperCase() === "CE";
        const row = state.chainData.chain.find(r => r.strike === atm) || state.chainData.chain[Math.floor(state.chainData.chain.length / 2)];
        const prem = isCall ? row.call.ltp : row.put.ltp;
        window.addLegFromChain(action, type, atm, prem);
    };

    window.addNewLeg = function () {
        state.legs.push({
            action: "BUY",
            type: "CE",
            strike: state.atmStrike,
            price: 50.0,
            lots: 1
        });
        recalculatePayoff();
    };

    window.addLegFromChain = function (action, type, strike, price) {
        state.legs.push({
            action: action.toUpperCase(),
            type: type.toUpperCase(),
            strike: parseFloat(strike),
            price: parseFloat(price),
            lots: 1
        });
        recalculatePayoff();
    };

    window.removeLeg = function (idx) {
        state.legs.splice(idx, 1);
        recalculatePayoff();
    };

    window.updateLegField = function (idx, field, value) {
        if (state.legs[idx]) {
            state.legs[idx][field] = value;
            recalculatePayoff();
        }
    };

    window.onPayoffDaysSlider = function (val) {
        state.daysToTarget = parseFloat(val);
        if (el.sliderDaysVal) {
            el.sliderDaysVal.textContent = state.daysToTarget === 0 ? "0 Days (Expiry)" : `${state.daysToTarget} Days to Target`;
        }
        recalculatePayoff();
    };

    window.onPayoffSpotSlider = function (val) {
        state.simulatedSpot = parseFloat(val);
        if (el.sliderSpotVal) {
            el.sliderSpotVal.textContent = `₹${Number(val).toFixed(2)}`;
        }
    };

    window.copyBrokerBasket = function () {
        // Sort BUY orders first for instant SEBI hedge margin benefit
        const sortedLegs = [...state.legs].sort((a, b) => {
            return (a.action.toUpperCase() === "BUY" ? 0 : 1) - (b.action.toUpperCase() === "BUY" ? 0 : 1);
        });

        const basket = [];
        sortedLegs.forEach(leg => {
            basket.push({
                variety: "regular",
                tradingsymbol: `${state.symbol}${parseInt(leg.strike, 10)}${leg.type.toUpperCase()}`,
                exchange: "NFO",
                transaction_type: leg.action.toUpperCase(),
                order_type: "LIMIT",
                quantity: (leg.lots || 1) * state.lotSize,
                price: parseFloat(leg.price),
                product: "NRML"
            });
        });

        const basketJson = JSON.stringify(basket, null, 2);
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(basketJson).then(() => {
                alert(`📋 Copied Smart-Sequenced Zerodha Kite / Upstox Basket (${state.legs.length} legs) to clipboard!\n(BUY orders prioritized first for SEBI margin benefit)`);
            });
        } else {
            prompt("Zerodha Kite Basket JSON (BUY orders prioritized):", basketJson);
        }
    };

    function roundTo50(num) {
        return Math.round(num * 2.0) / 2.0;
    }

    /* ==========================================================================
       6. MOBILE DOCK NAVIGATION CONTROLLER
       ========================================================================== */

    window.switchMobileOptionsView = function (view) {
        const btnSingles = document.getElementById("mob-btn-singles");
        const btnSpreads = document.getElementById("mob-btn-spreads");
        const btnPayoff = document.getElementById("mob-btn-payoff");
        const btnChain = document.getElementById("mob-btn-chain");
        const btnAll = document.getElementById("mob-btn-all");

        if (btnSingles) btnSingles.classList.toggle("active", view === "singles");
        if (btnSpreads) btnSpreads.classList.toggle("active", view === "spreads");
        if (btnPayoff) btnPayoff.classList.toggle("active", view === "payoff");
        if (btnChain) btnChain.classList.toggle("active", view === "chain");
        if (btnAll) btnAll.classList.toggle("active", view === "all");

        const secSingles = document.getElementById("section-singles");
        const secSpreads = document.getElementById("section-spreads");
        const secPayoff = document.getElementById("section-payoff");
        const secChain = document.getElementById("section-chain");

        if (window.innerWidth <= 900) {
            if (view === "singles") {
                if (secSingles) secSingles.style.display = "flex";
                if (secSpreads) secSpreads.style.display = "none";
                if (secPayoff) secPayoff.style.display = "none";
                if (secChain) secChain.style.display = "none";
            } else if (view === "spreads") {
                if (secSingles) secSingles.style.display = "none";
                if (secSpreads) secSpreads.style.display = "flex";
                if (secPayoff) secPayoff.style.display = "none";
                if (secChain) secChain.style.display = "none";
            } else if (view === "payoff") {
                if (secSingles) secSingles.style.display = "none";
                if (secSpreads) secSpreads.style.display = "none";
                if (secPayoff) {
                    secPayoff.style.display = "flex";
                    setTimeout(() => {
                        if (state.payoffChart) state.payoffChart.resize();
                        if (state.oiChart) state.oiChart.resize();
                    }, 50);
                }
                if (secChain) secChain.style.display = "none";
            } else if (view === "chain") {
                if (secSingles) secSingles.style.display = "none";
                if (secSpreads) secSpreads.style.display = "none";
                if (secPayoff) secPayoff.style.display = "none";
                if (secChain) secChain.style.display = "flex";
            } else if (view === "all") {
                if (secSingles) secSingles.style.display = "flex";
                if (secSpreads) secSpreads.style.display = "flex";
                if (secPayoff) {
                    secPayoff.style.display = "flex";
                    setTimeout(() => {
                        if (state.payoffChart) state.payoffChart.resize();
                        if (state.oiChart) state.oiChart.resize();
                    }, 50);
                }
                if (secChain) secChain.style.display = "flex";
            }
        }
    };

    /* ==========================================================================
       7. INITIALIZATION & SEARCH
       ========================================================================== */

    document.addEventListener("DOMContentLoaded", () => {
        fetchOptionChain("NIFTY");
        fetchSingleOptionSignals();
        fetchOptionRecommendations();
        if (window.innerWidth <= 900) {
            window.switchMobileOptionsView("singles");
        }
    });

    window.addEventListener("resize", () => {
        if (state.payoffChart) state.payoffChart.resize();
        if (state.oiChart) state.oiChart.resize();

        if (window.innerWidth <= 900) {
            window.switchMobileOptionsView(state.activeMobileView || "singles");
        } else {
            const secSingles = document.getElementById("section-singles");
            const secSpreads = document.getElementById("section-spreads");
            const secPayoff = document.getElementById("section-payoff");
            const secChain = document.getElementById("section-chain");
            if (secSingles) secSingles.style.display = "block";
            if (secSpreads) secSpreads.style.display = "block";
            if (secPayoff) secPayoff.style.display = "block";
            if (secChain) secChain.style.display = "block";
        }
    });

})();

