const chatLog = document.getElementById("chat_log");
const sessionHint = document.getElementById("session_hint");
const timeline = document.getElementById("timeline");
const statusView = document.getElementById("status_view");
const resultView = document.getElementById("result_view");
const resultCards = document.getElementById("result_cards");

const STEP_ORDER = [
  "market_exploration",
  "persona_generation",
  "conjoint_design",
  "simulation_analysis",
  "reflection",
];

const STEP_LABEL = {
  market_exploration: "市场探索",
  persona_generation: "消费者画像",
  conjoint_design: "联合分析设计",
  simulation_analysis: "模拟与策略分析",
  reflection: "反思与建议",
};

let sessionId = null;
let pollTimer = null;

function showJson(target, obj) {
  target.textContent = JSON.stringify(obj, null, 2);
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "request failed");
  }
  return data;
}

function addChatMessage(role, text) {
  const div = document.createElement("div");
  div.className = `chat-msg ${role === "user" ? "chat-msg-user" : "chat-msg-agent"}`;
  div.textContent = `${role === "user" ? "你" : "Agent"}：${text}`;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderTimeline(steps = []) {
  const map = {};
  steps.forEach((item) => {
    map[item.name] = item;
  });
  timeline.innerHTML = "";
  STEP_ORDER.forEach((name) => {
    const item = map[name] || { name, status: "pending", summary: "" };
    const node = document.createElement("div");
    node.className = `timeline-item timeline-item-${item.status}`;
    node.textContent = `${STEP_LABEL[name]}：${item.status}${item.summary ? ` ｜ ${item.summary}` : ""}`;
    timeline.appendChild(node);
  });
}

function renderResultCards(steps = []) {
  resultCards.innerHTML = "";
  steps.forEach((step) => {
    const card = document.createElement("div");
    card.className = "result-card";
    const title = document.createElement("h3");
    title.textContent = STEP_LABEL[step.step] || step.step;
    const summary = document.createElement("div");
    summary.textContent = step.summary || "";
    card.appendChild(title);
    card.appendChild(summary);
    resultCards.appendChild(card);
  });
}

function setSessionHint() {
  sessionHint.textContent = sessionId ? `会话：${sessionId}` : "会话：未创建";
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function fetchStatus() {
  if (!sessionId) {
    throw new Error("请先发送业务需求，创建会话");
  }
  const response = await fetch(`/session/status?session_id=${encodeURIComponent(sessionId)}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "status request failed");
  }
  showJson(statusView, data);
  renderTimeline(data.data.steps || []);
  if (data.data.status === "completed" || data.data.status === "failed") {
    stopPolling();
  }
  return data;
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      await fetchStatus();
    } catch (error) {
      stopPolling();
      showJson(statusView, { ok: false, message: String(error) });
    }
  }, 2000);
}

document.getElementById("send_btn").addEventListener("click", async () => {
  try {
    const chat = document.getElementById("chat_input").value.trim();
    if (!chat) {
      throw new Error("请输入你的业务需求");
    }
    addChatMessage("user", chat);
    document.getElementById("chat_input").value = "";

    const data = await postJson("/session/message", {
      session_id: sessionId,
      message: chat,
    });
    sessionId = data.data.session_id;
    setSessionHint();
    addChatMessage("agent", data.data.assistant_message);
    showJson(statusView, data);
  } catch (error) {
    showJson(statusView, { ok: false, message: String(error) });
  }
});

document.getElementById("run_btn").addEventListener("click", async () => {
  try {
    if (!sessionId) {
      throw new Error("请先发送业务需求，再开始分析");
    }
    const data = await postJson("/session/run", { session_id: sessionId });
    showJson(statusView, data);
    startPolling();
  } catch (error) {
    showJson(statusView, { ok: false, message: String(error) });
  }
});

document.getElementById("status_btn").addEventListener("click", async () => {
  try {
    await fetchStatus();
  } catch (error) {
    showJson(statusView, { ok: false, message: String(error) });
  }
});

document.getElementById("result_btn").addEventListener("click", async () => {
  try {
    if (!sessionId) {
      throw new Error("请先发送业务需求");
    }
    const response = await fetch(`/session/result?session_id=${encodeURIComponent(sessionId)}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "result request failed");
    }
    showJson(resultView, data);
    renderResultCards(data.data.steps || []);
  } catch (error) {
    showJson(resultView, { ok: false, message: String(error) });
  }
});

setSessionHint();
renderTimeline([]);
