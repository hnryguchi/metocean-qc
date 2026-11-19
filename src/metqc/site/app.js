// metocean-qc dashboard (PT / EN). Reads stations.json and <id>/series.json produced by `metqc site`.
const FLAG_COLORS = { good: "#2da44e", suspect: "#f5a50a", fail: "#e8231c", not_evaluated: "#8c959f", missing: "#8c959f" };
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const dark = () => true; // brand theme is always dark
const UNITS = { degC: "°C", degT: "°", sec: "s" };

const I18N = {
  pt: {
    title: "Controle de qualidade automático em boias oceânicas reais",
    lede: "Todos os dias, os dados mais recentes de três boias da NOAA passam por testes determinísticos no padrão QARTOD. Cada valor recebe um flag; valores próximos viram eventos para revisão.",
    lastRecord: "Último registro:", rebuilt: "atualizado diariamente via GitHub Actions",
    kpiRecords: "registros analisados (últimos ~45 dias)", kpiFlagged: "valores sinalizados (suspeito ou falha)",
    kpiEvents: "eventos para revisão",
    buoysTitle: "Boias", buoysHint: "Situação nos últimos 7 dias. Clique em uma boia para ver os dados.",
    noAlerts: "Sem alertas em 7 dias", alerts: (n) => `${n} evento${n === 1 ? "" : "s"} em 7 dias`,
    chartTitle: "Série temporal", chartHint: "Valores dos últimos ~45 dias. Pontos marcados foram sinalizados pelos testes; faixas sombreadas são eventos desta variável e lacunas de transmissão. Arraste o seletor para dar zoom.",
    eventsTitle: "Eventos", thVar: "Variável", thStart: "Início", thEnd: "Fim", thTests: "Testes", thValues: "Valores", thFlag: "Flag",
    noEvents: "Nenhum evento no período.",
    testsTitle: "Testes aplicados", testsHint: "Versões simplificadas das famílias de testes do QARTOD (IOOS). Limites em src/metqc/config.py.",
    tests: {
      gross_range: ["Faixa (gross range)", "Fora dos limites físicos: falha. Fora dos limites climatológicos: suspeito."],
      spike: ["Pico (spike)", "Desvio grande em relação à média dos vizinhos; só o máximo local é sinalizado."],
      flat_line: ["Linha plana (flat line)", "Mesmo valor repetido por N horas, com limites ajustados à resolução do sensor."],
      gap: ["Lacuna (gap)", "Intervalo entre registros consecutivos maior que 3 horas."],
    },
    flags: { good: "bom", suspect: "suspeito", fail: "falha", not_evaluated: "não avaliado", missing: "ausente" },
    vars: { PRES: "Pressão", WTMP: "Temp. da água", ATMP: "Temp. do ar", DEWP: "Ponto de orvalho", WSPD: "Vento", GST: "Rajada", WVHT: "Altura de onda", DPD: "Período de onda", "*": "Estação (lacuna)" },
    period: "Período", records: "Registros", station: "Estação NDBC", latest: "Leituras mais recentes",
    aboutTitle: "Sobre os dados",
    aboutSource: "<b>Fonte:</b> NOAA National Data Buoy Center (NDBC), dados meteorológicos padrão em tempo real (~45 dias, registros de 10 min). Domínio público.",
    aboutFlags: "<b>Flags:</b> esquema QARTOD: 1 bom, 2 não avaliado, 3 suspeito, 4 falha, 9 ausente. Não é uma implementação QARTOD certificada.",
    aboutLlm: "<b>LLM:</b> esta execução diária não chama nenhum modelo. A segunda opinião por LLM é opcional (<code>--review claude</code>) e nunca altera flags.",
    aboutCode: "<b>Código:</b> <a href=\"https://github.com/hnryguchi/metocean-qc\">github.com/hnryguchi/metocean-qc</a> · Henry Noguchi.",
    built: (d) => `Gerado em ${d} UTC.`, loadError: "Não foi possível carregar os dados:",
    hoverFlag: "sinalizado", dateFmt: "%d/%m %H:%M",
    hudWave: "altura de onda", hudWind: "vento", hudPres: "pressão", hudNow: "mar agora", hudReplay: "replay",
    replayHint: "Reproduza os últimos ~45 dias: o mar 3D segue as ondas e o vento medidos.",
    flagToast: (v, test, f) => `QC: ${v} · ${test} → ${f}`,
  },
  en: {
    title: "Automatic quality control on real ocean buoys",
    lede: "Every day, the latest data from three NOAA buoys runs through deterministic QARTOD-style tests. Each value gets a flag; nearby flags are grouped into events for review.",
    lastRecord: "Last record:", rebuilt: "rebuilt daily by GitHub Actions",
    kpiRecords: "records analysed (last ~45 days)", kpiFlagged: "values flagged (suspect or fail)", kpiEvents: "events for review",
    buoysTitle: "Buoys", buoysHint: "Status over the last 7 days. Click a buoy to explore its data.",
    noAlerts: "No alerts in 7 days", alerts: (n) => `${n} event${n === 1 ? "" : "s"} in 7 days`,
    chartTitle: "Time series", chartHint: "Values over the last ~45 days. Marked points were flagged by the tests; shaded bands are events for this variable and transmission gaps. Drag the slider to zoom.",
    eventsTitle: "Events", thVar: "Variable", thStart: "Start", thEnd: "End", thTests: "Tests", thValues: "Values", thFlag: "Flag",
    noEvents: "No events in this period.",
    testsTitle: "Tests", testsHint: "Simplified versions of the IOOS QARTOD test families. Limits in src/metqc/config.py.",
    tests: {
      gross_range: ["Gross range", "Outside physical limits: fail. Outside climatological limits: suspect."],
      spike: ["Spike", "Large deviation from the neighbour mean; only the local maximum is flagged."],
      flat_line: ["Flat line", "Same value repeated for N hours, with limits tuned to sensor resolution."],
      gap: ["Gap", "More than 3 hours between consecutive records."],
    },
    flags: { good: "good", suspect: "suspect", fail: "fail", not_evaluated: "not evaluated", missing: "missing" },
    vars: { PRES: "Pressure", WTMP: "Water temp.", ATMP: "Air temp.", DEWP: "Dew point", WSPD: "Wind", GST: "Gust", WVHT: "Wave height", DPD: "Wave period", "*": "Station (gap)" },
    period: "Period", records: "Records", station: "NDBC station", latest: "Latest readings",
    aboutTitle: "About the data",
    aboutSource: "<b>Source:</b> NOAA National Data Buoy Center (NDBC), realtime standard meteorological data (~45 days, 10-minute records). Public domain.",
    aboutFlags: "<b>Flags:</b> QARTOD scheme: 1 good, 2 not evaluated, 3 suspect, 4 fail, 9 missing. Not a certified QARTOD implementation.",
    aboutLlm: "<b>LLM:</b> this daily run calls no model. The LLM second opinion is optional (<code>--review claude</code>) and never changes flags.",
    aboutCode: "<b>Code:</b> <a href=\"https://github.com/hnryguchi/metocean-qc\">github.com/hnryguchi/metocean-qc</a> · Henry Noguchi.",
    built: (d) => `Built ${d} UTC.`, loadError: "Could not load data:",
    hoverFlag: "flagged", dateFmt: "%b %d %H:%M",
    hudWave: "wave height", hudWind: "wind", hudPres: "pressure", hudNow: "sea now", hudReplay: "replay",
    replayHint: "Replay the last ~45 days: the 3D sea follows the measured waves and wind.",
    flagToast: (v, test, f) => `QC: ${v} · ${test} → ${f}`,
  },
};

