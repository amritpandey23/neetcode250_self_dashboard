(() => {
  const editor =
    document.getElementById("md-editor") ||
    document.getElementById("notes-editor");
  const input =
    document.getElementById("md-input") ||
    document.getElementById("notes-input");
  const preview =
    document.getElementById("md-preview") ||
    document.getElementById("notes-preview");
  if (!editor || !input || !preview || typeof marked === "undefined") return;

  const extended = editor.dataset.extended === "1";
  const emptyHint = extended
    ? "Markdown, LaTeX, Mermaid, fenced code, and YouTube embeds supported."
    : "Markdown, LaTeX, and fenced code (```java / ```python) supported.";

  marked.setOptions({
    gfm: true,
    breaks: true,
  });

  function mermaidTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark"
      ? "dark"
      : "neutral";
  }

  if (typeof mermaid !== "undefined") {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: mermaidTheme(),
    });
  }

  const EMPTY_PREVIEW = `
    <div class="md-empty-state">
      <p>Write your document here.</p>
      <p class="muted">${emptyHint}</p>
    </div>
  `;

  const MATH_BLOCK = /\$\$([\s\S]+?)\$\$/g;
  const MATH_INLINE = /\$([^$\n]+?)\$/g;
  const CODEISH = /(```[\s\S]*?```|`[^`\n]+`)/g;
  const YT_ID = /^[a-zA-Z0-9_-]{11}$/;

  function escapeHtml(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function extractYouTubeId(raw) {
    const text = String(raw || "").trim();
    if (!text) return null;
    try {
      const url = new URL(text);
      const host = url.hostname.replace(/^www\./, "");
      if (host === "youtu.be") {
        const id = url.pathname.split("/").filter(Boolean)[0];
        return YT_ID.test(id || "") ? id : null;
      }
      if (host === "youtube.com" || host === "m.youtube.com" || host === "youtube-nocookie.com") {
        if (url.pathname.startsWith("/embed/")) {
          const id = url.pathname.split("/")[2];
          return YT_ID.test(id || "") ? id : null;
        }
        if (url.pathname.startsWith("/shorts/")) {
          const id = url.pathname.split("/")[2];
          return YT_ID.test(id || "") ? id : null;
        }
        const id = url.searchParams.get("v");
        return YT_ID.test(id || "") ? id : null;
      }
    } catch (_err) {
      /* not a URL */
    }
    return YT_ID.test(text) ? text : null;
  }

  function youtubeEmbedHtml(videoId) {
    return `<div class="md-youtube"><iframe src="https://www.youtube-nocookie.com/embed/${videoId}" title="YouTube video" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe></div>`;
  }

  function renderKatex(tex, displayMode) {
    if (typeof katex === "undefined") return escapeHtml(tex);
    try {
      return katex.renderToString(tex.trim(), {
        displayMode,
        throwOnError: false,
        strict: "ignore",
      });
    } catch (err) {
      const mode = displayMode ? "block" : "inline";
      return `<span class="md-math-error" title="${escapeHtml(String(err))}">[Invalid ${mode} LaTeX]</span>`;
    }
  }

  function protectMathInText(src, slots) {
    let text = src.replace(MATH_BLOCK, (_, tex) => {
      const token = `@@MATH${slots.length}@@`;
      slots.push(renderKatex(tex, true));
      return token;
    });
    text = text.replace(MATH_INLINE, (_, tex) => {
      const token = `@@MATH${slots.length}@@`;
      slots.push(renderKatex(tex, false));
      return token;
    });
    return text;
  }

  function protectMath(src) {
    const slots = [];
    const parts = src.split(CODEISH);
    const text = parts
      .map((part, index) => {
        if (index % 2 === 1) return part;
        return protectMathInText(part, slots);
      })
      .join("");
    return { text, slots };
  }

  function restoreMath(html, slots) {
    return html.replace(/@@MATH(\d+)@@/g, (_, index) => slots[Number(index)] || "");
  }

  function highlightSource(code, lang) {
    const source = String(code ?? "");
    if (typeof hljs === "undefined") return escapeHtml(source);
    const language = String(lang || "")
      .trim()
      .split(/\s+/)[0];
    try {
      if (language && hljs.getLanguage(language)) {
        return hljs.highlight(source, { language }).value;
      }
      return hljs.highlightAuto(source).value;
    } catch (_err) {
      return escapeHtml(source);
    }
  }

  function renderCodeBlock(code, lang) {
    const language = String(lang || "")
      .trim()
      .split(/\s+/)[0]
      .toLowerCase();

    if (language === "mermaid") {
      const id = `mermaid-${Math.random().toString(36).slice(2, 10)}`;
      return `<div class="md-mermaid" data-mermaid-id="${id}"><pre class="mermaid">${escapeHtml(code)}</pre></div>\n`;
    }

    if (language === "youtube") {
      const videoId = extractYouTubeId(code.split("\n")[0] || "");
      if (videoId) return `${youtubeEmbedHtml(videoId)}\n`;
      return `<p class="md-embed-error">Invalid YouTube URL.</p>\n`;
    }

    const highlighted = highlightSource(code, language);
    const className = language
      ? `hljs language-${escapeHtml(language)}`
      : "hljs";
    return `<pre><code class="${className}">${highlighted}</code></pre>\n`;
  }

  marked.use({
    renderer: {
      code(codeOrToken, infostring) {
        if (codeOrToken && typeof codeOrToken === "object") {
          return renderCodeBlock(codeOrToken.text, codeOrToken.lang);
        }
        return renderCodeBlock(codeOrToken, infostring);
      },
      link(href, title, text) {
        // marked@13 may pass token object as first arg
        if (href && typeof href === "object") {
          const token = href;
          const videoId = extractYouTubeId(token.href);
          if (videoId && (!token.text || token.text === token.href)) {
            return youtubeEmbedHtml(videoId);
          }
          const t = token.title
            ? ` title="${escapeHtml(token.title)}"`
            : "";
          return `<a href="${escapeHtml(token.href || "")}"${t}>${token.text || token.href || ""}</a>`;
        }
        const videoId = extractYouTubeId(href);
        if (videoId && (!text || text === href)) {
          return youtubeEmbedHtml(videoId);
        }
        const t = title ? ` title="${escapeHtml(title)}"` : "";
        return `<a href="${escapeHtml(href)}"${t}>${text}</a>`;
      },
    },
  });

  async function renderMermaidBlocks(root) {
    if (typeof mermaid === "undefined") return;
    const nodes = root.querySelectorAll("pre.mermaid");
    if (!nodes.length) return;
    try {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: mermaidTheme(),
      });
      await mermaid.run({ nodes: Array.from(nodes) });
    } catch (err) {
      console.error("Mermaid render failed:", err);
    }
  }

  function renderMarkdown(source) {
    try {
      if (!source.trim()) {
        preview.innerHTML = EMPTY_PREVIEW;
        return;
      }
      const { text, slots } = protectMath(source);
      const rawHtml = marked.parse(text);
      const clean = DOMPurify.sanitize(rawHtml, {
        ADD_TAGS: ["iframe", "div", "span"],
        ADD_ATTR: [
          "class",
          "allow",
          "allowfullscreen",
          "frameborder",
          "src",
          "title",
          "loading",
          "data-mermaid-id",
        ],
      });
      preview.innerHTML = restoreMath(clean, slots);
      renderMermaidBlocks(preview);
    } catch (err) {
      console.error("Markdown preview failed:", err);
      preview.innerHTML = `<pre class="md-preview-fallback">${escapeHtml(source)}</pre>`;
    }
  }

  function wrapSelection(before, after = before, placeholder = "text") {
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const value = input.value;
    const selected = value.slice(start, end) || placeholder;
    const next = value.slice(0, start) + before + selected + after + value.slice(end);
    input.value = next;
    const selectStart = start + before.length;
    input.focus();
    input.setSelectionRange(selectStart, selectStart + selected.length);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function prefixLines(prefix) {
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const value = input.value;
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    const lineEnd = value.indexOf("\n", end);
    const sliceEnd = lineEnd === -1 ? value.length : lineEnd;
    const block = value.slice(lineStart, sliceEnd);
    const nextBlock = block
      .split("\n")
      .map((line, i) => {
        if (prefix === "1. ") return `${i + 1}. ${line.replace(/^\d+\.\s+/, "")}`;
        if (line.startsWith(prefix)) return line;
        return prefix + line;
      })
      .join("\n");
    input.value = value.slice(0, lineStart) + nextBlock + value.slice(sliceEnd);
    input.focus();
    input.setSelectionRange(lineStart, lineStart + nextBlock.length);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  const actions = {
    bold: () => wrapSelection("**", "**", "bold"),
    italic: () => wrapSelection("*", "*", "italic"),
    strike: () => wrapSelection("~~", "~~", "text"),
    h2: () => prefixLines("## "),
    ul: () => prefixLines("- "),
    ol: () => prefixLines("1. "),
    quote: () => prefixLines("> "),
    code: () => wrapSelection("`", "`", "code"),
    codeblock: () => wrapSelection("```python\n", "\n```", "code"),
    link: () => wrapSelection("[", "](https://)", "label"),
    table: () =>
      wrapSelection(
        "",
        "\n\n| Column | Column |\n| --- | --- |\n| value | value |\n\n",
        ""
      ),
    math: () => wrapSelection("$", "$", "x"),
    mathblock: () => wrapSelection("$$\n", "\n$$\n", "E = mc^2"),
    mermaid: () =>
      wrapSelection(
        "```mermaid\nflowchart LR\n  A[Start] --> B[End]\n",
        "\n```\n",
        ""
      ),
    youtube: () =>
      wrapSelection("```youtube\n", "\n```\n", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
  };

  editor.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = actions[btn.dataset.action];
      if (action) action();
    });
  });

  function setMode(mode) {
    editor.dataset.mode = mode;
    editor.querySelectorAll("[data-mode]").forEach((b) => {
      b.classList.toggle("is-active", b.dataset.mode === mode);
    });
  }

  editor.querySelectorAll("[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => setMode(btn.dataset.mode));
  });

  const editToggle =
    document.getElementById("md-edit-toggle") ||
    document.getElementById("notes-edit-toggle");
  if (editToggle) {
    const editLabel = extended ? "Edit" : "Edit notes";
    const doneLabel = "Done editing";
    const setEditing = (editing) => {
      editor.classList.toggle("is-view", !editing);
      editor.classList.toggle("is-editing", editing);
      editToggle.innerHTML = editing
        ? `<i data-lucide="check" class="icon"></i><span>${doneLabel}</span>`
        : `<i data-lucide="pen-line" class="icon"></i><span>${editLabel}</span>`;
      if (typeof window.refreshIcons === "function") window.refreshIcons();
      if (editing) {
        setMode("split");
        input.focus();
      } else {
        setMode("preview");
        renderMarkdown(input.value);
      }
    };

    setEditing(false);
    editToggle.addEventListener("click", () => {
      setEditing(editor.classList.contains("is-view"));
    });
  }

  input.addEventListener("keydown", (event) => {
    const mod = event.metaKey || event.ctrlKey;
    if (mod && event.key.toLowerCase() === "b") {
      event.preventDefault();
      actions.bold();
    } else if (mod && event.key.toLowerCase() === "i") {
      event.preventDefault();
      actions.italic();
    } else if (event.key === "Tab") {
      event.preventDefault();
      const start = input.selectionStart;
      const end = input.selectionEnd;
      input.value = `${input.value.slice(0, start)}  ${input.value.slice(end)}`;
      input.setSelectionRange(start + 2, start + 2);
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });

  let frame = null;
  input.addEventListener("input", () => {
    if (frame) cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => renderMarkdown(input.value));
  });

  document.addEventListener("themechange", () => {
    renderMarkdown(input.value);
  });

  renderMarkdown(input.value);
})();
