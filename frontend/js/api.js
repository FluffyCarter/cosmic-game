// js/api.js
const API = {
  base() { return window.API_URL; },

  async request(path, { method = "GET", body = null, token = null } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;

    const res = await fetch(this.base() + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });

    let data = null;
    try { data = await res.json(); } catch (e) {}

    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  },

  // --- sessions ---
  createSession(roundsTotal) {
    return this.request("/api/sessions", {
      method: "POST",
      body: { rounds_total: roundsTotal },
    });
  },

  adminSession(token) {
    return this.request("/api/admin/session", { token });
  },

  joinSession(joinCode, name) {
    return this.request("/api/sessions/join", {
      method: "POST",
      body: { join_code: joinCode, name: name },
    });
  },

  adminStart(token) {
    return this.request("/api/admin/start", { method: "POST", token });
  },

  adminEndRound(token) {
    return this.request("/api/admin/end-round", { method: "POST", token });
  },

  // --- player ---
  me(token) { return this.request("/api/me", { token }); },
  playerState(token) { return this.request("/api/session/state", { token }); },

  // Публичное состояние. token — опциональный (для скрытия чужих щитов).
  publicState(sessionId, token = null) {
    let url = "/api/session/public?session_id=" + sessionId;
    if (token) url += "&token=" + encodeURIComponent(token);
    return this.request(url);
  },
};