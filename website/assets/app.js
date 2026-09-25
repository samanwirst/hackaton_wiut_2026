/* TrafficWatch website: renders everything from the JSON files in data/ (written by tools/). */
"use strict";

const CLASSES = ["accident", "near_miss", "red_light", "wrong_way", "illegal_u_turn", "stopped_vehicle",
  "jaywalking", "failure_to_yield", "illegal_turn", "solid_line_crossing", "stop_line", "congestion",
  "road_obstacle", "fire_smoke"];
const RULES = [
  ["stopped_vehicle", "Vehicle still for ≥ 10 s on the carriageway while traffic in its direction flows past it, so a signal queue does not count; a vehicle that stopped behind a stop line on red and leaves with the queue at green never counts. Stationary fragments of one vehicle are joined across track ids."],
  ["congestion", "Per direction of travel: at least 4 vehicles, median speed crawling and most of them stopped, for ≥ 30 s. A queue waiting at a red signal is not congestion."],
  ["wrong_way", "A heading the learned direction field has (almost) never seen at that place while the opposite heading is common, for ≥ 1.5 s; or against a drawn lane direction."],
  ["illegal_u_turn", "Heading turns ≥ 150° within 20 s outside zones where U-turns are allowed."],
  ["illegal_turn", "A turn into a prohibited entry → exit movement, or a turn not allowed from the entry lane."],
  ["solid_line_crossing", "Both approximate wheel points change side of a solid marking."],
  ["red_light", "The front of the vehicle crosses the stop line while its signal has been red for ≥ 0.3 s; ends when it leaves the junction."],
  ["stop_line", "The vehicle stops past the stop line on red without entering the junction; ends when the signal turns green."],
  ["jaywalking", "A pedestrian (not a rider) walking on the carriageway outside a crossing for ≥ 1 s, or stepping onto a crossing against its red pedestrian signal."],
  ["failure_to_yield", "A vehicle drives through a crossing while a pedestrian is on it near its path."],
  ["accident", "Two road users make contact after a fast approach, then at least one loses ≥ 60 % of its speed and they come to rest."],
  ["near_miss", "Closest-approach analysis predicts contact within 2 s, one road user brakes sharply or swerves, and they never touch. Off by default until it is validated."],
  ["road_obstacle", "An animal on the carriageway, or a static foreign object that differs from the long-term background where no tracked road user is."],
  ["fire_smoke", "Flickering, saturated flame-coloured regions (enabled only after validation)."],
];
const SERIES = [["vehicle", "--s1"], ["two_wheeler", "--s2"], ["person", "--s3"], ["animal", "--s4"]];
const NS = "http://www.w3.org/2000/svg";
const $ = (sel, root = document) => root.querySelector(sel);
const redraws = new Map();   // section -> function that re-renders its charts (resize, theme)
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/* ---------- small DOM helpers ---------- */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v; else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v); else node.setAttribute(k, v);
  }
  for (const c of children) if (c != null) node.append(c);
  return node;
}
function svg(tag, attrs = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}
async function load(path) {
  try { const r = await fetch(path, { cache: "no-cache" }); return r.ok ? await r.json() : null; } catch (e) { return null; }
}
const fmt = (v, d = 1) => Number(v).toFixed(d);
const pretty = s => s.replace(/_/g, " ");

