/* Searchable dropdown: replaces long native <select> lists.
   Markup contract:
   [data-search-select]
     [data-search-select-value]           hidden input with the submitted value
     [data-search-select-input]           visible text input (role=combobox)
     [data-search-select-options]         listbox container
       [data-search-select-option]        option rows (data-value, data-label)
     [data-search-select-empty]           optional "no matches" row
*/
(() => {
  function init(root) {
    const hidden = root.querySelector("[data-search-select-value]");
    const input = root.querySelector("[data-search-select-input]");
    const list = root.querySelector("[data-search-select-options]");
    const empty = root.querySelector("[data-search-select-empty]");
    if (!hidden || !input || !list) return;

    const form = root.closest("form");
    const options = Array.from(
      list.querySelectorAll("[data-search-select-option]")
    ).map((el) => {
      const label = (el.dataset.label || el.textContent || "").replace(/\s+/g, " ").trim();
      return {
        el,
        value: el.dataset.value || "",
        label,
        haystack: label.toLowerCase(),
      };
    });

    let visible = options.slice();
    let active = -1;
    let opened = false;
    let selected = null;

    function setExpanded(state) {
      opened = state;
      root.classList.toggle("is-open", state);
      list.hidden = !state;
      input.setAttribute("aria-expanded", state ? "true" : "false");
      if (!state) {
        clearActive();
        input.removeAttribute("aria-activedescendant");
      }
    }

    function clearActive() {
      visible.forEach((opt) => opt.el.classList.remove("is-active"));
      active = -1;
    }

    function setActive(index, scroll = true) {
      if (!visible.length) {
        clearActive();
        input.removeAttribute("aria-activedescendant");
        return;
      }
      const next = Math.max(0, Math.min(index, visible.length - 1));
      visible.forEach((opt, i) => {
        opt.el.classList.toggle("is-active", i === next);
      });
      active = next;
      const el = visible[next].el;
      if (el.id) input.setAttribute("aria-activedescendant", el.id);
      if (scroll) el.scrollIntoView({ block: "nearest" });
    }

    function filter(query) {
      const needle = query.trim().toLowerCase();
      visible = [];
      options.forEach((opt) => {
        const match = !needle || opt.haystack.includes(needle);
        opt.el.hidden = !match;
        if (match) visible.push(opt);
      });
      if (empty) empty.hidden = visible.length > 0;
      clearActive();
      input.removeAttribute("aria-activedescendant");
    }

    function openList(showAll) {
      filter(showAll ? "" : input.value);
      setExpanded(true);
      const preselected = selected ? visible.indexOf(selected) : -1;
      if (preselected >= 0) setActive(preselected);
      else if (visible.length) setActive(0);
    }

    function closeList() {
      if (!opened) return;
      setExpanded(false);
    }

    function applySelection(opt) {
      selected = opt;
      hidden.value = opt.value;
      input.value = opt.label;
      options.forEach((candidate) => {
        candidate.el.setAttribute("aria-selected", candidate === opt ? "true" : "false");
      });
      root.classList.remove("is-invalid");
      closeList();
      input.focus();
    }

    function clearSelection() {
      selected = null;
      hidden.value = "";
      options.forEach((candidate) => candidate.el.setAttribute("aria-selected", "false"));
    }

    input.addEventListener("focus", () => openList(true));

    input.addEventListener("click", () => {
      if (!opened) openList(true);
    });

    input.addEventListener("input", () => {
      if (selected && input.value !== selected.label) clearSelection();
      filter(input.value);
      setExpanded(true);
      if (visible.length) setActive(0);
    });

    input.addEventListener("keydown", (event) => {
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          if (!opened) openList(true);
          else setActive(active + 1);
          break;
        case "ArrowUp":
          event.preventDefault();
          if (!opened) openList(true);
          else if (active <= 0) setActive(visible.length - 1);
          else setActive(active - 1);
          break;
        case "Home":
          if (opened) {
            event.preventDefault();
            setActive(0);
          }
          break;
        case "End":
          if (opened) {
            event.preventDefault();
            setActive(visible.length - 1);
          }
          break;
        case "Enter":
          if (opened && visible.length) {
            event.preventDefault();
            applySelection(visible[active >= 0 ? active : 0]);
          }
          break;
        case "Escape":
          if (opened) {
            event.preventDefault();
            closeList();
          }
          break;
        case "Tab":
          closeList();
          break;
        default:
          break;
      }
    });

    options.forEach((opt) => {
      opt.el.addEventListener("mousedown", (event) => event.preventDefault());
      opt.el.addEventListener("click", () => applySelection(opt));
      opt.el.addEventListener("mousemove", () => {
        const index = visible.indexOf(opt);
        if (index >= 0 && index !== active) setActive(index, false);
      });
    });

    document.addEventListener("click", (event) => {
      if (!root.contains(event.target)) closeList();
    });

    root.addEventListener("focusout", (event) => {
      if (!root.contains(event.relatedTarget)) closeList();
    });

    if (form) {
      form.addEventListener("submit", (event) => {
        if (hidden.value) return;
        event.preventDefault();
        root.classList.add("is-invalid");
        openList(true);
        input.focus();
      });
    }

    // Support a server-rendered value (e.g. after a failed submit).
    const preset = options.find((opt) => String(opt.value) === String(hidden.value));
    if (preset) {
      selected = preset;
      input.value = preset.label;
      preset.el.setAttribute("aria-selected", "true");
    }
  }

  function initAll() {
    document.querySelectorAll("[data-search-select]").forEach(init);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
