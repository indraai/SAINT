// pySAINT browser UI: plain JS, no build step, talks to /api/*.
"use strict";
const $ = (id) => document.getElementById(id);
let lastRequest = null;

async function api(path, body) {
  const opt = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opt);
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  return { ok: r.ok, status: r.status, data };
}

function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function fmt(v) { return typeof v === "number" ? (Number.isInteger(v) ? v : v.toPrecision(5)) : (v ?? ""); }

function status(msg, cls) { $("status").className = cls || ""; $("status").textContent = msg; }

function showDiagnostics(d) {
  const box = $("diagnostics"); box.innerHTML = "";
  const items = [];
  if (d.stage === "parse") {
    items.push({ severity: "error", code: "PARSE", message: d.message, location: "" });
    (d.details || []).forEach((x) => items.push({ severity: "error", code: "SCHEMA", message: x.message, location: x.location }));
  } else {
    (d.errors || []).forEach((x) => items.push(x));
    (d.warnings || []).forEach((x) => items.push(x));
  }
  if (d.stage === "run") items.push({ severity: "error", code: "RUN", message: d.message, location: "" });
  for (const x of items) {
    const div = document.createElement("div");
    div.className = "diag " + x.severity;
    div.textContent = `${x.severity.toUpperCase()} ${x.code}${x.location ? " [" + x.location + "]" : ""}: ${x.message}`;
    box.appendChild(div);
  }
}

function request() {
  const req = { text: $("text").value, format: $("format").value };
  const s = $("seed").value, n = $("iterations").value;
  if (s !== "") req.seed = parseInt(s, 10);
  if (n !== "") req.iterations = parseInt(n, 10);
  return req;
}

function table(rows, cols, labels) {
  if (!rows || !rows.length) return '<p class="muted">(none)</p>';
  let h = "<table><tr>" + cols.map((c, i) => `<th class="${i < labels ? "l" : ""}">${esc(c)}</th>`).join("") + "</tr>";
  for (const r of rows) h += "<tr>" + cols.map((c, i) => `<td class="${i < labels ? "l" : ""}">${esc(fmt(r[c]))}</td>`).join("") + "</tr>";
  return h + "</table>";
}

// ---- network diagram: layered layout (BFS depth from sources), inline SVG
function drawGraph(g) {
  const nodes = g.nodes, edges = g.edges;
  if (!nodes.length) { $("diagram").innerHTML = '<p class="muted">(no tasks)</p>'; return; }
  const succ = {}; nodes.forEach((n) => (succ[n.id] = []));
  edges.forEach((e) => succ[e.from] && succ[e.from].push(e.to));
  const depth = {}; const q = [];
  nodes.filter((n) => n.role === "SO").forEach((n) => { depth[n.id] = 0; q.push(n.id); });
  if (!q.length) { depth[nodes[0].id] = 0; q.push(nodes[0].id); }
  while (q.length) { const u = q.shift(); for (const v of succ[u] || []) if (depth[v] === undefined && succ[v]) { depth[v] = depth[u] + 1; q.push(v); } }
  let maxd = Math.max(...Object.values(depth));
  nodes.forEach((n) => { if (depth[n.id] === undefined) depth[n.id] = ++maxd; });
  const cols = {}; nodes.forEach((n) => (cols[depth[n.id]] = cols[depth[n.id]] || []).push(n));
  const W = 120, H = 70, NW = 90, NH = 34, pos = {};
  let maxRows = 1;
  Object.entries(cols).forEach(([d, list]) => { maxRows = Math.max(maxRows, list.length); list.forEach((n, i) => (pos[n.id] = { x: 20 + d * W, y: 20 + i * H })); });
  const width = 40 + (maxd + 1) * W, height = 40 + maxRows * H;
  let s = `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><defs><marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" fill="#55607a"/></marker></defs>`;
  for (const e of edges) {
    const a = pos[e.from], b = pos[e.to]; if (!a || !b) continue;
    let x1 = a.x + NW, y1 = a.y + NH / 2, x2 = b.x, y2 = b.y + NH / 2, path;
    if (b.x <= a.x) { // back edge: loop under the nodes
      const yy = Math.max(a.y, b.y) + NH + 14; x1 = a.x + NW / 2; y1 = a.y + NH; x2 = b.x + NW / 2; y2 = b.y + NH;
      path = `M${x1},${y1} C${x1},${yy} ${x2},${yy} ${x2},${y2}`;
    } else { const mx = (x1 + x2) / 2; path = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`; }
    s += `<path d="${path}" fill="none" stroke="#55607a" stroke-width="1.3" ${e.type === "PRO" ? 'stroke-dasharray="4 3"' : ""} marker-end="url(#arr)"/>`;
    if (e.label) s += `<text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 4}" text-anchor="middle" fill="#9a3b00">${esc(e.label)}</text>`;
  }
  const fill = { SO: "#d9f2e1", SI: "#fde2e2", NS: "#e4ebfa" };
  for (const n of nodes) {
    const p = pos[n.id];
    s += `<g><title>Task ${n.id} ${esc(n.label)} (${n.role})${n.resources.length ? " resources " + n.resources.join(",") : ""}</title>`;
    s += `<rect x="${p.x}" y="${p.y}" width="${NW}" height="${NH}" rx="${n.role === "NS" ? 5 : 16}" fill="${fill[n.role] || "#eee"}" stroke="#55607a"/>`;
    s += `<text x="${p.x + NW / 2}" y="${p.y + 14}" text-anchor="middle" font-weight="600">${esc(n.label)}</text>`;
    s += `<text x="${p.x + NW / 2}" y="${p.y + 27}" text-anchor="middle" fill="#55607a">#${n.id}${n.resources.length ? " · R" + n.resources.join(",") : ""}</text></g>`;
  }
  s += "</svg>";
  $("diagram").innerHTML = s + '<p class="muted">Green = source, red = sink, dashed = probabilistic branch. Hover a task for details.</p>';
}