/* ---------- tooltip ---------- */
const tip = $("#tooltip");
function showTip(ev, rows, title) {
  tip.replaceChildren();
  if (title) tip.append(el("div", { class: "k", text: title }));
  for (const r of rows) {
    const row = el("div", { class: "row" });
    if (r.color) row.append(el("span", { class: "key", style: `background:${r.color}` }));
    row.append(el("span", { class: "v", text: r.value }), el("span", { class: "k", text: r.label || "" }));
    tip.append(row);
  }
  const x = Math.min(ev.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
  const y = Math.min(ev.clientY + 14, window.innerHeight - tip.offsetHeight - 8);
  tip.style.left = `${x}px`; tip.style.top = `${y}px`; tip.style.opacity = 1;
}
function hideTip() { tip.style.opacity = 0; }

/* ---------- charts (plain SVG) ---------- */
function niceMax(v) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v))), m = v / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p;
}
function axes(g, W, H, m, xMax, yMax, xLabel, yTicks) {
  const grid = svg("g", { class: "grid" }), ax = svg("g", { class: "axis" });
  const ticks = yTicks || [0, yMax / 2, yMax];
  for (const t of ticks) {
    const y = m.t + (1 - t / yMax) * (H - m.t - m.b);
    grid.append(svg("line", { x1: m.l, x2: W - m.r, y1: y, y2: y }));
    const lab = svg("text", { x: m.l - 6, y: y + 4, "text-anchor": "end" }); lab.textContent = +t.toFixed(2); ax.append(lab);
  }
  ax.append(svg("line", { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));
  const step = niceMax(xMax / 6);
  for (let s = 0; s <= xMax + 1e-9; s += step) {
    const x = m.l + s / xMax * (W - m.l - m.r);
    const lab = svg("text", { x, y: H - m.b + 16, "text-anchor": "middle" }); lab.textContent = `${+s.toFixed(1)}`; ax.append(lab);
  }
  if (xLabel) { const t = svg("text", { x: W - m.r, y: H - 4, "text-anchor": "end" }); t.textContent = xLabel; ax.append(t); }
  g.append(grid, ax);
}

/** Line chart. series: [{name, color, points: [[x, y]]}]; one y-axis; crosshair + tooltip. */
function lineChart(host, { series, xMax, yMax, xLabel, yFormat = v => fmt(v, 0), threshold, height = 220, onPick }) {
  host.replaceChildren();
  const W = Math.max(host.clientWidth, 280), H = height, m = { l: 40, r: 12, t: 10, b: 30 };
  yMax = yMax || niceMax(Math.max(1, ...series.flatMap(s => s.points.map(p => p[1]))));
  const root = svg("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img" });
  axes(root, W, H, m, xMax, yMax, xLabel, threshold !== undefined ? [0, threshold, yMax] : null);
  const X = x => m.l + x / xMax * (W - m.l - m.r), Y = y => m.t + (1 - y / yMax) * (H - m.t - m.b);
  if (threshold !== undefined) root.append(svg("line", { x1: m.l, x2: W - m.r, y1: Y(threshold), y2: Y(threshold),
    stroke: css("--muted"), "stroke-width": 1, "stroke-dasharray": "3 3" }));
  for (const s of series) {
    if (!s.points.length) continue;
    const d = s.points.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
    root.append(svg("path", { d, fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
  }
  const cross = svg("line", { y1: m.t, y2: H - m.b, stroke: css("--axis"), "stroke-width": 1, opacity: 0 });
  const hit = svg("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent", tabindex: 0 });
  root.append(cross, hit);
  const nearest = (pts, x) => { let lo = 0, hi = pts.length - 1; while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (pts[mid][0] < x) lo = mid; else hi = mid; }
    return Math.abs(pts[lo][0] - x) <= Math.abs(pts[hi][0] - x) ? pts[lo] : pts[hi]; };
  const at = ev => { const r = root.getBoundingClientRect(); return Math.max(0, Math.min(xMax, ((ev.clientX - r.left) / r.width * W - m.l) / (W - m.l - m.r) * xMax)); };
  hit.addEventListener("pointermove", ev => {
    const x = at(ev); cross.setAttribute("x1", X(x)); cross.setAttribute("x2", X(x)); cross.setAttribute("opacity", 1);
    showTip(ev, series.filter(s => s.points.length).map(s => ({ color: s.color, value: yFormat(nearest(s.points, x)[1]), label: s.name })), `${fmt(x)} s`);
  });
  hit.addEventListener("pointerleave", () => { cross.setAttribute("opacity", 0); hideTip(); });
  if (onPick) { hit.style.cursor = "pointer"; hit.addEventListener("click", ev => onPick(at(ev))); }
  host.append(root);
}

/** Column chart for a histogram: bins [{x0, x1, n}] - one series, one colour. */
function columnChart(host, { bins, color, xLabel, height = 200, unit = "" }) {
  host.replaceChildren();
  const W = Math.max(host.clientWidth, 280), H = height, m = { l: 40, r: 12, t: 10, b: 30 };
  const xMax = bins[bins.length - 1].x1, yMax = niceMax(Math.max(1, ...bins.map(b => b.n)));
  const root = svg("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img" });
  axes(root, W, H, m, xMax, yMax, xLabel);
  const X = x => m.l + x / xMax * (W - m.l - m.r), Y = y => m.t + (1 - y / yMax) * (H - m.t - m.b);
  for (const b of bins) {
    const x = X(b.x0) + 1, w = Math.max(1, Math.min(24, X(b.x1) - X(b.x0) - 2)), y = Y(b.n), h = H - m.b - y;
    if (h <= 0) continue;
    const r = Math.min(4, w / 2, h);
    const d = `M${x},${H - m.b}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${H - m.b}Z`;
    const bar = svg("path", { d, fill: color, tabindex: 0 });
    const hit = svg("rect", { x: X(b.x0), y: m.t, width: X(b.x1) - X(b.x0), height: H - m.t - m.b, fill: "transparent" });
    const show = ev => showTip(ev, [{ value: `${b.n}${unit}`, label: `${fmt(b.x0, 2)}–${fmt(b.x1, 2)}` }]);
    for (const n of [bar, hit]) { n.addEventListener("pointermove", show); n.addEventListener("pointerleave", hideTip); }
    root.append(bar, hit);
  }
  host.append(root);
}

