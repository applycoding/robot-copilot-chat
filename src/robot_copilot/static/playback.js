import { setExecPath, setMarker } from "./map.js";

let frames = [];
let index = 0;
let status = "idle";

function setStatus(s) {
  status = s;
  const el = document.getElementById("playback-status");
  if (el) {
    el.textContent = s;
    el.dataset.status = s;
  }
}

function setTelemetry(i) {
  const tel = document.getElementById("telemetry");
  if (tel) {
    tel.dataset.frameIndex = String(i);
    const f = frames[i];
    if (
      f &&
      f.event === "land" &&
      Math.abs(f.x_m) < 1e-6 &&
      Math.abs(f.y_m) < 1e-6
    ) {
      tel.textContent = "landed at home";
    }
  }
}

function renderFrame(i) {
  const f = frames[i];
  if (!f) return;
  setMarker(f.x_m, f.y_m);
  const sub = frames.slice(0, i + 1);
  const d = sub
    .map((p, j) => `${j === 0 ? "M" : "L"} ${p.x_m} ${-p.y_m}`)
    .join(" ");
  setExecPath(d);
  setTelemetry(i);
}

export function initPlayback(run) {
  frames = run.frames || [];
  index = 0;
  setStatus("idle");
  setExecPath("");
  const f0 = frames[0];
  if (f0) {
    setMarker(f0.x_m, f0.y_m);
    setTelemetry(0);
  }
}

document.getElementById("step-btn")?.addEventListener("click", () => {
  if (!frames.length) return;
  if (index < frames.length - 1) index += 1;
  renderFrame(index);
  setStatus("paused");
});

document.getElementById("end-btn")?.addEventListener("click", () => {
  if (!frames.length) return;
  index = frames.length - 1;
  renderFrame(index);
  setStatus("completed");
});

document.getElementById("reset-btn")?.addEventListener("click", () => {
  index = 0;
  renderFrame(0);
  setStatus("idle");
});

document.getElementById("play-btn")?.addEventListener("click", () => setStatus("playing"));
document.getElementById("pause-btn")?.addEventListener("click", () => setStatus("paused"));
