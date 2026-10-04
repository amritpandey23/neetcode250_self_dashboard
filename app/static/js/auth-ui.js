(() => {
  document.querySelectorAll("[data-password-toggle]").forEach((btn) => {
    const wrap = btn.closest(".auth-password");
    const input = wrap ? wrap.querySelector("input") : null;
    if (!input) return;

    btn.addEventListener("click", () => {
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      btn.setAttribute("title", showing ? "Show password" : "Hide password");
      btn.innerHTML = showing
        ? '<i data-lucide="eye" class="icon" aria-hidden="true"></i>'
        : '<i data-lucide="eye-off" class="icon" aria-hidden="true"></i>';
      if (typeof window.refreshIcons === "function") window.refreshIcons();
    });
  });
})();
