/**
 * HM AI 4.0 — Universal Authentication & Session Management Module
 * Handles login modal, token persistence, user profile header widgets, and server-side logout.
 */
(function () {
    "use strict";

    const AUTH_STORAGE_KEY = "jarvis_auth_token";
    const USER_STORAGE_KEY = "jarvis_user_info";

    window.HM_AUTH = {
        getToken: function () {
            return localStorage.getItem(AUTH_STORAGE_KEY) || "";
        },

        getUser: function () {
            try {
                const raw = localStorage.getItem(USER_STORAGE_KEY);
                return raw ? JSON.parse(raw) : null;
            } catch (e) {
                return null;
            }
        },

        saveSession: function (data) {
            if (!data || !data.token) return;
            localStorage.setItem(AUTH_STORAGE_KEY, data.token);
            const userInfo = {
                username: data.username || "admin",
                role: data.role || "ADMIN",
                full_name: data.full_name || "Administrator"
            };
            localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(userInfo));
            document.cookie = `jarvis_auth_token=${data.token}; path=/; max-age=86400; SameSite=Lax`;
            this.updateHeaderUI(userInfo);
        },

        clearSession: function () {
            localStorage.removeItem(AUTH_STORAGE_KEY);
            localStorage.removeItem(USER_STORAGE_KEY);
            document.cookie = "jarvis_auth_token=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT";
            this.updateHeaderUI(null);
        },

        verifyToken: async function () {
            const token = this.getToken();
            if (!token) {
                this.updateHeaderUI(null);
                return false;
            }
            try {
                const res = await fetch("/api/auth/verify", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    }
                });
                const data = await res.json();
                if (data && data.valid && data.user) {
                    const user = data.user;
                    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
                    this.updateHeaderUI(user);
                    return true;
                }
            } catch (e) {
                console.warn("Auth verification network error:", e);
            }
            this.clearSession();
            return false;
        },

        login: async function (username, password) {
            try {
                const res = await fetch("/api/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username: username.trim(), password: password.trim() })
                });
                const data = await res.json();
                if (res.ok && data && data.token) {
                    this.saveSession(data);
                    return { success: true, data: data };
                } else {
                    return { success: false, error: data.error || "Invalid username or password" };
                }
            } catch (e) {
                return { success: false, error: "Network error connecting to authentication server" };
            }
        },

        logout: async function () {
            const token = this.getToken();
            if (token) {
                try {
                    await fetch("/api/auth/logout", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": `Bearer ${token}`
                        }
                    });
                } catch (e) {
                    console.warn("Logout API notice:", e);
                }
            }
            this.clearSession();
            this.openLoginModal("Session ended. Please log in to continue.");
        },

        updateHeaderUI: function (user) {
            let container = document.getElementById("auth-header-widget");
            if (!container) {
                // Find right-most nav container
                const navLinks = document.querySelector(".nav-links-wrapper") ||
                                 document.querySelector(".hud-actions") ||
                                 document.querySelector("header");
                if (navLinks) {
                    container = document.createElement("div");
                    container.id = "auth-header-widget";
                    container.className = "auth-header-widget";
                    navLinks.appendChild(container);
                }
            }

            if (!container) return;

            if (user && user.username) {
                container.innerHTML = `
                    <div class="auth-user-pill" title="Logged in as ${user.full_name || user.username}">
                        <span>👤</span>
                        <span style="font-family:'JetBrains Mono',monospace;">${user.username}</span>
                        <span class="auth-user-role-tag">${user.role || 'USER'}</span>
                    </div>
                    <button class="auth-logout-btn" onclick="window.HM_AUTH.logout()" title="Logout from terminal">
                        <span>🚪</span> Logout
                    </button>
                `;
            } else {
                container.innerHTML = `
                    <button class="auth-login-btn" onclick="window.HM_AUTH.openLoginModal()" title="Login to terminal">
                        <span>🔒</span> Login
                    </button>
                `;
            }
        },

        openLoginModal: function (msg) {
            let modal = document.getElementById("universal-auth-modal");
            if (!modal) {
                modal = document.createElement("div");
                modal.id = "universal-auth-modal";
                modal.className = "universal-auth-overlay";
                modal.innerHTML = `
                    <div class="universal-auth-card">
                        <button class="auth-close-btn" onclick="window.HM_AUTH.closeLoginModal()" title="Close">✕</button>
                        <div class="auth-card-top-icon">🔒</div>
                        <div class="auth-card-title">HM AI 4.0 TERMINAL LOGIN</div>
                        <div class="auth-card-subtitle" id="auth-modal-subtitle">Secure Multi-Market Execution Desk</div>
                        <div id="auth-modal-error" class="auth-error-alert"></div>
                        <form id="universal-auth-form" onsubmit="window.HM_AUTH.handleFormSubmit(event)">
                            <div class="auth-form-group">
                                <label class="auth-input-lbl">Username</label>
                                <div class="auth-input-wrapper">
                                    <input type="text" id="auth-input-user" class="auth-input-field" placeholder="Enter username (e.g. admin)" required autocomplete="username" value="admin">
                                </div>
                            </div>
                            <div class="auth-form-group">
                                <label class="auth-input-lbl">Password</label>
                                <div class="auth-input-wrapper">
                                    <input type="password" id="auth-input-pass" class="auth-input-field" placeholder="Enter password (default: jarvis2026)" required autocomplete="current-password" value="jarvis2026">
                                    <button type="button" class="auth-pwd-toggle" onclick="window.HM_AUTH.togglePasswordVisibility()">👁️</button>
                                </div>
                            </div>
                            <button type="submit" id="auth-submit-btn" class="auth-submit-btn">
                                UNLOCK TERMINAL ➔
                            </button>
                        </form>
                    </div>
                `;
                document.body.appendChild(modal);
            }

            const errEl = document.getElementById("auth-modal-error");
            if (errEl) {
                if (msg) {
                    errEl.textContent = msg;
                    errEl.style.display = "block";
                } else {
                    errEl.style.display = "none";
                }
            }

            modal.style.display = "flex";
            const userInp = document.getElementById("auth-input-user");
            if (userInp) userInp.focus();
        },

        closeLoginModal: function () {
            const modal = document.getElementById("universal-auth-modal");
            if (modal) modal.style.display = "none";
        },

        togglePasswordVisibility: function () {
            const passInp = document.getElementById("auth-input-pass");
            if (passInp) {
                passInp.type = passInp.type === "password" ? "text" : "password";
            }
        },

        handleFormSubmit: async function (e) {
            if (e) e.preventDefault();
            const userInp = document.getElementById("auth-input-user");
            const passInp = document.getElementById("auth-input-pass");
            const errEl = document.getElementById("auth-modal-error");
            const submitBtn = document.getElementById("auth-submit-btn");

            if (!userInp || !passInp) return;

            const username = userInp.value.trim();
            const password = passInp.value.trim();

            if (!username || !password) {
                if (errEl) {
                    errEl.textContent = "Please enter both username and password";
                    errEl.style.display = "block";
                }
                return;
            }

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = "AUTHENTICATING...";
            }

            const res = await this.login(username, password);

            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = "UNLOCK TERMINAL ➔";
            }

            if (res.success) {
                if (errEl) errEl.style.display = "none";
                this.closeLoginModal();
                // Trigger any page-specific refresh handlers if available
                if (typeof window.refreshData === "function") window.refreshData();
                if (typeof window.fetchTelemetry === "function") window.fetchTelemetry();
            } else {
                if (errEl) {
                    errEl.textContent = res.error || "Invalid username or password";
                    errEl.style.display = "block";
                }
            }
        }
    };

    // Auto-initialize on DOM ready
    document.addEventListener("DOMContentLoaded", () => {
        window.HM_AUTH.verifyToken();
    });

})();
