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

        // AI Recommendations Grid
        aiOptRecGrid: document.getElementById("ai-opt-rec-grid")
    };

    /* ==========================================================================
       1. DATA FETCHING & API INTERACTION
       ========================================================================== */

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
                <td class="${callItm}" style="text-align:center;">
                    <button class="btn-add-leg-mini" onclick="window.addLegFromChain('BUY', 'CE', ${row.strike}, ${call.ltp})">➕</button>
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
                <td class="${putItm}" style="text-align:center;">
                    <button class="btn-add-leg-mini" onclick="window.addLegFromChain('BUY', 'PE', ${row.strike}, ${put.ltp})">➕</button>
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
        if (el.stratMargin) el.stratMargin.textContent = `₹${Number(data.estimated_margin_inr).toLocaleString(undefined, {minimumFractionDigits:2})}`;

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

    window.applyPresetStrategy = function (presetType) {
        document.querySelectorAll(".preset-btn").forEach(b => b.classList.remove("active"));
        
        const spot = state.spotPrice;
        const step = state.strikeStep;
        const atm = state.atmStrike;

        if (presetType === "BULLISH") {
            state.legs = [
                { action: "BUY", type: "CE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 },
                { action: "SELL", type: "CE", strike: atm + (2 * step), price: roundTo50(spot * 0.008), lots: 1 }
            ];
        } else if (presetType === "BEARISH") {
            state.legs = [
                { action: "BUY", type: "PE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 },
                { action: "SELL", type: "PE", strike: atm - (2 * step), price: roundTo50(spot * 0.008), lots: 1 }
            ];
        } else if (presetType === "SHORT_STRADDLE") {
            state.legs = [
                { action: "SELL", type: "CE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 },
                { action: "SELL", type: "PE", strike: atm, price: roundTo50(spot * 0.018), lots: 1 }
            ];
        } else if (presetType === "IRON_CONDOR") {
            state.legs = [
                { action: "BUY", type: "PE", strike: atm - (4 * step), price: 12.0, lots: 1 },
                { action: "SELL", type: "PE", strike: atm - (2 * step), price: 42.0, lots: 1 },
                { action: "SELL", type: "CE", strike: atm + (2 * step), price: 45.0, lots: 1 },
                { action: "BUY", type: "CE", strike: atm + (4 * step), price: 14.0, lots: 1 }
            ];
        }
        recalculatePayoff();
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
            action: action,
            type: type,
            strike: strike,
            price: price,
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
        const basket = [];
        state.legs.forEach(leg => {
            basket.push({
                variety: "regular",
                tradingsymbol: `${state.symbol}${parseInt(leg.strike, 10)}${leg.type}`,
                exchange: "NFO",
                transaction_type: leg.action.toUpperCase(),
                order_type: "LIMIT",
                quantity: (leg.lots || 1) * state.lotSize,
                price: leg.price,
                product: "NRML"
            });
        });

        const basketJson = JSON.stringify(basket, null, 2);
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(basketJson).then(() => {
                alert(`📋 Copied Zerodha Kite / Upstox Basket (${state.legs.length} legs) to clipboard!`);
            });
        } else {
            prompt("Zerodha Kite Basket JSON:", basketJson);
        }
    };

    function roundTo50(num) {
        return Math.round(num * 2.0) / 2.0;
    }

    /* ==========================================================================
       6. INITIALIZATION & SEARCH
       ========================================================================== */

    document.addEventListener("DOMContentLoaded", () => {
        fetchOptionChain("NIFTY");
        fetchOptionRecommendations();
    });

})();
