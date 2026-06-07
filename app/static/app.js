const $ = (id) => document.getElementById(id);

let pendingAttachments = [];
let chatBusy = false;

function setStatus(cardId, text, ok = null) {
  const card = $(cardId);
  if (!card) return;
  const value = card.querySelector(".status-value");
  value.textContent = text;
  value.classList.remove("status-ok", "status-bad");
  if (ok === true) value.classList.add("status-ok");
  if (ok === false) value.classList.add("status-bad");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function renderTable(tableEl, columns, rows) {
  tableEl.innerHTML = "";
  if (!columns?.length) return;

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
  (rows || []).slice(0, 50).forEach((row) => {
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

function markChecklist(key, done) {
  const item = document.querySelector(`#setup-checklist li[data-check="${key}"]`);
  if (!item) return;
  item.classList.toggle("done", !!done);
}

async function loadConfigAndHealth() {
  try {
    const [health, config] = await Promise.all([api("/health"), api("/api/config/safe")]);
    setStatus("status-sql", health.sql_configured ? "Connected" : "Offline", health.sql_configured);
    setStatus("status-model", health.model_configured ? "Ready" : "Offline", health.model_configured);
    setStatus("status-schemas", (config.allowed_schemas || []).join(", ") || "—");
    setStatus("status-rows", String(config.max_rows ?? "—"));
    markChecklist("app", true);
    markChecklist("sql", health.sql_configured);
    markChecklist("ollama", health.model_configured);
    markChecklist("model", health.model_configured);
    await refreshSetupChecklist(health);
  } catch (err) {
    setStatus("status-sql", "Error", false);
    setStatus("status-model", "Error", false);
    console.error(err);
  }
}

async function refreshSetupChecklist(health) {
  let healthData = health;
  if (!healthData) {
    try {
      healthData = await api("/health");
    } catch {
      return;
    }
  }
  markChecklist("login", healthData.sql_configured);
  try {
    const schema = await api("/api/schema");
    markChecklist("schema", (schema.schemas || []).some((s) => (s.objects || []).length > 0));
  } catch {
    markChecklist("schema", false);
  }
  try {
    const guard = await api("/api/sql/validate", {
      method: "POST",
      body: JSON.stringify({ sql: "DELETE FROM dbo.Orders" }),
    });
    markChecklist("guardrails", !guard.valid);
  } catch {
    markChecklist("guardrails", false);
  }
  try {
    const audit = await api("/api/audit/recent");
    const events = audit.events || [];
    markChecklist(
      "brief",
      events.some((e) => ["brief_generated", "investigation_completed"].includes(e.event_type))
    );
  } catch {
    /* optional */
  }
}

function downloadHtml(html, filename) {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function renderChatMessage(msg) {
  const el = document.createElement("article");
  el.className = `chat-message chat-${msg.role}`;
  el.dataset.id = msg.id;

  const meta = document.createElement("div");
  meta.className = "chat-meta";
  meta.textContent = msg.role === "user" ? "You" : "Prelytical";
  if (msg.action && msg.role === "assistant" && msg.action !== "reply") {
    meta.textContent += ` · ${msg.action}`;
  }
  el.appendChild(meta);

  const body = document.createElement("div");
  body.className = "chat-body";
  body.innerHTML = escapeHtml(msg.content).replace(/\n/g, "<br>");
  el.appendChild(body);

  if (msg.attachments?.length) {
    const att = document.createElement("div");
    att.className = "chat-attachment-tags";
    att.textContent = msg.attachments.map((a) => a.filename).join(", ");
    el.appendChild(att);
  }

  const artifact = msg.artifact || {};
  if (artifact.sql) {
    const pre = document.createElement("pre");
    pre.className = "code-block chat-sql";
    pre.textContent = artifact.sql;
    el.appendChild(pre);
  }

  if (artifact.columns?.length) {
    const wrap = document.createElement("div");
    wrap.className = "table-wrap chat-table-wrap";
    const table = document.createElement("table");
    renderTable(table, artifact.columns, artifact.rows);
    wrap.appendChild(table);
    if (artifact.row_count > 50) {
      const note = document.createElement("p");
      note.className = "hint";
      note.textContent = `Showing first 50 of ${artifact.row_count} rows`;
      wrap.appendChild(note);
    }
    el.appendChild(wrap);
  }

  if (artifact.html_report) {
    const iframe = document.createElement("iframe");
    iframe.className = "chat-report-frame";
    iframe.title = "Report preview";
    iframe.sandbox = "";
    iframe.srcdoc = artifact.html_report;
    el.appendChild(iframe);

    const dl = document.createElement("button");
    dl.type = "button";
    dl.className = "btn secondary chat-download-btn";
    dl.textContent = "Download report";
    dl.addEventListener("click", () =>
      downloadHtml(artifact.html_report, artifact.download_name || "prelytical-report.html")
    );
    el.appendChild(dl);
  }

  return el;
}

function scrollChatToBottom() {
  const box = $("chat-messages");
  box.scrollTop = box.scrollHeight;
}

function clearWelcome() {
  const welcome = document.querySelector(".chat-welcome");
  if (welcome) welcome.remove();
}

async function loadChatHistory() {
  try {
    const data = await api("/api/chat/history");
    const messages = data.messages || [];
    if (!messages.length) return;
    clearWelcome();
    const box = $("chat-messages");
    messages.forEach((msg) => box.appendChild(renderChatMessage(msg)));
    scrollChatToBottom();
  } catch (err) {
    console.error(err);
  }
}

function setChatBusy(busy, text = "Working…") {
  chatBusy = busy;
  $("chat-send-btn").disabled = busy;
  $("chat-input").disabled = busy;
  $("chat-pending").classList.toggle("hidden", !busy);
  $("chat-pending-text").textContent = text;
}

function renderAttachmentChips() {
  const container = $("chat-attachments");
  container.innerHTML = "";
  if (!pendingAttachments.length) {
    container.classList.add("hidden");
    return;
  }
  container.classList.remove("hidden");
  pendingAttachments.forEach((att, index) => {
    const chip = document.createElement("span");
    chip.className = "chat-attachment-chip";
    chip.textContent = att.filename;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      pendingAttachments.splice(index, 1);
      renderAttachmentChips();
    });
    chip.appendChild(remove);
    container.appendChild(chip);
  });
}

async function handleChatSubmit(event) {
  event.preventDefault();
  if (chatBusy) return;

  const input = $("chat-input");
  const message = input.value.trim();
  if (!message && !pendingAttachments.length) return;

  clearWelcome();
  const box = $("chat-messages");

  const previewUser = {
    id: "pending-user",
    role: "user",
    content: message || "(file attached)",
    attachments: pendingAttachments.map((a) => ({ filename: a.filename })),
  };
  box.appendChild(renderChatMessage(previewUser));
  scrollChatToBottom();

  const attachments = [...pendingAttachments];
  input.value = "";
  pendingAttachments = [];
  renderAttachmentChips();

  const started = Date.now();
  setChatBusy(true, "Thinking…");
  const timer = setInterval(() => {
    const secs = Math.floor((Date.now() - started) / 1000);
    $("chat-pending-text").textContent =
      secs < 30
        ? `Working… ${secs}s`
        : secs < 120
          ? `Still working (${secs}s) — briefs and investigations take time on CPU`
          : `Still working (${secs}s) — large jobs can take 10–20+ minutes`;
  }, 1000);

  try {
    const result = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, attachments }),
    });

    box.querySelector('[data-id="pending-user"]')?.remove();
    (result.messages || []).forEach((msg) => box.appendChild(renderChatMessage(msg)));
    scrollChatToBottom();
    markChecklist("brief", true);
  } catch (err) {
    box.querySelector('[data-id="pending-user"]')?.remove();
    const errMsg = {
      id: "err",
      role: "assistant",
      content: err.message,
      action: "error",
    };
    box.appendChild(renderChatMessage(errMsg));
    scrollChatToBottom();
  } finally {
    clearInterval(timer);
    setChatBusy(false);
  }
}