let DATA = null, current = null, currentVar = null, map = null;
const SERIES = {}, markers = {};
let lang = (() => {
  try { const s = localStorage.getItem("mq-lang"); if (s === "pt" || s === "en") return s; } catch (e) { /* storage blocked */ }
  return (navigator.language || "pt").toLowerCase().startsWith("en") ? "en" : "pt";
})();
const t = (k) => I18N[lang][k];
const $ = (id) => document.getElementById(id);
const locale = () => (lang === "pt" ? "pt-BR" : "en-US");
const fmt = (n, d = 1) => Number(n).toLocaleString(locale(), { minimumFractionDigits: d, maximumFractionDigits: d });
const unit = (u) => UNITS[u] || u;
const fmtTime = (iso) => new Date(iso).toLocaleString(locale(), { timeZone: "UTC", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) + " UTC";
const varLabel = (v) => t("vars")[v] || v;
const flagChip = (f) => `<span class="chip" style="background:${FLAG_COLORS[f]};color:${f === "fail" ? "#fff" : "#111"}">${t("flags")[f] || f}</span>`;
const testLabel = (k) => (t("tests")[k] ? t("tests")[k][0] : k);

function countUp(el, target) {
  if (reduceMotion) { el.textContent = fmt(target, 0); return; }
  const t0 = performance.now(), dur = 1400;
  const step = (now) => {
    const p = Math.min(1, (now - t0) / dur);
    el.textContent = fmt(target * (1 - Math.pow(1 - p, 3)), 0);
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function plotLayout(extra = {}) {
  const fg = "#c6e2f3", grid = "#16324f";
  return Object.assign({
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter, system-ui, sans-serif", color: fg, size: 12 },
    margin: { l: 56, r: 16, t: 16, b: 40 }, xaxis: { gridcolor: grid }, yaxis: { gridcolor: grid, zeroline: false },
    hovermode: "closest", showlegend: false, separators: lang === "pt" ? ",." : ".,",
  }, extra);
}

function applyStaticText() {
  document.documentElement.lang = lang === "pt" ? "pt-BR" : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll(".lang button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  $("tests").innerHTML = Object.values(t("tests")).map(([n, d]) => `<div class="flag-card"><b>${n}</b>${d}</div>`).join("");
  $("legend").innerHTML = ["good", "suspect", "fail"].map((f) =>
    `<span><span class="fdot" style="background:${FLAG_COLORS[f]}"></span>${t("flags")[f]}</span>`).join("") +
    `<span><span class="swatch" style="background:rgba(245,165,10,.25)"></span>${t("eventsTitle")}</span>` +
    `<span><span class="swatch" style="background:rgba(140,149,159,.3)"></span>${testLabel("gap")}</span>`;
}

function renderKpis(animate) {
  const st = DATA.stations;
  const sum = (k) => st.reduce((a, s) => a + s[k], 0);
  const set = (el, v) => { if (animate) countUp(el, v); else el.textContent = fmt(v, 0); };
  set($("kpi-records"), sum("records")); set($("kpi-flagged"), sum("flagged")); set($("kpi-events"), sum("events"));
  const last = st.map((s) => s.period[1]).sort().pop();
  $("last-date").textContent = fmtTime(last);
  $("generated").textContent = t("built")(DATA.generated_utc.replace("T", " "));
}

function renderCards() {
  $("cards").innerHTML = DATA.stations.map((s, i) => {
    const ok = s.events_7d === 0;
    const color = ok ? FLAG_COLORS.good : FLAG_COLORS.suspect;
    const w = s.latest.WTMP, p = s.latest.PRES;
    return `<button class="card ${current && current.id === s.id ? "active" : ""}" data-id="${s.id}" style="animation-delay:${i * 70}ms">
      <div class="name">${s.id} · ${s.name}</div>
      <div class="lvl" style="color:${color}"><span class="dot ${ok ? "" : "pulse"}" style="background:${color}"></span>
        <span style="color:var(--fg)">${ok ? t("noAlerts") : t("alerts")(s.events_7d)}</span></div>
      <div class="meta">${w ? `${varLabel("WTMP")} ${fmt(w.value)} °C` : ""}${w && p ? " · " : ""}${p ? `${fmt(p.value)} hPa` : ""}</div>
    </button>`;
  }).join("");
  document.querySelectorAll(".card").forEach((c) => c.addEventListener("click", () => select(c.dataset.id)));
}

function renderMap() {
  map = L.map("map", { scrollWheelZoom: false }).setView([36, -95], 3);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 9, subdomains: "abcd", attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
  }).addTo(map);
  DATA.stations.forEach((s) => {
    const m = L.circleMarker([s.lat, s.lon], {
      radius: 9, color: "#e8f4fd", weight: 1.5, fillColor: s.events_7d ? FLAG_COLORS.suspect : FLAG_COLORS.good, fillOpacity: 0.95,
    }).addTo(map);
    m.on("click", () => select(s.id));
    markers[s.id] = m;
  });
  map.fitBounds(DATA.stations.map((s) => [s.lat, s.lon]), { padding: [40, 40] });
  updateMapTooltips();
}

function updateMapTooltips() {
  DATA.stations.forEach((s) => markers[s.id].unbindTooltip().bindTooltip(`${s.id} · ${s.name}: ${s.events_7d ? t("alerts")(s.events_7d) : t("noAlerts")}`));
}

function renderFacts(s) {
  const readings = Object.entries(s.latest).map(([v, r]) => `
    <div class="reading"><div class="k"><span class="fdot" style="background:${FLAG_COLORS[r.flag]}" title="${t("flags")[r.flag]}"></span>${varLabel(v)}</div>
      <div class="v">${fmt(r.value, v === "WSPD" || v === "GST" ? 1 : v === "DPD" ? 0 : 1)}<span class="u">${unit(r.unit)}</span></div></div>`).join("");
  const ns = s.lat >= 0 ? "N" : "S", ew = s.lon >= 0 ? "E" : "W";
  $("facts").innerHTML = `
    <h3>${s.id} · ${s.name}</h3>
    <div class="coords">${Math.abs(s.lat).toFixed(2)}°${ns}, ${Math.abs(s.lon).toFixed(2)}°${ew} · <a href="${s.url}">${t("station")}</a></div>
    <dl>
      <dt>${t("period")}</dt><dd>${fmtTime(s.period[0])} – ${fmtTime(s.period[1])}</dd>
      <dt>${t("records")}</dt><dd>${s.records.toLocaleString(locale())}</dd>
    </dl>
    <div class="coords" style="margin:14px 0 4px">${t("latest")}</div>
    <div class="readings">${readings}</div>`;
}

function defaultVar(ser) {
  const evs = ser.events.filter((e) => e.variable !== "*" && ser.variables[e.variable]);
  if (evs.length) return evs[evs.length - 1].variable;
  return ser.variables.PRES ? "PRES" : Object.keys(ser.variables)[0];
}

function renderTabs(ser) {
  const count = (v) => ser.variables[v].flagged.length;
  $("tabs").innerHTML = Object.keys(ser.variables).map((v) =>
    `<button type="button" data-var="${v}" aria-pressed="${v === currentVar}">${varLabel(v)}${count(v) ? `<span class="n">${count(v)}</span>` : ""}</button>`).join("");
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => { currentVar = b.dataset.var; renderTabs(ser); renderChart(ser); }));
}