/** Swimlane timeline: one labelled row per class; predictions filled, dev labels outlined. */
function timeline(host, { duration, events, labels, onPick }) {
  host.replaceChildren();
  const used = CLASSES.filter(c => events.some(e => e[2] === c) || (labels || []).some(e => e[2] === c));
  const rows = used.length ? used : ["no events"];
  const W = Math.max(host.clientWidth, 280), lab = Math.min(150, W * 0.32), rowH = 26, m = { t: 6, b: 26 };
  const H = m.t + rows.length * rowH + m.b;
  const root = svg("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img" });
  const X = t => lab + t / duration * (W - lab - 8);
  const grid = svg("g", { class: "grid" });
  const step = niceMax(duration / 8);
  for (let s = 0; s <= duration + 1e-9; s += step) {
    grid.append(svg("line", { x1: X(s), x2: X(s), y1: m.t, y2: H - m.b }));
    const t = svg("text", { x: X(s), y: H - 8, "text-anchor": "middle" }); t.textContent = `${+s.toFixed(0)}s`; root.append(t);
  }
  root.append(grid);
  rows.forEach((c, i) => {
    const y = m.t + i * rowH;
    const t = svg("text", { x: 0, y: y + rowH / 2 + 4 }); t.textContent = pretty(c); t.style.fill = css("--ink-2"); root.append(t);
    for (const e of (labels || []).filter(e => e[2] === c))
      root.append(svg("rect", { x: X(e[0]), y: y + 3, width: Math.max(2, X(e[1]) - X(e[0])), height: rowH - 6, rx: 4,
        fill: "none", stroke: css("--ink-2"), "stroke-width": 1 }));
    for (const e of events.filter(e => e[2] === c)) {
      const bar = svg("rect", { class: "tl-bar", x: X(e[0]), y: y + 7, width: Math.max(3, X(e[1]) - X(e[0])), height: rowH - 14,
        rx: 3, fill: css("--s1"), tabindex: 0, role: "button", "aria-label": `${c} ${fmt(e[0])} to ${fmt(e[1])} s` });
      bar.addEventListener("pointermove", ev => showTip(ev, [{ value: `${fmt(e[0])}–${fmt(e[1])} s`, label: pretty(c) }]));
      bar.addEventListener("pointerleave", hideTip);
      bar.addEventListener("click", () => onPick && onPick(e[0]));
      bar.addEventListener("keydown", ev => { if (ev.key === "Enter") onPick && onPick(e[0]); });
      root.append(bar);
    }
  });
  const head = svg("line", { class: "playhead", x1: X(0), x2: X(0), y1: 0, y2: H - m.b });
  root.append(head);
  host.append(root);
  return t => { head.setAttribute("x1", X(t)); head.setAttribute("x2", X(t)); };
}

