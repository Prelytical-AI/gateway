const $ = (id) => document.getElementById(id);

function setStatus(cardId, text, ok = null) {
  const card = $(cardId);
  const value = card.querySelector(".status-value");
  value.textContent = text;
  value.classList.remove("status-ok", "status-bad");
  if (ok === true) value.classList.add("status-ok");
  if (ok === false) value.classList.add("status-bad");
}

function renderTable(tableEl, columns, rows) {
  tableEl.innerHTML = "";
  if (!columns.length) return;

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  tableEl.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((col) => {
      const td = document.createElement("td");
      td.textContent = row[col] ?? "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tableEl.appendChild(tbody);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || response.statusText || "Request failed");
  }
  return data;
}

async function loadConfigAndHealth() {
  try {
    const [health, config] = await Promise.all([
      api("/health"),
      api("/api/config/safe"),
    ]);

    setStatus("status-sql", health.sql_configured ? "Connected" : "Not connected", health.sql_configured);
    setStatus("status-model", health.model_configured ? "Ready" : "Unavailable", health.model_configured);
    setStatus("status-schemas", (config.allowed_schemas || []).join(", ") || "—");
    setStatus("status-rows", String(config.max_rows ?? "—"));

    markChecklist("app", true);
    markChecklist("sql", health.sql_configured);
    markChecklist("ollama", health.model_configured);
    markChecklist("model", health.model_configured);
  } catch (err) {
    setStatus("status-sql", "Error", false);
    setStatus("status-model", "Error", false);
    console.error(err);
  }
}

function markChecklist(key, done) {
  const item = document.querySelector(`#setup-checklist li[data-check="${key}"]`);
  if (item && done) item.classList.add("done");
}

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      $(`panel-${tab.dataset.tab}`).classList.add("active");
    });
  });
}

let lastBriefHtml = "";

