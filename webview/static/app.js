/* ============================================================
   AgriPolicy Sandbox · 实验可视化 —— 前端逻辑
   依赖：无（原生 JS + SVG，零第三方库）
   ============================================================ */
"use strict";

const REFRESH_MS = 3000;

const CROP_COLORS = {
  wheat: "#e6c229",
  corn: "#f2a03d",
  rice: "#6fc3a0",
  soybean: "#93c95e",
  vegetable: "#b39ddb",
};
const CROP_LABELS = {
  wheat: "小麦", corn: "玉米", rice: "水稻",
  soybean: "大豆", vegetable: "蔬菜",
};
const SCALE_LABELS = { small: "小农", medium: "中农", large: "大户" };

const state = {
  overview: null,
  scenarioDefs: null,
  selected: null, // { scenario, repeat }
  runData: null,
  selectedFarmer: null,
};

const $ = (id) => document.getElementById(id);

/* ---------------- 基础工具 ---------------- */
async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

const fmtInt = (v) => (v == null ? "—" : Math.round(v).toLocaleString());
const fmt1 = (v) => (v == null ? "—" : Number(v).toFixed(1));
const fmtPct = (v) => (v == null ? "—" : (v * 100).toFixed(1) + "%");
const fmtDur = (sec) => {
  if (sec == null) return "—";
  sec = Math.round(sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`;
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function cropColor(plan) {
  let best = null, maxA = 0;
  for (const [c, a] of Object.entries(plan || {})) {
    if (a > maxA) { maxA = a; best = c; }
  }
  return best || null;
}

/* ---------------- 顶栏 / 卡片 / 表格 ---------------- */
function setConn(ok) {
  $("conn").className = "conn " + (ok ? "ok" : "bad");
}

function renderTopStats(o) {
  $("stat-running").textContent = o.totals.running;
  $("stat-done").textContent = o.totals.done;
  $("stat-pending").textContent = o.totals.pending;
}

function renderCards(o) {
  const wrap = $("scenario-cards");
  wrap.innerHTML = "";
  for (const sc of o.scenarios) {
    const card = document.createElement("div");
    card.className = "card" + (state.selected && state.selected.scenario === sc.scenario_key ? " active" : "");
    const pct = sc.total ? Math.round(((sc.done + sc.running) / sc.total) * 100) : 0;
    card.innerHTML = `
      <div class="c-top">
        <div>
          <div class="c-name">${esc(sc.label)}</div>
          <div class="c-label">${esc(sc.scenario_key)}</div>
        </div>
        <span class="badge ${sc.running ? "running" : sc.total && sc.done === sc.total ? "done" : "pending"}">
          <span class="bd"></span>${sc.running ? "运行中" : sc.total && sc.done === sc.total ? "完成" : sc.total ? "进行中" : "待运行"}
        </span>
      </div>
      <div class="c-counts">
        <span>完成 <b>${sc.done}</b></span>
        <span>运行 <b>${sc.running}</b></span>
        <span>共 <b>${sc.total}</b></span>
      </div>
      <div class="c-bar"><i style="width:${pct}%"></i></div>`;
    card.onclick = () => selectScenario(sc.scenario_key);
    wrap.appendChild(card);
  }
}

function renderTable(o) {
  const tb = $("runs-table").querySelector("tbody");
  tb.innerHTML = "";
  for (const r of o.runs) {
    const st = r.status === "running" ? "running" : r.status === "done" ? "done" : "pending";
    const pct = r.step_total ? Math.round((r.step / r.step_total) * 100) : r.status === "done" ? 100 : 0;
    const tr = document.createElement("tr");
    const sel = state.selected && state.selected.scenario === r.scenario_key && state.selected.repeat === r.repeat;
    if (sel) tr.className = "selected";
    tr.innerHTML = `
      <td>${esc(r.scenario_label)}</td>
      <td>#${r.repeat}</td>
      <td><span class="badge ${st}"><span class="bd"></span>${st === "running" ? "运行中" : st === "done" ? "已完成" : "待运行"}</span></td>
      <td>${r.phase ? (r.phase === "baseline" ? "基线期" : "政策期") : "—"}</td>
      <td>${r.step ?? "—"} / ${r.step_total ?? "—"}</td>
      <td><div class="progress-track"><i class="${st === "done" ? "done" : ""}" style="width:${pct}%"></i></div></td>
      <td>${fmtDur(r.elapsed_sec)}</td>
      <td>${esc(r.model || "—")}</td>`;
    tr.onclick = () => selectRun(r.scenario_key, r.repeat);
    tb.appendChild(tr);
  }
  $("runs-hint").textContent = `共 ${o.runs.length} 个运行 · 结果目录 ${o.results_dir}`;
}

/* ---------------- 情景 / 运行选择 ---------------- */
function runsOf(scenario) {
  return (state.overview?.runs || []).filter((r) => r.scenario_key === scenario);
}

function selectScenario(sk) {
  const runs = runsOf(sk);
  const pick = runs.find((r) => r.status === "running") || runs.find((r) => r.status === "done") || runs[0];
  if (!pick) return;
  fillRunSelect(sk, runs, pick.repeat);
  selectRun(sk, pick.repeat);
}

function fillRunSelect(sk, runs, activeRepeat) {
  const sel = $("run-select");
  sel.innerHTML = "";
  for (const r of runs) {
    const op = document.createElement("option");
    op.value = r.repeat;
    op.textContent = `重复 #${r.repeat} · ${r.status === "running" ? "运行中" : r.status === "done" ? "已完成" : "待运行"}`;
    sel.appendChild(op);
  }
  sel.value = String(activeRepeat);
  sel.onchange = () => selectRun(sk, Number(sel.value));
}

