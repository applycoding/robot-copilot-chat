import { drawSite, initMap } from "./map.js";
import { initPlayback, resetPlayback } from "./playback.js";

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
  const box = el("messages");
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
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

function formatAction(a) {
  switch (a.type) {
    case "takeoff":
      return `Take off to ${a.altitude_m} m`;
    case "goto": {
      let s = "Go to ";
      if (a.place) s += a.place;
      else if (a.xy) s += `(${a.xy.x_m}, ${a.xy.y_m})`;
      else s += "target";
      if (a.altitude_m != null) s += ` at ${a.altitude_m} m`;
      if (a.speed_mps != null) s += `, ${a.speed_mps} m/s`;
      return s;
    }
    case "hover":
      return `Hover ${a.seconds} s`;
    case "photo":
      return `Photo${a.label ? `: ${a.label}` : ""}`;
    case "land":
      return "Land";
    case "return_home":
      return "Return home";
    default:
      return a.type;
  }
}

function renderMission(m) {
  if (!m) {
    el("mission").hidden = true;
    return;
  }
  el("mission").hidden = false;
  el("mission-status").textContent = m.status;
  const summaryEl = el("plan-summary");
  summaryEl.textContent = m.plan?.summary || "";
  const noticeEl = el("adjustment-notice");
  if (m.adjustment_notice) {
    noticeEl.textContent = m.adjustment_notice;
    noticeEl.hidden = false;
  } else {
    noticeEl.textContent = "";
    noticeEl.hidden = true;
  }
  const steps = el("plan-steps");
  steps.textContent = "";
  if (m.plan?.actions) {
    m.plan.actions.forEach((a) => {
      const li = document.createElement("li");
      li.textContent = formatAction(a);
      steps.appendChild(li);
    });
  }
  const issues = el("issue-list");
  issues.textContent = "";
  for (const i of m.issues || []) {
    const li = document.createElement("li");
    li.textContent = i.message;
    issues.appendChild(li);
  }
  const executed = m.status === "executed" || m.status === "aborted";
  el("repair-btn").hidden = !m.can_repair;
  el("confirm-btn").hidden = !m.can_confirm || executed;
  if (executed) {
    el("confirm-dialog").hidden = true;
  }
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
  state.run = null;
  resetPlayback();
  renderMission(res.mission);
  if (res.mission?.path_preview) {
    initMap(res.mission.path_preview);
  } else if (res.kind === "help" || !res.mission) {
    initMap([]);
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
  state.run = null;
  resetPlayback();
  renderMission(res.mission);
  if (res.mission?.path_preview) {
    initMap(res.mission.path_preview);
  }
}

async function confirmFlow() {
  if (!state.mission) return;
  el("confirm-dialog").hidden = false;
  const parts = [];
  if (state.mission.adjustment_notice) parts.push(state.mission.adjustment_notice);
  if (state.mission.explanation) parts.push(state.mission.explanation);
  el("confirm-summary").textContent = parts.join("\n\n");
}

async function execute() {
  if (!state.mission?.plan_hash) return;
  const run = await api(`/api/missions/${state.mission.id}/confirm`, {
    method: "POST",
    body: JSON.stringify({ plan_hash: state.mission.plan_hash }),
  });
  state.run = run;
  state.mission = {
    ...state.mission,
    status: "executed",
    can_confirm: false,
    can_repair: false,
  };
  renderMission(state.mission);
  el("confirm-dialog").hidden = true;
  initPlayback(run);
}

el("send-btn").addEventListener("click", () => sendChat().catch(console.error));
el("repair-btn").addEventListener("click", () => repair().catch(console.error));
el("confirm-btn").addEventListener("click", () => confirmFlow());
el("execute-btn").addEventListener("click", () => execute().catch(console.error));

api("/api/site")
  .then((site) => drawSite(site))
  .catch(() => {});

initMap([]);
