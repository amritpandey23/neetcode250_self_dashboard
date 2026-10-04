(() => {
  // Clickable space rows (actions stopPropagation in markup).
  document.querySelectorAll(".spaces-list-item[data-href]").forEach((row) => {
    const go = () => {
      window.location.href = row.dataset.href;
    };
    row.addEventListener("click", (event) => {
      if (event.target.closest("a, button, form, details, .spaces-list-actions")) return;
      go();
    });
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        go();
      }
    });
  });

  const focusCreate = document.getElementById("focus-create-space");
  const spaceInput = document.getElementById("space-name");
  if (focusCreate && spaceInput) {
    focusCreate.addEventListener("click", () => {
      spaceInput.focus();
      spaceInput.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  }
})();
