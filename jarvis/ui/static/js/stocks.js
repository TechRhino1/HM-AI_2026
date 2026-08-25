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
        dossierOpen: false
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
        
        // Dossier Modal
        dossierModal: document.getElementById("stock-dossier-modal"),
        dossierTicker: document.getElementById("dossier-ticker"),
        dossierCompany: document.getElementById("dossier-company"),
        dossierSector: document.getElementById("dossier-sector"),
        dossierLivePrice: document.getElementById("dossier-live-price"),
        dossierChangeBadge: document.getElementById("dossier-change-badge"),
        dossierProbVal: document.getElementById("dossier-prob-val"),
        dossierProbFill: document.getElementById("dossier-prob-fill"),
        dossierSqueezeBadge: document.getElementById("dossier-squeeze-badge"),
        dossierRecBadge: document.getElementById("dossier-rec-badge"),
        dossierRiskRating: document.getElementById("dossier-risk-rating"),
        
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
        chartContainer: document.getElementById("dossier-tv-chart")
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
            el.screenerTableBody.innerHTML = `
                <tr>
                    <td colspan="10" style="text-align:center; padding:30px; color:var(--text-dim);">
                        No stocks matched the active breakout filters. Try broadening your criteria.
                    </td>
                </tr>`;
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

            html += `
            <tr class="${isSelected ? 'active-row' : ''}" onclick="window.openStockDossier('${st.symbol}')">
                <td>
                    <button class="btn-star-watch ${isStarred ? 'starred' : ''}" onclick="event.stopPropagation(); window.toggleWatchlist('${st.symbol}')">
                        ${isStarred ? '★' : '☆'}
                    </button>
                </td>
                <td>
                    <div class="stock-sym-cell">
                        <div class="stock-sym-name">
                            <span class="stock-ticker">${st.symbol}</span>
                            <span class="stock-comp-name">${st.name}</span>
                        </div>
                    </div>
                </td>
                <td style="color:var(--text-secondary); font-size:11px;">${st.sector}</td>
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
                <td class="mono-num" style="color:${st.rvol >= 1.5 ? 'var(--neon-amber)' : 'var(--text-secondary)'}; font-weight:700;">
                    ${Number(st.rvol).toFixed(2)}x
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
       4. GLOBAL WINDOW ACTIONS
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
       5. SEARCH AUTOCOMPLETE CONTROLLER
       ========================================================================== */

    function initSearchController() {
        if (!el.searchInput) return;

        let debounceTimer = null;
        el.searchInput.addEventListener("input", (e) => {
            const query = e.target.value;
            state.filters.searchQuery = query;
            renderScreenerTableDOM();

            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(async () => {
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
            }, 180);
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
       6. GLOBAL INITIALIZATION
       ========================================================================== */

    document.addEventListener("DOMContentLoaded", () => {
        initSearchController();
        fetchScreenerData();
        fetchAlerts();

        // Background polling
        setInterval(fetchScreenerData, 4000);
        setInterval(fetchAlerts, 6000);
    });

})();