/* ---------- matching against dev labels (same rule as the metric, IoU >= tau) ---------- */
function tiou(a, b) { const i = Math.max(0, Math.min(a[1], b[1]) - Math.max(a[0], b[0])); const u = (a[1] - a[0]) + (b[1] - b[0]) - i; return u > 0 ? i / u : 0; }
function f1At(pred, gt, tau) {
  const pairs = [];
  gt.forEach((g, i) => pred.forEach((p, j) => pairs.push([tiou(g, p), i, j])));
  pairs.sort((a, b) => b[0] - a[0]);
  const ug = new Set(), up = new Set(); let tp = 0;
  for (const [iou, i, j] of pairs) { if (iou < tau) break; if (!ug.has(i) && !up.has(j)) { ug.add(i); up.add(j); tp++; } }
  const fp = pred.length - tp, fn = gt.length - tp;
  return tp ? 2 * tp / (2 * tp + fp + fn) : 0;
}

/* ---------- sections ---------- */
function tile(label, value, note) {
  return el("div", { class: "tile" }, el("div", { class: "label", text: label }), el("div", { class: "value", text: value }),
    note ? el("div", { class: "note", text: note }) : null);
}

function renderPipeline() {
  const host = $("#pipeline");
  const W = 1080, H = 250;
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Pipeline diagram" });
  const box = (x, y, w, h, title, sub, accent) => {
    root.append(svg("rect", { x, y, width: w, height: h, rx: 10, fill: accent ? css("--label-wash") : css("--surface-2"),
      stroke: accent ? css("--accent") : css("--axis"), "stroke-width": 1 }));
    const t = svg("text", { x: x + w / 2, y: y + h / 2 - (sub ? 4 : -4), "text-anchor": "middle" });
    t.textContent = title; t.style.fill = css("--ink"); t.style.font = "600 14px system-ui"; root.append(t);
    if (sub) { const s = svg("text", { x: x + w / 2, y: y + h / 2 + 14, "text-anchor": "middle" }); s.textContent = sub; s.style.fill = css("--ink-2"); s.style.font = "12px system-ui"; root.append(s); }
  };
  const arrow = (x1, y1, x2, y2) => {
    root.append(svg("line", { x1, y1, x2, y2, stroke: css("--muted"), "stroke-width": 1.5 }));
    const a = Math.atan2(y2 - y1, x2 - x1), s = 7;
    root.append(svg("path", { d: `M${x2},${y2}L${x2 - s * Math.cos(a - 0.45)},${y2 - s * Math.sin(a - 0.45)}L${x2 - s * Math.cos(a + 0.45)},${y2 - s * Math.sin(a + 0.45)}Z`, fill: css("--muted") }));
  };
  const y1 = 22, h = 64, y2 = 160;
  box(10, y1, 140, h, "Video (.mp4)", "every k-th frame");
  box(185, y1, 150, h, "YOLO11", "detector (learned)", true);
  box(370, y1, 150, h, "ByteTrack", "online tracking");
  box(555, y1, 160, h, "Trajectories", "smoothed kinematics");
  box(750, y1, 150, h, "14 event rules", "explainable");
  box(935, y1, 135, h, "Part A", "[start, end, label]");
  box(370, y2, 150, h, "Scene layout", "drawn + learned", true);
  box(555, y2, 160, h, "Conflicts", "closest approach, braking");
  box(750, y2, 150, h, "Risk fusion", "hold + calibration");
  box(935, y2, 135, h, "Part B", "P(accident ≤ 5 s)");
  arrow(150, y1 + h / 2, 185, y1 + h / 2); arrow(335, y1 + h / 2, 370, y1 + h / 2); arrow(520, y1 + h / 2, 555, y1 + h / 2);
  arrow(715, y1 + h / 2, 750, y1 + h / 2); arrow(900, y1 + h / 2, 935, y1 + h / 2);
  arrow(520, y2 + 10, 750, y1 + h + 2);
  arrow(635, y1 + h, 635, y2); arrow(715, y2 + h / 2, 750, y2 + h / 2); arrow(900, y2 + h / 2, 935, y2 + h / 2);
  host.replaceChildren(root, el("figcaption", { class: "muted", text: "Part B runs its own causal detector and tracker on the frames it has received; it never reads the video file." }));
}

