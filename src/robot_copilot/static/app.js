import { initMap } from "./map.js";
import { initPlayback } from "./playback.js";

const state = {
  conversationId: null,
  mission: null,
  run: null,
};

function el(id) {
  return document.getElementById(id);
}

function appendMessage(text, role) {
  const div = document.createElement("div");
  div.textContent = text;
  div.dataset.role = role;
  el("messages").appendChild(div);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail?.message || res.statusText);
    err.status = res.status;
    err.detail = data.detail;
    throw err;
  }
  return data;
}

function renderMission(m) {
  if (!m) {
    el("mission").hidden = true;
    return;
  }
  el("mission").hidden = false;
  el("mission-status").textContent = m.status;
  const steps = el("plan-steps");
  steps.textContent = "";
  if (m.plan?.actions) {
    for (const a of m.plan.actions) {
      const li = document.createElement("li");
      li.textContent = JSON.stringify(a);
      steps.appendChild(li);
    }
  }
  const issues = el("issue-list");
  issues.textContent = "";
  for (const i of m.issues || []) {
    const li = document.createElement("li");
    li.textContent = i.message;
    issues.appendChild(li);
  }
  el("repair-btn").hidden = !m.can_repair;
  el("confirm-btn").hidden = !m.can_confirm;
}

async function sendChat() {
  const message = el("chat-input").value;
  if (!message.trim()) return;
  const body = {
    conversation_id: state.conversationId,
    message,
    vehicle: el("vehicle-select").value,
    battery_pct: Number(el("battery-input").value),
  };
  const res = await api("/api/chat", { method: "POST", body: JSON.stringify(body) });
  state.conversationId = res.conversation_id;
  appendMessage(message, "user");
  appendMessage(res.assistant_message, "assistant");
  state.mission = res.mission;
  renderMission(res.mission);
  if (res.mission?.path_preview) {
    initMap(res.mission.path_preview);
  }
  el("chat-input").value = "";
}

async function repair() {
  if (!state.mission) return;
  const res = await api(`/api/missions/${state.mission.id}/repair`, {
    method: "POST",
    body: "{}",
  });
  appendMessage(res.assistant_message, "assistant");
  state.mission = res.mission;
  renderMission(res.mission);
}

async function confirmFlow() {
  if (!state.mission) return;
  el("confirm-dialog").hidden = false;
  el("confirm-summary").textContent = state.mission.explanation || "";
}

async function execute() {
  if (!state.mission?.plan_hash) return;
  const run = await api(`/api/missions/${state.mission.id}/confirm`, {
    method: "POST",
    body: JSON.stringify({ plan_hash: state.mission.plan_hash }),
  });
  state.run = run;
  state.mission = { ...state.mission, status: run.status };
  renderMission(state.mission);
  el("confirm-dialog").hidden = true;
  initPlayback(run);
}

el("send-btn").addEventListener("click", () => sendChat().catch(console.error));
el("repair-btn").addEventListener("click", () => repair().catch(console.error));
el("confirm-btn").addEventListener("click", () => confirmFlow());
el("execute-btn").addEventListener("click", () => execute().catch(console.error));

initMap([]);