async function selectRun(sk, rep) {
  state.selected = { scenario: sk, repeat: rep };
  state.selectedFarmer = null;
  state.runData = null;
  // 更新卡片高亮
  document.querySelectorAll(".card").forEach((c) => c.classList.remove("active"));
  const cards = $("scenario-cards").children;
  [...cards].forEach((c) => { if (c.textContent.includes(sk)) c.classList.add("active"); });
  renderTable(state.overview); // 同步行高亮
  await refreshRun(true);
}

/* ---------------- 运行数据拉取与渲染 ---------------- */
async function refreshRun(force) {
  if (!state.selected) return;
  const { scenario, repeat } = state.selected;
  const cur = state.runData;
  // 若非运行中且已有数据，无需刷新
  if (!force && cur && cur.progress?.status !== "running") return;
  try {
    const [run, ts, ag] = await Promise.all([
      api(`/api/run/${scenario}/${repeat}`),
      api(`/api/run/${scenario}/${repeat}/timeseries`),
      api(`/api/run/${scenario}/${repeat}/agent-series`),
    ]);
    state.runData = { run, ts, ag };
    renderScene();
    renderCharts();
  } catch (e) {
    console.warn("refreshRun failed", e);
  }
}

/* ---------------- 场景元信息条 ---------------- */
function renderSceneMeta(run) {
  const meta = run.meta || {};
  const st = run.state || {};
  const env = st.env || null;
  const prog = run.progress || {};
  const el = $("scene-meta");
  if (!env) {
    el.innerHTML = `<span class="m">步骤 <b>${prog.step ?? "—"} / ${prog.step_total ?? "—"}</b></span>
      <span class="m">状态 <b>${prog.status === "running" ? "运行中" : prog.status === "done" ? "已完成" : "等待数据"}</b></span>
      <span class="m">模型 <b>${esc(meta.model || "—")}</b></span>`;
    return;
  }
  const wx = env.weather_shock ?? 0;
  const wIcon = wx < -0.15 ? "🌧" : wx < 0 ? "⛅" : "☀";
  el.innerHTML = `
    <span class="m">步骤 <b>${env.step}</b></span>
    <span class="m">日期 <b>${esc(env.t ? String(env.t).slice(0, 10) : "—")}</b></span>
    <span class="m weather">${wIcon} 天气冲击 <b>${wx >= 0 ? "+" : ""}${wx.toFixed(2)}</b></span>
    <span class="m">平均净收入 <b>${fmtInt(env.avg_net_income)}</b> 元/季</span>
    <span class="m">保险覆盖率 <b>${fmtPct(env.insurance_coverage_rate)}</b></span>
    <span class="m">平均种植 <b>${fmt1(env.avg_planted_area)}</b> 亩</span>
    <span class="m">补贴支出 <b>${fmtInt(env.total_subsidy)}</b> 元</span>`;
}