function renderApproach(site) {
  const learned = site?.approach?.learned || ["YOLO11 detectors pretrained on COCO (m for Part A on GPU, s for Part B).",
    "Drivable-area mask learned from where moving vehicles drive in the sample videos.",
    "Direction field: a histogram of vehicle headings in every image cell."];
  const rules = site?.approach?.rules || ["Tracking and kinematics: ByteTrack, Savitzky–Golay smoothing, speeds in object sizes per second.",
    "One explainable rule per event class, all thresholds in configs/pipeline.yaml.",
    "Segment post-processing tuned for temporal IoU up to 0.7.",
    "Part B: constant-velocity closest approach, braking and wrong-way evidence, logistic calibration."];
  $("#learnedList").replaceChildren(...learned.map(t => el("li", { text: t })));
  $("#rulesList").replaceChildren(...rules.map(t => el("li", { text: t })));
  $("#rulesTable tbody").replaceChildren(...RULES.map(([c, r]) => el("tr", {}, el("td", {}, el("code", { text: c })), el("td", { text: r }))));
  renderPipeline();
}

function renderEda(eda) {
  const sel = $("#edaVideo"), body = $("#edaBody");
  if (!eda || !eda.videos || !eda.videos.length) { sel.parentElement.hidden = true; return; }
  sel.replaceChildren(...eda.videos.map((v, i) => el("option", { value: i, text: v.video })));
  const draw = () => {
    const v = eda.videos[+sel.value || 0];
    const b = v.brightness.mean;
    const lighting = b == null ? "–" : b < 60 ? "night" : b < 100 ? "dusk / dim" : "daylight";
    const total = Object.values(v.tracks_by_class || {}).reduce((a, c) => a + c, 0);
    const counts = el("div", { class: "card" }), speed = el("div", { class: "card" }), light = el("div", { class: "card" });
    body.replaceChildren(
      el("div", { class: "tiles" }, tile("Resolution", `${v.width}×${v.height}`), tile("Frame rate", `${fmt(v.fps, 1)} fps`),
        tile("Duration", `${fmt(v.duration / 60, 1)} min`, `${v.n_frames} frames`), tile("Lighting", lighting, `mean luma ${b ?? "–"}`),
        tile("Tracked road users", `${total}`, Object.entries(v.tracks_by_class || {}).map(([k, n]) => `${pretty(k)} ${n}`).join(" · "))),
      el("div", { style: "height:16px" }), counts, el("div", { class: "grid2" }, speed, light), imagesCard(v), lightsCard(v));
    const secs = v.counts_per_second;
    const series = SERIES.filter(([k]) => secs[k] && secs[k].some(n => n > 0)).map(([k, c]) => ({ name: pretty(k), color: css(c), points: secs[k].map((n, i) => [i, n]) }));
    counts.append(el("div", { class: "chart-head" }, el("h3", { text: "Road users in view, per second" }), legend(series)));
    const ch = el("div"); counts.append(ch);
    lineChart(ch, { series, xMax: v.duration, xLabel: "seconds" });
    counts.append(tableToggle(["second", ...series.map(s => s.name)], secs.vehicle.map((_, i) => [i, ...series.map(s => s.points[i]?.[1] ?? 0)])));
    const hb = v.vehicle_speed_hist;
    speed.append(el("div", { class: "chart-head" }, el("h3", { text: "Vehicle speed distribution" })),
      el("p", { class: "muted", text: `Speed in vehicle sizes per second. ${Math.round((v.stopped_share || 0) * 100)} % of vehicle observations are stationary.` }));
    const sh = el("div"); speed.append(sh);
    columnChart(sh, { bins: hb.counts.map((n, i) => ({ x0: hb.edges[i], x1: hb.edges[i + 1], n })), color: css("--s1"), xLabel: "sizes / s" });
    light.append(el("div", { class: "chart-head" }, el("h3", { text: "Lighting over time" })), el("p", { class: "muted", text: "Mean frame brightness (0–255)." }));
    const lh = el("div"); light.append(lh);
    lineChart(lh, { series: [{ name: "brightness", color: css("--s1"), points: v.brightness.per_second.map((y, i) => [i, y]) }], xMax: v.duration, yMax: 255, xLabel: "seconds" });
  };
  sel.onchange = draw; draw();
  redraws.set("eda", draw);
}
function legend(series) { return el("div", { class: "legend" }, ...series.map(s => el("span", {}, el("span", { class: "key", style: `background:${s.color}` }), s.name))); }
function tableToggle(head, rows) {
  const wrap = el("div", { class: "table-scroll", hidden: "" });
  const table = el("table", { class: "data" }, el("thead", {}, el("tr", {}, ...head.map(h => el("th", { text: h })))),
    el("tbody", {}, ...rows.map(r => el("tr", {}, ...r.map(c => el("td", { class: "num", text: String(c) }))))));
  wrap.append(table);
  const btn = el("button", { class: "linkish", type: "button", text: "Show data table" });
  btn.onclick = () => { wrap.hidden = !wrap.hidden; btn.textContent = wrap.hidden ? "Show data table" : "Hide data table"; };
  return el("div", {}, btn, wrap);
}
function imagesCard(v) {
  const caps = { frame: "Camera view", trajectories: "Vehicle trajectories, coloured by direction of travel",
    heat_vehicles: "Where vehicles drive", heat_stops: "Where vehicles stand still (queues, parking)", heat_pedestrians: "Where pedestrians walk" };
  const figs = Object.entries(caps).filter(([k]) => v.images && v.images[k]).map(([k, c]) =>
    el("figure", {}, el("img", { src: v.images[k], alt: c, loading: "lazy" }), el("figcaption", { text: c })));
  return el("div", { class: "card" }, el("h3", { text: "Where things happen" }), el("div", { class: "imgs" }, ...figs));
}
function lightsCard(v) {
  const L = v.traffic_lights || [];
  return el("div", { class: "card" }, el("h3", { text: "Traffic lights found by the detector" }),
    L.length ? el("div", { class: "table-scroll" }, el("table", { class: "data" }, el("thead", {}, el("tr", {}, el("th", { text: "box (x1, y1, x2, y2)" }), el("th", { text: "detections" }))),
      el("tbody", {}, ...L.map(l => el("tr", {}, el("td", { class: "num", text: l.roi.join(", ") }), el("td", { class: "num", text: l.hits })))))) :
      el("p", { class: "muted", text: "No traffic light is visible often enough to read its state." }));
}

