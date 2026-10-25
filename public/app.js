/* Buggy dashboard: fetch, render, filter. No build step, no framework. */

const els = {
  status: document.getElementById("status"),
  statGroups: document.getElementById("stat-groups"),
  statEvents: document.getElementById("stat-events"),
  statToday: document.getElementById("stat-today"),
  search: document.getElementById("search"),
  service: document.getElementById("service-filter"),
  refresh: document.getElementById("refresh"),
  rows: document.getElementById("error-rows"),
  tableEmpty: document.getElementById("table-empty"),
  placeholder: document.getElementById("detail-placeholder"),
  detail: document.getElementById("detail-body"),
  detailMessage: document.getElementById("detail-message"),
  detailService: document.getElementById("detail-service"),
  detailCount: document.getElementById("detail-count"),
  detailFirst: document.getElementById("detail-first"),
  detailLast: document.getElementById("detail-last"),
  detailStack: document.getElementById("detail-stack"),
  detailEvents: document.getElementById("detail-events"),
  chart: document.getElementById("chart"),
};

const state = { selected: null, chart: null };

function showError(err) {
  els.status.textContent = "Could not reach the Buggy API: " + err.message;
  els.status.classList.add("show");
}

function clearError() {
  els.status.classList.remove("show");
}

async function getJSON(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(res.status + " " + url);
  return res.json();
}

function formatTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso || "—";
  return date.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

function renderStats(stats) {
  els.statGroups.textContent = stats.total_groups;
  els.statEvents.textContent = stats.total_events;
  els.statToday.textContent = stats.events_today;
}

function populateServices(groups) {
  const current = els.service.value;
  const services = [...new Set(groups.map((g) => g.service))].sort();
  els.service.replaceChildren(new Option("All services", ""));
  for (const name of services) els.service.append(new Option(name, name));
  els.service.value = services.includes(current) ? current : "";
}

function renderTable(groups) {
  els.rows.replaceChildren();
  els.tableEmpty.hidden = groups.length !== 0;

  for (const group of groups) {
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    tr.dataset.fingerprint = group.fingerprint;
    tr.setAttribute("role", "button");
    tr.setAttribute("aria-label", "Open " + group.message);
    if (group.fingerprint === state.selected) tr.classList.add("selected");

    const count = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "count";
    badge.textContent = group.count;
    count.append(badge);

    const message = document.createElement("td");
    const text = document.createElement("div");
    text.className = "message";
    text.textContent = group.message;
    message.append(text);

    const service = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = "service";
    pill.textContent = group.service;
    service.append(pill);

    const time = document.createElement("td");
    time.className = "time";
    time.textContent = formatTime(group.last_seen);
    time.title = group.last_seen;

    tr.append(count, message, service, time);
    const open = () => selectGroup(group.fingerprint);
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
    els.rows.append(tr);
  }
}

async function selectGroup(fingerprint) {
  state.selected = fingerprint;
  for (const row of els.rows.children) {
    row.classList.toggle("selected", row.dataset.fingerprint === fingerprint);
  }
  try {
    const detail = await getJSON(
      "/api/errors/" + encodeURIComponent(fingerprint) + "?events_limit=20"
    );
    renderDetail(detail);
    clearError();
  } catch (err) {
    showError(err);
  }
}

function renderDetail(detail) {
  els.placeholder.hidden = true;
  els.detail.hidden = false;
  els.detailMessage.textContent = detail.error.message;
  els.detailService.textContent = detail.error.service;
  els.detailCount.textContent = detail.error.count;
  els.detailFirst.textContent = formatTime(detail.error.first_seen);
  els.detailLast.textContent = formatTime(detail.error.last_seen);

  els.detailEvents.replaceChildren();
  const events = detail.events || [];

  const showStack = (event) => {
    els.detailStack.textContent = event.stack?.trim()
      ? event.stack.trimEnd()
      : "No stack captured for this event.";
  };

  if (events.length === 0) {
    els.detailStack.textContent = "No events captured.";
    return;
  }

  events.forEach((event, index) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    const meta = document.createElement("div");
    meta.className = "event-meta";
    const route = event.route || "(no route)";
    const extras = [event.request_id && "req " + event.request_id, event.user_id && "user " + event.user_id]
      .filter(Boolean)
      .join(" · ");
    meta.textContent = "#" + event.id + " · " + route + " · " + formatTime(event.timestamp) + (extras ? " · " + extras : "");
    button.append(meta);
    button.addEventListener("click", () => showStack(event));
    item.append(button);
    els.detailEvents.append(item);
    if (index === 0) showStack(event);
  });
}

function renderChart(groups) {
  const days = [];
  const today = new Date();
  for (let i = 6; i >= 0; i -= 1) {
    const day = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - i));
    days.push(day.toISOString().slice(0, 10));
  }

  const totals = Object.fromEntries(days.map((day) => [day, 0]));
  for (const group of groups) {
    const day = (group.last_seen || "").slice(0, 10);
    if (day in totals) totals[day] += group.count;
  }

  const labels = days.map((day) =>
    new Date(day + "T00:00:00Z").toLocaleDateString(undefined, { month: "short", day: "numeric" })
  );
  const values = days.map((day) => totals[day]);

  if (state.chart) {
    state.chart.data.labels = labels;
    state.chart.data.datasets[0].data = values;
    state.chart.update();
    return;
  }

  state.chart = new Chart(els.chart, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Events",
        data: values,
        backgroundColor: "rgba(79, 140, 255, 0.55)",
        borderColor: "#4f8cff",
        borderWidth: 1,
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#8b949e" } },
        y: {
          beginAtZero: true,
          ticks: { color: "#8b949e", precision: 0 },
          grid: { color: "rgba(42, 50, 64, 0.7)" },
        },
      },
    },
  });
}

function tableUrl() {
  const params = new URLSearchParams({ limit: "50" });
  const search = els.search.value.trim();
  if (search) params.set("search", search);
  if (els.service.value) params.set("service", els.service.value);
  return "/api/errors?" + params.toString();
}

async function loadOverview() {
  try {
    const [groups, stats] = await Promise.all([
      getJSON("/api/errors?limit=500"),
      getJSON("/api/stats"),
    ]);
    populateServices(groups);
    renderStats(stats);
    renderChart(groups);
    if (!els.search.value.trim() && !els.service.value) renderTable(groups);
    clearError();
  } catch (err) {
    showError(err);
  }
}

async function loadTable() {
  try {
    const groups = await getJSON(tableUrl());
    renderTable(groups);
    clearError();
  } catch (err) {
    showError(err);
  }
}

function refresh() {
  state.selected = null;
  els.detail.hidden = true;
  els.placeholder.hidden = false;
  loadOverview();
  loadTable();
}

els.search.addEventListener("input", debounce(loadTable, 250));
els.service.addEventListener("change", loadTable);
els.refresh.addEventListener("click", refresh);

loadOverview();
loadTable();
