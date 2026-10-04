(() => {
  const shell = document.getElementById("problem-shell");
  const chat = document.getElementById("ai-chat");
  const messagesEl = document.getElementById("ai-chat-messages");
  const form = document.getElementById("ai-chat-form");
  const input = document.getElementById("ai-chat-input");
  const sendBtn = document.getElementById("ai-chat-send");
  const clearBtn = document.getElementById("ai-chat-clear");
  const collapseBtn = document.getElementById("ai-chat-collapse");
  const expandBtn = document.getElementById("ai-chat-expand");
  const fabBtn = document.getElementById("ai-chat-fab");
  const suggestions = document.getElementById("ai-chat-suggestions");
  if (!shell || !chat || !messagesEl || !form || !input || !sendBtn) return;

  const enabled = chat.dataset.enabled === "1";
  const chatUrl = chat.dataset.chatUrl;
  const slug = chat.dataset.slug || "unknown";
  const problemName = chat.dataset.problemName || "this problem";
  const storageKey = `neetcode250:ai-chat:${slug}`;
  const collapseKey = "neetcode250:ai-chat-collapsed";
  const desktopMq = window.matchMedia("(min-width: 1101px)");
  const history = [];
  let pending = false;
  let lastFailedPrompt = null;
  let panelVisible = false;

  function escapeHtml(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function refreshIcons() {
    if (typeof window.refreshIcons === "function") window.refreshIcons();
  }

  async function copyText(text, button) {
    const value = String(text ?? "");
    try {
      await navigator.clipboard.writeText(value);
    } catch (_err) {
      const area = document.createElement("textarea");
      area.value = value;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }

    if (!button) return;
    const previous = button.innerHTML;
    button.classList.add("is-copied");
    button.innerHTML = '<i data-lucide="check" class="icon"></i><span>Copied</span>';
    button.setAttribute("aria-label", "Copied");
    refreshIcons();
    window.setTimeout(() => {
      button.classList.remove("is-copied");
      button.innerHTML = previous;
      button.setAttribute("aria-label", "Copy to clipboard");
      refreshIcons();
    }, 1400);
  }

  function makeCopyButton(label = "Copy") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ai-copy-btn";
    button.title = "Copy to clipboard";
    button.setAttribute("aria-label", "Copy to clipboard");
    button.innerHTML = `<i data-lucide="copy" class="icon"></i><span>${escapeHtml(label)}</span>`;
    return button;
  }

  function decorateCodeBlocks(root) {
    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.parentElement?.classList.contains("ai-code-block")) return;
      const code = pre.querySelector("code");
      const wrap = document.createElement("div");
      wrap.className = "ai-code-block";
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);

      const copyBtn = makeCopyButton("Copy");
      copyBtn.classList.add("ai-copy-code");
      copyBtn.addEventListener("click", () => {
        copyText(code ? code.textContent : pre.textContent, copyBtn);
      });
      wrap.appendChild(copyBtn);
    });
  }

  function highlightCode(root) {
    if (typeof hljs === "undefined") return;
    root.querySelectorAll("pre code").forEach((block) => {
      if (block.dataset.highlighted === "yes") {
        delete block.dataset.highlighted;
        block.classList.remove("hljs");
      }
      hljs.highlightElement(block);
    });
  }

  function renderMarkdown(source) {
    if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
      return `<p>${escapeHtml(source)}</p>`;
    }
    const raw = marked.parse(source, { gfm: true, breaks: true });
    return DOMPurify.sanitize(raw, {
      ADD_TAGS: ["span"],
      ADD_ATTR: ["class"],
    });
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function persistHistory() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(history));
    } catch (_err) {
      /* ignore */
    }
  }

  function loadHistory() {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter(
          (item) =>
            item &&
            (item.role === "user" || item.role === "model") &&
            typeof item.content === "string" &&
            item.content.trim()
        )
        .map((item) => ({ role: item.role, content: item.content }));
    } catch (_err) {
      return [];
    }
  }

  function setPanelVisible(visible, { persist = true } = {}) {
    panelVisible = visible;
    const desktop = desktopMq.matches;

    shell.classList.toggle("is-ai-collapsed", desktop && !visible);
    chat.classList.toggle("is-open", visible);
    document.body.classList.toggle("is-ai-chat-open", !desktop && visible);

    [expandBtn, fabBtn].forEach((btn) => {
      if (!btn) return;
      btn.setAttribute("aria-expanded", visible ? "true" : "false");
    });
    if (collapseBtn) {
      collapseBtn.setAttribute(
        "aria-label",
        desktop ? "Collapse AI Coach" : "Close AI Coach"
      );
      collapseBtn.title = desktop ? "Collapse AI Coach" : "Close AI Coach";
    }

    if (persist && desktop) {
      try {
        localStorage.setItem(collapseKey, visible ? "0" : "1");
      } catch (_err) {
        /* ignore */
      }
    }

    if (visible && !desktop) {
      window.setTimeout(() => input.focus(), 120);
    }
  }

  function appendThinking() {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-assistant is-pending";

    const top = document.createElement("div");
    top.className = "ai-msg-top";
    const label = document.createElement("div");
    label.className = "ai-msg-label";
    label.textContent = "AI Coach";
    top.appendChild(label);

    const body = document.createElement("div");
    body.className = "ai-msg-body";
    body.innerHTML = `
      <p class="ai-thinking" aria-live="polite">
        <span class="ai-thinking-label">Thinking</span>
        <span class="ai-thinking-dots" aria-hidden="true">
          <span></span><span></span><span></span>
        </span>
      </p>
    `;

    wrap.appendChild(top);
    wrap.appendChild(body);
    messagesEl.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function appendError(retryPrompt) {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-system is-error";

    const top = document.createElement("div");
    top.className = "ai-msg-top";
    const label = document.createElement("div");
    label.className = "ai-msg-label";
    label.textContent = "System";
    top.appendChild(label);

    const body = document.createElement("div");
    body.className = "ai-msg-body";
    body.innerHTML = `<p>Couldn't generate a response.</p>`;

    if (retryPrompt) {
      const actions = document.createElement("div");
      actions.className = "ai-error-actions";
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn btn-ghost btn-icon ai-retry-btn";
      retry.innerHTML =
        '<i data-lucide="refresh-cw" class="icon"></i><span>Try again</span>';
      retry.addEventListener("click", () => sendMessage(retryPrompt));
      actions.appendChild(retry);
      body.appendChild(actions);
    }

    wrap.appendChild(top);
    wrap.appendChild(body);
    messagesEl.appendChild(wrap);
    refreshIcons();
    scrollToBottom();
    return wrap;
  }

  function appendMessage(
    role,
    content,
    { markdown = false, error = false, skipCopy = false } = {}
  ) {
    const wrap = document.createElement("div");
    wrap.className = `ai-msg ai-msg-${role}${error ? " is-error" : ""}`;

    const top = document.createElement("div");
    top.className = "ai-msg-top";

    const label = document.createElement("div");
    label.className = "ai-msg-label";
    label.textContent =
      role === "user" ? "You" : role === "system" ? "System" : "AI Coach";
    top.appendChild(label);

    const canCopy = !skipCopy && !error && role !== "system" && content.trim();
    if (canCopy) {
      const copyBtn = makeCopyButton("Copy");
      copyBtn.addEventListener("click", () => copyText(content, copyBtn));
      top.appendChild(copyBtn);
    }

    const body = document.createElement("div");
    body.className = "ai-msg-body" + (markdown ? " markdown-body" : "");
    if (markdown) {
      body.innerHTML = renderMarkdown(content);
      highlightCode(body);
      decorateCodeBlocks(body);
    } else {
      body.innerHTML = `<p>${escapeHtml(content)}</p>`;
    }

    wrap.appendChild(top);
    wrap.appendChild(body);
    messagesEl.appendChild(wrap);
    refreshIcons();
    scrollToBottom();
    return wrap;
  }

  function renderWelcome() {
    if (!enabled) {
      appendMessage(
        "system",
        "AI Coach is not configured.\n\nSet `GEMINI_API_KEY` in `.env` (local) or the server environment, then restart the app.",
        { markdown: true, skipCopy: true }
      );
      return;
    }
    appendMessage(
      "assistant",
      `Ask for a **gentle hint**, an approach outline, or a review of your notes for **${problemName}**.\n\nI can see your live status and notes from this page — and I'll coach rather than dump full solutions unless you ask.`,
      { markdown: true }
    );
  }

  function restoreMessages() {
    messagesEl.innerHTML = "";
    const saved = loadHistory();
    history.length = 0;
    if (!saved.length) {
      renderWelcome();
      return;
    }
    saved.forEach((item) => {
      history.push(item);
      if (item.role === "user") appendMessage("user", item.content);
      else appendMessage("assistant", item.content, { markdown: true });
    });
  }

  function setPending(isPending) {
    pending = isPending;
    sendBtn.disabled = !enabled || isPending || !input.value.trim();
    input.disabled = !enabled || isPending;
    if (clearBtn) clearBtn.disabled = !enabled || isPending;
    if (suggestions) {
      suggestions.querySelectorAll("button").forEach((btn) => {
        btn.disabled = !enabled || isPending;
      });
    }
    sendBtn.classList.toggle("is-loading", isPending);
  }

  function collectContext() {
    const statusSelect = document.getElementById("status-select");
    const notesInput = document.getElementById("notes-input");
    return {
      status: statusSelect ? statusSelect.value : "todo",
      notes: notesInput ? notesInput.value : "",
      bookmarked: chat.dataset.bookmarked === "1",
      solve_count: Number(chat.dataset.solveCount || 0),
      last_practiced_at: chat.dataset.lastPracticed || "",
    };
  }

  async function sendMessage(rawText) {
    const text = (rawText || "").trim();
    if (!enabled || !text || pending) return;

    if (!panelVisible) setPanelVisible(true);

    appendMessage("user", text);
    history.push({ role: "user", content: text });
    persistHistory();
    input.value = "";
    autosizeInput();
    setPending(true);
    lastFailedPrompt = null;

    const thinking = appendThinking();

    try {
      const response = await fetch(chatUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: history.slice(0, -1),
          context: collectContext(),
        }),
      });
      const data = await response.json().catch(() => ({}));
      thinking.remove();

      if (!response.ok) {
        lastFailedPrompt = text;
        appendError(lastFailedPrompt);
        history.pop();
        persistHistory();
        return;
      }

      const reply = data.reply || "";
      appendMessage("assistant", reply, { markdown: true });
      history.push({ role: "model", content: reply });
      persistHistory();
    } catch (err) {
      thinking.remove();
      lastFailedPrompt = text;
      appendError(lastFailedPrompt);
      history.pop();
      persistHistory();
      console.error(err);
    } finally {
      setPending(false);
      if (panelVisible) input.focus();
    }
  }

  function autosizeInput() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });

  input.addEventListener("input", () => {
    sendBtn.disabled = !enabled || pending || !input.value.trim();
    autosizeInput();
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage(input.value);
    }
  });

  if (suggestions) {
    suggestions.addEventListener("click", (event) => {
      const chip = event.target.closest("[data-prompt]");
      if (!chip) return;
      sendMessage(chip.dataset.prompt);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if (pending) return;
      if (!window.confirm("Clear this conversation for the current problem?")) {
        return;
      }
      history.length = 0;
      lastFailedPrompt = null;
      try {
        localStorage.removeItem(storageKey);
      } catch (_err) {
        /* ignore */
      }
      messagesEl.innerHTML = "";
      appendMessage(
        "assistant",
        "Conversation cleared. Ask anytime — I still see your live status and notes.",
        { markdown: true }
      );
    });
  }

  function openPanel() {
    setPanelVisible(true);
  }

  function closePanel() {
    setPanelVisible(false);
  }

  if (collapseBtn) collapseBtn.addEventListener("click", closePanel);
  if (expandBtn) expandBtn.addEventListener("click", openPanel);
  if (fabBtn) fabBtn.addEventListener("click", openPanel);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panelVisible && !desktopMq.matches) {
      closePanel();
    }
  });

  document.addEventListener("click", (event) => {
    if (desktopMq.matches || !panelVisible) return;
    if (
      chat.contains(event.target) ||
      (fabBtn && fabBtn.contains(event.target)) ||
      (expandBtn && expandBtn.contains(event.target))
    ) {
      return;
    }
    closePanel();
  });

  function syncViewport() {
    if (desktopMq.matches) {
      let collapsed = false;
      try {
        collapsed = localStorage.getItem(collapseKey) === "1";
      } catch (_err) {
        collapsed = false;
      }
      setPanelVisible(!collapsed, { persist: false });
    } else {
      setPanelVisible(false, { persist: false });
    }
  }

  syncViewport();
  desktopMq.addEventListener("change", syncViewport);

  restoreMessages();
  setPending(false);
  autosizeInput();
  refreshIcons();
})();