async function clearChat() {
  if (chatBusy) return;
  if (!confirm("Clear this conversation? The loaded brief stays in memory.")) return;
  await api("/api/chat/clear", { method: "POST" });
  $("chat-messages").innerHTML = `
    <div class="chat-welcome">
      <p>New conversation. Tell Prelytical what you need.</p>
    </div>`;
}

async function loadSchema() {
  try {
    const data = await api("/api/schema");
    const container = $("schema-content");
    container.innerHTML = "";
    (data.schemas || []).forEach((schema) => {
      const heading = document.createElement("h4");
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
    markChecklist("schema", (data.schemas || []).some((s) => (s.objects || []).length > 0));
  } catch (err) {
    $("schema-content").innerHTML = `<p class="validation bad">${err.message}</p>`;
  }
}

async function validateSql(execute = false) {
  const sql = $("sql-input").value.trim();
  if (!sql) return;
  const endpoint = execute ? "/api/sql/execute" : "/api/sql/validate";
  try {
    const result = await api(endpoint, { method: "POST", body: JSON.stringify({ sql }) });
    $("validator-result").classList.remove("hidden");
    $("validator-normalized").textContent = result.normalized_sql || sql;
    const message = $("validator-message");
    if (result.valid) {
      message.textContent = execute ? `Valid · ${result.row_count || 0} rows` : "Valid SQL";
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
        ${event.question ? `<div><strong>Q:</strong> ${escapeHtml(event.question)}</div>` : ""}
        ${event.generated_sql ? `<div><strong>SQL:</strong> <code>${escapeHtml(event.generated_sql)}</code></div>` : ""}
        ${event.blocked_reason ? `<div class="validation bad">${escapeHtml(event.blocked_reason)}</div>` : ""}
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
  loadChatHistory();

  $("refresh-status-btn").addEventListener("click", loadConfigAndHealth);
  $("chat-form").addEventListener("submit", handleChatSubmit);
  $("chat-clear-btn").addEventListener("click", clearChat);
  $("chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      $("chat-form").requestSubmit();
    }
  });
  $("chat-file-input").addEventListener("change", async (e) => {
    for (const file of e.target.files || []) {
      const content = await file.text();
      pendingAttachments.push({ filename: file.name, content });
    }
    renderAttachmentChips();
    e.target.value = "";
  });
  $("load-schema-btn").addEventListener("click", loadSchema);
  $("validate-btn").addEventListener("click", () => validateSql(false));
  $("execute-btn").addEventListener("click", () => validateSql(true));
  $("load-audit-btn").addEventListener("click", loadAudit);
});