/* ---------------- 村庄场景 SVG ---------------- */
function renderVillageSVG(agents, env) {
  const W = 660, H = 380, TOP = 6;
  const n = agents.length;
  if (!n) {
    $("village").innerHTML = `<div class="placeholder">该运行暂无农户回放数据</div>`;
    return;
  }
  const cols = Math.max(1, Math.ceil(Math.sqrt(n * 1.25)));
  const rows = Math.ceil(n / cols);
  const cw = (W - 40) / cols, ch = (H - 60) / rows;

  let svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  // 背景田地网格
  for (let gx = 0; gx < 8; gx++) for (let gy = 0; gy < 5; gy++) {
    svg += `<rect x="${gx * 84 + 4}" y="${gy * 76 + 6}" width="78" height="70" rx="10"
      fill="${(gx + gy) % 2 ? "rgba(102,187,106,.035)" : "rgba(79,195,247,.028)"}"
      stroke="rgba(255,255,255,.03)" stroke-width="1"/>`;
  }

  const showLabel = n <= 16;
  agents.forEach((a, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const cx = 22 + cw * (col + 0.5), cy = TOP + 24 + ch * (row + 0.5);
    const plant = a.planted_area_mu || 0;
    const r = Math.max(12, Math.min(26, 11 + plant * 0.85));
    const cc = cropColor(a.plan);
    const fill = cc ? CROP_COLORS[cc] : "#3a4552";
    const insured = (a.insured_area_mu || 0) > 0;
    const tin = a.transfer_in_mu || 0, tout = a.transfer_out_mu || 0;
    const sel = state.selectedFarmer === a.agent_id;

    svg += `<g class="farmer-node${sel ? " selected" : ""}" data-id="${a.agent_id}">`;
    svg += `<circle class="node-ring" cx="${cx}" cy="${cy}" r="${r + 5}"
      fill="none" stroke="${insured ? "#4fc3f7" : "#33404f"}" stroke-width="2"
      ${insured ? 'style="filter: drop-shadow(0 0 6px rgba(79,195,247,.55))"' : ""}/>`;
    svg += `<circle class="node-core" cx="${cx}" cy="${cy}" r="${r}" fill="${fill}"
      fill-opacity="0.88" stroke="rgba(0,0,0,.35)" stroke-width="1"/>`;
    if (tin > 0) svg += `<path d="M${cx} ${cy - r - 12} l-4.5 7 h9 z" fill="#4fc3f7" opacity="0.92"/>`;
    if (tout > 0) svg += `<path d="M${cx} ${cy + r + 12} l-4.5 -7 h9 z" fill="#ffb74d" opacity="0.92"/>`;
    if (showLabel) svg += `<text x="${cx}" y="${cy + r + 22}" text-anchor="middle"
      font-size="9.5" fill="#8b9aab">F${a.agent_id}</text>`;
    svg += `</g>`;
  });

  // 场景内提示
  svg += `<text x="${W - 14}" y="${H - 10}" text-anchor="end" font-size="10.5" fill="#5f6f80">投保=青色描边 · 流转: ▲租入 ▼转出</text>`;
  svg += `</svg>`;

  $("village").innerHTML = svg;

  // 事件绑定
  $("village").querySelectorAll(".farmer-node").forEach((g) => {
    const id = Number(g.dataset.id);
    g.addEventListener("mouseenter", () => showFarmer(agents.find((a) => a.agent_id === id)));
    g.addEventListener("click", () => {
      state.selectedFarmer = id;
      document.querySelectorAll(".farmer-node").forEach((x) => x.classList.remove("selected"));
      g.classList.add("selected");
      showFarmer(agents.find((a) => a.agent_id === id));
    });
  });
  // 默认显示第一个农户详情
  if (agents.length) showFarmer(agents[0]);
}

function showFarmer(a) {
  if (!a) return;
  const el = $("farmer-detail");
  el.classList.add("show");
  const crops = Object.entries(a.plan || {})
    .map(([c, v]) => `<span class="crop-chip"><b>${CROP_LABELS[c] || c}</b> ${fmt1(v)} 亩</span>`).join("");
  el.innerHTML = `
    <h4>农户 F${a.agent_id} · 详情</h4>
    <div class="grid">
      <span class="k">净收入</span><span class="v">${fmtInt(a.net_income)} 元</span>
      <span class="k">毛收入</span><span class="v">${fmtInt(a.gross_revenue)} 元</span>
      <span class="k">成本</span><span class="v">${fmtInt(a.total_cost)} 元</span>
      <span class="k">补贴</span><span class="v">${fmtInt(a.subsidy_income)} 元</span>
      <span class="k">赔付</span><span class="v">${fmtInt(a.insurance_payout)} 元</span>
      <span class="k">种植面积</span><span class="v">${fmt1(a.planted_area_mu)} 亩</span>
      <span class="k">投保面积</span><span class="v">${fmt1(a.insured_area_mu)} 亩</span>
      <span class="k">租入 / 转出</span><span class="v">${fmt1(a.transfer_in_mu)} / ${fmt1(a.transfer_out_mu)} 亩</span>
    </div>
    <div class="crops">${crops || '<span class="crop-chip">未种植</span>'}</div>`;
}

