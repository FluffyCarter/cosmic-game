// js/game.js
(function () {
  const token = store.getPlayerToken();
  if (!token) {
    window.location.href = "index.html";
    return;
  }

  // --- DOM ---
  const planetNameEl = document.getElementById("planet-name");
  const roundInfoEl = document.getElementById("round-info");
  const anomalyEl = document.getElementById("anomaly");
  const moneyEl = document.getElementById("money");
  const missilesEl = document.getElementById("missiles");
  const deadlineBar = document.getElementById("deadline-bar");
  const timerEl = document.getElementById("timer");

  const citiesEl = document.getElementById("cities");
  const ordersEl = document.getElementById("orders");
  const ordersTotalEl = document.getElementById("orders-total");
  const btnReady = document.getElementById("btn-ready");
  const btnClear = document.getElementById("btn-clear");
  const readyStatus = document.getElementById("ready-status");

  const actionsEl = document.getElementById("actions");
  const otherPlayersEl = document.getElementById("other-players");
  const payTargetEl = document.getElementById("pay-target");
  const payAmountEl = document.getElementById("pay-amount");
  const btnPay = document.getElementById("btn-pay");

  const sanctionsBlock = document.getElementById("sanctions-block");
  const sanctionsList = document.getElementById("sanctions-list");

  const modal = document.getElementById("modal");
  const modalTitle = document.getElementById("modal-title");
  const modalBody = document.getElementById("modal-body");
  const modalClose = document.getElementById("modal-close");

  const finishModal = document.getElementById("finish-modal");
  const finishTitle = document.getElementById("finish-title");
  const finishText = document.getElementById("finish-text");
  const btnBackLobby = document.getElementById("btn-back-lobby");

  const globalError = document.getElementById("global-error");

  // --- State ---
  let state = null;
  let deadlineTimer = null;
  let myTalks = { incoming: [], outgoing: [], busy_with: null };

  // --- Utils ---
  function error(msg) {
    globalError.textContent = msg || "";
    globalError.style.display = msg ? "block" : "none";
  }

  function fmtMoney(n) { return new Intl.NumberFormat("ru-RU").format(n); }

  function remainingTime(deadline) {
    if (!deadline) return "—";
    const sec = Math.max(0, Math.floor(deadline - Date.now() / 1000));
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  // --- Render ---
  function render() {
    if (!state) return;
    const { session, player, cities, orders, other_players } = state;

    planetNameEl.textContent = player.planet;
    roundInfoEl.textContent = `${session.current_round} / ${session.rounds_total}`;
    anomalyEl.textContent = session.anomaly;
    moneyEl.textContent = fmtMoney(player.money);
    missilesEl.textContent = player.missiles;

    const sanctions = state.sanctions_against_me || [];
    if (sanctions.length > 0) {
      sanctionsBlock.classList.remove("hidden");
      const names = sanctions.map(s => s.from_planet).join(", ");
      sanctionsList.textContent = names;
    } else {
      sanctionsBlock.classList.add("hidden");
    }

    if (session.paused) {
      deadlineBar.classList.remove("hidden");
      timerEl.textContent = "⏸ На паузе";
      if (deadlineTimer) clearInterval(deadlineTimer);
    } else if (session.deadline) {
      deadlineBar.classList.remove("hidden");
      if (deadlineTimer) clearInterval(deadlineTimer);
      const tick = () => { timerEl.textContent = remainingTime(session.deadline); };
      tick();
      deadlineTimer = setInterval(tick, 1000);
    } else {
      deadlineBar.classList.add("hidden");
    }

    // Города
    citiesEl.innerHTML = "";
    cities.forEach(c => {
      const div = document.createElement("div");
      div.className = "city " + (c.is_destroyed ? "city-dead" : "");
      const shield = c.has_shield ? " 🛡" : "";
      div.innerHTML = `
        <div class="city-name">${c.name}${shield}</div>
        <div class="city-stats">
          разв. <strong>${c.development}</strong> ·
          жизнь <strong>${c.life_level}</strong>
        </div>
      `;
      citiesEl.appendChild(div);
    });

    // Корзина
    ordersEl.innerHTML = "";
    let total = 0;
    orders.forEach(o => {
      total += o.cost;
      const li = document.createElement("li");
      li.className = "order-item";
      const span = document.createElement("span");
      span.textContent = describeOrder(o, state);
      li.appendChild(span);
      if (!player.order_ready) {
        const x = document.createElement("button");
        x.className = "order-remove";
        x.textContent = "✕";
        x.title = "Отменить";
        x.onclick = () => removeOrder(o.id);
        li.appendChild(x);
      }
      ordersEl.appendChild(li);
    });
    ordersTotalEl.textContent = `Итого: ${fmtMoney(total)} 💵`;

    if (player.order_ready) {
      btnReady.classList.add("hidden");
      btnClear.classList.add("hidden");
      readyStatus.classList.remove("hidden");
      readyStatus.textContent = "✅ Приказ отправлен. Ждём остальных.";
      readyStatus.style.color = "var(--secondary)";
    } else {
      btnReady.classList.remove("hidden");
      btnClear.classList.remove("hidden");
      readyStatus.classList.add("hidden");
    }

    renderActions(player, session);

    otherPlayersEl.innerHTML = "";
    other_players.forEach(p => {
      const div = document.createElement("div");
      div.className = "other-player";
      div.textContent = `${p.planet}${p.is_alive ? "" : " ☠"}`;
      otherPlayersEl.appendChild(div);
    });

    payTargetEl.innerHTML = "";
    other_players.forEach(p => {
      if (!p.is_alive) return;
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.planet;
      payTargetEl.appendChild(opt);
    });

    renderTalks();

    if (session.status === "discussion" && session.last_summary) {
      openSummaryTab(session.last_summary);
    }

    if (session.status === "finished") {
      showFinish(session);
    }
  }

  // --- Сводка ---
  let summaryOpenedForRound = null;

  function openSummaryTab(lastSummary) {
    const r = lastSummary.round;
    if (summaryOpenedForRound === r) return;
    summaryOpenedForRound = r;
    const url = window.API_URL + lastSummary.html_url;
    window.open(url, "_blank");
  }
  // --- Описание заказа ---
  function describeOrder(o, st) {
    const n = o.target_name || "?";
    if (o.action_type === "dev") {
      return `📈 Развитие ${n} (−${o.cost} 💵)`;
    }
    if (o.action_type === "shield") {
      return `🛡 Щит над ${n} (−${o.cost} 💵)`;
    }
    if (o.action_type === "tech") return `🛠 Технология метеоритов (−${o.cost} 💵)`;
    if (o.action_type === "buy_missile") return `☄️ Покупка метеорита (−${o.cost} 💵)`;
    if (o.action_type === "meteor_city") return `☄️ Метеорит в ${n}`;
    if (o.action_type === "meteor_anomaly") return `💥 Метеорит в аномалию`;
    if (o.action_type === "sanction") return `🧾 Санкции против ${n}`;
    return o.action_type;
  }

  // --- Действия ---
  function renderActions(player, session) {
    actionsEl.innerHTML = "";
    if (player.order_ready) {
      actionsEl.innerHTML = "<p class='muted'>Приказ уже отправлен.</p>";
      return;
    }

    addAction("📈 Развить город", "150 💵", () => chooseCity("dev"));

    if (session.current_round >= 2) {
      addAction("🛡 Поставить щит", "300 💵", () => chooseCity("shield"));
    }

    if (!player.tech_meteor && !player.pending_tech) {
      addAction("🛠 Разработать технологию", "500 💵", () => order("tech"));
    } else if (player.tech_meteor) {
      addAction("☄️ Купить метеорит", "150 💵", () => order("buy_missile"));
      if (player.missiles > 0) {
        addAction("☄️ Метеорит в город", "бесплатно", () => chooseTargetPlanet("meteor_city"));
        addAction("💥 Метеорит в аномалию", "бесплатно", () => order("meteor_anomaly"));
      }
    }
    if (player.pending_tech) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = "🛠 Технология изучена в этом раунде — станет доступна в следующем.";
      actionsEl.appendChild(p);
    }

    addAction("🧾 Санкции", "бесплатно", () => chooseTargetPlanet("sanction"));
  }

  function addAction(label, hint, handler) {
    const btn = document.createElement("button");
    btn.className = "btn btn-action";
    btn.innerHTML = `<strong>${label}</strong><span class="hint">${hint}</span>`;
    btn.onclick = handler;
    actionsEl.appendChild(btn);
  }

  // --- Модалка ---
  function openModal(title, bodyBuilder) {
    modalTitle.textContent = title;
    modalBody.innerHTML = "";
    bodyBuilder(modalBody);
    modal.classList.remove("hidden");
  }
  function closeModal() {
    modal.classList.add("hidden");
  }
  modalClose.addEventListener("click", closeModal);

  function chooseCity(action) {
    const cities = state.cities.filter(c => !c.is_destroyed);
    if (action === "shield") {
      const filtered = cities.filter(c => !c.has_shield);
      openModal("Выбери город для щита", body => {
        filtered.forEach(c => {
          const b = document.createElement("button");
          b.className = "btn btn-secondary";
          b.textContent = `${c.name} (разв. ${c.development})`;
          b.onclick = () => { closeModal(); order(action, c.id); };
          body.appendChild(b);
        });
      });
    } else {
      openModal("Выбери город", body => {
        cities.forEach(c => {
          const b = document.createElement("button");
          b.className = "btn btn-secondary";
          b.textContent = `${c.name} (разв. ${c.development})`;
          b.onclick = () => { closeModal(); order(action, c.id); };
          body.appendChild(b);
        });
      });
    }
  }

  function chooseTargetPlanet(action) {
    const others = state.other_players.filter(p => p.is_alive);
    if (others.length === 0) {
      error("Нет живых планет для атаки.");
      return;
    }
    openModal("Выбери планету", body => {
      others.forEach(p => {
        const b = document.createElement("button");
        b.className = "btn btn-secondary";
        b.textContent = p.planet;
        b.onclick = () => {
          closeModal();
          if (action === "meteor_city") {
            chooseTargetCity(p.id);
          } else {
            order(action, p.id);
          }
        };
        body.appendChild(b);
      });
    });
  }

  function chooseTargetCity(targetPlayerId) {
    API.publicState(state.session.id, token)
      .then(pub => {
        const target = pub.players.find(p => p.id === targetPlayerId);
        if (!target) { error("Планета не найдена."); return; }
        const alive = target.cities.filter(c => !c.is_destroyed);
        if (alive.length === 0) {
          error(`У планеты ${target.planet} не осталось живых городов.`);
          return;
        }
        openModal(`Города планеты ${target.planet}`, body => {
          alive.forEach(c => {
            const b = document.createElement("button");
            b.className = "btn btn-secondary";
            b.textContent = `${c.name} (разв. ${c.development})`;
            b.onclick = () => { closeModal(); order("meteor_city", c.id); };
            body.appendChild(b);
          });
        });
      })
      .catch(e => error("Не удалось загрузить города: " + e.message));
  }

  // --- Переговоры ---
  async function refreshTalks() {
    try {
      myTalks = await API.request("/api/talk/my", { token });
      renderTalks();
    } catch (e) {}
  }

  function renderTalks() {
    const incomingEl = document.getElementById("talk-incoming");
    const outgoingEl = document.getElementById("talk-outgoing");
    const sendEl = document.getElementById("talk-send");

    incomingEl.innerHTML = "";
    if (myTalks.incoming.length === 0) {
      incomingEl.innerHTML = "<p class='muted'>Нет входящих запросов.</p>";
    }
    myTalks.incoming.forEach(t => {
      const div = document.createElement("div");
      div.className = "talk-request";

      if (t.status === "pending") {
        const ttl = Math.max(0, t.ttl_left);
        div.innerHTML = `
          <div>📞 <strong>${t.from_planet}</strong> просит переговоров.
            <span class="ttl">${ttl}с</span></div>
          <div class="row"></div>
        `;
        const row = div.querySelector(".row");
        if (myTalks.busy_with) {
          row.innerHTML = "<span class='muted'>Ты занят другим дипломатом.</span>";
        } else {
          const acceptBtn = document.createElement("button");
          acceptBtn.className = "btn btn-secondary btn-small";
          acceptBtn.textContent = "✅ Принять";
          acceptBtn.onclick = () => acceptTalk(t.id);
          const rejectBtn = document.createElement("button");
          rejectBtn.className = "btn btn-ghost btn-small";
          rejectBtn.textContent = "❌ Отклонить";
          rejectBtn.onclick = () => rejectTalk(t.id);
          row.appendChild(acceptBtn);
          row.appendChild(rejectBtn);
        }
      } else if (t.status === "accepted") {
        div.innerHTML = `<div>📞 <strong>${t.from_planet}</strong> — дипломат в пути. Ждём сопровождающего.</div>`;
      } else if (t.status === "arrived") {
        div.innerHTML = `
          <div>📞 Переговоры с <strong>${t.from_planet}</strong> идут.</div>
          <div class="row"></div>
        `;
        const finishBtn = document.createElement("button");
        finishBtn.className = "btn btn-primary btn-small";
        finishBtn.textContent = "🏁 Завершить переговоры";
        finishBtn.onclick = () => finishTalk(t.id);
        div.querySelector(".row").appendChild(finishBtn);
      }
      incomingEl.appendChild(div);
    });

    outgoingEl.innerHTML = "";
    if (myTalks.outgoing.length === 0) {
      outgoingEl.innerHTML = "<p class='muted'>Нет исходящих запросов.</p>";
    }
    myTalks.outgoing.forEach(t => {
      const div = document.createElement("div");
      div.className = "talk-request";
      let text = "";
      if (t.status === "pending") {
        text = `📞 Запрос к <strong>${t.to_planet}</strong>. Ждём ответа (${t.ttl_left}с).`;
      } else if (t.status === "accepted") {
        text = `📞 <strong>${t.to_planet}</strong> принял запрос. Дипломат в пути.`;
      } else if (t.status === "arrived") {
        text = `📞 Переговоры с <strong>${t.to_planet}</strong> идут.`;
      }
      div.innerHTML = `<div>${text}</div>`;
      outgoingEl.appendChild(div);
    });

    sendEl.innerHTML = "";
    state.other_players.forEach(p => {
      if (!p.is_alive) return;
      const btn = document.createElement("button");
      btn.className = "btn btn-small";
      btn.textContent = `📞 ${p.planet}`;
      btn.onclick = () => requestTalk(p.id);
      sendEl.appendChild(btn);
    });
  }

  async function requestTalk(toId) {
    try {
      await API.request("/api/talk", { method: "POST", token, body: { to_player_id: toId } });
      await refresh();
    } catch (e) { error(e.message); }
  }

  async function acceptTalk(requestId) {
    try {
      await API.request(`/api/talk/${requestId}/accept`, { method: "POST", token });
      await refresh();
    } catch (e) { error(e.message); }
  }

  async function rejectTalk(requestId) {
    try {
      await API.request(`/api/talk/${requestId}/reject`, { method: "POST", token });
      await refresh();
    } catch (e) { error(e.message); }
  }

  async function finishTalk(requestId) {
    try {
      await API.request(`/api/talk/${requestId}/finish`, { method: "POST", token });
      await refresh();
    } catch (e) { error(e.message); }
  }

  // --- API ---
  async function refresh() {
    try {
      state = await API.playerState(token);
      render();
      await refreshTalks();
      error("");
    } catch (e) {
      if (e.message.includes("Invalid") || e.message.includes("token")) {
        store.clearPlayer();
        window.location.href = "index.html";
        return;
      }
      error(e.message);
    }
  }

  async function order(action, targetId = null) {
    try {
      const res = await API.request("/api/order", {
        method: "POST", token, body: { action, target_id: targetId },
      });
      state = res.state;
      render();
      error("");
    } catch (e) { error(e.message); }
  }

  async function removeOrder(orderId) {
    try {
      await API.request(`/api/order/${orderId}`, { method: "DELETE", token });
      await refresh();
    } catch (e) { error(e.message); }
  }

  btnClear.onclick = async () => {
    try {
      await API.request("/api/order", { method: "DELETE", token });
      await refresh();
    } catch (e) { error(e.message); }
  };

  btnReady.onclick = async () => {
    try {
      await API.request("/api/ready", { method: "POST", token });
      await refresh();
    } catch (e) { error(e.message); }
  };

  btnPay.onclick = async () => {
    const to = parseInt(payTargetEl.value, 10);
    const amount = parseInt(payAmountEl.value, 10);
    if (!to || !amount || amount <= 0) return error("Укажи планету и сумму");
    try {
      await API.request("/api/pay", {
        method: "POST", token, body: { to_player_id: to, amount },
      });
      payAmountEl.value = "";
      await refresh();
    } catch (e) { error(e.message); }
  };

  // --- Финал ---
  function showFinish(session) {
    finishModal.classList.remove("hidden");
    finishTitle.textContent = "🏁 Игра окончена";
    finishText.textContent =
      "Игра окончена, результаты в ближайшее время появятся на общем экране!";
  }

  btnBackLobby.onclick = () => { window.location.href = "lobby.html"; };

  // --- WebSocket ---
  let ws = null;
  let wsRetryTimer = null;

  function connectWS() {
    if (!state) return;
    const sessionId = state.session.id;
    const url = window.API_URL.replace(/^http/, "ws") + "/ws/" + sessionId;
    try { ws = new WebSocket(url); } catch (e) { return; }
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (["order_added", "orders_cleared", "order_removed",
             "player_ready", "round_finished", "game_started",
             "money_transferred", "round_paused", "round_resumed",
             "talk_requested", "talk_accepted", "talk_rejected",
             "talk_arrived", "talk_finished", "round_started"].includes(msg.type)) {
          refresh();
        }
        if (msg.type === "round_started") {
          summaryOpenedForRound = null;
        }
      } catch (e) {}
    };
    ws.onclose = () => {
      ws = null;
      if (wsRetryTimer) clearTimeout(wsRetryTimer);
      wsRetryTimer = setTimeout(connectWS, 3000);
    };
    ws.onerror = () => ws.close();
  }

  refresh().then(() => { if (state) connectWS(); });
  setInterval(refresh, 5000);
  setInterval(refreshTalks, 2000);
})();