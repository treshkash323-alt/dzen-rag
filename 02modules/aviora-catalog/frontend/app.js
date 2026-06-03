/* AIKIVAVIORA Catalog v0.3.13 */
(function () {
  const UI_VERSION = "0.3.13";
  const AUDIO_EXTS = new Set([
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".flac",
    ".aac",
    ".wma",
    ".opus",
  ]);
  const API = "";
  /** Только эти коды — блокирующее окно; 422/чат/convert — toast */
  const IMG_EXTS = new Set([".jpg", ".jpeg", ".png", ".webp", ".gif"]);
  const CODE_EXTS = new Set([
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".css",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
  ]);

  const MODAL_ERROR_CODES = new Set([
    "ERR_PATH_OUTSIDE_ROOT",
    "ERR_READ_ONLY",
    "ERR_SCAN_HANG",
    "ERR_ZIP_SLIP",
    "ERR_RAR_V02",
    "ERR_NOT_EDITABLE",
    "ERR_LLM_HANG",
  ]);
  const state = {
    cwd: "",
    currentPath: null,
    dirty: false,
    scanJobId: null,
    transcribeJobId: null,
    cropper: null,
    readOnly: localStorage.getItem("avioraReadOnly") === "1",
    recent: JSON.parse(localStorage.getItem("avioraRecent") || "[]"),
    starred: JSON.parse(localStorage.getItem("avioraStarred") || "[]"),
    findIdx: 0,
    messages: {},
    glossary: {},
    lastHealth: null,
    markedPrimary: new Set(),
    lastSearch: null,
    lastChat: null,
    scanStallAt: null,
    llmStallAt: null,
    chatInFlight: false,
    llmEnabled: localStorage.getItem("avioraLlmEnabled") !== "0",
    llmProvider: localStorage.getItem("avioraLlmProvider") || "auto",
    textMode: "both",
    boardElements: [],
    figmaSelId: null,
  };
  let previewTimer = null;
  let undoTimer = null;
  const undoHist = { stack: [], redo: [], snap: "", path: null };

  const $ = (id) => document.getElementById(id);

  function roHeaders() {
    const h = { "Content-Type": "application/json" };
    if (state.readOnly) h["X-Read-Only"] = "true";
    return h;
  }

  async function api(path, opts = {}) {
    const quiet = !!opts.quiet;
    const silent = !!opts.silent;
    const { quiet: _q, silent: _s, ...fetchOpts } = opts;
    const res = await fetch(API + path, {
      ...fetchOpts,
      headers: { ...roHeaders(), ...(fetchOpts.headers || {}) },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const code = data.code || (res.status === 422 ? "ERR_VALIDATION" : "ERR_HTTP");
      const msg = parseApiError(data, res.status);
      if (!silent) {
        if (quiet) {
          toast(msg, false);
        } else if (MODAL_ERROR_CODES.has(code) && state.messages[code]) {
          showError(code, msg);
        } else {
          toast(msg, false);
        }
      }
      throw new Error(code);
    }
    return data;
  }

  function syncReadOnlyFromUi() {
    const el = $("read-only-toggle");
    if (!el) return;
    state.readOnly = !!el.checked;
    localStorage.setItem("avioraReadOnly", state.readOnly ? "1" : "0");
  }

  async function loadJson() {
    const [m, g] = await Promise.all([
      fetch("/ui/app-messages.ru.json").then((r) => r.json()),
      fetch("/ui/glossary.ru.json").then((r) => r.json()),
    ]);
    state.messages = m;
    state.glossary = g;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function toast(msg, ok = true) {
    const el = $("toast");
    el.textContent = msg;
    el.hidden = false;
    el.classList.toggle("toast--err", !ok);
    setTimeout(() => {
      el.hidden = true;
    }, 4000);
  }

  function parseApiError(data, status) {
    if (data.code && data.message) return data.message;
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((d) => {
          const loc = (d.loc || []).join(".");
          if (d.msg === "Input should be a valid string" && loc.includes("path")) {
            return "Превью: нет пути к файлу (переоткройте файл слева)";
          }
          return d.msg || JSON.stringify(d);
        })
        .join("; ");
    }
    if (typeof data.detail === "string") return data.detail;
    if (status === 422) return "Ошибка запроса (422) — проверьте текст вопроса в чате";
    return data.message || `HTTP ${status}`;
  }

  function markTreeSelection(filePath) {
    document.querySelectorAll(".tree-item[data-path]").forEach((el) => {
      el.classList.toggle("tree-item--sel", el.dataset.path === filePath);
    });
    document.querySelectorAll(".search-results .hit").forEach((el) => {
      el.classList.toggle("hit--sel", el.dataset.path === filePath);
    });
    document.querySelectorAll(".recent li, .starred li").forEach((el) => {
      const t = (el.title || el.textContent || "").replace(/^\s*★\s*/, "").trim();
      el.classList.toggle("list-row--sel", t === filePath);
    });
  }

  function showError(code, fallback) {
    const m = state.messages[code];
    if (!m) {
      toast(fallback || code, false);
      return;
    }
    openModal(m.title, m.cause, (m.actions || []).slice(0, 3));
  }

  function openModal(title, body, actions = []) {
    $("modal-title").textContent = title;
    $("modal-body").textContent = body;
    const box = $("modal-actions");
    box.innerHTML = "";
    actions.forEach((act) => {
      const label = typeof act === "string" ? act : act.label;
      const fn = typeof act === "object" && act.fn ? act.fn : null;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn-gold btn-interactive";
      b.textContent = label;
      b.onclick = async () => {
        if (fn) await fn();
        $("modal").hidden = true;
        if (typeof label === "string" && label.includes("лог")) toggleLogs(true);
        if (typeof label === "string" && label.includes("Останов")) stopAll();
      };
      box.appendChild(b);
    });
    const close = document.createElement("button");
    close.type = "button";
    close.className = "btn-gold btn-interactive";
    close.textContent = "Закрыть";
    close.onclick = () => {
      $("modal").hidden = true;
    };
    box.appendChild(close);
    $("modal").hidden = false;
  }

  function toggleLogs(open) {
    const on =
      open !== undefined ? open : !$("logs-panel").hidden;
    $("logs-panel").hidden = !on;
    document.body.classList.toggle("logs-open", on);
    if (on) refreshLogs();
  }

  async function refreshLogs() {
    const data = await api("/logs/tail?n=120");
    $("logs-body").textContent = (data.lines || []).join("\n");
  }

  function updateClock() {
    const el = $("clock");
    if (!el) return;
    const d = new Date();
    const main = d.toLocaleString("ru-RU", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    const sec = String(d.getSeconds()).padStart(2, "0");
    el.innerHTML = `${escapeHtml(main)}:<span class="clock__sec">${sec}</span>`;
  }

  function getLlmProvider() {
    const v =
      $("llm-provider-header")?.value ||
      $("llm-provider")?.value ||
      state.llmProvider ||
      "auto";
    return v;
  }

  function syncLlmProviderSelects(value) {
    state.llmProvider = value;
    localStorage.setItem("avioraLlmProvider", value);
    ["llm-provider-header", "llm-provider"].forEach((id) => {
      const el = $(id);
      if (el && el.value !== value) el.value = value;
    });
  }

  async function setLlmEnabled(enabled) {
    state.llmEnabled = !!enabled;
    localStorage.setItem("avioraLlmEnabled", state.llmEnabled ? "1" : "0");
    await api("/session/llm", {
      method: "POST",
      body: JSON.stringify({ enabled: state.llmEnabled }),
    }).catch(() => null);
    await refreshLlmStatus(true);
  }

  async function toggleLlmEnabled() {
    await setLlmEnabled(!state.llmEnabled);
    toast(
      state.llmEnabled
        ? `LLM включён · ${getLlmProvider()}`
        : "LLM выключен — чат не вызывает модель",
      state.llmEnabled
    );
  }

  function updateLlmPowerButton() {
    const btn = $("btn-llm-power");
    if (!btn) return;
    btn.textContent = state.llmEnabled ? "ON" : "OFF";
    btn.className =
      "btn-llm-power " + (state.llmEnabled ? "btn-llm-power--on" : "btn-llm-power--off");
    btn.dataset.tip = state.llmEnabled
      ? "Чат с LLM включён — нажмите OFF"
      : "Чат выключен — нажмите ON (сервер всё равно проверяется ↻)";
  }

  function updateLlmStatusPill(h, probing) {
    const pill = $("llm-status-pill");
    if (!pill) return;
    updateLlmPowerButton();
    if (probing) {
      pill.textContent = "проверка LM Studio…";
      pill.className = "llm-status-pill llm-status-pill--checking";
      return;
    }
    const prov = (h && h.llm_ui_provider) || getLlmProvider();
    const ok = !!(h && h.llm_reachable && h.llm_auto_resolves_to);
    const model = shortenModel((h && h.llm_active_model) || "—", 22);
    const url = (h && h.llm_lm_studio_url) || "127.0.0.1:1234";

    if (!state.llmEnabled) {
      if (ok) {
        pill.textContent = `сервер ✓ · ${model} · чат OFF`;
        pill.className = "llm-status-pill llm-status-pill--idle-ok";
      } else if (h) {
        pill.textContent = `сервер ✗ · ${prov}`;
        pill.className = "llm-status-pill llm-status-pill--idle-warn";
      } else {
        pill.textContent = "нажмите ↻";
        pill.className = "llm-status-pill llm-status-pill--off";
      }
      pill.dataset.tip = `Сервер: ${url}. ON — включить чат.`;
      return;
    }

    if (ok) {
      pill.textContent = `● в сети · ${model}`;
      pill.className = "llm-status-pill llm-status-pill--online";
      pill.dataset.tip = `Готово к чату · ${prov} · ${url}`;
    } else {
      const err = (h && h.llm_probe_error) || "нет ответа";
      pill.textContent = `● нет связи · ${prov}`;
      pill.className = "llm-status-pill llm-status-pill--offline";
      pill.dataset.tip =
        (h && h.llm_probe_hint) ||
        `LM Studio: Start Server на :1234. ${err}`;
    }
  }

  function setBranchQuickActive(cmd) {
    document.querySelectorAll(".branch-quick__btn").forEach((btn) => {
      const on =
        cmd === "branch-all"
          ? btn.dataset.cmd === "branch-all"
          : btn.dataset.cmd === cmd;
      btn.classList.toggle("branch-quick__btn--on", on);
    });
  }

  async function refreshLlmStatus(forceProbe) {
    const prov = getLlmProvider();
    updateLlmStatusPill(null, true);
    try {
      let extra = {};
      if (forceProbe) {
        extra = await api(
          `/llm/probe?provider=${encodeURIComponent(prov)}`,
          { method: "POST", quiet: true }
        );
      }
      const en = state.llmEnabled ? "true" : "false";
      const h = await api(
        `/health?provider=${encodeURIComponent(prov)}&llm_enabled=${en}`,
        { quiet: true }
      );
      state.lastHealth = { ...h, ...extra };
      updateLlmStatusPill(state.lastHealth, false);
      if (forceProbe && state.lastHealth && !state.lastHealth.llm_reachable) {
        const hint = state.lastHealth.llm_probe_error || state.lastHealth.llm_probe_hint;
        if (hint) toast(hint, false);
      }
      return state.lastHealth;
    } catch {
      updateLlmStatusPill(null, false);
      return null;
    }
  }

  function shortenModel(name, max = 26) {
    const s = String(name || "—");
    return s.length > max ? `${s.slice(0, max - 1)}…` : s;
  }

  function setScanButtonsDisabled(disabled) {
    const scanBtn = $("btn-scan");
    if (scanBtn) {
      scanBtn.disabled = disabled;
      scanBtn.classList.toggle("btn-scan--active", disabled);
      if (!disabled && !state.scanJobId) scanBtn.textContent = "Scan";
    }
    document.querySelectorAll('[data-cmd="scan"]').forEach((el) => {
      el.disabled = disabled;
      el.classList.toggle("btn-scan--active", disabled);
    });
  }

  function renderScanProgress(st) {
    const box = $("scan-progress");
    if (!box) return;
    const total = Math.max(st.total || 0, 1);
    const prog = st.progress || 0;
    const pct = total > 0 ? Math.min(100, Math.round((prog / total) * 100)) : 0;
    const fill = $("scan-progress-fill");
    const track = $("scan-progress-track");
    const label = $("scan-progress-label");
    const pctEl = $("scan-progress-pct");
    const fileEl = $("scan-progress-file");
    if (fill) fill.style.width = `${pct}%`;
    if (track) {
      track.setAttribute("aria-valuenow", String(pct));
      track.setAttribute("aria-valuemax", "100");
    }
    if (pctEl) pctEl.textContent = `${pct}%`;
    const cur = (st.current || "").trim();
    if (fileEl) {
      fileEl.textContent = cur
        ? `${prog} / ${st.total || "?"} — ${cur}`
        : `${prog} / ${st.total || "?"} — подготовка…`;
    }
    if (label) {
      if (st.doneLabel) label.textContent = st.doneLabel;
      else if (st.status === "pending") label.textContent = "Запуск сканирования…";
      else label.textContent = `Сканирование: ${prog} из ${st.total || "?"}`;
    }
    const badge = $("status-badge");
    if (badge && state.scanJobId) {
      badge.textContent = `scan ${prog}/${st.total || "?"}`;
      badge.className = "badge badge--scan";
    }
    const scanBtn = $("btn-scan");
    if (scanBtn && state.scanJobId) scanBtn.textContent = `Scan ${pct}%`;
  }

  function setTranscribeButtonsDisabled(disabled) {
    const tr = $("btn-audio-transcribe");
    const stop = $("btn-audio-transcribe-stop");
    if (tr) {
      tr.disabled = disabled;
      tr.textContent = disabled ? "Идёт…" : "Транскрипт";
    }
    if (stop) stop.hidden = !disabled;
  }

  function renderTranscribeProgress(st) {
    const box = $("transcribe-progress");
    if (!box) return;
    const total = Math.max(st.total || 100, 1);
    const prog = st.progress || 0;
    const pct = Math.min(100, Math.round((prog / total) * 100));
    const fill = $("transcribe-progress-fill");
    const track = $("transcribe-progress-track");
    const label = $("transcribe-progress-label");
    const pctEl = $("transcribe-progress-pct");
    const fileEl = $("transcribe-progress-file");
    if (fill) fill.style.width = `${pct}%`;
    if (track) {
      track.setAttribute("aria-valuenow", String(pct));
      track.setAttribute("aria-valuemax", "100");
    }
    if (pctEl) pctEl.textContent = `${pct}%`;
    const msg = (st.message || st.current || "").trim();
    if (fileEl) {
      fileEl.textContent = msg || st.status || "Обработка…";
    }
    if (label) {
      if (st.doneLabel) label.textContent = st.doneLabel;
      else label.textContent = `Транскрипция: ${pct}%`;
    }
    const badge = $("status-badge");
    if (badge && state.transcribeJobId) {
      badge.textContent = `audio ${pct}%`;
      badge.className = "badge badge--scan";
    }
  }

  function showTranscribeProgress(active, st = {}) {
    const box = $("transcribe-progress");
    if (!box) return;
    if (!active) {
      box.hidden = true;
      setTranscribeButtonsDisabled(false);
      const badge = $("status-badge");
      if (badge && !state.scanJobId) {
        badge.className = "badge";
      }
      return;
    }
    box.hidden = false;
    setTranscribeButtonsDisabled(true);
    renderTranscribeProgress(st);
  }

  function saveTranscribeJob(jobId, path) {
    localStorage.setItem(
      "avioraTranscribeJob",
      JSON.stringify({ job_id: jobId, path: path || "", at: Date.now() })
    );
  }

  function clearTranscribeJob() {
    localStorage.removeItem("avioraTranscribeJob");
  }

  async function cancelTranscribe() {
    if (!state.transcribeJobId) return;
    await api(`/scan/cancel/${state.transcribeJobId}`, { method: "POST" });
    clearTranscribeJob();
    toast("Останавливаем транскрипцию…", true);
  }

  async function resumeTranscribeJobOnLoad() {
    let saved = null;
    try {
      saved = JSON.parse(localStorage.getItem("avioraTranscribeJob") || "null");
    } catch {
      return;
    }
    if (!saved?.job_id) return;
    try {
      const st = await api(`/audio/transcribe/status/${saved.job_id}`, {
        silent: true,
      });
      if (st.status === "running" || st.status === "pending") {
        state.transcribeJobId = saved.job_id;
        toast(
          "Транскрипция ещё идёт на сервере — показываю полосу прогресса",
          true
        );
        pollTranscribe();
        return;
      }
      clearTranscribeJob();
      if (st.status === "done" && saved.path) {
        toast("Транскрипт уже готов — откройте файл снова", true);
      }
    } catch {
      clearTranscribeJob();
      toast(
        "Транскрипция прервана: перезапущен сервер или закрыто окно bat. Запустите Транскрипт заново.",
        false
      );
    }
  }

  function showScanProgress(active, st = {}) {
    const box = $("scan-progress");
    if (!box) return;
    if (!active) {
      box.hidden = true;
      setScanButtonsDisabled(false);
      return;
    }
    box.hidden = false;
    setScanButtonsDisabled(true);
    renderScanProgress(st);
  }

  function setChatBusy(busy) {
    const btn = $("btn-chat-send");
    const inp = $("chat-input");
    const form = $("chat-form");
    const hint = $("chat-hint");
    const bar = $("chat-busy");
    if (bar) bar.hidden = !busy;
    if (btn) {
      btn.disabled = busy;
      btn.textContent = busy ? "Отправка…" : "Send";
      btn.classList.toggle("btn--busy", busy);
    }
    if (inp) inp.disabled = busy;
    if (form) form.classList.toggle("chat-form--busy", busy);
    if (hint) {
      hint.textContent = busy
        ? "Ждём ответ модели… (Стоп — Ctrl+.)"
        : "Send — вопрос по каталогу (после Scan). LM Studio :1234 или DeepSeek";
    }
  }

  function warnBackendVersion(h) {
    if (!h?.version || h.version === UI_VERSION) return;
    toast(
      `Backend v${h.version} — перезапустите uvicorn (нужен v${UI_VERSION}), иначе чат «Отменён»`,
      false
    );
  }

  async function resetStuckChatCancel() {
    try {
      await api("/chat/reset-cancel", { method: "POST", silent: true });
    } catch {
      /* старый backend без маршрута */
    }
  }

  function updateStatusBadge(h) {
    const badge = $("status-badge");
    if (!badge) return;
    if (state.scanJobId) return;
    if (!h) {
      badge.textContent = "offline";
      badge.className = "badge badge--warn";
      return;
    }
    const ro = h.read_only ? " · RO" : "";
    badge.textContent = `idx ${h.files_indexed} · API ok${ro}`;
    badge.className = "badge badge--ok";
    badge.dataset.tip = `Файлов в индексе: ${h.files_indexed}. Корень: ${h.catalog_root || "—"}`;
  }

  function isHealthApiModern(h) {
    return h && typeof h.llm_reachable === "boolean";
  }

  function warnOldBackend(h) {
    if (!h || isHealthApiModern(h)) return;
    const pill = $("llm-status-pill");
    if (pill) {
      pill.textContent = "рестарт backend :8002";
      pill.className = "llm-status-pill llm-status-pill--offline";
      pill.dataset.tip =
        "Запущен старый Catalog без проверки LM Studio. Остановите uvicorn и запустите снова из backend/.";
    }
    toast(
      "Backend Catalog устарел (нет llm в /health). Перезапустите сервер :8002",
      false
    );
  }

  function bindFloatingTips() {
    const floater = $("tip-float");
    if (!floater || floater.dataset.bound === "1") return;
    floater.dataset.bound = "1";
    const sel =
      ".header [data-tip], .ribbon [data-tip], .branch-bar [data-tip], .header-llm [data-tip], .ribbon-quick [data-tip]";
    document.querySelectorAll(sel).forEach((el) => {
      const show = () => {
        const text = el.getAttribute("data-tip");
        if (!text) return;
        floater.textContent = text;
        floater.hidden = false;
        const r = el.getBoundingClientRect();
        const cx = Math.max(12, Math.min(window.innerWidth - 12, r.left + r.width / 2));
        let top = r.bottom + 10;
        floater.style.left = `${cx}px`;
        floater.style.top = `${top}px`;
        floater.style.transform = "translateX(-50%)";
        requestAnimationFrame(() => {
          const fh = floater.offsetHeight;
          if (top + fh > window.innerHeight - 8) {
            top = Math.max(8, r.top - fh - 8);
            floater.style.top = `${top}px`;
          }
        });
      };
      const hide = () => {
        floater.hidden = true;
      };
      el.addEventListener("mouseenter", show);
      el.addEventListener("focus", show);
      el.addEventListener("mouseleave", hide);
      el.addEventListener("blur", hide);
    });
  }

  async function pollHealth() {
    try {
      const prov = getLlmProvider();
      const en = state.llmEnabled ? "true" : "false";
      const h = await api(
        `/health?provider=${encodeURIComponent(prov)}&llm_enabled=${en}`
      );
      state.lastHealth = h;
      warnOldBackend(h);
      warnBackendVersion(h);
      updateStatusBadge(h);
      if (isHealthApiModern(h)) updateLlmStatusPill(h, false);
      const whisper = h.whisper_ok ? " · whisper" : "";
      $("footer-health").textContent = `health ok · ${h.files_indexed} files${whisper}`;
      const fv = $("footer-version");
      if (fv) {
        const mismatch = h.version && h.version !== UI_VERSION;
        fv.textContent = mismatch
          ? `UI ${UI_VERSION} / API v${h.version} ⚠`
          : `v${h.version}`;
        fv.title = mismatch
          ? "Версии не совпадают — перезапустите uvicorn из backend\\.venv"
          : "";
      }
      $("footer-tokens").textContent = `tokens sess: ${h.tokens_session || 0}`;
      const bill = $("footer-billing");
      if (bill) {
        bill.textContent = `Billing: ${h.features_billing_enabled ? "on" : "off"}`;
      }
      /* Не трогаем галочку Read-only каждые 30 с — иначе снова включается */
    } catch {
      updateStatusBadge(null);
      updateLlmStatusPill(null, false);
    }
  }

  function renderStarred() {
    const ul = $("starred-list");
    ul.innerHTML = "";
    state.starred.forEach((p) => {
      const li = document.createElement("li");
      li.className = "list-row";
      li.textContent = "★ " + p;
      li.title = p;
      li.onclick = () => loadTree(p);
      ul.appendChild(li);
    });
  }

  function toggleStarFolder(folderPath) {
    const i = state.starred.indexOf(folderPath);
    if (i >= 0) state.starred.splice(i, 1);
    else state.starred.push(folderPath);
    localStorage.setItem("avioraStarred", JSON.stringify(state.starred));
    renderStarred();
    loadTree(state.cwd);
  }

  function activeExtChip() {
    return document.querySelector(".chip--on")?.dataset.ext || "";
  }

  function matchesExtChip(child, chipExt) {
    if (!chipExt || child.is_dir) return true;
    const ext = (child.ext || "").toLowerCase();
    if (chipExt === ".jpg") return IMG_EXTS.has(ext);
    if (chipExt === ".py") return CODE_EXTS.has(ext);
    return ext === chipExt;
  }

  function updateTreeHint() {
    const hint = $("tree-hint");
    if (!hint) return;
    const chipExt = activeExtChip();
    const q = ($("search-input")?.value || "").trim();
    if (q) {
      const br = $("branch-filter")?.value;
      const brNote = br ? `, ветка «${br}»` : ", все ветки";
      hint.textContent = `Поиск по индексу${brNote} — нажмите Enter. Кнопки md/pdf ниже — только для дерева папки.`;
      return;
    }
    if (chipExt) {
      hint.textContent = `Фильтр «${chipExt.replace(".", "")}» в этой папке. Папки 📁 всегда видны.`;
      return;
    }
    hint.textContent =
      "Клик по 📁 — войти в папку. Кнопки md/pdf/… — фильтр списка; для поиска по всему каталогу введите текст в «Поиск».";
  }

  async function loadTree(path = "") {
    state.cwd = path;
    const chipExt = activeExtChip();
    const data = await api(`/tree?path=${encodeURIComponent(path)}`);
    const el = $("tree");
    el.innerHTML = "";
    if (path) {
      const up = document.createElement("div");
      up.className = "tree-item";
      up.setAttribute("role", "button");
      up.tabIndex = 0;
      up.textContent = "⬆ ..";
      up.onclick = () => {
        const parts = path.split("/");
        parts.pop();
        loadTree(parts.join("/"));
      };
      el.appendChild(up);
    }
    (data.children || []).forEach((c) => {
      if (!matchesExtChip(c, chipExt)) return;
      const row = document.createElement("div");
      row.className = "tree-item" + (c.is_dir ? " tree-dir" : "");
      if (!c.is_dir) row.dataset.path = c.path;
      row.setAttribute("role", "button");
      row.tabIndex = 0;
      const badge = c.branch ? ` [${c.branch}]` : "";
      const label = document.createElement("span");
      label.textContent = (c.is_dir ? "📁 " : "📄 ") + c.name + badge;
      row.appendChild(label);
      if (c.is_dir) {
        const star = document.createElement("span");
        star.className =
          "tree-item__star" +
          (state.starred.includes(c.path) ? " tree-item__star--on" : "");
        star.textContent = " ★";
        star.onclick = (ev) => {
          ev.stopPropagation();
          toggleStarFolder(c.path);
        };
        row.appendChild(star);
      }
      row.onclick = () => {
        if (c.is_dir) loadTree(c.path);
        else openFile(c.path);
      };
      el.appendChild(row);
    });
    $("search-results").hidden = true;
    if (state.currentPath) markTreeSelection(state.currentPath);
    updateTreeHint();
  }

  function canonicalHitBadge(r) {
    if (r.is_primary) {
      return '<span class="hit-badge hit-badge--primary">★ главный</span> ';
    }
    const n = r.duplicate_count || 0;
    if (n > 1) {
      return `<span class="hit-badge hit-badge--dup">копия (${n})</span> `;
    }
    return "";
  }

  function canonicalStatusLine(can) {
    if (!can) return "";
    if (can.is_primary) {
      const dup =
        (can.duplicate_count || 0) > 1
          ? ` · в группе: ${can.duplicate_count}`
          : "";
      const src = can.user_marked ? "ваша метка" : "авто";
      return `★ Главный (${src})${dup}`;
    }
    if ((can.duplicate_count || 0) > 1 && can.primary_path) {
      return `Копия — главный: ${can.primary_path}`;
    }
    return "";
  }

  async function refreshCanonical() {
    const data = await api("/canonical", { silent: true }).catch(() => ({
      marked_paths: [],
    }));
    state.markedPrimary = new Set((data.marked_paths || []).map((p) => p));
    return data;
  }

  async function toggleCanonicalPrimary() {
    if (!state.currentPath) {
      toast("Откройте файл, затем лента → Сервис → ★ Главный", false);
      return;
    }
    const info = await api(
      `/canonical/info?path=${encodeURIComponent(state.currentPath)}`,
      { silent: true }
    );
    if (info.user_marked) {
      await api("/canonical/unmark", {
        method: "POST",
        body: JSON.stringify({ path: state.currentPath }),
      });
      toast("Метка «главный» снята", true);
    } else {
      await api("/canonical/mark", {
        method: "POST",
        body: JSON.stringify({ path: state.currentPath }),
      });
      toast("★ Файл отмечен как главный", true);
    }
    await refreshCanonical();
    const meta = await api(
      `/file/meta?path=${encodeURIComponent(state.currentPath)}`,
      { silent: true }
    );
    applyCanonicalToLabels(meta.canonical);
    if ($("search-input").value.trim()) runSearch();
  }

  function applyCanonicalToLabels(can) {
    const line = canonicalStatusLine(can);
    const banner = $("viewer-banner");
    if (line && banner) {
      banner.hidden = false;
      banner.className = "viewer-banner viewer-banner--canonical";
      banner.textContent = line;
    } else if (banner && banner.classList.contains("viewer-banner--canonical")) {
      banner.hidden = true;
      banner.className = "viewer-banner";
    }
  }

  function updateSaveSearchBtn() {
    const btn = $("btn-save-search");
    if (!btn) return;
    const ok = !!(state.lastSearch && state.lastSearch.results?.length);
    btn.disabled = !ok;
  }

  function updateSaveChatBtn() {
    const btn = $("btn-save-chat");
    if (!btn) return;
    const ok = !!(state.lastChat && state.lastChat.answer);
    btn.disabled = !ok;
  }

  async function saveSearchReport(openAfter) {
    const snap = state.lastSearch;
    if (!snap?.results?.length) {
      toast("Сначала поиск: слово + Enter", false);
      return;
    }
    try {
      const res = await api("/reports/save-search", {
        method: "POST",
        body: JSON.stringify({
          query: snap.query,
          branch: snap.branch || "",
          results: snap.results,
        }),
      });
      toast(`Сохранено: ${res.path}`, true);
      if (openAfter !== false) {
        await openFile(res.path);
      }
    } catch (err) {
      toast(err.message || "Не удалось сохранить поиск", false);
    }
  }

  async function saveChatReport(openAfter) {
    const snap = state.lastChat;
    if (!snap?.answer) {
      toast("Сначала получите ответ в чате (Send)", false);
      return;
    }
    try {
      const res = await api("/reports/save-chat", {
        method: "POST",
        body: JSON.stringify({
          question: snap.question,
          answer: snap.answer,
          path: snap.path || "",
        }),
      });
      toast(`Сохранено: ${res.path}`, true);
      if (openAfter !== false) {
        await openFile(res.path);
      }
    } catch (err) {
      toast(err.message || "Не удалось сохранить ответ", false);
    }
  }

  async function runSearch() {
    const q = $("search-input").value.trim();
    const branch = $("branch-filter").value;
    if (!q) {
      state.lastSearch = null;
      updateSaveSearchBtn();
      loadTree(state.cwd);
      updateTreeHint();
      return;
    }
    const indexed = state.lastHealth?.files_indexed ?? 0;
    if (indexed === 0) {
      toast("Индекс пуст — сначала Scan (кнопка справа в ленте), затем снова Enter в поиске", false);
      updateTreeHint();
      return;
    }
    updateTreeHint();
    let url = `/search?q=${encodeURIComponent(q)}`;
    if (branch) url += `&branch=${encodeURIComponent(branch)}`;
    const chipOn = document.querySelector("#ext-chips .chip--on");
    const ext = chipOn?.dataset?.ext;
    if (ext) url += `&ext=${encodeURIComponent(ext)}`;
    const data = await api(url);
    const results = data.results || [];
    state.lastSearch = { query: q, branch, results };
    updateSaveSearchBtn();
    const box = $("search-results");
    box.innerHTML = "";
    if (!results.length) {
      const empty = document.createElement("div");
      empty.className = "search-empty";
      const branchNote = branch ? `, ветка «${branch}»` : "";
      empty.textContent = `Ничего не найдено по «${q}»${branchNote}. Выберите «Ветка: все» или другой запрос.`;
      box.appendChild(empty);
    } else {
      results.forEach((r) => {
        const d = document.createElement("div");
        d.className = "hit";
        d.dataset.path = r.path;
        const snip = r.snippet
          ? `<br><small class="hit-snippet">${escapeHtml(r.snippet)}</small>`
          : "";
        d.innerHTML = `${canonicalHitBadge(r)}<strong>${escapeHtml(r.name)}</strong><br><small>${escapeHtml(r.path)}</small>${snip}`;
        d.onclick = () => openFile(r.path);
        d.oncontextmenu = (ev) => {
          ev.preventDefault();
          openFile(r.path).then(() => toggleCanonicalPrimary());
        };
        box.appendChild(d);
      });
    }
    box.hidden = false;
    $("tree").innerHTML = "";
    const capped = results.length >= 100 ? " (первые 100)" : "";
    toast(
      results.length ? `Найдено: ${results.length}${capped}` : "Нет совпадений в индексе",
      results.length > 0
    );
  }

  function pushRecent(path) {
    state.recent = [path, ...state.recent.filter((p) => p !== path)].slice(0, 10);
    localStorage.setItem("avioraRecent", JSON.stringify(state.recent));
    const ul = $("recent-list");
    ul.innerHTML = "";
    state.recent.forEach((p) => {
      const li = document.createElement("li");
      li.className = "list-row";
      li.textContent = p;
      li.title = p;
      li.onclick = () => openFile(p);
      ul.appendChild(li);
    });
  }

  function normText(s) {
    return (s || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  }

  function mdPreviewLocal(text) {
    const lines = String(text || "").split(/\r?\n/);
    const out = [];
    let inPre = false;
    for (const line of lines) {
      if (line.trim().startsWith("```")) {
        inPre = !inPre;
        out.push(inPre ? "<pre>" : "</pre>");
        continue;
      }
      if (inPre) {
        out.push(escapeHtml(line));
        continue;
      }
      if (line.startsWith("# ")) out.push(`<h1>${escapeHtml(line.slice(2).trim())}</h1>`);
      else if (line.startsWith("## "))
        out.push(`<h2>${escapeHtml(line.slice(3).trim())}</h2>`);
      else if (!line.trim()) out.push("<br/>");
      else out.push(`<p>${escapeHtml(line)}</p>`);
    }
    if (inPre) out.push("</pre>");
    return out.join("");
  }

  async function renderWordPreview(path, text) {
    const box = $("word-preview");
    if (!box) return;
    const safePath = path && String(path).trim();
    let html = mdPreviewLocal(text);
    try {
      const payload = { target: "html_snippet", content: String(text ?? "") };
      if (safePath) payload.path = safePath;
      const data = await api("/convert", {
        method: "POST",
        silent: true,
        body: JSON.stringify(payload),
      });
      if (data.html) html = data.html;
    } catch {
      /* локальное превью уже в html */
    }
    box.innerHTML = `<div class="word-doc__page">${html}</div>`;
  }

  function boardPathForFile(filePath) {
    if (!filePath) return null;
    return filePath.replace(/\.[^.]+$/, "") + ".aviora.json";
  }

  function setTextMode(mode) {
    state.textMode = mode;
    const ws = $("text-workspace");
    const fw = $("figma-workspace");
    if (!ws) return;

    ["btn-mode-both", "btn-mode-word", "btn-mode-edit", "btn-mode-figma"].forEach((id) => {
      const b = $(id);
      if (b) b.classList.remove("text-mode-btn--on");
    });

    if (mode === "figma") {
      ws.hidden = true;
      if (fw) fw.hidden = false;
      $("btn-mode-figma")?.classList.add("text-mode-btn--on");
      const bp = boardPathForFile(state.currentPath);
      const lbl = $("figma-board-path");
      if (lbl) lbl.textContent = bp || "(откройте файл .md)";
      loadFigmaBoard();
      return;
    }

    if (fw) fw.hidden = true;
    ws.hidden = false;
    ws.classList.remove(
      "text-workspace--word",
      "text-workspace--edit",
      "text-workspace--both",
      "text-workspace--code"
    );
    const m =
      mode === "word" ? "word" : mode === "edit" ? "edit" : "both";
    ws.classList.add(`text-workspace--${m}`);
    $(`btn-mode-${m}`)?.classList.add("text-mode-btn--on");

    const wp = $("word-preview");
    const ed = $("editor");
    if (wp) wp.removeAttribute("hidden");
    if (ed) ed.removeAttribute("hidden");

    const text = ed?.value ?? "";
    if (state.currentPath && m !== "edit") {
      renderWordPreview(state.currentPath, text);
    }
    if (m === "edit" || m === "both") ed?.focus();
  }

  function hideViewers() {
    [
      "viewer-empty",
      "text-workspace",
      "figma-workspace",
      "pdf-view",
      "image-workspace",
      "preview-text",
      "zip-panel",
      "audio-workspace",
      "props-panel",
      "find-bar",
    ].forEach((id) => {
      const el = $(id);
      if (el) el.hidden = true;
    });
    if (state.cropper) {
      state.cropper.destroy();
      state.cropper = null;
    }
    if (previewTimer) {
      clearTimeout(previewTimer);
      previewTimer = null;
    }
  }

  function formatFileSize(bytes) {
    if (bytes == null || Number.isNaN(bytes)) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatAudioMetaLine(ameta) {
    if (!ameta) return "";
    const parts = [];
    if (ameta.duration_sec != null) {
      const s = Math.round(ameta.duration_sec);
      const m = Math.floor(s / 60);
      parts.push(`${m}:${String(s % 60).padStart(2, "0")}`);
    }
    if (ameta.title) parts.push(ameta.title);
    if (ameta.artist) parts.push(ameta.artist);
    return parts.join(" · ");
  }

  function showAudioWorkspace(path, data, metaLine) {
    $("audio-workspace").hidden = false;
    const props = $("props-panel");
    if (props) props.hidden = true;
    const player = $("audio-player");
    if (player) {
      player.src = data.url || `/file/raw?path=${encodeURIComponent(path)}`;
      player.load();
    }
    const ta = $("audio-transcript");
    if (ta) ta.value = data.transcript || "";
    const metaLbl = $("audio-meta-label");
    if (metaLbl) {
      const extra = formatAudioMetaLine(data.audio_meta);
      metaLbl.textContent = `${path} — ${metaLine}${extra ? " · " + extra : ""}`;
    }
    const openMd = $("btn-audio-open-md");
    if (openMd) {
      if (data.transcript_path) {
        openMd.hidden = false;
        openMd.onclick = () => openFile(data.transcript_path);
      } else {
        openMd.hidden = true;
      }
    }
    const st = $("audio-transcribe-status");
    if (st) {
      if (!data.whisper_ok) {
        st.hidden = false;
        st.textContent =
          "Whisper не установлен: pip install faster-whisper (+ ffmpeg в PATH)";
      } else if (data.has_transcript) {
        st.hidden = false;
        st.textContent = "Транскрипт в индексе — поиск по тексту после Scan";
      } else {
        st.hidden = true;
        st.textContent = "";
      }
    }
    document.title = path + " ⟨audio⟩";
  }

  async function startAudioTranscribe() {
    if (!state.currentPath) {
      toast("Откройте .mp3 / .wav / .m4a в дереве", false);
      return;
    }
    const ext = (state.currentPath.match(/\.[^.]+$/) || [""])[0].toLowerCase();
    if (!AUDIO_EXTS.has(ext)) {
      toast("Не аудиофайл", false);
      return;
    }
    let meta = null;
    try {
      meta = await api(
        `/file/meta?path=${encodeURIComponent(state.currentPath)}`,
        { silent: true }
      );
    } catch (_) {
      meta = null;
    }
    const dur = meta?.audio_meta?.duration_sec ?? meta?.duration_sec;
    if (dur && dur >= 45 * 60) {
      const mins = Math.round(dur / 60);
      if (
        !confirm(
          `Запись ~${mins} мин (~${Math.round(mins / 60)} ч). ` +
            "На CPU транскрипция может занять 1–3+ часа. Запустить?"
        )
      ) {
        return;
      }
    }
    if (state.transcribeJobId) {
      toast("Транскрипция уже идёт — смотрите полосу под лентой", false);
      showTranscribeProgress(true, { progress: 0, total: 100, message: "Уже запущено…" });
      return;
    }
    showTranscribeProgress(true, {
      progress: 0,
      total: 100,
      message: "Запуск…",
      status: "pending",
    });
    toast("Транскрипция запущена — полоса под лентой, можно работать в каталоге", true);
    try {
      const { job_id } = await api("/audio/transcribe/start", {
        method: "POST",
        body: JSON.stringify({ path: state.currentPath }),
      });
      state.transcribeJobId = job_id;
      saveTranscribeJob(job_id, state.currentPath);
      pollTranscribe();
    } catch (err) {
      showTranscribeProgress(false);
      toast(err.message || "Транскрипт недоступен", false);
    }
  }

  async function pollTranscribe() {
    if (!state.transcribeJobId) return;
    let st;
    try {
      st = await api(`/audio/transcribe/status/${state.transcribeJobId}`, {
        silent: true,
      });
    } catch {
      state.transcribeJobId = null;
      clearTranscribeJob();
      showTranscribeProgress(false);
      toast(
        "Связь с задачей потеряна (сервер выключен?). Запустите start-api.bat и Транскрипт снова.",
        false
      );
      return;
    }
    renderTranscribeProgress(st);
    showTranscribeProgress(true, st);
    const hint = $("audio-transcribe-status");
    if (hint) {
      hint.hidden = false;
      hint.textContent = st.message || st.current || "…";
    }
    if (st.status === "running" || st.status === "pending") {
      setTimeout(pollTranscribe, 700);
      return;
    }
    state.transcribeJobId = null;
    clearTranscribeJob();
    if (st.status === "done") {
      const chars = st.result?.chars;
      showTranscribeProgress(true, {
        progress: 100,
        total: 100,
        doneLabel: "Транскрипт готов",
        message: chars ? `Символов: ${chars}` : "Готово",
        status: "done",
      });
      toast("Транскрипт готов — текст ниже и в 05data/aviora_audio_transcripts", true);
      setTimeout(() => showTranscribeProgress(false), 8000);
      await openFile(state.currentPath);
      pollHealth();
      return;
    }
    if (st.status === "cancelled") {
      showTranscribeProgress(false);
      toast("Транскрипция отменена", false);
      return;
    }
    showTranscribeProgress(false);
    toast(st.error || "Ошибка транскрипции", false);
    if (hint) hint.textContent = st.error || "error";
  }

  async function openFile(path) {
    const parent = path.includes("/") ? path.split("/").slice(0, -1).join("/") : "";
    if (parent !== state.cwd) {
      await loadTree(parent);
    }
    state.currentPath = path;
    pushRecent(path);
    markTreeSelection(path);
    hideViewers();
    const meta = await api(`/file/meta?path=${encodeURIComponent(path)}`);
    const props = $("props-panel");
    const sz = formatFileSize(meta.size);
    const metaLine = `${meta.name} · ${sz} · ${meta.ext || ""}`;

    const data = await api(`/file/content?path=${encodeURIComponent(path)}`);
    $("viewer-empty").hidden = true;

    if (data.banner === "secrets") {
      $("viewer-banner").hidden = false;
      $("viewer-banner").className = "viewer-banner";
      $("viewer-banner").textContent = data.warning || "Секреты — только просмотр";
    } else {
      applyCanonicalToLabels(meta.canonical);
    }

    if (data.kind === "text") {
      const ed = $("editor");
      const text = data.content || "";
      ed.value = text;
      ed.readOnly = !!data.read_only || state.readOnly;
      ed.classList.remove("editor--code");
      $("text-workspace").hidden = false;
      props.hidden = true;
      const lbl = $("save-path-label");
      if (lbl) lbl.textContent = `${path} — ${metaLine}`;
      setTextMode("both");
      initUndoHistory(path, text);
      await renderWordPreview(path, text);
      state.dirty = false;
      document.title = path;
      return;
    }
    if (data.kind === "code") {
      const ed = $("editor");
      const text = data.content || "";
      ed.value = text;
      ed.readOnly = true;
      ed.classList.add("editor--code");
      $("text-workspace").hidden = false;
      $("text-workspace").classList.add("text-workspace--code");
      props.hidden = true;
      const lbl = $("save-path-label");
      if (lbl) {
        lbl.textContent =
          `${path} — ${metaLine} · только просмотр · Снимок → 05data/aviora_code_snapshots`;
      }
      setTextMode("edit");
      initUndoHistory(path, text);
      state.dirty = false;
      document.title = path + " ⟨code⟩";
      toast("Код: Ctrl+S не меняет оригинал. Лента → Снимок — дубликат с индексом SEQ", true);
      return;
    }
    props.hidden = false;
    props.textContent = [
      meta.name,
      "path: " + meta.path,
      "size: " + sz,
      "mtime: " + (meta.mtime || ""),
      "ext: " + (meta.ext || ""),
      "branch: " + (meta.branch || "—"),
    ].join("\n");

    if (data.kind === "audio") {
      showAudioWorkspace(path, data, metaLine);
      toast(
        data.has_transcript
          ? "Аудио + транскрипт. Плеер сверху, текст ниже"
          : "Аудио: Транскрипт — распознавание (нужен faster-whisper)",
        true
      );
      return;
    }
    if (data.kind === "pdf") {
      $("pdf-view").hidden = false;
      $("pdf-view").src = `/file/raw?path=${encodeURIComponent(path)}`;
      return;
    }
    if (data.kind === "image") {
      $("image-workspace").hidden = false;
      const img = $("crop-image");
      img.src = `/file/raw?path=${encodeURIComponent(path)}`;
      img.onload = () => {
        if (state.cropper) state.cropper.destroy();
        state.cropper = new Cropper(img, { viewMode: 1 });
      };
      return;
    }
    if (data.kind === "docx_preview" || data.kind === "xlsx_preview") {
      $("preview-text").hidden = false;
      $("preview-text").textContent = data.preview || "(пусто)";
      return;
    }
    if (data.kind === "view_only" || data.kind === "binary") {
      $("viewer-empty").hidden = false;
      $("viewer-empty").innerHTML =
        `<p><strong>${escapeHtml(meta.name)}</strong> — на диске есть.</p>` +
        `<p>${escapeHtml(data.message || "Редактирование только .md и .txt в этом окне.")}</p>` +
        `<p>Для правки откройте файл в <strong>Cursor / VS Code</strong> (проводник Windows не заменён).</p>` +
        (data.download
          ? `<p><a href="${data.download}" target="_blank" rel="noopener">Скачать / открыть raw</a></p>`
          : "");
      return;
    }
    if (data.kind === "zip") {
      const z = await api("/archive/zip/list", {
        method: "POST",
        body: JSON.stringify({ path }),
      });
      $("zip-panel").hidden = false;
      const ul = $("zip-list");
      ul.innerHTML = "";
      (z.entries || []).forEach((e) => {
        const li = document.createElement("li");
        li.textContent = e;
        ul.appendChild(li);
      });
      $("zip-extract").onclick = async () => {
        await api("/archive/zip/extract", {
          method: "POST",
          body: JSON.stringify({ path, dest: path.split("/").slice(0, -1).join("/") }),
        });
        toast("Extracted");
        loadTree(state.cwd);
      };
      return;
    }
    $("viewer-empty").hidden = false;
    $("viewer-empty").textContent = "Просмотр не поддерживается для этого типа.";
  }

  async function saveFile(asPath) {
    syncReadOnlyFromUi();
    const target = (asPath || state.currentPath || "").replace(/\\/g, "/").trim();
    if (state.readOnly) {
      toast("Включён Read-only — снимите галочку справа вверху", false);
      return;
    }
    if (!target) {
      toast("Сначала откройте файл (.md или .txt)", false);
      return;
    }
    if ($("text-workspace").hidden) {
      toast("Этот файл нельзя править в Catalog — только .md / .txt", false);
      return;
    }
    const content = String($("editor").value ?? "");
    try {
      const res = await api("/file/content", {
        method: "PUT",
        body: JSON.stringify({
          path: target,
          content,
          encoding: "utf-8",
        }),
      });
      if (!res?.ok) {
        toast("Сервер не подтвердил сохранение", false);
        return;
      }
      state.dirty = false;
      document.title = target;
      undoHist.snap = content;
      undoHist.redo = [];
      toast(`Сохранено на диск: ${target}`, true);
      if (state.textMode === "both" || state.textMode === "word") {
        await renderWordPreview(target, content);
      }
      try {
        const verify = await api(
          `/file/content?path=${encodeURIComponent(target)}`,
          { silent: true }
        );
        if (normText(verify.content) !== normText(content)) {
          toast("Файл записан; при проверке отличались переводы строк", true);
        }
      } catch {
        /* уже сохранено */
      }
      const parent = target.includes("/")
        ? target.split("/").slice(0, -1).join("/")
        : "";
      await loadTree(parent);
      markTreeSelection(target);
    } catch (err) {
      if (err.message === "ERR_READ_ONLY") {
        toast(
          "Сохранение заблокировано: Read-only (галочка справа или READ_ONLY в .env)",
          false
        );
      }
    }
  }

  async function saveFileAs() {
    if (!state.currentPath || state.readOnly) return;
    const name = prompt("Сохранить как (относительный путь):", state.currentPath);
    if (!name) return;
    await saveFile(name.replace(/\\/g, "/"));
  }

  function openPathDialog() {
    $("open-path-input").value = state.currentPath || state.cwd || "";
    $("open-modal").hidden = false;
    $("open-path-input").focus();
  }

  function toggleFindBar(show) {
    if ($("text-workspace").hidden && $("figma-workspace").hidden) return;
    if ($("figma-workspace") && !$("figma-workspace").hidden) return;
    setTextMode("edit");
    const on = show !== undefined ? show : $("find-bar").hidden;
    $("find-bar").hidden = !on;
    if (on) $("find-input").focus();
  }

  function findInEditor(dir) {
    const ed = $("editor");
    if (ed.hidden) return;
    const needle = $("find-input").value;
    if (!needle) return;
    const text = ed.value;
    const start = dir > 0 ? ed.selectionEnd : ed.selectionStart - 1;
    let idx = text.indexOf(needle, Math.max(0, start));
    if (idx < 0 && dir < 0) idx = text.lastIndexOf(needle);
    if (idx < 0) {
      toast("Не найдено", false);
      return;
    }
    ed.focus();
    ed.setSelectionRange(idx, idx + needle.length);
    state.findIdx = idx;
  }

  async function revealExplorer() {
    const p = state.currentPath || state.cwd;
    if (!p) {
      toast("Нет пути", false);
      return;
    }
    await api(`/explorer/reveal?path=${encodeURIComponent(p)}`);
    toast("Проводник");
  }

  async function startScan() {
    if (state.scanJobId) {
      toast("Сканирование уже идёт — смотрите полосу прогресса", false);
      return;
    }
    const est = await api("/scan/estimate");
    const msg = `Сканировать ~${est.total} файлов?\nКорень: ${est.catalog_root}`;
    if (!confirm(msg)) return;
    showScanProgress(true, {
      progress: 0,
      total: est.total,
      current: "Запуск…",
      status: "pending",
    });
    toast("Сканирование запущено — полоса под лентой", true);
    const { job_id } = await api("/scan/start", { method: "POST" });
    state.scanJobId = job_id;
    state.scanStallAt = Date.now();
    pollScan();
  }

  function endScanProgress(st, ok) {
    const n = st.result?.indexed ?? st.progress ?? "?";
    const doneLabel =
      st.status === "cancelled"
        ? `Скан отменён (${n} файлов в индексе)`
        : `Скан готов: ${n} файлов`;
    renderScanProgress({
      progress: st.progress,
      total: st.total,
      current: st.current,
      doneLabel,
    });
    const fill = $("scan-progress-fill");
    if (fill && st.status !== "cancelled") fill.style.width = "100%";
    setTimeout(() => showScanProgress(false), ok ? 5000 : 3500);
  }

  async function pollScan() {
    if (!state.scanJobId) return;
    const st = await api(`/scan/status/${state.scanJobId}`);
    renderScanProgress(st);
    if (st.progress > 0) state.scanStallAt = Date.now();
    if (Date.now() - state.scanStallAt > 120000) {
      state.scanJobId = null;
      showScanProgress(false);
      showError("ERR_SCAN_HANG", "Сканирование зависло");
      pollHealth();
      return;
    }
    if (st.status === "running" || st.status === "pending") {
      setTimeout(pollScan, 500);
      return;
    }
    state.scanJobId = null;
    const ok = st.status !== "cancelled";
    if (st.status === "cancelled") {
      toast("Скан отменён — индекс неполный, запустите Scan снова", false);
    } else {
      const n = st.result?.indexed ?? st.progress ?? "?";
      const dg = st.result?.duplicate_groups;
      const dupNote =
        dg != null ? ` · групп дубликатов: ${dg}` : "";
      toast(`Скан готов: ${n} файлов в индексе${dupNote}`, true);
    }
    endScanProgress(st, ok);
    pollHealth();
    runSearch();
  }

  async function stopAll() {
    if (state.transcribeJobId) {
      await cancelTranscribe();
      state.transcribeJobId = null;
      showTranscribeProgress(false);
    }
    if (state.scanJobId) {
      await api(`/scan/cancel/${state.scanJobId}`, { method: "POST" });
      state.scanJobId = null;
      showScanProgress(false);
      pollHealth();
    }
    await api("/chat/cancel", { method: "POST" });
    setChatBusy(false);
    toast("Остановлено");
  }

  async function resetSession() {
    if (!confirm("Сбросить сессию? Файлы на диске не удаляются.")) return;
    await api("/session/reset", { method: "POST" });
    state.markedPrimary = new Set();
    state.currentPath = null;
    state.dirty = false;
    hideViewers();
    $("viewer-empty").hidden = false;
    loadTree("");
    pollHealth();
    toast("Сессия сброшена");
  }

  function downloadBlob(content, filename, mime) {
    const blob = new Blob([content], {
      type: mime || "application/octet-stream",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function exportCurrentFile() {
    const path = state.currentPath;
    if (!path || $("text-workspace").hidden) {
      toast("Откройте .md или .txt для экспорта", false);
      return;
    }
    const fmt = $("export-format")?.value || "html";
    const base =
      path
        .split("/")
        .pop()
        ?.replace(/\.[^.]+$/, "") || "export";
    const content = $("editor").value;
    try {
      if (fmt === "txt") {
        downloadBlob(content, `${base}.txt`, "text/plain;charset=utf-8");
        toast(`Скачан ${base}.txt`);
        return;
      }
      if (fmt === "html") {
        const payload = { target: "html_snippet", content };
        if (path) payload.path = path;
        const data = await api("/convert", {
          method: "POST",
          silent: true,
          body: JSON.stringify(payload),
        });
        const page = `<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>${escapeHtml(base)}</title><style>body{font-family:Calibri,Segoe UI,sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem}</style></head><body>${data.html || mdPreviewLocal(content)}</body></html>`;
        downloadBlob(page, `${base}.html`, "text/html;charset=utf-8");
        toast(`Скачан ${base}.html`);
        return;
      }
      if (fmt === "docx") {
        toast(
          "DOCX в v0.2 (pandoc). Сейчас: «HTML» или сохраните .md (Ctrl+S)",
          false
        );
      }
    } catch {
      toast("Экспорт не удался", false);
    }
  }

  async function sharePath() {
    const path = state.currentPath || state.cwd;
    if (!path) {
      toast("Сначала откройте файл или папку слева", false);
      return;
    }
    const data = await api("/share", {
      method: "POST",
      body: JSON.stringify({ path: state.currentPath || state.cwd }),
    });
    const text = `${data.relative}\n${data.absolute}`;
    const copyFn = async () => {
      try {
        await navigator.clipboard.writeText(text);
        toast("Путь скопирован в буфер");
      } catch {
        toast("Не удалось скопировать — выделите текст в окне", false);
      }
    };
    if (navigator.share) {
      try {
        await navigator.share({
          title: "AIKIVAVIORA Catalog",
          text: data.relative,
        });
        toast("Поделились");
        return;
      } catch {
        /* fallback modal */
      }
    }
    await copyFn();
    openModal(
      "Поделиться",
      `Путь скопирован в буфер.\n\nОтносительный:\n${data.relative}\n\nПолный:\n${data.absolute}\n\nПубличная ссылка и почта — в v0.2 (SMTP).`,
      [{ label: "Копировать снова", fn: copyFn }]
    );
  }

  function renderFigmaCanvas() {
    const canvas = $("figma-canvas");
    if (!canvas) return;
    canvas.innerHTML = "";
    state.boardElements.forEach((el) => {
      const node = document.createElement("div");
      node.className =
        "figma-node" +
        (el.type === "frame" ? " figma-node--frame" : "") +
        (state.figmaSelId === el.id ? " figma-node--sel" : "");
      node.style.left = `${el.x}px`;
      node.style.top = `${el.y}px`;
      node.style.width = `${el.w}px`;
      node.style.height = `${el.h}px`;
      node.textContent = el.text || "";
      node.dataset.id = el.id;
      node.onmousedown = (ev) => startFigmaDrag(ev, el.id);
      node.onclick = (ev) => {
        ev.stopPropagation();
        state.figmaSelId = el.id;
        renderFigmaCanvas();
      };
      canvas.appendChild(node);
    });
    canvas.onclick = () => {
      state.figmaSelId = null;
      renderFigmaCanvas();
    };
  }

  function startFigmaDrag(ev, id) {
    ev.preventDefault();
    const el = state.boardElements.find((x) => x.id === id);
    if (!el) return;
    state.figmaSelId = id;
    const startX = ev.clientX;
    const startY = ev.clientY;
    const ox = el.x;
    const oy = el.y;
    const move = (e) => {
      el.x = Math.max(0, ox + e.clientX - startX);
      el.y = Math.max(0, oy + e.clientY - startY);
      renderFigmaCanvas();
    };
    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  }

  function addFigmaNode(type) {
    const id = `n${Date.now()}`;
    state.boardElements.push({
      id,
      type,
      x: 24 + state.boardElements.length * 18,
      y: 24 + state.boardElements.length * 18,
      w: type === "frame" ? 220 : 160,
      h: type === "frame" ? 140 : 90,
      text:
        type === "frame"
          ? "Рамка"
          : prompt("Текст стикера:", "Идея") || "Стикер",
    });
    state.figmaSelId = id;
    renderFigmaCanvas();
  }

  async function loadFigmaBoard() {
    const bp = boardPathForFile(state.currentPath);
    if (!bp) {
      state.boardElements = [];
      renderFigmaCanvas();
      return;
    }
    try {
      const data = await api(`/board?path=${encodeURIComponent(bp)}`, {
        silent: true,
      });
      state.boardElements = Array.isArray(data.elements) ? data.elements : [];
    } catch {
      state.boardElements = [];
    }
    renderFigmaCanvas();
  }

  async function saveFigmaBoard() {
    syncReadOnlyFromUi();
    if (state.readOnly) {
      toast("Read-only — макет не сохранить", false);
      return;
    }
    const bp = boardPathForFile(state.currentPath);
    if (!bp) {
      toast("Откройте .md/.txt — макет привязан к файлу", false);
      return;
    }
    try {
      await api("/board", {
        method: "PUT",
        body: JSON.stringify({
          path: bp,
          data: { version: 1, elements: state.boardElements },
        }),
      });
      toast(`Макет сохранён: ${bp}`, true);
      const parent = bp.includes("/") ? bp.split("/").slice(0, -1).join("/") : "";
      await loadTree(parent);
    } catch (err) {
      if (err.message === "ERR_READ_ONLY") {
        toast("Read-only — снимите галочку", false);
      }
    }
  }

  function openFigmaStudio() {
    if (!state.currentPath) {
      toast("Сначала откройте файл слева", false);
      return;
    }
    $("viewer-empty").hidden = true;
    ["pdf-view", "image-workspace", "preview-text", "zip-panel"].forEach((id) => {
      const el = $(id);
      if (el) el.hidden = true;
    });
    setTextMode("figma");
  }

  function showStudioHelp() {
    const imgOpen = state.currentPath && IMG_EXTS.has(
      (state.currentPath.match(/\.[^.]+$/) || [""])[0].toLowerCase()
    );
    const html = `
      <h2>Студия</h2>
      <h3>Фото (Photoshop-lite)</h3>
      <p>Откройте <strong>.jpg / .png</strong> → Crop, поворот, <strong>Save image</strong>.</p>
      <p>${imgOpen ? "✓ Открыто изображение." : "Сейчас не изображение."}</p>
      <h3>Макет (Figma-lite)</h3>
      <p>Вкладка <strong>Макет (Figma)</strong> или кнопка <strong>Студия</strong>: рамки и стикеры → <strong>Сохранить макет</strong> → файл <code>имя.aviora.json</code> рядом с .md.</p>
      <h3>Текст</h3>
      <p><strong>Превью + правка</strong>: лист Word сверху, кнопка <strong>Сохранить</strong> под превью, редактор снизу.</p>
    `;
    $("help-content").innerHTML = html;
    $("help-overlay").hidden = false;
  }

  function scrollChatToBottom() {
    const box = $("chat-messages");
    if (box) box.scrollTop = box.scrollHeight;
  }

  function appendChatBubble(role, text) {
    const box = $("chat-messages");
    if (!box) return null;
    const el = document.createElement("div");
    el.className =
      role === "user"
        ? "chat-bubble chat-bubble--user"
        : "chat-bubble chat-bubble--bot";
    el.textContent = text;
    box.appendChild(el);
    scrollChatToBottom();
    return el;
  }

  async function submitChat() {
    if (state.chatInFlight) {
      toast("Подождите ответ на предыдущий вопрос (не жмите Stop)", false);
      return;
    }
    if (!state.llmEnabled) {
      toast("LLM выключен — кликните ON в шапке", false);
      return;
    }
    const msg = ($("chat-input")?.value || "").trim();
    if (!msg) {
      toast("Введите вопрос в чат (справа внизу)", false);
      $("chat-input")?.focus();
      return;
    }
    const indexed = state.lastHealth?.files_indexed ?? 0;
    if (indexed < 50) {
      toast(
        `В индексе ${indexed} файлов — для поиска и чата по каталогу нужен Scan (~3500)`,
        false
      );
    }
    state.chatInFlight = true;
    setChatBusy(true);
    appendChatBubble("user", msg);
    $("chat-input").value = "";
    const wait = appendChatBubble("bot", "Думаю… (LM Studio / DeepSeek)");
    state.llmStallAt = Date.now();
    try {
      const res = await api("/chat", {
        method: "POST",
        quiet: true,
        body: JSON.stringify({
          message: msg,
          ...(state.currentPath ? { path: state.currentPath } : {}),
          provider: $("llm-provider")?.value || "auto",
        }),
      });
      let answer = (res.answer || "").trim();
      if (res.cancelled) {
        answer =
          "Запрос отменён (Stop). Перезапустите backend :8002 (v0.3.10) и обновите страницу Ctrl+Shift+R.";
        await resetStuckChatCancel();
      }
      else if (!answer) {
        answer =
          "Пустой ответ модели. Запустите LM Studio → Load model → Start server (:1234), " +
          "или укажите ключ DeepSeek в .env.";
      }
      const providerTag = res.provider ? `\n\n[${res.provider}]` : "";
      const answerForSave = (res.answer || "").trim();
      const answerDisplay = answerForSave + providerTag;
      state.lastChat = {
        question: msg,
        answer: answerForSave,
        path: state.currentPath || "",
      };
      updateSaveChatBtn();
      if (wait) wait.textContent = answerDisplay;
      else appendChatBubble("bot", answerDisplay);
      scrollChatToBottom();
      pollHealth();
      toast("Ответ в чате — 💾 Ответ сохранит в .md", true);
    } catch (err) {
      let errText = "Ошибка чата — см. подсказку внизу";
      if (err.message === "ERR_LLM") {
        const detail = String(err.detail || err.cause || "");
        if (detail.includes("400")) {
          errText =
            "LM Studio 400: загрузите модель и Start Server :1234. " +
            "В шапке должна быть та же модель, что в LM Studio (не local-model).";
        } else {
          errText = "LLM недоступен: LM Studio :1234 или ключ DeepSeek в .env";
        }
      }
      if (wait) wait.textContent = errText;
      else appendChatBubble("bot", errText);
      scrollChatToBottom();
    } finally {
      state.chatInFlight = false;
      setChatBusy(false);
    }
  }

  function bindChat() {
    const form = $("chat-form");
    if (!form || form.dataset.bound === "1") return;
    form.dataset.bound = "1";
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      submitChat();
    });
    $("btn-chat-send")?.addEventListener("click", (e) => {
      e.preventDefault();
      submitChat();
    });
    $("chat-input")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitChat();
      }
    });
  }

  function bindShareButtons() {
    const handler = (e) => {
      e.preventDefault();
      e.stopPropagation();
      sharePath();
    };
    ["btn-share", "btn-share-inline"].forEach((id) => {
      const el = $(id);
      if (!el || el.dataset.boundShare === "1") return;
      el.dataset.boundShare = "1";
      el.addEventListener("click", handler);
    });
  }

  function bindSaveButtons() {
    const handler = (e) => {
      e.preventDefault();
      e.stopPropagation();
      saveFile();
    };
    ["btn-save", "btn-save-inline"].forEach((id) => {
      const el = $(id);
      if (!el || el.dataset.bound === "1") return;
      el.dataset.bound = "1";
      el.addEventListener("click", handler);
    });
  }

  function initUndoHistory(path, text) {
    undoHist.path = path;
    undoHist.stack = [];
    undoHist.redo = [];
    undoHist.snap = text;
    updateUndoRedoButtons();
  }

  function updateUndoRedoButtons() {
    const u = $("btn-undo");
    const r = $("btn-redo");
    if (u) u.disabled = undoHist.stack.length === 0;
    if (r) r.disabled = undoHist.redo.length === 0;
  }

  function applyEditorContent(text) {
    const ed = $("editor");
    if (!ed) return;
    ed.value = text;
    undoHist.snap = text;
    state.dirty = true;
    document.title = (state.currentPath || "") + " ●";
    if (
      state.currentPath &&
      (state.textMode === "both" || state.textMode === "word")
    ) {
      renderWordPreview(state.currentPath, text);
    }
  }

  function commitUndoSnapshot() {
    const ed = $("editor");
    if (!ed || $("text-workspace").hidden) return;
    const v = ed.value;
    if (v === undoHist.snap) return;
    undoHist.stack.push(undoHist.snap);
    if (undoHist.stack.length > 100) undoHist.stack.shift();
    undoHist.snap = v;
    undoHist.redo = [];
    updateUndoRedoButtons();
  }

  function editorUndo() {
    if (!undoHist.stack.length) return;
    undoHist.redo.push($("editor").value);
    const prev = undoHist.stack.pop();
    applyEditorContent(prev);
    updateUndoRedoButtons();
  }

  function editorRedo() {
    if (!undoHist.redo.length) return;
    undoHist.stack.push($("editor").value);
    const next = undoHist.redo.pop();
    applyEditorContent(next);
    updateUndoRedoButtons();
  }

  function switchRibbonTab(tab) {
    document.querySelectorAll(".ribbon-tab").forEach((el) => {
      const on = el.dataset.tab === tab;
      el.classList.toggle("ribbon-tab--on", on);
      el.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll(".ribbon-page").forEach((page) => {
      page.hidden = page.dataset.page !== tab;
    });
  }

  function formatDiffHtml(text) {
    return (text || "")
      .split("\n")
      .map((line) => {
        let cls = "";
        if (
          line.startsWith("+++") ||
          line.startsWith("---") ||
          line.startsWith("@@")
        ) {
          cls = "diff-line--hdr";
        } else if (line.startsWith("+")) cls = "diff-line--add";
        else if (line.startsWith("-")) cls = "diff-line--del";
        return `<span class="${cls}">${escapeHtml(line)}</span>`;
      })
      .join("\n");
  }

  function toggleDiffModal(open) {
    const modal = $("diff-modal");
    if (!modal) return;
    const on = open !== undefined ? open : modal.hidden;
    modal.hidden = !on;
  }

  async function openDiffModal() {
    toggleDiffModal(true);
    const b = $("diff-path-b");
    const a = $("diff-path-a");
    if (b && state.currentPath && !b.value) b.value = state.currentPath;
    try {
      const recent = await api("/code/snapshots/recent?limit=8", { quiet: true });
      const items = recent.items || [];
      if (items.length && a && !a.value) {
        a.value = String(items[0].seq || "");
        $("diff-summary").textContent =
          `Подсказка: последний снимок SEQ ${items[0].seq} → ${items[0].source_path || ""}`;
      }
    } catch {
      /* ignore */
    }
  }

  async function runCodeDiff() {
    const pathA = ($("diff-path-a")?.value || "").trim();
    const pathB = ($("diff-path-b")?.value || "").trim();
    if (!pathA || !pathB) {
      toast("Укажите стороны A и B (путь или SEQ)", false);
      return;
    }
    try {
      const res = await api("/code/diff", {
        method: "POST",
        quiet: true,
        body: JSON.stringify({ path_a: pathA, path_b: pathB }),
      });
      const sim = ((res.similarity || 0) * 100).toFixed(1);
      $("diff-summary").textContent =
        `${res.path_a} ↔ ${res.path_b} · схожесть ${sim}% · строк A:${res.lines_a} B:${res.lines_b}` +
        (res.equal ? " · файлы идентичны" : "");
      $("diff-output").innerHTML = formatDiffHtml(
        res.diff_text || "(нет строк diff — файлы совпадают)"
      );
    } catch (err) {
      $("diff-summary").textContent = err.message || "Ошибка diff";
      $("diff-output").textContent = "";
    }
  }

  async function saveCodeBatch() {
    let folder = state.cwd;
    if (!folder) {
      folder = prompt("Папка от корня Python_kash:", "Cursor/AIKIVAVIORA_v.3_Cursor/02modules/aviora-catalog");
      if (!folder) return;
    }
    const note =
      prompt(
        "Заметка к пакету (batch):\nнапример: «состояние модуля перед рефакторингом»",
        ""
      ) || "";
    const rev = prompt("Версия/rev (Enter = из пути):", "") || null;
    if (
      !confirm(
        `Снимок всех code-файлов в папке?\n${folder}\n(до 120 файлов, без node_modules/.venv)`
      )
    ) {
      return;
    }
    try {
      const res = await api("/code/snapshot/batch", {
        method: "POST",
        body: JSON.stringify({
          path: folder,
          note: note.trim(),
          ...(rev && rev.trim() ? { rev: rev.trim() } : {}),
        }),
      });
      toast(
        `Пакет ${res.batch_id}: ${res.count} файлов (SEQ ${res.created?.[0]?.seq}…${res.created?.[res.count - 1]?.seq})`,
        true
      );
      if (confirm(`Открыть манифест пакета?\n${res.manifest_path}`)) {
        await openFile(res.manifest_path);
      }
    } catch (err) {
      toast(err.message || "Пакетный снимок не удался", false);
    }
  }

  async function showCatalogMap() {
    const overlay = $("map-overlay");
    if (!overlay) return;
    overlay.hidden = false;
    try {
      const data = await api("/catalog/map", { quiet: true });
      const zones = $("map-zones");
      if (zones) {
        zones.innerHTML = (data.branch_zones || [])
          .map(
            (z) =>
              `<span class="map-zone ${z.exists ? "map-zone--ok" : ""}"><strong>${escapeHtml(z.branch)}</strong> — ${escapeHtml(z.role)} · ${z.exists ? "✓" : "—"} ${escapeHtml(z.path)}</span>`
          )
          .join("");
      }
      const wrap = $("map-table-wrap");
      if (!wrap) return;
      const branchCols = ["Cursor", "Claude", "AIKIVAVIORA", "GEN"];
      let html =
        '<table class="map-table"><thead><tr><th>Модуль</th><th>Порт</th><th>Статус</th>';
      branchCols.forEach((b) => {
        html += `<th>${escapeHtml(b)}</th>`;
      });
      html += "</tr></thead><tbody>";
      (data.modules || []).forEach((mod) => {
        html += `<tr><td><strong>${escapeHtml(mod.title)}</strong><br><code>${escapeHtml(mod.id)}</code></td>`;
        html += `<td class="map-port">${mod.port ? ":" + mod.port : "—"}</td>`;
        html += `<td>${escapeHtml(mod.status || "")}</td>`;
        branchCols.forEach((b) => {
          const info = (mod.branches || {})[b];
          if (!info) {
            html += "<td>—</td>";
            return;
          }
          const cls = info.exists ? "map-path" : "map-path map-path--missing";
          const click = info.exists
            ? ` data-map-path="${escapeHtml(info.path)}"`
            : "";
          html += `<td><span class="${cls}"${click} title="${escapeHtml(info.path)}">${info.exists ? "✓ " : ""}${escapeHtml(info.path)}</span></td>`;
        });
        html += "</tr>";
      });
      html += "</tbody></table>";
      wrap.innerHTML = html;
      wrap.querySelectorAll("[data-map-path]").forEach((el) => {
        el.addEventListener("click", () => {
          const p = el.getAttribute("data-map-path");
          if (p) mapNavigateTo(p);
        });
      });
    } catch (err) {
      toast(err.message || "Карта недоступна", false);
    }
  }

  async function mapNavigateTo(path) {
    $("map-overlay").hidden = true;
    const parent = path.includes("/") ? path.split("/").slice(0, -1).join("/") : "";
    await loadTree(parent || path);
    try {
      const meta = await api(`/file/meta?path=${encodeURIComponent(path)}`, {
        quiet: true,
      });
      if (!meta.is_dir) await openFile(path);
    } catch {
      /* tree only */
    }
    toast(`Открыто: ${path}`, true);
  }

  async function saveCodeSnapshot() {
    if (!state.currentPath) {
      toast("Сначала откройте файл кода (.py, .js, …)", false);
      return;
    }
    const note =
      prompt(
        "Заметка к снимку (необязательно):\nнапример: «каркас auth до рефакторинга»",
        ""
      ) || "";
    const rev = prompt("Версия/rev (Enter = из пути, напр. v0.2.3):", "") || null;
    try {
      const res = await api("/code/snapshot", {
        method: "POST",
        body: JSON.stringify({
          path: state.currentPath,
          note: note.trim(),
          ...(rev && rev.trim() ? { rev: rev.trim() } : {}),
        }),
      });
      toast(
        `Снимок #${String(res.seq).padStart(6, "0")}: ${res.filename}`,
        true
      );
      if (
        confirm(
          `Открыть папку снимка?\n${res.path}\n\n(или Поиск по SEQ ${res.seq})`
        )
      ) {
        await openFile(res.path);
      }
      pollHealth();
    } catch (err) {
      toast(err.message || "Не удалось создать снимок", false);
    }
  }

  async function runRibbonCmd(cmd) {
    switch (cmd) {
      case "code-snapshot":
        await saveCodeSnapshot();
        break;
      case "code-batch":
        await saveCodeBatch();
        break;
      case "code-diff":
        await openDiffModal();
        break;
      case "open-snapshots":
        await loadTree("05data/aviora_code_snapshots");
        toast("Дерево: 05data/aviora_code_snapshots — после Scan ищется по SEQ/PROJ", true);
        break;
      case "show-map":
        await showCatalogMap();
        break;
      case "branch-all": {
        const bf = $("branch-filter");
        if (bf) bf.value = "";
        setBranchQuickActive("branch-all");
        await loadTree("");
        toast("Весь каталог", true);
        break;
      }
      case "map-cursor":
        if ($("branch-filter")) $("branch-filter").value = "Cursor";
        setBranchQuickActive("map-cursor");
        await loadTree("Cursor/AIKIVAVIORA_v.3_Cursor");
        toast("Cursor v.3", true);
        break;
      case "map-claude":
        if ($("branch-filter")) $("branch-filter").value = "Claude";
        setBranchQuickActive("map-claude");
        await loadTree("Claude");
        toast("Claude-зона", true);
        break;
      case "map-avi":
        if ($("branch-filter")) $("branch-filter").value = "AIKIVAVIORA";
        setBranchQuickActive("map-avi");
        await loadTree("AIKIVAVIORA");
        toast("AIKIVAVIORA / NEXUS", true);
        break;
      case "undo":
        editorUndo();
        break;
      case "redo":
        editorRedo();
        break;
      case "upload":
        $("file-input")?.click();
        break;
      case "folder": {
        const name = prompt("Имя папки:");
        if (!name) return;
        const path = state.cwd ? `${state.cwd}/${name}` : `Docs/${name}`;
        await api("/file/mkdir", {
          method: "POST",
          body: JSON.stringify({ path }),
        });
        loadTree(state.cwd || "Docs");
        break;
      }
      case "new": {
        const name = prompt("Имя файла .md:");
        if (!name) return;
        const base = state.cwd ? state.cwd + "/" : "Docs/";
        const path = base + (name.endsWith(".md") ? name : name + ".md");
        await api("/file/content", {
          method: "PUT",
          body: JSON.stringify({ path, content: "# Новый файл\n", encoding: "utf-8" }),
        });
        openFile(path);
        break;
      }
      case "open":
        openPathDialog();
        break;
      case "save":
        saveFile();
        break;
      case "save-as":
        saveFileAs();
        break;
      case "share":
        sharePath();
        break;
      case "explorer":
        revealExplorer();
        break;
      case "scan":
        startScan();
        break;
      case "find":
        toggleFindBar(true);
        break;
      case "stop":
        stopAll();
        break;
      case "mode-both":
        setTextMode("both");
        break;
      case "mode-word":
        setTextMode("word");
        break;
      case "mode-edit":
        setTextMode("edit");
        break;
      case "mode-figma":
        openFigmaStudio();
        break;
      case "logs":
        toggleLogs(true);
        break;
      case "help":
        showHelp();
        break;
      case "export-html":
        $("export-format").value = "html";
        exportCurrentFile();
        break;
      case "export-txt":
        $("export-format").value = "txt";
        exportCurrentFile();
        break;
      case "export-docx":
        $("export-format").value = "docx";
        exportCurrentFile();
        break;
      case "figma":
        openFigmaStudio();
        break;
      case "figma-frame":
        if (state.textMode !== "figma") openFigmaStudio();
        addFigmaNode("frame");
        break;
      case "figma-note":
        if (state.textMode !== "figma") openFigmaStudio();
        addFigmaNode("note");
        break;
      case "figma-save":
        if (state.textMode === "figma") saveFigmaBoard();
        else {
          openFigmaStudio();
          toast("Добавьте блоки и снова «Сохранить макет»", true);
        }
        break;
      case "photo-hint":
        toast("Откройте .jpg / .png / .webp в дереве слева → Crop, Save image", true);
        break;
      case "studio-help":
        showStudioHelp();
        break;
      case "star":
        toggleStarFolder(state.cwd);
        toast(
          state.starred.includes(state.cwd)
            ? "Папка в закладках"
            : "Убрано из закладок"
        );
        loadTree(state.cwd);
        break;
      case "mark-primary":
        await toggleCanonicalPrimary();
        break;
      case "save-search":
        await saveSearchReport(true);
        break;
      case "save-chat":
        await saveChatReport(true);
        break;
      case "open-saves":
        await loadTree("05data/aviora_search_saves");
        toast("Папка сохранённых отчётов", true);
        break;
      case "audio-transcribe":
        await startAudioTranscribe();
        break;
      case "audio-hint":
        toast("Откройте .mp3 / .wav / .m4a в дереве — плеер и Транскрипт", true);
        break;
      case "open-transcripts":
        await loadTree("05data/aviora_audio_transcripts");
        toast("Транскрипты аудио", true);
        break;
      case "reset":
        resetSession();
        break;
      case "dzen":
        window.open("http://127.0.0.1:8001/ui/", "_blank", "noopener");
        break;
      default:
        break;
    }
  }

  function bindRibbon() {
    const ribbon = document.querySelector(".ribbon");
    if (!ribbon || ribbon.dataset.bound === "1") return;
    ribbon.dataset.bound = "1";
    document.querySelectorAll(".ribbon-tab").forEach((tab) => {
      tab.addEventListener("click", () => switchRibbonTab(tab.dataset.tab));
    });
    document.querySelectorAll(".ribbon [data-cmd]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        runRibbonCmd(btn.dataset.cmd);
      });
    });
    document.querySelectorAll(".branch-bar [data-cmd]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        runRibbonCmd(btn.dataset.cmd);
      });
    });
  }

  async function transformImage(opts) {
    if (!state.currentPath) return;
    const body = { path: state.currentPath, ...opts };
    if (state.cropper && opts.cropMode) {
      const d = state.cropper.getData(true);
      body.crop = {
        x: Math.round(d.x),
        y: Math.round(d.y),
        w: Math.round(d.width),
        h: Math.round(d.height),
      };
    }
    const w = parseInt($("img-w").value, 10);
    const h = parseInt($("img-h").value, 10);
    if (w && h) body.resize = { w, h };
    body.format = $("img-format").value;
    body.quality = parseInt($("img-quality").value, 10);
    await api("/image/transform", {
      method: "POST",
      body: JSON.stringify(body),
    });
    toast("Изображение сохранено");
    openFile(state.currentPath);
  }

  function bindUi() {
    bindRibbon();
    const tips = {
      "btn-save": "Сохранить .md/.txt (Ctrl+S)",
      "btn-scan": "Индекс для поиска",
      "btn-save-inline": "Сохранить под превью Word",
    };
    Object.keys(tips).forEach((id) => {
      const el = $(id);
      if (el && !el.getAttribute("data-tip")) el.setAttribute("data-tip", tips[id]);
    });

    bindSaveButtons();
    bindShareButtons();
    bindChat();
    $("btn-save-search")?.addEventListener("click", () => saveSearchReport(true));
    $("btn-save-chat")?.addEventListener("click", () => saveChatReport(true));
    $("btn-audio-transcribe")?.addEventListener("click", () => startAudioTranscribe());
    $("btn-audio-transcribe-stop")?.addEventListener("click", () => cancelTranscribe());
    $("btn-transcribe-cancel")?.addEventListener("click", () => cancelTranscribe());
    updateSaveSearchBtn();
    updateSaveChatBtn();
    $("btn-scan").onclick = startScan;
    $("btn-scan-cancel")?.addEventListener("click", async () => {
      if (!state.scanJobId) {
        toast("Скан не запущен", false);
        return;
      }
      await api(`/scan/cancel/${state.scanJobId}`, { method: "POST" });
      toast("Останавливаем скан…", true);
    });
    $("btn-mode-both").onclick = () => setTextMode("both");
    $("btn-mode-figma").onclick = () => openFigmaStudio();
    $("btn-figma-save").onclick = () => saveFigmaBoard();
    $("btn-figma-back").onclick = () => {
      if (!state.currentPath) {
        $("figma-workspace").hidden = true;
        $("viewer-empty").hidden = false;
        return;
      }
      $("figma-workspace").hidden = true;
      $("text-workspace").hidden = false;
      setTextMode("both");
    };
    $("figma-add-frame").onclick = () => addFigmaNode("frame");
    $("figma-add-note").onclick = () => addFigmaNode("note");
    $("open-path-go").onclick = () => {
      const p = $("open-path-input").value.trim().replace(/\\/g, "/");
      $("open-modal").hidden = true;
      if (p) openFile(p);
    };
    $("open-path-cancel").onclick = () => {
      $("open-modal").hidden = true;
    };
    $("find-close").onclick = () => toggleFindBar(false);
    $("find-next").onclick = () => findInEditor(1);
    $("find-prev").onclick = () => findInEditor(-1);
    $("find-input").onkeydown = (e) => {
      if (e.key === "Enter") findInEditor(1);
    };
    $("search-input").onkeydown = (e) => {
      if (e.key === "Enter") runSearch();
    };
    $("ext-chips").onclick = (e) => {
      const chip = e.target.closest(".chip");
      if (!chip) return;
      document.querySelectorAll(".chip").forEach((c) => c.classList.remove("chip--on"));
      chip.classList.add("chip--on");
      const q = ($("search-input")?.value || "").trim();
      if (q) runSearch();
      else loadTree(state.cwd);
    };
    $("branch-filter").onchange = runSearch;
    const onLlmProviderChange = async () => {
      syncLlmProviderSelects(getLlmProvider());
      if (!state.llmEnabled) await setLlmEnabled(true);
      else await refreshLlmStatus(true);
    };
    $("llm-provider")?.addEventListener("change", () => {
      onLlmProviderChange();
    });
    $("llm-provider-header")?.addEventListener("change", () => {
      onLlmProviderChange();
    });
    $("btn-llm-refresh")?.addEventListener("click", () => refreshLlmStatus(true));
    $("btn-llm-power")?.addEventListener("click", () => toggleLlmEnabled());
    $("diff-close")?.addEventListener("click", () => toggleDiffModal(false));
    $("diff-run")?.addEventListener("click", () => runCodeDiff());
    $("diff-use-current-a")?.addEventListener("click", () => {
      if (state.currentPath) $("diff-path-a").value = state.currentPath;
    });
    $("diff-use-current-b")?.addEventListener("click", () => {
      if (state.currentPath) $("diff-path-b").value = state.currentPath;
    });
    $("map-close")?.addEventListener("click", () => {
      $("map-overlay").hidden = true;
    });
    $("read-only-toggle").onchange = async () => {
      syncReadOnlyFromUi();
      await api("/session/read-only", {
        method: "POST",
        body: JSON.stringify({ enabled: state.readOnly }),
      });
      toast(state.readOnly ? "Read-only: сохранение отключено" : "Можно сохранять", !state.readOnly);
      if (state.currentPath && !$("text-workspace").hidden) {
        $("editor").readOnly = state.readOnly;
      }
    };
    $("file-input").onchange = async (e) => {
      const files = e.target.files;
      if (!files?.length) return;
      for (const f of files) {
        const fd = new FormData();
        fd.append("file", f);
        const res = await fetch(
          `/file/upload?path=${encodeURIComponent(state.cwd)}`,
          {
            method: "POST",
            headers: state.readOnly ? { "X-Read-Only": "true" } : {},
            body: fd,
          }
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          showError(data.code || "ERR_HTTP", data.message);
          return;
        }
      }
      toast("Загружено");
      loadTree(state.cwd);
    };
    $("btn-mode-word").onclick = () => setTextMode("word");
    $("btn-mode-edit").onclick = () => setTextMode("edit");
    $("editor").oninput = () => {
      state.dirty = true;
      document.title = (state.currentPath || "") + " ●";
      clearTimeout(undoTimer);
      undoTimer = setTimeout(commitUndoSnapshot, 450);
      clearTimeout(previewTimer);
      previewTimer = setTimeout(() => {
        if (
          state.currentPath &&
          (state.textMode === "both" || state.textMode === "word")
        ) {
          renderWordPreview(state.currentPath, $("editor").value);
        }
      }, 400);
    };
    $("img-rot-l").onclick = () => transformImage({ rotate: 90 });
    $("img-rot-r").onclick = () => transformImage({ rotate: -90 });
    $("img-flip-h").onclick = () => transformImage({ flip_h: true });
    $("img-flip-v").onclick = () => transformImage({ flip_v: true });
    $("img-crop").onclick = () => transformImage({ cropMode: true });
    $("img-save").onclick = () => transformImage({});
    $("logs-clear").onclick = () => {
      $("logs-body").textContent = "";
    };
    $("logs-download").onclick = () => {
      const blob = new Blob([$("logs-body").textContent], { type: "text/plain" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "debug-session.log";
      a.click();
    };
    $("btn-help").onclick = showHelp;
    $("help-close").onclick = () => {
      $("help-overlay").hidden = true;
    };
  }

  function showHelp() {
    const g = state.glossary;
    let html = "<h2>Горячие клавиши</h2><ul>";
    const keys = [
      ["Важно", "Catalog — сайт в браузере, не замена проводника и не блокирует VS Code"],
      ["Save", "только .md и .txt; Read-only справа — запрет сохранения"],
      ["Слева", "клик 📁 = войти в папку, тогда видны файлы"],
      ["Ctrl+K + Enter", "поиск по индексу (сначала Scan; Enter — не при каждой букве)"],
      ["Ctrl+O", "открыть"],
      ["Ctrl+S", "сохранить"],
      ["Ctrl+Z", "отменить правку"],
      ["Ctrl+Y / Ctrl+Shift+Z", "повторить"],
      ["Ctrl+Shift+S", "сохранить как"],
      ["Ctrl+F", "найти в файле"],
      ["Ctrl+E", "поделиться — путь"],
      ["Код → Снимок", "дубликат с SEQ в 05data/aviora_code_snapshots"],
      ["Код → Пакет", "снимок всех code-файлов папки, BATCH-id"],
      ["Код → Diff", "сравнить пути или SEQ (снимок ↔ оригинал)"],
      ["Карта", "модули × филиалы Cursor / Claude / AIKIVAVIORA"],
      ["Шапка LLM", "ON/OFF чат · ↻ проверка · зелёная «● в сети» = LM Studio отвечает"],
      ["Студия", "Фото PS-lite + Figma — справка"],
      ["Ctrl+L", "чат"],
      ["Ctrl+`", "логи"],
      ["Scan", "полоса прогресса под лентой; кнопка Scan показывает %"],
      ["Ctrl+.", "стоп скана / чата"],
      ["Ctrl+Shift+R", "сброс"],
      ["F1", "справка"],
    ];
    keys.forEach(([k, v]) => {
      html += `<li><kbd>${k}</kbd> — ${v}</li>`;
    });
    html += "</ul><h2>Глоссарий</h2>";
    Object.keys(g).forEach((id) => {
      html += `<p><strong>${escapeHtml(g[id].title)}</strong>: ${escapeHtml(g[id].text)}</p>`;
    });
    $("help-content").innerHTML = html;
    $("help-overlay").hidden = false;
  }

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key === "k") {
      e.preventDefault();
      $("search-input").focus();
    }
    if (
      e.ctrlKey &&
      (e.key === "z" || e.key === "Z") &&
      !$("text-workspace").hidden
    ) {
      e.preventDefault();
      if (e.shiftKey) editorRedo();
      else editorUndo();
    } else if (
      e.ctrlKey &&
      (e.key === "y" || e.key === "Y") &&
      !$("text-workspace").hidden
    ) {
      e.preventDefault();
      editorRedo();
    } else if (e.ctrlKey && e.shiftKey && (e.key === "S" || e.key === "s")) {
      e.preventDefault();
      saveFileAs();
    } else if (e.ctrlKey && e.key === "s") {
      e.preventDefault();
      saveFile();
    }
    if (e.ctrlKey && e.key === "o") {
      e.preventDefault();
      openPathDialog();
    }
    if (e.ctrlKey && e.key === "f") {
      e.preventDefault();
      toggleFindBar(true);
    }
    if (e.ctrlKey && e.key === "e") {
      e.preventDefault();
      sharePath();
    }
    if (e.ctrlKey && e.key === "l") {
      e.preventDefault();
      $("chat-input").focus();
    }
    if (e.ctrlKey && e.key === "`") {
      e.preventDefault();
      toggleLogs();
    }
    if (e.ctrlKey && e.key === ".") {
      e.preventDefault();
      stopAll();
    }
    if (e.ctrlKey && e.shiftKey && (e.key === "R" || e.key === "r")) {
      e.preventDefault();
      resetSession();
    }
    if (e.key === "F1" || (e.ctrlKey && e.key === "/")) {
      e.preventDefault();
      showHelp();
    }
    if (e.key === "Escape") {
      if (!$("modal").hidden) {
        $("modal").hidden = true;
        return;
      }
      if (!$("open-modal").hidden) {
        $("open-modal").hidden = true;
        return;
      }
      if (!$("help-overlay").hidden) {
        $("help-overlay").hidden = true;
        return;
      }
      if (!$("find-bar").hidden) {
        toggleFindBar(false);
        return;
      }
      if (state.scanJobId) stopAll();
    }
  });

  async function init() {
    const apiBase = $("footer-api-base");
    if (apiBase) apiBase.textContent = window.location.origin;
    bindUi();
    bindFloatingTips();
    bindSaveButtons();
    bindChat();
    try {
      await loadJson();
    } catch (err) {
      console.warn("loadJson", err);
      toast("Справочник сообщений не загружен — кнопки Save/чат работают", false);
    }
    syncLlmProviderSelects(state.llmProvider);
    updateClock();
    setInterval(updateClock, 1000);
    setInterval(pollHealth, 30000);
    setTimeout(() => $("splash").classList.add("splash--hide"), 2500);
    const h0 = await api("/health").catch(() => null);
    warnOldBackend(h0);
    warnBackendVersion(h0);
    await resetStuckChatCancel();
    state.readOnly =
      state.readOnly || !!(h0 && h0.read_only);
    $("read-only-toggle").checked = state.readOnly;
    if (state.readOnly) {
      toast("Read-only в .env или в сессии — снимите галочку для Save", false);
    }
    state.recent.forEach((p) => {
      const li = document.createElement("li");
      li.className = "list-row";
      li.textContent = p;
      li.title = p;
      li.onclick = () => openFile(p);
      $("recent-list").appendChild(li);
    });
    renderStarred();
    await api("/session/llm", {
      method: "POST",
      body: JSON.stringify({ enabled: state.llmEnabled }),
    }).catch(() => null);
    await pollHealth();
    await resumeTranscribeJobOnLoad();
    await refreshCanonical();
    await refreshLlmStatus(true);
    if (!state.llmEnabled) {
      toast(
        "Чат LLM выключен (OFF). Нажмите ON в шапке — зелёная таблетка «● в сети» = готово",
        false
      );
    }
    setInterval(() => refreshLlmStatus(true), 45000);
    window.addEventListener("focus", () => refreshLlmStatus(true));
    await loadTree("");
    updateTreeHint();
    const seen = localStorage.getItem("avioraFirstRunDone");
    if (!seen && (state.lastHealth?.files_indexed || 0) === 0) {
      setTimeout(() => {
        if (
          confirm(
            "Первый запуск: выполнить Scan для поиска по каталогу?\n(можно позже кнопкой Scan)"
          )
        ) {
          startScan();
        }
        localStorage.setItem("avioraFirstRunDone", "1");
      }, 3000);
    }
  }

  bindSaveButtons();
  bindShareButtons();
  bindChat();

  init().catch((err) => {
    console.error(err);
    $("status-badge").textContent = "init error";
  });
})();
