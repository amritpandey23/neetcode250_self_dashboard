(() => {
  // Autosubmit filters on change (GET form — no backend changes).
  const form = document.getElementById("filters-form");
  if (form) {
    form.querySelectorAll("[data-autosubmit]").forEach((el) => {
      el.addEventListener("change", () => form.requestSubmit());
    });
    const search = form.querySelector('input[name="q"]');
    let timer = null;
    if (search) {
      search.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => form.requestSubmit(), 350);
      });
    }
  }

  // Clickable problem rows (bookmark/leetcode stopPropagation in markup).
  document.querySelectorAll(".problem-row[data-href]").forEach((row) => {
    const go = () => {
      window.location.href = row.dataset.href;
    };
    row.addEventListener("click", (event) => {
      if (event.target.closest("a, button, form")) return;
      go();
    });
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        go();
      }
    });
  });

  // Mobile category drawer.
  const sidebar = document.getElementById("category-sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  const backdrop = document.getElementById("sidebar-backdrop");
  if (!sidebar || !toggle || !backdrop) return;

  const setOpen = (open) => {
    sidebar.classList.toggle("is-open", open);
    backdrop.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("sidebar-open", open);
  };

  toggle.addEventListener("click", () => setOpen(!sidebar.classList.contains("is-open")));
  backdrop.addEventListener("click", () => setOpen(false));
})();
