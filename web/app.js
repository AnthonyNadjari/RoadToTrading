"use strict";

const ROLE_LABELS = {
  TRADING: "Trading",
  QUANT_TRADING: "Quant Trading",
  QUANT_RESEARCH: "Quant Research",
  STRUCTURING: "Structuring",
  STRATS: "Strats",
  QUANT_DEV: "Quant Dev",
};
const TYPE_LABELS = { HF: "Hedge Fund", MM: "Market Maker", PROP: "Prop", QUANT: "Quant", BANK: "Bank" };

let JOBS = [], CHANGES = [], META = {};

async function loadJSON(path, fallback) {
  try {
    const r = await fetch(path + "?_=" + Date.now());
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch (e) { return fallback; }
}

function uniqueSorted(arr) { return [...new Set(arr)].sort(); }

function fillSelect(id, values, labels) {
  const sel = document.getElementById(id);
  sel.innerHTML = "";
  values.forEach((v) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = labels && labels[v] ? labels[v] : v;
    sel.appendChild(o);
  });
}

function selectedValues(id) {
  return [...document.getElementById(id).selectedOptions].map((o) => o.value);
}

function initFilters() {
  fillSelect("f-role", Object.keys(ROLE_LABELS).filter(r => JOBS.some(j => j.role === r)), ROLE_LABELS);
  fillSelect("f-type", uniqueSorted(JOBS.map(j => j.employer_type)), TYPE_LABELS);
  fillSelect("f-seniority", uniqueSorted(JOBS.map(j => j.seniority).filter(Boolean)));
  fillSelect("f-asset", uniqueSorted(JOBS.flatMap(j => j.assets || [])));
  fillSelect("f-source", uniqueSorted(JOBS.flatMap(j => j.sources || [])));
}

function matches(job) {
  const q = document.getElementById("q").value.trim().toLowerCase();
  if (q) {
    const blob = (job.title + " " + job.employer + " " + (job.locations || []).join(" ")).toLowerCase();
    if (!blob.includes(q)) return false;
  }
  const roles = selectedValues("f-role"); if (roles.length && !roles.includes(job.role)) return false;
  const types = selectedValues("f-type"); if (types.length && !types.includes(job.employer_type)) return false;
  const sen = selectedValues("f-seniority"); if (sen.length && !sen.includes(job.seniority)) return false;
  const assets = selectedValues("f-asset");
  if (assets.length && !(job.assets || []).some(a => assets.includes(a))) return false;
  const sources = selectedValues("f-source");
  if (sources.length && !(job.sources || []).some(s => sources.includes(s))) return false;
  if (document.getElementById("f-target").checked && !job.target_geo) return false;
  if (document.getElementById("f-open").checked && job.status === "closed") return false;
  return true;
}

function sortJobs(list) {
  const key = document.getElementById("sort").value;
  const c = [...list];
  if (key === "employer") c.sort((a, b) => a.employer.localeCompare(b.employer));
  else c.sort((a, b) => (b[key] || "").localeCompare(a[key] || ""));
  return c;
}

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

function renderJobs() {
  const list = sortJobs(JOBS.filter(matches));
  document.getElementById("result-count").textContent =
    `${list.length} offre(s) affichée(s) sur ${JOBS.length} en base`;
  const box = document.getElementById("jobs");
  box.innerHTML = "";
  list.slice(0, 800).forEach((j) => {
    const card = el("div", "card");
    const row1 = el("div", "row1");
    row1.appendChild(el("div", "title", j.title));
    row1.appendChild(el("div", "employer", j.employer));
    card.appendChild(row1);
    card.appendChild(el("div", "meta",
      `${(j.locations || []).join(" · ") || "—"} · vu ${fmtDate(j.last_seen)}`));
    const chips = el("div", "chips");
    chips.appendChild(el("span", "chip role", ROLE_LABELS[j.role] || j.role));
    if (j.seniority) chips.appendChild(el("span", "chip", j.seniority));
    (j.assets || []).forEach(a => chips.appendChild(el("span", "chip", a)));
    if (j.target_geo) chips.appendChild(el("span", "chip geo", "ville cible"));
    if (j.status === "closed") chips.appendChild(el("span", "chip closed", "fermée"));
    else if (j.status === "stale") chips.appendChild(el("span", "chip stale", "à confirmer"));
    card.appendChild(chips);
    const sl = el("div", "sources-line");
    (j.source_links || []).forEach((s) => {
      const a = el("a"); a.href = s.url; a.target = "_blank"; a.rel = "noopener";
      a.textContent = `${s.source} ↗`;
      sl.appendChild(a);
    });
    card.appendChild(sl);
    box.appendChild(card);
  });
}