async function renderResults(index) {
  const sel = $("#resVideo"), body = $("#resBody");
  if (!index || !index.length) { sel.parentElement.hidden = true; return; }
  sel.replaceChildren(...index.map((v, i) => el("option", { value: i, text: `${v.video} · ${v.events} events` })));
  const cache = {};
  const draw = async () => {
    const item = index[+sel.value || 0];
    const r = cache[item.file] || (cache[item.file] = await load(item.file));
    if (!r) { body.replaceChildren(el("p", { class: "empty", text: "Could not load this result." })); return; }
    const video = el("video", { src: r.annotated, controls: "", preload: "metadata", playsinline: "" });
    const seek = t => { video.currentTime = Math.max(0, t - 0.5); video.play().catch(() => {}); };
    const tlHost = el("div"), riskHost = el("div");
    const tlCard = el("div", { class: "card timeline-wrap" }, el("div", { class: "chart-head" }, el("h3", { text: "Event timeline" }),
      el("div", { class: "legend" }, el("span", {}, el("span", { class: "box", style: `background:${css("--s1")}` }), "predicted"),
        r.labels ? el("span", {}, el("span", { class: "box", style: `border:1px solid ${css("--ink-2")}` }), "our dev label") : null)), tlHost);
    const riskCard = el("div", { class: "card" }, el("div", { class: "chart-head" }, el("h3", { text: "Part B: probability that an accident starts within 5 s" }),
      el("span", { class: "muted", text: "dotted line: alarm threshold 0.5" })), riskHost);
    const rows = r.events.map(e => el("tr", { class: "clickable", onclick: () => seek(e[0]) },
      el("td", {}, el("code", { text: e[2] })), el("td", { class: "num", text: fmt(e[0], 2) }), el("td", { class: "num", text: fmt(e[1], 2) }),
      el("td", { class: "num", text: fmt(e[1] - e[0], 1) })));
    const evCard = el("div", { class: "card" }, el("h3", { text: `Events (${r.events.length})` }),
      r.events.length ? el("div", { class: "table-scroll" }, el("table", { class: "data" },
        el("thead", {}, el("tr", {}, ...["class", "start s", "end s", "length s"].map(h => el("th", { text: h })))), el("tbody", {}, ...rows)))
        : el("p", { class: "muted", text: "No events detected in this video." }));
    const player = el("div", { class: "card player" }, video);
    // videos are kept out of the repository: without the file, say how to render it instead of a broken player
    video.addEventListener("error", () => player.replaceChildren(el("p", { class: "muted",
      text: "The annotated video is not published here (videos stay out of the repository). Render it locally with tools/export_results.py." })));
    body.replaceChildren(player, tlCard, riskCard, evCard, r.labels ? scoreCard(r) : null);
    let move = () => {};
    const charts = () => {
      move = timeline(tlHost, { duration: r.duration, events: r.events, labels: r.labels, onPick: seek });
      lineChart(riskHost, { series: [{ name: "risk", color: css("--s1"), points: r.risk }], xMax: r.duration, yMax: 1, threshold: 0.5,
        xLabel: "seconds", yFormat: v => fmt(v, 2), height: 160, onPick: seek });
      move(video.currentTime || 0);
    };
    charts();
    video.addEventListener("timeupdate", () => move(video.currentTime));
    redraws.set("results", charts);
  };
  sel.onchange = draw; await draw();
}
function scoreCard(r) {
  const classes = CLASSES.filter(c => r.events.some(e => e[2] === c) || r.labels.some(e => e[2] === c));
  const rows = classes.map(c => {
    const p = r.events.filter(e => e[2] === c), g = r.labels.filter(e => e[2] === c);
    const f = [0.3, 0.5, 0.7].map(t => f1At(p, g, t));
    return [c, g.length, p.length, ...f.map(v => fmt(v, 2)), fmt((f[0] + f[1] + f[2]) / 3, 2)];
  });
  return el("div", { class: "card" }, el("h3", { text: "Against our dev labels (this video)" }),
    el("div", { class: "table-scroll" }, el("table", { class: "data" },
      el("thead", {}, el("tr", {}, ...["class", "labelled", "predicted", "F1@0.3", "F1@0.5", "F1@0.7", "mean"].map(h => el("th", { text: h })))),
      el("tbody", {}, ...rows.map(r => el("tr", {}, el("td", {}, el("code", { text: r[0] })), ...r.slice(1).map(v => el("td", { class: "num", text: String(v) }))))))));
}

