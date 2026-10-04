(() => {
  document.querySelectorAll(".doc-entry-list-row[data-href]").forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("a, button, form, .doc-entry-tools")) return;
      window.location.href = row.dataset.href;
    });
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        window.location.href = row.dataset.href;
      }
    });
  });
})();