function renderActivity() {
  const kinds = selectedValues("a-kind");
  const box = document.getElementById("activity");
  box.innerHTML = "";
  CHANGES.filter(c => !kinds.length || kinds.includes(c.kind)).slice(0, 600).forEach((c) => {
    const ev = el("div", "ev");
    ev.appendChild(el("span", "when", fmtDate(c.ts)));
    ev.appendChild(el("span", "kind " + c.kind, c.kind));
    ev.appendChild(el("span", "", `<b>${c.employer_name}</b> — ${c.title} `
      + `<span style="color:var(--muted)">[${ROLE_LABELS[c.role_family] || c.role_family} · ${(c.locations || []).join(", ")}]</span>`));
    box.appendChild(ev);
  });
}

function renderSources() {
  const emps = (META.employers || []).slice().sort((a, b) => (b.count || 0) - (a.count || 0));
  const rows = emps.map(e => `
    <tr>
      <td><span class="dot ${e.health}"></span>${e.name}</td>
      <td>${TYPE_LABELS[e.type] || e.type}</td>
      <td>${e.ats}</td>
      <td>${e.status}</td>
      <td>${e.count}</td>
      <td>${e.consecutive_failures > 1 ? '⚠️ ' + e.consecutive_failures : (e.consecutive_failures || 0)}</td>
      <td><a href="${e.careers_url}" target="_blank" rel="noopener">careers ↗</a></td>
    </tr>`).join("");
  document.getElementById("sources").innerHTML = `
    <table>
      <thead><tr><th>Employeur</th><th>Type</th><th>ATS</th><th>État</th>
        <th>Offres</th><th>Échecs consécutifs</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderStats() {
  const c = META.counts || {};
  document.getElementById("stats").innerHTML = `
    <div class="stat"><b>${c.jobs_in_scope_open ?? "—"}</b><span>offres in-scope</span></div>
    <div class="stat"><b>${c.employers_crawled_ok ?? "—"}/${c.employers_total ?? "—"}</b><span>sources OK</span></div>
    <div class="stat"><b>${(META.events_last_run || {}).NEW || 0}</b><span>nouvelles (dernier run)</span></div>`;
  document.getElementById("footer-meta").textContent =
    "Dernier crawl : " + (META.generated_at ? fmtDate(META.generated_at) : "—");
}

function fmtDate(s) {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d)) return s;
  return d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function wireTabs() {
  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      document.getElementById("tab-" + t.dataset.tab).classList.add("active");
    });
  });
}

function wireFilters() {
  ["q", "f-role", "f-type", "f-seniority", "f-asset", "f-source", "f-target", "f-open", "sort"]
    .forEach(id => document.getElementById(id).addEventListener("input", renderJobs));
  document.getElementById("a-kind").addEventListener("input", renderActivity);
  document.getElementById("reset").addEventListener("click", () => {
    document.getElementById("q").value = "";
    ["f-role", "f-type", "f-seniority", "f-asset", "f-source"].forEach(id =>
      [...document.getElementById(id).options].forEach(o => o.selected = false));
    document.getElementById("f-target").checked = false;
    document.getElementById("f-open").checked = true;
    renderJobs();
  });
}

async function main() {
  [JOBS, CHANGES, META] = await Promise.all([
    loadJSON("data/jobs.json", []),
    loadJSON("data/changes.json", []),
    loadJSON("data/meta.json", {}),
  ]);
  initFilters();
  wireTabs();
  wireFilters();
  renderStats();
  renderJobs();
  renderActivity();
  renderSources();
}

main();
