const API = window.location.origin;

function el(id) {
  return document.getElementById(id);
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

async function loadHealth() {
  const badge = el("health-badge");
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();
    const lm = data.llm_auto_resolves_to === "lm_studio" ? "LM Studio ✓" : data.llm_deepseek_configured ? "DeepSeek ✓" : "LLM ✗";
    const chunks = data.docs_count ?? data.chunks_in_index ?? 0;
    badge.textContent = `${chunks} чанков · ${lm}`;
    badge.className = "badge " + (chunks > 0 ? "badge--ok" : "badge--warn");
  } catch {
    badge.textContent = "API недоступен";
    badge.className = "badge badge--warn";
  }
}

function setUploadStatus(text, ok) {
  const node = el("upload-status");
  node.textContent = text;
  node.className =
    "upload-status " + (ok === true ? "upload-status--ok" : ok === false ? "upload-status--err" : "");
}

async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/upload`, { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || res.statusText);
  }
  return data;
}

function addMessage(kind, html) {
  const box = el("messages");
  const div = document.createElement("div");
  div.className = `msg msg--${kind} panel-rim panel-rim--soft`;
  div.innerHTML = html;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function renderSources(sources) {
  if (!sources?.length) return "";
  const items = sources
    .map((s, i) => {
      const name = s.metadata?.filename || s.metadata?.relative_path || `фрагмент ${i + 1}`;
      const score = s.score != null ? ` · score ${s.score}` : "";
      return `<details class="source panel-rim panel-rim--soft">
        <summary>${escapeHtml(name)}${score}</summary>
        <pre>${escapeHtml(s.text || "")}</pre>
      </details>`;
    })
    .join("");
  return `<div class="sources">${items}</div>`;
}

async function sendChat(query, provider, topK) {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, provider, top_k: topK }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || res.statusText);
  }
  return data;
}

el("api-base").textContent = API;

function initDropdowns() {
  const wraps = document.querySelectorAll(".drop-wrap");

  function closeAll() {
    wraps.forEach((wrap) => {
      const btn = wrap.querySelector(".btn-gold");
      const panel = wrap.querySelector(".drop-panel");
      if (!btn || !panel) return;
      btn.setAttribute("aria-expanded", "false");
      panel.hidden = true;
    });
  }

  wraps.forEach((wrap) => {
    const btn = wrap.querySelector(".btn-gold");
    const panel = wrap.querySelector(".drop-panel");
    if (!btn || !panel) return;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = btn.getAttribute("aria-expanded") === "true";
      closeAll();
      if (!open) {
        btn.setAttribute("aria-expanded", "true");
        panel.hidden = false;
      }
    });
  });

  document.addEventListener("click", closeAll);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAll();
  });
}

initDropdowns();

function setFileNameLabel(file) {
  const label = el("file-name");
  if (!label) return;
  label.textContent = file ? file.name : "не выбран";
}

el("upload-file")?.addEventListener("change", (e) => {
  setFileNameLabel(e.target.files?.[0] || null);
});

el("refresh-health").addEventListener("click", loadHealth);

el("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = el("upload-file");
  const file = input.files?.[0];
  if (!file) return;

  const btn = el("upload-btn");
  btn.disabled = true;
  btn.textContent = "Загрузка…";
  setUploadStatus("");

  try {
    const data = await uploadFile(file);
    setUploadStatus(
      `${data.message}: ${data.chunks} фрагментов («${data.filename}»). Всего в базе: ${data.total_chunks_in_index ?? "?"}`,
      true
    );
    await loadHealth();
    input.value = "";
    setFileNameLabel(null);
  } catch (err) {
    setUploadStatus(err.message, false);
  } finally {
    btn.disabled = false;
    btn.textContent = "Загрузить";
  }
});

el("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = el("query").value.trim();
  if (!query) return;

  const provider = el("provider").value;
  const topK = Number(el("top-k").value) || 5;
  const btn = el("send-btn");

  addMessage("user", `<div class="msg__body">${escapeHtml(query)}</div>`);
  el("query").value = "";
  btn.disabled = true;
  btn.textContent = "Думаю…";

  try {
    const data = await sendChat(query, provider, topK);
    let meta = `provider: ${data.llm_provider || "—"} · ${data.llm_status}`;
    let body = "";

    if (data.answer) {
      body = `<div class="msg__body">${escapeHtml(data.answer)}</div>`;
    } else if (data.llm_status === "retrieval_only") {
      body = `<div class="msg__body msg--muted">Ответ LLM отключён (provider: none). Ниже — найденные фрагменты.</div>`;
    } else if (data.llm_status === "no_llm_configured") {
      body = `<div class="msg__body error">LLM не настроен. Добавьте DEEPSEEK_API_KEY в backend\\.env и перезапустите API.</div>`;
    } else {
      body = `<div class="msg__body error">Ответ не получен (${escapeHtml(data.llm_status || "unknown")})</div>`;
    }

    addMessage(
      "bot",
      `<div class="msg__meta">${escapeHtml(meta)}</div>${body}${renderSources(data.sources)}`
    );
  } catch (err) {
    addMessage("bot", `<div class="msg__body error">${escapeHtml(err.message)}</div>`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Спросить";
  }
});

loadHealth();
