(() => {
  const editor = document.getElementById("notes-editor");
  const input = document.getElementById("notes-input");
  const preview = document.getElementById("notes-preview");
  if (!editor || !input || !preview || typeof marked === "undefined") return;

  marked.setOptions({
    gfm: true,
    breaks: true,
  });

  const EMPTY_PREVIEW = `
    <div class="md-empty-state">
      <p>Write your approach, observations, edge cases, or solution notes here.</p>
      <p class="muted">Markdown, LaTeX, and fenced code (\`\`\`java / \`\`\`python) supported.</p>
    </div>
  `;

  const MATH_BLOCK = /\$\$([\s\S]+?)\$\$/g;
  const MATH_INLINE = /\$([^$\n]+?)\$/g;
  const CODEISH = /(```[\s\S]*?```|`[^`\n]+`)/g;

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderKatex(tex, displayMode) {
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

  function highlightCodeBlocks() {
    if (typeof hljs === "undefined") return;
    preview.querySelectorAll("pre code").forEach((block) => {
      if (block.dataset.highlighted === "yes") {
        delete block.dataset.highlighted;
        block.classList.remove("hljs");
      }
      hljs.highlightElement(block);
    });
  }

  function renderMarkdown(source) {
    if (!source.trim()) {
      preview.innerHTML = EMPTY_PREVIEW;
      return;
    }
    const { text, slots } = protectMath(source);
    const rawHtml = marked.parse(text);
    const clean = DOMPurify.sanitize(rawHtml, {
      ADD_ATTR: ["class"],
    });
    preview.innerHTML = restoreMath(clean, slots);
    highlightCodeBlocks();
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

  const editToggle = document.getElementById("notes-edit-toggle");
  if (editToggle) {
    const setEditing = (editing) => {
      editor.classList.toggle("is-view", !editing);
      editor.classList.toggle("is-editing", editing);
      editToggle.innerHTML = editing
        ? '<i data-lucide="check" class="icon"></i><span>Done editing</span>'
        : '<i data-lucide="pen-line" class="icon"></i><span>Edit notes</span>';
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

  renderMarkdown(input.value);
})();
