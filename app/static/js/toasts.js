(() => {
  const AUTO_HIDE_MS = 5000;
  const EXIT_MS = 180;

  function dismissToast(toast) {
    if (!toast || toast.dataset.leaving === "1") return;
    toast.dataset.leaving = "1";
    toast.classList.add("is-leaving");
    window.setTimeout(() => {
      toast.remove();
      const stack = document.getElementById("toast-stack");
      if (stack && !stack.querySelector("[data-toast]")) stack.remove();
    }, EXIT_MS);
  }

  function bindToast(toast) {
    let timer = null;

    const schedule = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => dismissToast(toast), AUTO_HIDE_MS);
    };

    const dismissBtn = toast.querySelector("[data-toast-dismiss]");
    if (dismissBtn) {
      dismissBtn.addEventListener("click", () => {
        window.clearTimeout(timer);
        dismissToast(toast);
      });
    }

    toast.addEventListener("mouseenter", () => window.clearTimeout(timer));
    toast.addEventListener("mouseleave", schedule);
    schedule();
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-toast]").forEach((toast) => {
      requestAnimationFrame(() => toast.classList.add("is-visible"));
      bindToast(toast);
    });
  });
})();
