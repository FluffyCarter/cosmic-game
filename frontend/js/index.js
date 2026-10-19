// js/index.js
(function () {
  const joinCodeInput = document.getElementById("join-code");
  const joinNameInput = document.getElementById("join-name");
  const btnJoin = document.getElementById("btn-join");
  const joinError = document.getElementById("join-error");

  const roundsSelect = document.getElementById("rounds-total");
  const btnCreate = document.getElementById("btn-create");
  const createError = document.getElementById("create-error");

  function showError(el, msg) {
    el.textContent = msg || "";
    el.style.display = msg ? "block" : "none";
  }

  // --- Игрок ---
  btnJoin.addEventListener("click", async () => {
    showError(joinError, "");
    const code = joinCodeInput.value.trim();
    const name = joinNameInput.value.trim();
    if (!code || code.length !== 6) {
      return showError(joinError, "Введи 6-значный код комнаты");
    }
    if (!name) {
      return showError(joinError, "Введи имя");
    }

    btnJoin.disabled = true;
    try {
      const res = await API.joinSession(code, name);
      store.setPlayer(res.player_token, res.player_id, res.session_id, res.planet);
      window.location.href = "lobby.html";
    } catch (e) {
      showError(joinError, e.message);
    } finally {
      btnJoin.disabled = false;
    }
  });

  // --- Админ ---
  btnCreate.addEventListener("click", async () => {
    showError(createError, "");
    const rounds = parseInt(roundsSelect.value, 10);
    btnCreate.disabled = true;
    try {
      const res = await API.createSession(rounds);
      store.setAdmin(res.admin_token, res.session_id);
      // временно сохраняем join_code для показа в лобби
      sessionStorage.setItem("cosmic_join_code", res.join_code);
      window.location.href = "lobby.html";
    } catch (e) {
      showError(createError, e.message);
    } finally {
      btnCreate.disabled = false;
    }
  });

  // Если есть сохранённый токен — предложить продолжить
  if (store.getPlayerToken()) {
    joinNameInput.value = "";
    showError(joinError, "У тебя есть сохранённая сессия игрока. " +
      "Открой lobby.html, если игра ещё активна.");
  }
})();