const SVG_NS = "http://www.w3.org/2000/svg";

export function drawSite(site) {
  const svg = document.getElementById("map-svg");
  if (!svg || !site) return;
  let layer = document.getElementById("site-layer");
  if (!layer) {
    layer = document.createElementNS(SVG_NS, "g");
    layer.setAttribute("id", "site-layer");
    svg.insertBefore(layer, svg.firstChild);
  }
  while (layer.firstChild) layer.removeChild(layer.firstChild);

  if (Array.isArray(site.geofence) && site.geofence.length >= 3) {
    const pts = site.geofence
      .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]))
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p[0]} ${-p[1]}`)
      .join(" ");
    const fence = document.createElementNS(SVG_NS, "path");
    fence.setAttribute("d", `${pts} Z`);
    fence.setAttribute("fill", "none");
    fence.setAttribute("stroke", "#999");
    fence.setAttribute("stroke-width", "1");
    layer.appendChild(fence);
  }

  for (const ko of site.keep_outs || []) {
    const poly = ko.polygon;
    if (!Array.isArray(poly) || poly.length < 3) continue;
    const pts = poly
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p[0]} ${-p[1]}`)
      .join(" ");
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", `${pts} Z`);
    path.setAttribute("fill", "rgba(200,80,80,0.15)");
    path.setAttribute("stroke", "#a44");
    layer.appendChild(path);
  }

  for (const place of site.places || []) {
    for (const p of place.points || []) {
      if (!Number.isFinite(p[0]) || !Number.isFinite(p[1])) continue;
      const dot = document.createElementNS(SVG_NS, "circle");
      dot.setAttribute("cx", String(p[0]));
      dot.setAttribute("cy", String(-p[1]));
      dot.setAttribute("r", "3");
      dot.setAttribute("fill", "#555");
      layer.appendChild(dot);
    }
  }
}

export function initMap(points) {
  const path = document.getElementById("plan-path");
  if (!path) return;
  if (!Array.isArray(points) || points.length === 0) {
    path.setAttribute("d", "");
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
  if (!g || !Number.isFinite(x) || !Number.isFinite(y)) return;
  while (g.firstChild) g.removeChild(g.firstChild);
  const c = document.createElementNS(SVG_NS, "circle");
  c.setAttribute("cx", String(x));
  c.setAttribute("cy", String(-y));
  c.setAttribute("r", "5");
  c.setAttribute("fill", "#0a5");
  g.appendChild(c);
}