function renderChart(ser) {
  const v = ser.variables[currentVar], t0 = Date.parse(ser.t0);
  const x = ser.minutes.map((m) => new Date(t0 + m * 60000).toISOString());
  const grid = "#16324f";
  const u = unit(v.unit);
  // Variables are sampled at different rates (e.g. waves hourly, wind every 10 min): plot only measured points,
  // and break the line only where the station had a real gap (> 3 h between measurements).
  const lx = [], ly = [];
  let prev = null;
  v.values.forEach((val, i) => {
    if (val === null) return;
    if (prev !== null && ser.minutes[i] - ser.minutes[prev] > 180) { lx.push(null); ly.push(null); }
    lx.push(x[i]); ly.push(val); prev = i;
  });
  const line = {
    x: lx, y: ly, type: "scatter", mode: "lines", connectgaps: false, line: { color: "#38bdf8", width: 1.4 },
    hovertemplate: `%{x|${t("dateFmt")}} UTC<br>%{y:.2f} ${u}<extra></extra>`,
  };
  const pts = (code, name) => {
    const sel = v.flagged.filter(([, f]) => f === code);
    return {
      x: sel.map(([i]) => x[i]), y: sel.map(([i]) => v.values[i]), type: "scatter", mode: "markers",
      marker: { size: 10, color: "rgba(0,0,0,0)", line: { color: FLAG_COLORS[name], width: 2.5 } },
      hovertemplate: `%{x|${t("dateFmt")}} UTC<br>%{y:.2f} ${u} · ${t("flags")[name]}<extra></extra>`,
    };
  };
  const pad = 30 * 60000;
  const shapes = ser.events.filter((e) => e.variable === currentVar || e.variable === "*").map((e) => ({
    type: "rect", xref: "x", yref: "paper", y0: 0, y1: 1, line: { width: 0 }, layer: "below",
    x0: new Date(Date.parse(e.start) - pad).toISOString(), x1: new Date(Date.parse(e.end) + pad).toISOString(),
    fillcolor: e.variable === "*" ? "rgba(140,149,159,.3)" : "rgba(245,165,10,.25)",
  }));
  baseShapes = shapes;
  const layout = plotLayout({
    shapes: shapes.concat(cursorShape()), yaxis: { title: `${varLabel(currentVar)} (${u})`, gridcolor: grid, zeroline: false },
    xaxis: { type: "date", gridcolor: grid, rangeslider: { visible: true, thickness: 0.08 } },
  });
  $("chart-title").textContent = `${t("chartTitle")}: ${current.id} · ${current.name}`;
  Plotly.react("chart", [line, pts(3, "suspect"), pts(4, "fail")], layout, { responsive: true, displaylogo: false });
}

