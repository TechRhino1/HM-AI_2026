/**
 * HM AI 4.0 — UNIFIED CLIENT-SIDE ROUTER & DESK MANAGER (app_shell.js)
 * Manages client-side navigation between Forex Terminal, US Stocks, India Equities, and Options Desk.
 * Eliminates full-page reloads, preserves auth/session tokens, and coordinates background data sync.
 */

class AppRouter {
    constructor() {
        this.routes = {
            "/": { desk: "terminal", title: "Forex & Crypto Terminal" },
            "/terminal": { desk: "terminal", title: "Forex & Crypto Terminal" },
            "/stocks": { desk: "stocks", title: "US Stocks Screener" },
            "/india": { desk: "india", title: "NSE/BSE India Equities" },
            "/options": { desk: "options", title: "India Options & Derivatives" }
        };
        this.currentDesk = null;
        this.initializedDesks = new Set();
    }

    init() {
        console.log("[AppRouter] Initializing Unified Single-Interface Router...");
        
        // Handle popstate (Back/Forward browser buttons)
        window.addEventListener("popstate", (e) => {
            const path = window.location.pathname.toLowerCase();
            this.navigate(path, false);
        });

        // Intercept internal desk links
        document.addEventListener("click", (e) => {
            const link = e.target.closest("[data-desk-route]");
            if (link) {
                e.preventDefault();
                const route = link.getAttribute("data-desk-route");
                this.navigate(route, true);
            }
        });

        // Determine initial route from URL or body data attribute
        const initialPath = window.location.pathname.toLowerCase();
        this.navigate(initialPath, false);
    }

    navigate(path, pushState = true) {
        let routeConfig = this.routes[path];
        if (!routeConfig) {
            // Check matching prefix
            if (path.startsWith("/stocks")) routeConfig = this.routes["/stocks"];
            else if (path.startsWith("/india")) routeConfig = this.routes["/india"];
            else if (path.startsWith("/options")) routeConfig = this.routes["/options"];
            else routeConfig = this.routes["/"];
        }

        const desk = routeConfig.desk;
        if (this.currentDesk === desk) return;

        console.log(`[AppRouter] Switching to Desk: ${desk} (Route: ${path})`);
        
        if (pushState && window.location.pathname !== path) {
            window.history.pushState({ desk: desk }, routeConfig.title, path);
        }

        document.title = `HM AI 4.0 — ${routeConfig.title}`;
        this.activateDesk(desk);
    }

    activateDesk(desk) {
        this.currentDesk = desk;

        // 1. Update Navigation Tabs UI (Desktop & Mobile)
        document.querySelectorAll(".desk-tab, .mobile-nav-item").forEach(el => {
            const targetDesk = el.getAttribute("data-desk");
            if (targetDesk === desk) {
                el.classList.add("active");
            } else {
                el.classList.remove("active");
            }
        });

        // 2. Switch Active Panel
        document.querySelectorAll(".app-panel").forEach(panel => {
            if (panel.id === `panel-${desk}`) {
                panel.classList.add("active");
            } else {
                panel.classList.remove("active");
            }
        });

        // 3. Lazily initialize desk specific controllers if needed
        this.initializeDeskIfNeeded(desk);

        // 4. Scroll window to top
        window.scrollTo({ top: 0, behavior: "instant" });
    }

    initializeDeskIfNeeded(desk) {
        if (this.initializedDesks.has(desk)) return;
        this.initializedDesks.add(desk);

        console.log(`[AppRouter] First-time initialization for ${desk} controller...`);
        try {
            if (desk === "terminal" && typeof initTerminal === "function") {
                initTerminal();
            } else if (desk === "stocks" && typeof initStocksScreener === "function") {
                initStocksScreener();
            } else if (desk === "india" && typeof initIndiaScreener === "function") {
                initIndiaScreener();
            } else if (desk === "options" && typeof initIndiaOptions === "function") {
                initIndiaOptions();
            }
        } catch (e) {
            console.error(`[AppRouter] Error initializing ${desk}:`, e);
        }
    }
}

// Global router singleton
const APP_ROUTER = new AppRouter();
document.addEventListener("DOMContentLoaded", () => {
    APP_ROUTER.init();
});
