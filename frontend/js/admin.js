// js/admin.js
(function () {
  const adminToken = store.getAdminToken();
  if (!adminToken) {
    window.location.href = "index.html";
    return;
  }

  // --- DOM ---
  const winnerCard = document.getElementById("winner-card");
  const winnerText = document.getElementById("winner-text");

  const sessionIdEl = document.getElementById("session-id");
  const joinCodeEl = document.getElementById("join-code");
  const statusEl = document.getElementById("session-status");
  const roundInfoEl = document.getElementById("round-info");
  const anomalyEl = document.getElementById("anomaly");
  const readyCountEl = document.getElementById("ready-count");

  const deadlineBar = document.getElementById("deadline-bar");
  const timerEl = document.getElementById("timer");

  const btnEndRound = document.getElementById("btn-end-round");
  const btnNextRound = document.getElementById("btn-next-round");
  const btnPause = document.getElementById("btn-pause");
  const btnResume = document.getElementById("btn-resume");
  const btnRefresh = document.getElementById("btn-refresh");
  const adminError = document.getElementById("admin-error");

  const playersListEl = document.getElementById("players-list");
  const talkEventsEl = document.getElementById("talk-events");
  const summaryTextEl = document.getElementById("summary-text");
  const summaryCard = document.getElementById("summary-card");
  const btnOpenHtml = document.getElementById("btn-open-html");
  const btnDownloadHtml = document.getElementById("btn-download-html");

  const btnToLobby = document.getElementById("btn-to-lobby");
  const btnExit = document.getElementById("btn-exit");
  const globalError = document.getElementById("global-error");

  // --- State ---
  let state = null;
  let deadlineTimer = null;

  // --- Utils ---
  function error(msg) {
    globalError.textContent = msg || "";
    globalError.style.display = msg ? "block" : "none";
  }

  function remainingTime(deadline) {
    if (!deadline) return "—";
    const sec = Math.max(0, Math.floor(deadline - Date.now() / 1000));
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  // --- Загрузка состояния ---
  async function refresh() {
    try {
      const s = await API.adminSession(adminToken);
      state = s;
      render();
      error("");
    } catch (e) {
      if (e.message.toLowerCase().includes("invalid") ||
          e.message.toLowerCase().includes("missing")) {
        store.clearAdmin();
        window.location.href = "index.html";
        return;
      }
      error(e.message);
    }
  }

  // --- Рендер ---
  function render() {
    if (!state) return;

    sessionIdEl.textContent = "#" + state.id;
    joinCodeEl.textContent = state.status === "lobby"
      ? (sessionStorage.getItem("cosmic_join_code") || "—")
      : "—";

    statusEl.textContent =
      state.status === "lobby" ? "Лобби"
      : state.status === "active" ? "Игра идёт"
      : state.status === "discussion" ? "Обсуждение"
      : state.status === "finished" ? "Завершена"
      : state.status;

    roundInfoEl.textContent = `${state.current_round} / ${state.rounds_total}`;
    anomalyEl.textContent = state.anomaly;

    const players = state.players || [];
    const ready = players.filter(p => p.order_ready).length;
    readyCountEl.textContent = `${ready} / ${players.length}`;

    // --- Таймер ---
    if (state.paused) {
      deadlineBar.classList.remove("hidden");
      timerEl.textContent = "⏸ На паузе";
      if (deadlineTimer) { clearInterval(deadlineTimer); deadlineTimer = null; }
    } else if (state.deadline) {
      deadlineBar.classList.remove("hidden");
      if (deadlineTimer) clearInterval(deadlineTimer);
      const tick = () => { timerEl.textContent = remainingTime(state.deadline); };
      tick();
      deadlineTimer = setInterval(tick, 1000);
    } else {
      deadlineBar.classList.add("hidden");
      if (deadlineTimer) { clearInterval(deadlineTimer); deadlineTimer = null; }
    }

    // --- Кнопки ---
    btnEndRound.classList.toggle("hidden", state.status !== "active");
    btnNextRound.classList.toggle("hidden", state.status !== "discussion");

    const paused = !!state.paused;
    btnPause.classList.toggle("hidden", paused || state.status !== "active");
    btnResume.classList.toggle("hidden", !paused);

    // --- Таблица игроков ---
    playersListEl.innerHTML = "";
    const table = document.createElement("table");
    table.className = "admin-table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Планета</th>
          <th>Имя</th>
          <th>Готов</th>
          <th>Статус</th>
        </tr>
      </thead>
      <tbody></tbody>
    `;
    const tbody = table.querySelector("tbody");
    players.forEach(p => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${p.planet}</td>
        <td>${p.name}</td>
        <td>${p.order_ready ? "✅" : "—"}</td>
        <td>${p.is_alive ? "жива" : "☠ разрушена"}</td>
      `;
      tbody.appendChild(tr);
    });
    playersListEl.appendChild(table);

    // --- Сводка ---
    if (state.status === "discussion" || state.status === "finished") {
      loadSummaryUrls();
    } else {
      summaryCard.style.display = "none";
    }

    // --- Победитель ---
    if (state.status === "finished") {
      loadWinner();
    } else {
      winnerCard.style.display = "none";
    }

    // --- Текстовая сводка ---
    if (state.status === "active" || state.status === "discussion" || state.status === "finished") {
      loadTextSummary();
    }
  }

  // --- Сводка: ссылки ---
  async function loadSummaryUrls() {
    try {
      const pub = await API.request("/api/admin/public", { token: adminToken });
      if (!pub.last_summary) {
        summaryCard.style.display = "none";
        return;
      }
      const base = window.API_URL;
      const s = pub.last_summary;
      btnOpenHtml.href = base + s.html_url;
      btnDownloadHtml.href = base + s.html_url;
      btnDownloadHtml.setAttribute("download", `summary_round${s.round}.html`);
      summaryCard.style.display = "block";
    } catch (e) {
      summaryCard.style.display = "none";
    }
  }

  // --- Победитель ---
  async function loadWinner() {
    try {
      const pub = await API.request("/api/admin/public", { token: adminToken });
      const reason = pub.finished_reason;
      const winners = Array.isArray(pub.winners) ? pub.winners : [];
      const winnerSingle = pub.winner_planet || null;

      if (reason === "anomaly") {
        winnerText.innerHTML =
          "💀 Аномалия достигла 100%. <strong>Проиграли все.</strong>";
      } else if (winners.length > 1) {
        winnerText.innerHTML =
          `🤝 <strong>Ничья!</strong> Победители: ` +
          winners.map(w => `<strong>${w}</strong>`).join(", ");
      } else if (winners.length === 1) {
        winnerText.innerHTML =
          `🏆 Победила планета <strong>${winners[0]}</strong>.`;
      } else if (winnerSingle) {
        winnerText.innerHTML =
          `🏆 Победила планета <strong>${winnerSingle}</strong>.`;
      } else {
        winnerText.innerHTML =
          "Игра окончена, но победитель не определён.";
      }
      winnerCard.style.display = "block";
    } catch (e) {
      console.warn("loadWinner error:", e);
      winnerCard.style.display = "none";
    }
  }

  // --- Сводка: текст ---
  async function loadTextSummary() {
    try {
      const pub = await API.request("/api/admin/public", { token: adminToken });
      renderSummary(pub);
    } catch (e) { /* ignore */ }
  }

  function renderSummary(pub) {
    const lines = [];
    lines.push(`<h3>Раунд ${pub.current_round} / ${pub.rounds_total}</h3>`);
    lines.push(`<p>🌌 Аномалия: <strong>${pub.anomaly}%</strong></p>`);
    lines.push("<ul>");
    pub.players.forEach(p => {
      const cities = p.cities.map(c => {
        if (c.is_destroyed) return `<span class="dead-city">${c.name}</span>`;
        const shield = c.has_shield ? " 🛡" : "";
        return `${c.name} (${c.development}/${c.life_level})${shield}`;
      }).join(", ");
      const alive = p.is_alive ? "" : " ☠";
      lines.push(`<li><strong>${p.planet}</strong>${alive}: ${cities}</li>`);
    });
    lines.push("</ul>");
    summaryTextEl.innerHTML = lines.join("");
  }

  // --- Кнопки ---
  btnEndRound.onclick = async () => {
    if (!confirm("Завершить раунд досрочно?")) return;
    try {
      await API.adminEndRound(adminToken);
      await refresh();
    } catch (e) {
      adminError.textContent = e.message;
    }
  };

  btnNextRound.onclick = async () => {
    try {
      await API.request("/api/admin/next-round", { method: "POST", token: adminToken });
      await refresh();
    } catch (e) {
      adminError.textContent = e.message;
    }
  };

  btnPause.onclick = async () => {
    try {
      await API.request("/api/admin/pause", { method: "POST", token: adminToken });
      await refresh();
    } catch (e) { adminError.textContent = e.message; }
  };

  btnResume.onclick = async () => {
    try {
      await API.request("/api/admin/resume", { method: "POST", token: adminToken });
      await refresh();
    } catch (e) { adminError.textContent = e.message; }
  };

  btnRefresh.onclick = refresh;

  btnToLobby.onclick = () => { window.location.href = "lobby.html"; };

  btnExit.onclick = () => {
    if (!confirm("Выйти из админ-сессии?")) return;
    store.clearAdmin();
    window.location.href = "index.html";
  };

  // --- Переговоры ---
  function addTalkEvent(text) {
    const div = document.createElement("div");
    div.className = "event";
    div.textContent = text;
    talkEventsEl.prepend(div);
    while (talkEventsEl.children.length > 30) {
      talkEventsEl.removeChild(talkEventsEl.lastChild);
    }
  }

  function addArriveButton(t) {
    if (document.getElementById("arrive-" + t.request_id)) return;
    const div = document.createElement("div");
    div.className = "event";
    div.id = "arrive-" + t.request_id;
    div.innerHTML = `🚶 ${t.admin_hint} <button class="btn btn-small btn-primary">Дипломат прибыл</button>`;
    div.querySelector("button").onclick = async () => {
      try {
        await API.request(`/api/talk/${t.request_id}/arrived`,
          { method: "POST", token: adminToken });
        div.remove();
      } catch (e) {
        alert(e.message);
      }
    };
    talkEventsEl.prepend(div);
  }

  // --- WebSocket ---
  let ws = null;
  function connectWS() {
    if (!state) return;
    const url = window.API_URL.replace(/^http/, "ws") + "/ws/" + state.id;
    ws = new WebSocket(url);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "talk_requested" && msg.data) {
          addTalkEvent(`📨 ${msg.data.from_planet} отправил запрос на переговоры к ${msg.data.to_planet}`);
        }
        if (msg.type === "talk_accepted" && msg.data) {
          addArriveButton(msg.data);
        }
        if (msg.type === "talk_rejected") {
          addTalkEvent("❌ Запрос на переговоры отклонён.");
        }
        if (msg.type === "talk_arrived" && msg.data) {
          addTalkEvent(`🤝 Переговоры начались (request #${msg.data.request_id}).`);
        }
        if (msg.type === "talk_finished" && msg.data) {
          addTalkEvent(`🏁 ${msg.data.admin_hint}`);
        }
        if (["player_ready", "round_finished", "game_started",
             "round_paused", "round_resumed", "player_joined",
             "round_started"].includes(msg.type)) {
          refresh();
        }
      } catch (e) {}
    };
    ws.onclose = () => setTimeout(connectWS, 2000);
    ws.onerror = () => ws.close();
  }

  refresh().then(() => {
    if (state) connectWS();
  });
  setInterval(refresh, 5000);
})();