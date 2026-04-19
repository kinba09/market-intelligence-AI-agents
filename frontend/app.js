const TOKEN_KEY = "marketintel_token";

const byId = (id) => document.getElementById(id);
const page = document.body?.dataset?.page || "dashboard";

const state = {
  apiBase: "/api",
  token: localStorage.getItem(TOKEN_KEY) || "",
};

function setStatus(id, message, data) {
  const el = byId(id);
  if (!el) return;
  el.textContent = `${message}${data ? "\n\n" + JSON.stringify(data, null, 2) : ""}`;
}

function getApiBase() {
  const input = byId("apiBase");
  if (input && input.value.trim()) {
    state.apiBase = input.value.trim();
  }
  return state.apiBase;
}

function getToken() {
  return state.token || localStorage.getItem(TOKEN_KEY) || "";
}

function setToken(token) {
  state.token = token;
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

function escapeHtml(input) {
  return String(input)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(text) {
  let out = escapeHtml(text);
  out = out.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/\*(.+?)\*/g, "<em>$1</em>");
  return out;
}

function markdownToHtml(markdown) {
  let normalized = String(markdown || "")
    .replace(/\r\n/g, "\n")
    .replace(/\s+(#{1,3}\s+)/g, "\n$1")
    .replace(/\s+(\d+\.\s+)/g, "\n$1")
    .replace(/\s+([-*]\s+)/g, "\n$1")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  // Normalize common report section headings when model returns one-line markdown.
  normalized = normalized
    .replace(/#{1,3}\s*what changed\s+/gi, "### What changed\n")
    .replace(/#{1,3}\s*why it matters\s+/gi, "### Why it matters\n")
    .replace(/#{1,3}\s*recommended next actions\s+/gi, "### Recommended next actions\n");

  const lines = normalized.split("\n");
  const html = [];
  let inUl = false;
  let inOl = false;

  const closeLists = () => {
    if (inUl) {
      html.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      html.push("</ol>");
      inOl = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeLists();
      continue;
    }

    if (line.startsWith("### ")) {
      closeLists();
      html.push(`<h3>${renderInlineMarkdown(line.slice(4))}</h3>`);
      continue;
    }
    if (line.startsWith("## ")) {
      closeLists();
      html.push(`<h2>${renderInlineMarkdown(line.slice(3))}</h2>`);
      continue;
    }
    if (line.startsWith("# ")) {
      closeLists();
      html.push(`<h1>${renderInlineMarkdown(line.slice(2))}</h1>`);
      continue;
    }

    const olMatch = line.match(/^(\d+)\.\s+(.*)$/);
    if (olMatch) {
      if (inUl) {
        html.push("</ul>");
        inUl = false;
      }
      if (!inOl) {
        html.push("<ol>");
        inOl = true;
      }
      html.push(`<li>${renderInlineMarkdown(olMatch[2])}</li>`);
      continue;
    }

    const ulMatch = line.match(/^[-*]\s+(.*)$/);
    if (ulMatch) {
      if (inOl) {
        html.push("</ol>");
        inOl = false;
      }
      if (!inUl) {
        html.push("<ul>");
        inUl = true;
      }
      html.push(`<li>${renderInlineMarkdown(ulMatch[1])}</li>`);
      continue;
    }

    closeLists();
    html.push(`<p>${renderInlineMarkdown(line)}</p>`);
  }

  closeLists();
  return html.join("");
}

async function api(path, options = {}) {
  const base = getApiBase();
  const token = getToken();

  const headers = {
    ...(options.headers || {}),
  };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${base}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      detail = parsed.detail || text;
    } catch {
      // keep raw text
    }
    throw new Error(detail || `Request failed: ${res.status}`);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

async function loginPageInit() {
  byId("registerBtn")?.addEventListener("click", async () => {
    try {
      const payload = {
        email: byId("registerEmail").value.trim(),
        password: byId("registerPassword").value,
      };
      const out = await api("/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus("authStatus", "Registered successfully. You can now log in.", out);
    } catch (err) {
      setStatus("authStatus", `Error: ${err.message}`);
    }
  });

  byId("loginBtn")?.addEventListener("click", async () => {
    try {
      const payload = {
        email: byId("loginEmail").value.trim(),
        password: byId("loginPassword").value,
      };
      const out = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setToken(out.access_token);
      setStatus("authStatus", "Login successful. Redirecting...");
      window.location.href = "/app";
    } catch (err) {
      setStatus("authStatus", `Error: ${err.message}`);
    }
  });
}

async function requireAuth() {
  try {
    const me = await api("/auth/me");
    const userEmail = byId("userEmail");
    if (userEmail) userEmail.textContent = me.email;
    return me;
  } catch {
    setToken("");
    window.location.href = "/login";
    return null;
  }
}

async function refreshLLMKeys() {
  const keys = await api("/auth/llm-keys");
  const root = byId("llmKeys");
  if (!root) return;
  root.innerHTML = "";
  if (!keys.length) {
    root.innerHTML = "<li>No key saved yet.</li>";
    return;
  }
  keys.forEach((k) => {
    const li = document.createElement("li");
    li.textContent = `${k.label} | ${k.provider}/${k.model_name} | ${k.masked_api_key}${k.is_default ? " | default" : ""}`;
    root.appendChild(li);
  });
}

async function refreshWatchlist() {
  const items = await api("/watchlist/companies");
  const root = byId("watchlist");
  if (!root) return;
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
  if (!root) return;
  root.innerHTML = "";
  if (!events.length) {
    root.innerHTML = "<li>No events yet.</li>";
    return;
  }
  events.forEach((e) => {
    const li = document.createElement("li");
    li.textContent = `${e.event_time.slice(0, 10)} | ${e.event_type} | imp=${Number(e.importance).toFixed(2)} | ${e.summary}`;
    root.appendChild(li);
  });
}

async function refreshAlerts() {
  const alerts = await api("/alerts?days=14&limit=30");
  const root = byId("alerts");
  if (!root) return;
  root.innerHTML = "";
  if (!alerts.length) {
    root.innerHTML = "<li>No alerts yet.</li>";
    return;
  }
  alerts.forEach((a) => {
    const li = document.createElement("li");
    li.textContent = `${a.priority.toUpperCase()} | ${a.alert_type} | conf=${Number(a.confidence).toFixed(2)} | ${a.message}`;
    root.appendChild(li);
  });
}

async function refreshMonitors() {
  const monitors = await api("/automation/monitors");
  const root = byId("monitors");
  if (!root) return;
  root.innerHTML = "";
  if (!monitors.length) {
    root.innerHTML = "<li>No monitors yet.</li>";
    return;
  }

  monitors.forEach((m) => {
    const li = document.createElement("li");
    li.innerHTML = `${m.label} | ${m.source_type} | every ${m.frequency_hours}h | ${m.enabled ? "enabled" : "disabled"} |
      last=${m.last_status || "n/a"}
      <button class="mini-btn" data-action="run-monitor" data-id="${m.monitor_id}">Run now</button>
      <button class="mini-btn" data-action="toggle-monitor" data-id="${m.monitor_id}" data-enabled="${m.enabled}">${m.enabled ? "Disable" : "Enable"}</button>`;
    root.appendChild(li);
  });
}

async function refreshOpsLogs() {
  const llmRuns = await api("/ops/llm-runs?limit=30");
  const workflowRuns = await api("/ops/workflow-runs?limit=30");

  const llmRoot = byId("llmRuns");
  if (llmRoot) {
    llmRoot.innerHTML = "";
    if (!llmRuns.length) llmRoot.innerHTML = "<li>No LLM runs yet.</li>";
    llmRuns.forEach((r) => {
      const li = document.createElement("li");
      li.textContent = `${r.created_at.slice(0, 19)} | ${r.provider}/${r.model_name} | ${r.endpoint || "unknown"} | ${r.success ? "ok" : "fail"} | ${r.latency_ms}ms`;
      llmRoot.appendChild(li);
    });
  }

  const wfRoot = byId("workflowRuns");
  if (wfRoot) {
    wfRoot.innerHTML = "";
    if (!workflowRuns.length) wfRoot.innerHTML = "<li>No workflow runs yet.</li>";
    workflowRuns.forEach((r) => {
      const li = document.createElement("li");
      li.textContent = `${r.started_at.slice(0, 19)} | ${r.workflow_name} | ${r.status}`;
      wfRoot.appendChild(li);
    });
  }
}

async function dashboardInit() {
  const me = await requireAuth();
  if (!me) return;

  byId("logoutBtn")?.addEventListener("click", () => {
    setToken("");
    window.location.href = "/login";
  });

  byId("saveKeyBtn")?.addEventListener("click", async () => {
    try {
      const payload = {
        label: byId("keyLabel").value.trim() || "default",
        provider: byId("keyProvider").value.trim() || "gemini",
        model_name: byId("keyModel").value.trim(),
        api_key: byId("keyValue").value.trim(),
        base_url: byId("keyBaseUrl").value.trim() || null,
        is_default: true,
      };
      if (!payload.model_name || !payload.api_key) throw new Error("Model and API key are required.");

      const out = await api("/auth/llm-key", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus("status", "LLM key saved", out);
      byId("keyValue").value = "";
      await refreshLLMKeys();
    } catch (err) {
      setStatus("status", `Error: ${err.message}`);
    }
  });

  byId("addMonitorBtn")?.addEventListener("click", async () => {
    try {
      const payload = {
        label: byId("monLabel").value.trim(),
        source_type: byId("monType").value,
        source_url: byId("monUrl").value.trim(),
        ingest_source_type: byId("monIngestType").value,
        enabled: true,
        frequency_hours: Number(byId("monFreq").value || 24),
      };
      if (!payload.label || !payload.source_url) throw new Error("Monitor label and source URL are required.");
      const out = await api("/automation/monitors", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus("status", "Monitor added", out);
      await refreshMonitors();
    } catch (err) {
      setStatus("status", `Error: ${err.message}`);
    }
  });

  byId("monitors")?.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const action = target.dataset.action;
    const id = target.dataset.id;
    if (!action || !id) return;

    try {
      if (action === "run-monitor") {
        const out = await api(`/automation/monitors/${id}/run`, { method: "POST" });
        setStatus("status", "Monitor run completed", out);
      } else if (action === "toggle-monitor") {
        const currentlyEnabled = target.dataset.enabled === "true";
        const out = await api(`/automation/monitors/${id}/toggle?enabled=${String(!currentlyEnabled)}`, {
          method: "POST",
        });
        setStatus("status", "Monitor status updated", out);
      }
      await Promise.all([refreshMonitors(), refreshEvents(), refreshAlerts(), refreshOpsLogs()]);
    } catch (err) {
      setStatus("status", `Error: ${err.message}`);
    }
  });

  byId("addWatchBtn")?.addEventListener("click", async () => {
    try {
      const payload = {
        name: byId("cmpName").value.trim(),
        domain: byId("cmpDomain").value.trim() || null,
        watchlist_tier: 1,
      };
      if (!payload.name) throw new Error("Company name is required.");

      const out = await api("/watchlist/companies", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus("status", "Watchlist updated", out);
      await refreshWatchlist();
    } catch (err) {
      setStatus("status", `Error: ${err.message}`);
    }
  });

  byId("ingestUrlBtn")?.addEventListener("click", async () => {
    try {
      const payload = {
        url: byId("ingestUrl").value.trim(),
        source_type: byId("ingestType").value,
      };
      if (!payload.url) throw new Error("URL is required.");

      const out = await api("/ingest/url", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus("status", "URL ingestion completed", out);
      await Promise.all([refreshEvents(), refreshAlerts(), refreshOpsLogs()]);
    } catch (err) {
      setStatus("status", `Error: ${err.message}`);
    }
  });

  byId("ingestRssBtn")?.addEventListener("click", async () => {
    try {
      const payload = {
        feed_url: byId("rssUrl").value.trim(),
        source_type: "news",
        limit: 5,
      };
      if (!payload.feed_url) throw new Error("RSS URL is required.");

      const out = await api("/ingest/rss", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus("status", "RSS ingestion completed", out);
      await Promise.all([refreshEvents(), refreshAlerts(), refreshOpsLogs()]);
    } catch (err) {
      setStatus("status", `Error: ${err.message}`);
    }
  });

  byId("askBtn")?.addEventListener("click", async () => {
    try {
      const question = byId("question").value.trim();
      if (!question) throw new Error("Question is required.");

      const out = await api("/query/ask", {
        method: "POST",
        body: JSON.stringify({ question, top_k: 10 }),
      });

      byId("answer").textContent = `${out.answer}\n\nConfidence: ${Number(out.confidence).toFixed(2)}\nTrace ID: ${out.trace_id}`;
      byId("trace").textContent = JSON.stringify(out.trace, null, 2);

      const citationsRoot = byId("citations");
      citationsRoot.innerHTML = "";
      (out.citations || []).forEach((c) => {
        const div = document.createElement("div");
        div.className = "cite";
        div.textContent = `${c.chunk_id} | ${c.title || "Untitled"} | ${c.source_url}`;
        citationsRoot.appendChild(div);
      });

      setStatus("status", "Query answered", {
        trace_id: out.trace_id,
        confidence: out.confidence,
        citation_count: out.citations.length,
      });
      await refreshOpsLogs();
    } catch (err) {
      setStatus("status", `Error: ${err.message}`);
    }
  });

  byId("reportBtn")?.addEventListener("click", async () => {
    try {
      const out = await api("/reports/competitor-summary", {
        method: "POST",
        body: JSON.stringify({ company_ids: [], days: 14 }),
      });
      const reportEl = byId("report");
      reportEl.innerHTML = `${markdownToHtml(out.report_markdown)}<p><strong>Trace ID:</strong> ${escapeHtml(out.trace_id)}</p>`;
      setStatus("status", "Report generated", { trace_id: out.trace_id, generated_at: out.generated_at });
      await refreshOpsLogs();
    } catch (err) {
      setStatus("status", `Error: ${err.message}`);
    }
  });

  try {
    await Promise.all([
      refreshLLMKeys(),
      refreshMonitors(),
      refreshWatchlist(),
      refreshEvents(),
      refreshAlerts(),
      refreshOpsLogs(),
    ]);
    setStatus("status", "Dashboard initialized.");
  } catch (err) {
    setStatus("status", `Initialization warning: ${err.message}`);
  }
}

async function boot() {
  if (page === "login") {
    await loginPageInit();
    return;
  }
  if (page === "dashboard") {
    await dashboardInit();
    return;
  }
}

boot();