function renderEvents(ser) {
  $("events-title").textContent = `${t("eventsTitle")}: ${current.id} · ${current.name}`;
  const rows = ser.events.slice().reverse().map((e) => `<tr>
    <td>${varLabel(e.variable)}</td><td>${fmtTime(e.start)}</td><td>${fmtTime(e.end)}</td>
    <td>${e.tests.map(testLabel).join(", ")}</td><td>${e.n}</td><td>${flagChip(e.worst)}</td></tr>`);
  document.querySelector("#events tbody").innerHTML = rows.join("") || `<tr><td colspan="6">${t("noEvents")}</td></tr>`;
}

async function loadSeries(id) {
  if (!SERIES[id]) SERIES[id] = await (await fetch(`${id}/series.json`)).json();
  return SERIES[id];
}

async function select(id, { animate = true, keepVar = false } = {}) {
  current = DATA.stations.find((s) => s.id === id);
  document.querySelectorAll(".card").forEach((c) => c.classList.toggle("active", c.dataset.id === id));
  Object.entries(markers).forEach(([k, m]) => m.setStyle({ weight: k === id ? 4 : 1.5, radius: k === id ? 12 : 9 }));
  if (map && animate) map.flyTo([current.lat, current.lon], 5, { duration: reduceMotion ? 0 : 0.8 });
  renderFacts(current);
  const ser = await loadSeries(id);
  if (!keepVar || !ser.variables[currentVar]) currentVar = defaultVar(ser);
  renderTabs(ser); renderChart(ser); renderEvents(ser);
  history.replaceState(null, "", `#${id}`);
  stopReplay(); $("scrub").value = 1000; setTime(ser.minutes.length - 1, { force: true });
}