/* ---------------- 折线图组件（原生 SVG 手绘） ---------------- */
function lineChart(el, cfg) {
  const W = 560, H = cfg.height || 190;
  const PAD = { l: 46, r: 14, t: 12, b: 24 };
  const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
  const series = cfg.series || [];
  let xs = [];
  series.forEach((s) => (s.pts || []).forEach((p) => { if (!xs.includes(p.x)) xs.push(p.x); }));
  xs.sort((a, b) => a - b);
  if (!xs.length) {
    el.innerHTML = `<div class="c-title">${esc(cfg.title)}</div><div style="color:var(--muted);font-size:12px;padding:8px">暂无数据</div>`;
    return;
  }
  let lo = cfg.yMin ?? Infinity, hi = cfg.yMax ?? -Infinity;
  series.forEach((s) => (s.pts || []).forEach((p) => {
    lo = Math.min(lo, p.v); hi = Math.max(hi, p.v);
    if (cfg.band) { cfg.band.forEach((b) => { lo = Math.min(lo, b(p.x)); hi = Math.max(hi, b(p.x)); }); }
  }));
  if (lo === Infinity) { lo = 0; hi = 1; }
  if (hi === lo) { hi = lo + 1; }
  const span = hi - lo;
  lo -= span * 0.08; hi += span * 0.08;

  const X = (x) => PAD.l + (xs.length === 1 ? iw / 2 : ((x - xs[0]) / (xs[xs.length - 1] - xs[0])) * iw);
  const Y = (v) => PAD.t + ih - ((v - lo) / (hi - lo)) * ih;

  let svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  // 网格 + y 轴刻度（4 条）
  for (let g = 0; g <= 4; g++) {
    const y = PAD.t + (ih / 4) * g;
    const val = hi - ((hi - lo) / 4) * g;
    svg += `<line class="grid-line" x1="${PAD.l}" y1="${y}" x2="${W - PAD.r}" y2="${y}"/>`;
    svg += `<text class="axis-label" x="${PAD.l - 6}" y="${y + 3}" text-anchor="end">${cfg.fmt ? cfg.fmt(val) : val.toFixed(1)}</text>`;
  }
  // x 轴刻度
  xs.forEach((x) => {
    svg += `<text class="axis-label" x="${X(x)}" y="${H - 8}" text-anchor="middle">${x}</text>`;
  });
  // 政策分界竖线
  if (cfg.phaseStep != null && xs.length > 1) {
    svg += `<line class="phase-line" x1="${X(cfg.phaseStep)}" y1="${PAD.t}" x2="${X(cfg.phaseStep)}" y2="${H - PAD.b}"/>`;
  }
  // 置信带（均值±sd）
  if (cfg.band) {
    const band = cfg.band;
    const xs2 = xs.filter((x) => band.lo(x) != null);
    const ptsLo = xs2.map((x) => `${X(x)},${Y(band.lo(x))}`).join(" ");
    const ptsHi = xs2.slice().reverse().map((x) => `${X(x)},${Y(band.hi(x))}`).join(" ");
    svg += `<polygon class="series-band" points="${ptsLo} ${ptsHi}"/>`;
  }
  // 系列折线
  series.forEach((s) => {
    const pts = (s.pts || []).map((p) => `${X(p.x)},${Y(p.v)}`).join(" ");
    svg += `<polyline class="series-line" points="${pts}" stroke="${s.color}"/>`;
    (s.pts || []).forEach((p) => {
      svg += `<circle class="series-dot" cx="${X(p.x)}" cy="${Y(p.v)}" r="2.6" stroke="${s.color}"/>`;
    });
  });
  svg += `</svg>`;

  el.innerHTML = `<div class="c-title">${esc(cfg.title)}</div>
    <div class="legend-inline">${series.map((s) =>
      `<span class="lg"><span class="sw" style="background:${s.color}"></span>${esc(s.name)}</span>`).join("")}
      ${cfg.phaseStep != null ? `<span class="lg"><span class="sw" style="background:var(--warn)"></span>政策分界</span>` : ""}
    </div>` + svg;
}

