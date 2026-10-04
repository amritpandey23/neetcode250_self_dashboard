(() => {
  const STORAGE_KEY = "neetcode-theme";

  function systemTheme() {
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function resolveTheme(preferred) {
    if (preferred === "dark" || preferred === "light") return preferred;
    return systemTheme();
  }

  function storedTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (_) {
      return null;
    }
  }

  function applyTheme(theme, { persist = true } = {}) {
    const next = resolveTheme(theme);
    document.documentElement.setAttribute("data-theme", next);
    document.documentElement.style.colorScheme = next;
    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch (_) {
        /* ignore */
      }
    }
    document.dispatchEvent(
      new CustomEvent("themechange", { detail: { theme: next } })
    );
    syncToggle(next);
    return next;
  }

  function syncToggle(theme) {
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      const nextLabel =
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
      btn.setAttribute("aria-label", nextLabel);
      btn.setAttribute("title", nextLabel);
      btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    });
  }

  function currentTheme() {
    return (
      document.documentElement.getAttribute("data-theme") || resolveTheme(storedTheme())
    );
  }

  function toggleTheme() {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  }

  // Apply immediately if the early head script did not run.
  if (!document.documentElement.getAttribute("data-theme")) {
    applyTheme(storedTheme() || systemTheme(), { persist: false });
  } else {
    syncToggle(currentTheme());
  }

  document.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-theme-toggle]");
    if (!btn) return;
    event.preventDefault();
    toggleTheme();
  });

  if (window.matchMedia) {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const stored = storedTheme();
      if (stored === "dark" || stored === "light") return;
      applyTheme(systemTheme(), { persist: false });
    };
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", onChange);
    } else if (typeof mq.addListener === "function") {
      mq.addListener(onChange);
    }
  }

  window.NeetTheme = {
    apply: applyTheme,
    toggle: toggleTheme,
    current: currentTheme,
  };
})();