function setLang(next) {
  if (next === lang) return;
  lang = next;
  try { localStorage.setItem("mq-lang", lang); } catch (e) { /* storage blocked */ }
  document.body.classList.add("switching");
  setTimeout(() => {
    applyStaticText();
    if (DATA) { renderKpis(false); renderCards(); updateMapTooltips(); select(current.id, { animate: false, keepVar: true }); }
    document.body.classList.remove("switching");
  }, reduceMotion ? 0 : 180);
}

// ---- live 3D sea + replay -------------------------------------------------------------------
const ocean = window.Ocean3D ? Ocean3D.mount(document.querySelector(".hero")) : { set() {} };
let baseShapes = [], cursorIdx = null, playing = false, lastRelayout = 0, lastFlagCheck = null, flagTimer = null;

function nearest(ser, v, i, back = 18) {           // latest measured value at or before i (waves are hourly)
  const col = ser.variables[v]; if (!col) return null;
  for (let k = i; k >= Math.max(0, i - back); k--) if (col.values[k] !== null) return col.values[k];
  return null;
}
function cursorShape() {
  const ser = current && SERIES[current.id];
  if (!ser || cursorIdx === null) return [];
  const x = new Date(Date.parse(ser.t0) + ser.minutes[cursorIdx] * 60000).toISOString();
  return [{ type: "line", xref: "x", yref: "paper", x0: x, x1: x, y0: 0, y1: 1, line: { color: "#2dd4bf", width: 2 } }];
}
function showFlag(ser, i0, i1) {
  for (const [v, col] of Object.entries(ser.variables)) {
    const hit = col.flagged.find(([i]) => i > i0 && i <= i1);
    if (!hit) continue;
    const when = Date.parse(ser.t0) + ser.minutes[hit[0]] * 60000, slack = 60 * 60000;
    const ev = ser.events.find((e) => e.variable === v && Date.parse(e.start) - slack <= when && when <= Date.parse(e.end) + slack);
    const f = hit[1] === 4 ? "fail" : "suspect", el = $("hud-flag");
    el.textContent = t("flagToast")(varLabel(v), ev ? ev.tests.map(testLabel).join(", ") : "QC", t("flags")[f]);
    el.className = `hud-flag ${f === "fail" ? "fail" : ""}`; el.hidden = false;
    clearTimeout(flagTimer); flagTimer = setTimeout(() => { el.hidden = true; }, 2600);
    return;
  }
}
function setTime(i, { force = false } = {}) {
  const ser = current && SERIES[current.id]; if (!ser) return;
  i = Math.max(0, Math.min(ser.minutes.length - 1, i));
  if (lastFlagCheck !== null && i > lastFlagCheck && !force) showFlag(ser, lastFlagCheck, i);
  lastFlagCheck = i; cursorIdx = i;
  const wave = nearest(ser, "WVHT", i), wind = nearest(ser, "WSPD", i, 6), pres = nearest(ser, "PRES", i, 6);
  const live = i === ser.minutes.length - 1;
  $("hud-title").textContent = `${live ? t("hudNow") : t("hudReplay")} · ${current.id} ${current.name}`;
  $("hud-time").textContent = fmtTime(new Date(Date.parse(ser.t0) + ser.minutes[i] * 60000).toISOString());
  $("hud-wave").textContent = wave === null ? "–" : `${fmt(wave)} m`;
  $("hud-wind").textContent = wind === null ? "–" : `${fmt(wind)} m/s`;
  $("hud-pres").textContent = pres === null ? "–" : fmt(pres, 0);
  ocean.set({ waveHeight: wave === null ? 1 : wave, wind: wind === null ? 6 : wind });
  const now = performance.now();
  if (force || now - lastRelayout > 120) { lastRelayout = now; Plotly.relayout("chart", { shapes: baseShapes.concat(cursorShape()) }); }
}
function stopReplay() { playing = false; $("play").classList.remove("on"); $("play").setAttribute("aria-label", "Play"); }
function startReplay() {
  const ser = current && SERIES[current.id]; if (!ser) return;
  if (Number($("scrub").value) >= 1000) { $("scrub").value = 0; lastFlagCheck = 0; }
  playing = true; $("play").classList.add("on"); $("play").setAttribute("aria-label", "Pause");
  let prev = performance.now();
  const tick = (now) => {
    if (!playing) return;
    const v = Math.min(1000, Number($("scrub").value) + (now - prev) / 30000 * 1000);   // whole period in ~30 s
    prev = now; $("scrub").value = v;
    setTime(Math.round((v / 1000) * (ser.minutes.length - 1)));
    if (v >= 1000) { stopReplay(); setTime(ser.minutes.length - 1, { force: true }); return; }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
$("play").addEventListener("click", () => (playing ? stopReplay() : startReplay()));
$("scrub").addEventListener("input", () => {
  const ser = current && SERIES[current.id]; if (!ser) return;
  stopReplay(); lastFlagCheck = null;
  setTime(Math.round((Number($("scrub").value) / 1000) * (ser.minutes.length - 1)));
});

document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));
applyStaticText();

fetch("stations.json").then((r) => r.json()).then((d) => {
  DATA = d;
  if (!d.stations.length) throw new Error("no stations");
  renderKpis(true); renderCards(); renderMap();
  const fromHash = location.hash.slice(1);
  const initial = d.stations.find((s) => s.id === fromHash) || d.stations.reduce((a, b) => (b.events_7d > a.events_7d ? b : a));
  select(initial.id);
}).catch((e) => {
  document.querySelector("main").insertAdjacentHTML("afterbegin", `<p>${t("loadError")} ${e}</p>`);
});