/* ---------------- 图表渲染 ---------------- */
function renderCharts() {
  const rd = state.runData;
  if (!rd) return;
  const meta = rd.run.meta || {};
  const ts = rd.ts.series || [];
  const ag = rd.ag.series || [];
  const bs = meta.baseline_steps ?? 8;
  $("chart-sub").textContent = `情景 ${meta.scenario_key} · 重复 #${rd.run.repeat} · 基线 ${bs} 季`;
  const fmt = (v) => (Math.abs(v) >= 10000 ? (v / 10000).toFixed(1) + "w" : Math.round(v).toLocaleString());

  // 1) 净收入：农户均值 ± 离散度带
  if (ag.length) {
    const band = {
      lo: (x) => { const p = ag.find((r) => r.step === x); return p ? p.avg_net - p.sd_net : null; },
      hi: (x) => { const p = ag.find((r) => r.step === x); return p ? p.avg_net + p.sd_net : null; },
    };
    lineChart($("chart-income"), {
      title: "农户家庭净收入（均值 ± 农户间标准差，元/季）",
      height: 200, phaseStep: bs, band,
      series: [{ name: "平均净收入", color: "#66bb6a", pts: ag.map((r) => ({ x: r.step, v: r.avg_net })) }],
      fmt,
    });
  } else {
    $("chart-income").innerHTML = `<div class="c-title">农户家庭净收入</div><div style="color:var(--muted);font-size:12px;padding:8px">暂无数据</div>`;
  }

  // 2) 保险覆盖率
  lineChart($("chart-coverage"), {
    title: "全村保险覆盖率（投保/种植面积均值）",
    height: 150, phaseStep: bs,
    series: [{ name: "覆盖率", color: "#4fc3f7", pts: ts.map((r) => ({ x: r.step, v: r.insurance_coverage_rate })) }],
    fmt: (v) => (v * 100).toFixed(0) + "%",
  });

  // 3) 平均种植面积
  lineChart($("chart-planted"), {
    title: "平均种植面积（亩）",
    height: 150, phaseStep: bs,
    series: [{ name: "种植面积", color: "#f2a03d", pts: ts.map((r) => ({ x: r.step, v: r.avg_planted_area })) }],
    fmt: (v) => v.toFixed(1),
  });

  // 4) 全村补贴支出
  lineChart($("chart-subsidy"), {
    title: "全村补贴支出（元/季）",
    height: 150, phaseStep: bs,
    series: [{ name: "补贴支出", color: "#b39ddb", pts: ts.map((r) => ({ x: r.step, v: r.total_subsidy })) }],
    fmt,
  });
}

/* ---------------- 场景渲染 ---------------- */
function renderScene() {
  const rd = state.runData;
  if (!rd) return;
  renderSceneMeta(rd.run);
  const st = rd.run.state;
  if (st && st.agents && st.agents.length) {
    renderVillageSVG(st.agents, st.env);
  } else {
    $("village").innerHTML = `<div class="placeholder">该运行尚无回放数据（实验可能刚启动）</div>`;
  }
  renderLegend();
}

function renderLegend() {
  const lg = Object.entries(CROP_COLORS)
    .map(([c, col]) => `<span class="lg"><span class="sw" style="background:${col}"></span>${CROP_LABELS[c]}</span>`)
    .join("");
  $("legend").innerHTML = lg + `
    <span class="lg"><span class="sw" style="background:transparent;border:2px solid #4fc3f7"></span>投保</span>
    <span class="lg"><span class="sw" style="background:transparent;border:2px solid #33404f"></span>未投保</span>
    <span class="lg"><span style="color:#4fc3f7">▲</span>租入</span>
    <span class="lg"><span style="color:#ffb74d">▼</span>转出</span>`;
}

/* ---------------- 主循环 ---------------- */
async function refreshOverview() {
  try {
    state.overview = await api("/api/overview");
    if (!state.scenarioDefs) state.scenarioDefs = await api("/api/scenarios");
    setConn(true);
    renderTopStats(state.overview);
    renderCards(state.overview);
    renderTable(state.overview);
    // 首次无选择 → 默认选中第一个有数据的情景
    if (!state.selected) {
      const first = state.overview.scenarios.find((s) => s.total > 0);
      if (first) selectScenario(first.scenario_key);
    } else {
      await refreshRun(false);
    }
  } catch (e) {
    setConn(false);
    console.warn("overview failed", e);
  }
}

setInterval(refreshOverview, REFRESH_MS);
refreshOverview();
