const byId = (id) => document.getElementById(id);

const state = {
  apiBase: "/api",
};

function setStatus(message, data) {
  const el = byId("status");
  el.textContent = `${message}${data ? "\n\n" + JSON.stringify(data, null, 2) : ""}`;
}

function getApiBase() {
  const value = byId("apiBase").value.trim();
  state.apiBase = value || "/api";
  return state.apiBase;
}

async function api(path, options = {}) {
  const base = getApiBase();
  const res = await fetch(`${base}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function refreshWatchlist() {
  const items = await api("/watchlist/companies");
  const root = byId("watchlist");
  root.innerHTML = "";
  if (!items.length) {
    root.innerHTML = "<li>No watchlist companies yet.</li>";
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = `${item.name} (${item.company_id}) tier=${item.watchlist_tier}`;
    root.appendChild(li);
  });
}

async function refreshEvents() {
  const events = await api("/events?days=14&limit=30");
  const root = byId("events");
  root.innerHTML = "";
  if (!events.length) {
    root.innerHTML = "<li>No events yet.</li>";
    return;
  }
  events.forEach((e) => {
    const li = document.createElement("li");
    li.textContent = `${e.event_time.slice(0, 10)} | ${e.event_type} | imp=${e.importance.toFixed(2)} | ${e.summary}`;
    root.appendChild(li);
  });
}

async function refreshAlerts() {
  const alerts = await api("/alerts?days=14&limit=30");
  const root = byId("alerts");
  root.innerHTML = "";
  if (!alerts.length) {
    root.innerHTML = "<li>No alerts yet.</li>";
    return;
  }
  alerts.forEach((a) => {
    const li = document.createElement("li");
    li.textContent = `${a.priority.toUpperCase()} | ${a.alert_type} | conf=${a.confidence.toFixed(2)} | ${a.message}`;
    root.appendChild(li);
  });
}

async function boot() {
  byId("addWatchBtn").addEventListener("click", async () => {
    try {
      const payload = {
        name: byId("cmpName").value.trim(),
        domain: byId("cmpDomain").value.trim() || null,
        watchlist_tier: 1,
      };
      if (!payload.name) {
        throw new Error("Company name is required.");
      }
      const out = await api("/watchlist/companies", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus("Watchlist updated", out);
      await refreshWatchlist();
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  });

  byId("ingestUrlBtn").addEventListener("click", async () => {
    try {
      const payload = {
        url: byId("ingestUrl").value.trim(),
        source_type: byId("ingestType").value,
      };
      if (!payload.url) {
        throw new Error("URL is required.");
      }
      const out = await api("/ingest/url", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus("URL ingestion completed", out);
      await Promise.all([refreshEvents(), refreshAlerts()]);
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  });

  byId("ingestRssBtn").addEventListener("click", async () => {
    try {
      const payload = {
        feed_url: byId("rssUrl").value.trim(),
        source_type: "news",
        limit: Number(byId("rssLimit").value || 5),
      };
      if (!payload.feed_url) {
        throw new Error("Feed URL is required.");
      }
      const out = await api("/ingest/rss", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus("RSS ingestion completed", out);
      await Promise.all([refreshEvents(), refreshAlerts()]);
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  });

  byId("askBtn").addEventListener("click", async () => {
    try {
      const question = byId("question").value.trim();
      if (!question) {
        throw new Error("Question is required.");
      }
      const out = await api("/query/ask", {
        method: "POST",
        body: JSON.stringify({ question, top_k: 10 }),
      });

      byId("answer").textContent = `${out.answer}\n\nConfidence: ${out.confidence.toFixed(2)}`;
      byId("trace").textContent = JSON.stringify(out.trace, null, 2);
      const citationsRoot = byId("citations");
      citationsRoot.innerHTML = "";
      (out.citations || []).forEach((c) => {
        const div = document.createElement("div");
        div.className = "cite";
        div.textContent = `${c.chunk_id} | ${c.title || "Untitled"} | ${c.source_url}`;
        citationsRoot.appendChild(div);
      });
      setStatus("Query answered", { confidence: out.confidence, citation_count: out.citations.length });
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  });

  byId("reportBtn").addEventListener("click", async () => {
    try {
      const payload = {
        company_ids: [],
        days: Number(byId("reportDays").value || 14),
      };
      const out = await api("/reports/competitor-summary", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      byId("report").textContent = out.report_markdown;
      setStatus("Report generated", { generated_at: out.generated_at });
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    }
  });

  try {
    await Promise.all([refreshWatchlist(), refreshEvents(), refreshAlerts()]);
    setStatus("App initialized.");
  } catch (err) {
    setStatus(`Initialization warning: ${err.message}`);
  }
}

boot();
