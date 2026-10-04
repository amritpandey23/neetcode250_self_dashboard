(() => {
  const root = document.getElementById("doc-preview");
  const sourceEl = document.getElementById("doc-preview-source");
  if (!root || typeof marked === "undefined") return;

  const source = sourceEl ? sourceEl.value : "";

  function mermaidTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark"
      ? "dark"
      : "neutral";
  }

  // Mirror markdown-editor.js render pipeline (kept local so preview works without editor DOM).
  if (typeof mermaid !== "undefined") {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: mermaidTheme(),
    });
  }

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
      if (
        host === "youtube.com" ||
        host === "m.youtube.com" ||
        host === "youtube-nocookie.com"
      ) {
        if (url.pathname.startsWith("/embed/") || url.pathname.startsWith("/shorts/")) {
          const id = url.pathname.split("/")[2];
          return YT_ID.test(id || "") ? id : null;
        }
        const id = url.searchParams.get("v");
        return YT_ID.test(id || "") ? id : null;
      }
    } catch (_err) {
      /* ignore */
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
    } catch (_err) {
      return `<span class="md-math-error">[Invalid LaTeX]</span>`;
    }
  }

  function protectMath(src) {
    const slots = [];
    const parts = src.split(CODEISH);
    const text = parts
      .map((part, index) => {
        if (index % 2 === 1) return part;
        let chunk = part.replace(MATH_BLOCK, (_, tex) => {
          const token = `@@MATH${slots.length}@@`;
          slots.push(renderKatex(tex, true));
          return token;
        });
        chunk = chunk.replace(MATH_INLINE, (_, tex) => {
          const token = `@@MATH${slots.length}@@`;
          slots.push(renderKatex(tex, false));
          return token;
        });
        return chunk;
      })
      .join("");
    return { text, slots };
  }

  function highlightSource(code, lang) {
    const sourceCode = String(code ?? "");
    if (typeof hljs === "undefined") return escapeHtml(sourceCode);
    const language = String(lang || "").trim().split(/\s+/)[0];
    try {
      if (language && hljs.getLanguage(language)) {
        return hljs.highlight(sourceCode, { language }).value;
      }
      return hljs.highlightAuto(sourceCode).value;
    } catch (_err) {
      return escapeHtml(sourceCode);
    }
  }

  function renderCodeBlock(code, lang) {
    const language = String(lang || "").trim().split(/\s+/)[0].toLowerCase();
    if (language === "mermaid") {
      return `<div class="md-mermaid"><pre class="mermaid">${escapeHtml(code)}</pre></div>\n`;
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

  marked.setOptions({ gfm: true, breaks: true });
  marked.use({
    renderer: {
      code(codeOrToken, infostring) {
        if (codeOrToken && typeof codeOrToken === "object") {
          return renderCodeBlock(codeOrToken.text, codeOrToken.lang);
        }
        return renderCodeBlock(codeOrToken, infostring);
      },
      link(href, title, text) {
        if (href && typeof href === "object") {
          const token = href;
          const videoId = extractYouTubeId(token.href);
          if (videoId && (!token.text || token.text === token.href)) {
            return youtubeEmbedHtml(videoId);
          }
          const t = token.title ? ` title="${escapeHtml(token.title)}"` : "";
          return `<a href="${escapeHtml(token.href || "")}"${t}>${token.text || token.href || ""}</a>`;
        }
        const videoId = extractYouTubeId(href);
        if (videoId && (!text || text === href)) return youtubeEmbedHtml(videoId);
        const t = title ? ` title="${escapeHtml(title)}"` : "";
        return `<a href="${escapeHtml(href)}"${t}>${text}</a>`;
      },
    },
  });

  function renderPreview() {
    if (!source.trim()) {
      root.innerHTML =
        '<div class="md-empty-state"><p class="muted">This entry is empty. Click Edit to add content.</p></div>';
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
      ],
    });
    root.innerHTML = clean.replace(
      /@@MATH(\d+)@@/g,
      (_, index) => slots[Number(index)] || ""
    );

    if (typeof mermaid !== "undefined") {
      const nodes = root.querySelectorAll("pre.mermaid");
      if (nodes.length) {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: mermaidTheme(),
        });
        mermaid.run({ nodes: Array.from(nodes) }).catch((err) => {
          console.error("Mermaid preview failed:", err);
        });
      }
    }
  }

  document.addEventListener("themechange", renderPreview);
  renderPreview();
})();
