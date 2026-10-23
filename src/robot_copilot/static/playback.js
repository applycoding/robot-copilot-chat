import { setExecPath, setMarker } from "./map.js";

let frames = [];
let finalState = null;
let index = 0;
let timer = null;

function setStatus(s) {
  const el = document.getElementById("playback-status");
  if (el) {
    el.textContent = s;
    el.dataset.status = s;
  }
}

function speedFactor() {
  const sel = document.getElementById("speed-select");
  const v = sel ? Number(sel.value) : 1;
  return Number.isFinite(v) && v > 0 ? v : 1;
}

function setTelemetry(i) {
  const tel = document.getElementById("telemetry");
  if (!tel) return;
  tel.dataset.frameIndex = String(i);
  const f = frames[i];
  if (!f) {
    tel.textContent = "";
    return;
  }
  tel.textContent = `t=${f.t_s.toFixed(1)}s alt=${f.alt_m.toFixed(1)}m batt=${f.battery_wh.toFixed(1)} Wh`;
  if (
    finalState &&
    finalState.landed &&
    finalState.at_home &&
    i === frames.length - 1
  ) {
    tel.textContent = "landed at home";
  }
}

function renderFrame(i) {
  const f = frames[i];
  if (!f) return;
  setMarker(f.x_m, f.y_m);
  if (i === 0) {
    setExecPath("");
  } else {
    const sub = frames.slice(0, i + 1);
    const d = sub
      .map((p, j) => `${j === 0 ? "M" : "L"} ${p.x_m} ${-p.y_m}`)
      .join(" ");
    setExecPath(d);
  }
  setTelemetry(i);
}

function stopTimer() {
  if (timer !== null) {
    clearInterval(timer);
    timer = null;
  }
}

export function resetPlayback() {
  stopTimer();
  frames = [];
  finalState = null;
  index = 0;
  setStatus("idle");
  setExecPath("");
  const marker = document.getElementById("vehicle-marker");
  if (marker) marker.replaceChildren();
  const tel = document.getElementById("telemetry");
  if (tel) {
    tel.textContent = "";
    tel.dataset.frameIndex = "0";
  }
}

export function initPlayback(run) {
  stopTimer();
  frames = run.frames || [];
  finalState = run.final_state || null;
  index = 0;
  setStatus("idle");
  setExecPath("");
  if (frames.length) {
    setMarker(frames[0].x_m, frames[0].y_m);
    setTelemetry(0);
  }
}

function tickPlay() {
  if (!frames.length) return;
  if (index >= frames.length - 1) {
    stopTimer();
    setStatus("completed");
    renderFrame(index);
    return;
  }
  index += 1;
  renderFrame(index);
}

document.getElementById("step-btn")?.addEventListener("click", () => {
  if (!frames.length) return;
  stopTimer();
  if (index < frames.length - 1) index += 1;
  renderFrame(index);
  setStatus("paused");
});

document.getElementById("end-btn")?.addEventListener("click", () => {
  if (!frames.length) return;
  stopTimer();
  index = frames.length - 1;
  renderFrame(index);
  setStatus("completed");
});

document.getElementById("reset-btn")?.addEventListener("click", () => {
  stopTimer();
  index = 0;
  renderFrame(0);
  setStatus("idle");
});

document.getElementById("play-btn")?.addEventListener("click", () => {
  if (!frames.length) return;
  setStatus("playing");
  stopTimer();
  const baseMs = 250;
  timer = setInterval(tickPlay, baseMs / speedFactor());
});

document.getElementById("pause-btn")?.addEventListener("click", () => {
  stopTimer();
  setStatus("paused");
});
