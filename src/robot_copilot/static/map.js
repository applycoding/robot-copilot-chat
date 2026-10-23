const SVG_NS = "http://www.w3.org/2000/svg";

export function initMap(points) {
  const path = document.getElementById("plan-path");
  if (!path || !Array.isArray(points) || points.length === 0) {
    if (path) path.setAttribute("d", "");
    return;
  }
  const coords = points
    .filter((p) => Number.isFinite(p.x_m) && Number.isFinite(p.y_m))
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x_m} ${-p.y_m}`)
    .join(" ");
  path.setAttribute("d", coords);
}

export function setExecPath(d) {
  const path = document.getElementById("exec-path");
  if (path) path.setAttribute("d", d || "");
}

export function setMarker(x, y) {
  const g = document.getElementById("vehicle-marker");
  const svg = document.getElementById("map-svg");
  if (!g || !svg || !Number.isFinite(x) || !Number.isFinite(y)) return;
  while (g.firstChild) g.removeChild(g.firstChild);
  const c = document.createElementNS(SVG_NS, "circle");
  c.setAttribute("cx", String(x));
  c.setAttribute("cy", String(-y));
  c.setAttribute("r", "4");
  g.appendChild(c);
}