function renderDemo(site) {
  const card = $("#demoCard"), url = site?.demo_url, embed = site?.demo_embed_url || site?.demo_url;
  if (!url) { card.replaceChildren(el("p", { class: "empty", text: "The demo link will be added when the Hugging Face Space is published." })); return; }
  card.replaceChildren(el("p", {}, el("a", { href: url, target: "_blank", rel: "noopener", text: "Open the demo in a new tab ↗" }),
    el("span", { class: "muted", text: " — the Space may need a minute to wake up if nobody used it recently." })),
    el("iframe", { src: embed, title: "TrafficWatch live demo", loading: "lazy", allow: "fullscreen" }));
}

function renderReport(site) {
  const r = site?.report || {};
  const col = (title, items) => el("div", { class: "card" }, el("h3", { text: title }), el("ul", {}, ...(items || ["TODO"]).map(t => el("li", { text: t }))));
  $("#reportBody").replaceChildren(col("What worked", r.worked), col("What did not", r.failed), col("What we would do next", r.next));
}

function renderTeam(site) {
  const team = site?.team || [];
  $("#teamBody").replaceChildren(...team.map(p => el("div", { class: "card member" }, el("h3", { text: p.name }), el("div", { class: "role", text: p.role }),
    el("p", { text: p.contributions }), p.projects ? el("p", { text: `Proud of: ${p.projects}` }) : null,
    el("div", { class: "mlinks" }, ...[["GitHub", p.github], ["LinkedIn", p.linkedin], ["Portfolio", p.portfolio]]
      .filter(([, u]) => u).map(([t, u]) => el("a", { href: u, target: "_blank", rel: "noopener", text: t }))))));
}