function showResult(r) {
  const et = r.end_time;
  $("summary").innerHTML = `<b>${esc(r.model)}</b> — ${r.iterations} iteration(s), seed ${r.seed}` +
    (et ? ` — end time mean ${fmt(et.mean)} (sd ${fmt(et.sd)}, min ${fmt(et.min)}, max ${fmt(et.max)})` : "") +
    (r.warnings.length ? `<div class="warn">${r.warnings.map(esc).join("<br>")}</div>` : "");
  $("tasks").innerHTML = table(r.tasks, ["task", "label", "stat", "n", "mean", "sd", "min", "max", "ci95"], 3);
  const res = r.resources.map((x) => ({ ...x, bar: x.mean }));
  $("resources").innerHTML = res.length ? "<table><tr><th class=l>resource</th><th class=l>label</th><th class=l>utilization (mean)</th><th>sd</th><th>busy_time</th><th>n_tasks</th></tr>" +
    res.map((x) => `<tr><td class=l>${x.resource}</td><td class=l>${esc(x.label)}</td><td class=l><span class="bar" style="width:${Math.round((x.mean || 0) * 150)}px"></span>${(100 * (x.mean || 0)).toFixed(1)}%</td><td>${fmt(x.sd)}</td><td>${fmt(x.busy_time)}</td><td>${fmt(x.n_tasks)}</td></tr>`).join("") + "</table>" : '<p class="muted">(no resources)</p>';
  $("iters").innerHTML = '<div class="scroll">' + table(r.iterations_table, ["iteration", "end_time", "events", "sinks_done"], 0) + "</div>";
  $("downloads").hidden = false;
}

async function doValidate() {
  status("Validating…");
  const { data } = await api("/api/validate", request());
  showDiagnostics(data.detail || data);
  if (data.detail) return status("Could not read the model (see below).", "bad"), false;
  if (data.graph) drawGraph(data.graph);
  if (data.model) { $("seed").placeholder = data.model.seed; $("iterations").placeholder = data.model.iterations; }
  status(data.ok ? `Valid. ${data.warnings.length} warning(s).` : `${data.errors.length} error(s), ${data.warnings.length} warning(s).`, data.ok ? "ok" : "bad");
  return data.ok;
}

async function doRun() {
  $("btn-run").disabled = true; status("Running…");
  try {
    lastRequest = request();
    const { ok, data } = await api("/api/run", lastRequest);
    if (!ok) { showDiagnostics(data.detail || {}); return status("Run failed (see below).", "bad"); }
    showDiagnostics(data.validation); drawGraph(data.graph); showResult(data.result);
    status("Run complete.", "ok");
  } catch (e) { status("Error: " + e, "bad"); } finally { $("btn-run").disabled = false; }
}

async function download(tableName) {
  const r = await fetch("/api/run/csv?table=" + tableName, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(lastRequest || request()) });
  if (!r.ok) return status("CSV download failed.", "bad");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob()); a.download = tableName + ".csv"; a.click();
}

async function init() {
  const h = await api("/api/health"); $("version").textContent = "v" + h.data.version;
  const ex = await api("/api/examples");
  for (const e of ex.data) { const o = document.createElement("option"); o.value = e.name; o.textContent = e.name + (e.description ? " — " + e.description : ""); $("example").appendChild(o); }
  $("example").onchange = async () => { if (!$("example").value) return; const r = await api("/api/examples/" + encodeURIComponent($("example").value)); $("text").value = r.data.text; doValidate(); };
  $("upload").onchange = async (ev) => { const f = ev.target.files[0]; if (f) { $("text").value = await f.text(); doValidate(); } };
  $("btn-validate").onclick = doValidate; $("btn-run").onclick = doRun;
  document.querySelectorAll("#downloads button").forEach((b) => (b.onclick = () => download(b.dataset.table)));
  // Deep link: /?example=inspection_network.yaml&run=1
  const qs = new URLSearchParams(location.search);
  if (qs.get("example")) {
    const r = await api("/api/examples/" + encodeURIComponent(qs.get("example")));
    if (r.ok) { $("example").value = qs.get("example"); $("text").value = r.data.text; if (await doValidate() && qs.get("run")) doRun(); }
  }
}
init();