async function generateBrief() {
  const payload = {
    title: $("brief-title").value.trim(),
    objective: $("brief-objective").value.trim(),
    business_context: $("brief-context").value.trim() || null,
    audience: $("brief-audience").value.trim(),
  };
  if (!payload.objective) return;

  $("brief-btn").disabled = true;
  $("brief-progress").classList.remove("hidden");
  const started = Date.now();
  const progressEl = $("brief-progress");
  const timer = setInterval(() => {
    const secs = Math.floor((Date.now() - started) / 1000);
    $("brief-btn").textContent = `Generating… ${secs}s`;
    progressEl.textContent =
      secs < 60
        ? "Building executive brief from schema metadata (local Ollama)…"
        : `Still generating (${secs}s). Large HTML briefs on CPU can take 10–20+ minutes.`;
  }, 1000);
  $("brief-btn").textContent = "Generating… 0s";

  try {
    const result = await api("/api/brief/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    $("brief-result").classList.remove("hidden");
    $("brief-readiness").textContent = result.readiness_score ?? "—";
    $("brief-confidence").textContent = result.confidence_score ?? "—";
    $("brief-summary").textContent = result.executive_summary || "";
    lastBriefHtml = result.html_report || "";
    $("brief-frame").srcdoc = lastBriefHtml || "<p>No HTML report returned.</p>";
    const exportNotice = $("brief-export-notice");
    if (result.export_path) {
      exportNotice.textContent = `Saved to server export path: ${result.export_path}`;
      exportNotice.classList.remove("hidden", "export-error");
    } else if (result.export_error) {
      exportNotice.textContent = result.export_error;
      exportNotice.classList.remove("hidden");
      exportNotice.classList.add("export-error");
    } else {
      exportNotice.classList.add("hidden");
      exportNotice.textContent = "";
    }
    markChecklist("brief", true);
  } catch (err) {
    alert(`${err.message}\n\nTry warm_ollama_model.ps1 first and increase BRIEF_TIMEOUT_SECONDS in .env.`);
  } finally {
    clearInterval(timer);
    $("brief-progress").classList.add("hidden");
    $("brief-btn").disabled = false;
    $("brief-btn").textContent = "Generate Executive Brief";
  }
}

function downloadBriefHtml() {
  if (!lastBriefHtml) return;
  const blob = new Blob([lastBriefHtml], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "prelytical-executive-brief.html";
  a.click();
  URL.revokeObjectURL(url);
}

async function askQuestion() {
  const question = $("question-input").value.trim();
  if (!question) return;

  $("ask-btn").disabled = true;
  $("ask-progress").classList.remove("hidden");
  const started = Date.now();
  const progressEl = $("ask-progress");
  const timer = setInterval(() => {
    const secs = Math.floor((Date.now() - started) / 1000);
    $("ask-btn").textContent = `Working… ${secs}s`;
    progressEl.textContent =
      secs < 30
        ? "Generating SQL from your question (local Ollama on CPU — please wait)…"
        : `Still working (${secs}s). First run loads the model into memory and can take 3–10+ minutes on CPU-only VMs.`;
  }, 1000);
  $("ask-btn").textContent = "Working… 0s";

  try {
    const result = await api("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    });

    $("ask-result").classList.remove("hidden");
    $("ask-sql").textContent = result.sql || "(none)";
    $("ask-answer").textContent = result.answer || "";

    const validation = $("ask-validation");
    if (result.valid) {
      validation.textContent = `Valid SQL · ${result.row_count} rows returned`;
      validation.className = "validation ok";
    } else {
      validation.textContent = `Blocked: ${result.blocked_reason}`;
      validation.className = "validation bad";
      markChecklist("guardrails", true);
    }

    renderTable($("ask-table"), result.columns || [], result.rows || []);
  } catch (err) {
    alert(
      `${err.message}\n\nIf this was a timeout, increase MODEL_TIMEOUT_SECONDS in .env ` +
        "(default 600) or use a GPU inference VM. See docs/TROUBLESHOOTING.md."
    );
  } finally {
    clearInterval(timer);
    $("ask-progress").classList.add("hidden");
    $("ask-btn").disabled = false;
    $("ask-btn").textContent = "Ask Prelytical";
  }
}

async function loadSchema() {
  try {
    const data = await api("/api/schema");
    const container = $("schema-content");
    container.innerHTML = "";

    (data.schemas || []).forEach((schema) => {
      const heading = document.createElement("h3");
      heading.textContent = `Schema: ${schema.schema}`;
      container.appendChild(heading);

      (schema.objects || []).forEach((obj) => {
        const block = document.createElement("div");
        block.className = "schema-object";
        block.innerHTML = `<strong>${obj.type}: ${schema.schema}.${obj.name}</strong>`;
        const cols = document.createElement("p");
        cols.textContent = (obj.columns || [])
          .map((c) => `${c.name} (${c.type}${c.nullable ? ", nullable" : ""})`)
          .join(" · ");
        block.appendChild(cols);
        container.appendChild(block);
      });
    });

    markChecklist("schema", (data.schemas || []).length > 0);
    markChecklist("login", true);
  } catch (err) {
    $("schema-content").innerHTML = `<p class="validation bad">${err.message}</p>`;
  }
}

async function validateSql(execute = false) {
  const sql = $("sql-input").value.trim();
  if (!sql) return;

  const endpoint = execute ? "/api/sql/execute" : "/api/sql/validate";
  try {
    const result = await api(endpoint, {
      method: "POST",
      body: JSON.stringify({ sql }),
    });

    $("validator-result").classList.remove("hidden");
    $("validator-normalized").textContent = result.normalized_sql || sql;

    const message = $("validator-message");
    if (result.valid) {
      message.textContent = execute
        ? `Valid and executed · ${result.row_count || 0} rows`
        : "Valid SQL";
      message.className = "validation ok";
    } else {
      message.textContent = `Blocked: ${result.blocked_reason}`;
      message.className = "validation bad";
      markChecklist("guardrails", true);
    }

    renderTable($("validator-table"), result.columns || [], result.rows || []);
  } catch (err) {
    alert(err.message);
  }
}

async function loadAudit() {
  try {
    const data = await api("/api/audit/recent");
    const container = $("audit-content");
    container.innerHTML = "";

    (data.events || []).forEach((event) => {
      const block = document.createElement("div");
      block.className = "audit-event";
      block.innerHTML = `
        <div class="meta">#${event.id} · ${event.created_at} · ${event.event_type}</div>
        ${event.question ? `<div><strong>Q:</strong> ${event.question}</div>` : ""}
        ${event.generated_sql ? `<div><strong>SQL:</strong> <code>${event.generated_sql}</code></div>` : ""}
        ${event.blocked_reason ? `<div class="validation bad">${event.blocked_reason}</div>` : ""}
        ${event.metadata?.error ? `<div class="validation bad">${event.metadata.error}</div>` : ""}
        ${event.row_count != null ? `<div>Rows: ${event.row_count}</div>` : ""}
      `;
      container.appendChild(block);
    });
  } catch (err) {
    $("audit-content").innerHTML = `<p class="validation bad">${err.message}</p>`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  loadConfigAndHealth();

  $("refresh-status-btn").addEventListener("click", loadConfigAndHealth);
  $("brief-btn").addEventListener("click", generateBrief);
  $("brief-download-btn").addEventListener("click", downloadBriefHtml);
  $("ask-btn").addEventListener("click", askQuestion);
  $("load-schema-btn").addEventListener("click", loadSchema);
  $("validate-btn").addEventListener("click", () => validateSql(false));
  $("execute-btn").addEventListener("click", () => validateSql(true));
  $("load-audit-btn").addEventListener("click", loadAudit);
});