function renderLinks(site) {
  const L = [["Code repository", site?.repo_url], ["Model weights", site?.weights_url], ["predictions_samples.json", site?.predictions_url],
    ["Live demo (Hugging Face Space)", site?.demo_url]].filter(([, u]) => u);
  $("#linksBody").replaceChildren(...(L.length ? L.map(([t, u]) => el("li", {}, el("a", { href: u, target: "_blank", rel: "noopener", text: t }))) : [el("li", { class: "muted", text: "Links will be added at submission." })]));
}

function renderHero(site, eda, index) {
  const tiles = [];
  if (site?.metrics?.score_a_dev != null) tiles.push(tile("Score A on our dev labels", fmt(site.metrics.score_a_dev, 3), "macro F1, IoU 0.3/0.5/0.7"));
  if (eda?.videos?.length) {
    const mins = eda.videos.reduce((a, v) => a + v.duration, 0) / 60;
    tiles.push(tile("Sample footage analysed", `${fmt(mins, 1)} min`, `${eda.videos.length} videos`));
  }
  if (index?.length) tiles.push(tile("Events detected on samples", `${index.reduce((a, v) => a + v.events, 0)}`));
  if (site?.metrics?.speed) tiles.push(tile("Speed", site.metrics.speed, site.metrics.speed_note));
  tiles.push(tile("Event classes", "14", "plus accident anticipation"));
  $("#heroTiles").replaceChildren(...tiles);
}

function debounce(fn, ms) { let t; return () => { clearTimeout(t); t = setTimeout(fn, ms); }; }

function setupTheme(rerender) {
  const root = document.documentElement;
  try { const saved = localStorage.getItem("tw-theme"); if (saved) root.dataset.theme = saved; } catch (e) { /* storage unavailable */ }
  $("#themeBtn").onclick = () => {
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("tw-theme", root.dataset.theme); } catch (e) { /* storage unavailable */ }
    rerender();
  };
}

(async function main() {
  const [site, eda, index] = await Promise.all([load("data/site.json"), load("data/eda.json"), load("data/results_index.json")]);
  if (site?.lede) $("#heroLede").textContent = site.lede;
  renderApproach(site); renderEda(eda); renderDemo(site); renderReport(site); renderTeam(site); renderLinks(site);
  renderHero(site, eda, index);
  await renderResults(index);
  const rerender = () => { renderPipeline(); for (const f of redraws.values()) f(); };
  setupTheme(rerender);
  window.addEventListener("resize", debounce(() => { for (const f of redraws.values()) f(); }, 200));
})();
