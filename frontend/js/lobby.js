// js/lobby.js
(function () {
  const playerView = document.getElementById("player-view");
  const adminView = document.getElementById("admin-view");
  const playerPlanetEl = document.getElementById("player-planet");
  const playerStatusEl = document.getElementById("player-status");
  const btnGoGame = document.getElementById("btn-go-game");
  const btnLeavePlayer = document.getElementById("btn-leave-player");

  const joinCodeEl = document.getElementById("join-code");
  const roundsTotalEl = document.getElementById("rounds-total");
  const sessionStatusEl = document.getElementById("session-status");
  const sessionAnomalyEl = document.getElementById("session-anomaly");
  const playersListEl = document.getElementById("players-list");
  const playersCountEl = document.getElementById("players-count");
  const btnStart = document.getElementById("btn-start");
  const btnAdminPage = document.getElementById("btn-admin-page");
  const btnCopyCode = document.getElementById("btn-copy-code");
  const btnLeaveAdmin = document.getElementById("btn-leave-admin");
  const adminError = document.getElementById("admin-error");
  const globalError = document.getElementById("global-error");

  const playerToken = store.getPlayerToken();
  const adminToken = store.getAdminToken();
  const playerSessionId = store.getPlayerSessionId();

  if (!playerToken && !adminToken) {
    // Не залогинен ни как игрок, ни как админ
    window.location.href = "index.html";
    return;
  }

  // --- Игрок ---
  if (playerToken) {
    playerView.classList.remove("hidden");
    playerPlanetEl.textContent = store.getPlayerPlanet() || "—";

    // Проверяем, активна ли игра
    (async () => {
      try {
        const state = await API.playerState(playerToken);
        if (state.session.status === "lobby") {
          playerStatusEl.textContent = "Игра ещё не началась. Жди сигнала админа.";
        } else if (state.session.status === "active") {
          playerStatusEl.textContent = "Игра идёт!";
          btnGoGame.classList.remove("hidden");
        } else if (state.session.status === "finished") {
          playerStatusEl.textContent = "Игра завершена.";
          btnGoGame.classList.remove("hidden");
          btnGoGame.textContent = "Смотреть результаты";
        }
      } catch (e) {
        // Токен, возможно, от старой сессии
        globalError.textContent = "Не удалось загрузить состояние: " + e.message;
      }
    })();

    btnGoGame.addEventListener("click", () => {
      window.location.href = "game.html";
    });

    btnLeavePlayer.addEventListener("click", () => {
      if (!confirm("Выйти из сохранённой сессии? Придётся заново вводить код.")) return;
      store.clearPlayer();
      window.location.href = "index.html";
    });

    // Периодический poll статуса
    if (playerToken) {
      setInterval(async () => {
        try {
          const state = await API.playerState(playerToken);
          if (state.session.status === "active") {
            btnGoGame.classList.remove("hidden");
            playerStatusEl.textContent = "Игра идёт!";
          } else if (state.session.status === "finished") {
            btnGoGame.classList.remove("hidden");
            btnGoGame.textContent = "Смотреть результаты";
            playerStatusEl.textContent = "Игра завершена.";
          }
        } catch (e) {}
      }, 3000);
    }
  }

  // --- Админ ---
  if (adminToken) {
    adminView.classList.remove("hidden");

    const initialCode = sessionStorage.getItem("cosmic_join_code");
    if (initialCode) joinCodeEl.textContent = initialCode;

    async function refreshAdmin() {
      try {
        const s = await API.adminSession(adminToken);
        roundsTotalEl.textContent = s.rounds_total;
        sessionStatusEl.textContent =
          s.status === "lobby" ? "Лобби" :
          s.status === "active" ? `Идёт (раунд ${s.current_round})` :
          s.status === "finished" ? "Завершена" : s.status;
        sessionAnomalyEl.textContent = s.anomaly;
        playersCountEl.textContent = s.players.length;
        playersListEl.innerHTML = "";
        s.players.forEach(p => {
          const li = document.createElement("li");
          li.textContent = `${p.planet} — ${p.name}` +
            (p.is_alive ? "" : " ☠");
          playersListEl.appendChild(li);
        });

        if (s.status === "lobby") {
          btnStart.classList.remove("hidden");
          btnAdminPage.classList.add("hidden");
        } else {
          btnStart.classList.add("hidden");
          btnAdminPage.classList.remove("hidden");
          joinCodeEl.textContent = "—";
        }
      } catch (e) {
        adminError.textContent = e.message;
      }
    }

    refreshAdmin();
    setInterval(refreshAdmin, 2000);

    btnStart.addEventListener("click", async () => {
      adminError.textContent = "";
      btnStart.disabled = true;
      try {
        await API.adminStart(adminToken);
        await refreshAdmin();
        btnAdminPage.classList.remove("hidden");
      } catch (e) {
        adminError.textContent = e.message;
      } finally {
        btnStart.disabled = false;
      }
    });

    btnAdminPage.addEventListener("click", () => {
      window.location.href = "admin.html";
    });

    btnCopyCode.addEventListener("click", () => {
      const code = joinCodeEl.textContent.trim();
      if (code && code !== "—") {
        navigator.clipboard.writeText(code);
        btnCopyCode.textContent = "Скопировано";
        setTimeout(() => btnCopyCode.textContent = "Копировать", 1500);
      }
    });

    btnLeaveAdmin.addEventListener("click", () => {
      if (!confirm("Выйти из админ-сессии?")) return;
      store.clearAdmin();
      window.location.href = "index.html";
    });
  }
})();