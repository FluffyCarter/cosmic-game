// js/storage.js
const STORAGE_KEYS = {
  ADMIN_TOKEN: "cosmic_admin_token",
  ADMIN_SESSION_ID: "cosmic_admin_session_id",
  PLAYER_TOKEN: "cosmic_player_token",
  PLAYER_ID: "cosmic_player_id",
  PLAYER_SESSION_ID: "cosmic_player_session_id",
  PLAYER_PLANET: "cosmic_player_planet",
};

const store = {
  get(key) { return localStorage.getItem(key); },
  set(key, value) { localStorage.setItem(key, value); },
  remove(key) { localStorage.removeItem(key); },

  getAdminToken() { return this.get(STORAGE_KEYS.ADMIN_TOKEN); },
  setAdmin(token, sessionId) {
    this.set(STORAGE_KEYS.ADMIN_TOKEN, token);
    this.set(STORAGE_KEYS.ADMIN_SESSION_ID, sessionId);
  },
  clearAdmin() {
    this.remove(STORAGE_KEYS.ADMIN_TOKEN);
    this.remove(STORAGE_KEYS.ADMIN_SESSION_ID);
  },

  getPlayerToken() { return this.get(STORAGE_KEYS.PLAYER_TOKEN); },
  setPlayer(token, playerId, sessionId, planet) {
    this.set(STORAGE_KEYS.PLAYER_TOKEN, token);
    this.set(STORAGE_KEYS.PLAYER_ID, playerId);
    this.set(STORAGE_KEYS.PLAYER_SESSION_ID, sessionId);
    this.set(STORAGE_KEYS.PLAYER_PLANET, planet);
  },
  clearPlayer() {
    this.remove(STORAGE_KEYS.PLAYER_TOKEN);
    this.remove(STORAGE_KEYS.PLAYER_ID);
    this.remove(STORAGE_KEYS.PLAYER_SESSION_ID);
    this.remove(STORAGE_KEYS.PLAYER_PLANET);
  },
  getPlayerPlanet() { return this.get(STORAGE_KEYS.PLAYER_PLANET); },
  getPlayerSessionId() { return this.get(STORAGE_KEYS.PLAYER_SESSION_ID); },
};