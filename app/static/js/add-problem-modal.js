(() => {
  const modal = document.getElementById("add-problem-modal");
  if (!modal) return;

  const openButtons = document.querySelectorAll("#open-add-problem");
  const closeButtons = [
    document.getElementById("close-add-problem"),
    document.getElementById("cancel-add-problem"),
  ].filter(Boolean);
  const categorySelect = document.getElementById("add-problem-category");

  function openModal(category) {
    if (categorySelect && category) {
      categorySelect.value = category;
    }
    if (typeof modal.showModal === "function") {
      modal.showModal();
    } else {
      modal.setAttribute("open", "");
    }
    const nameInput = modal.querySelector('input[name="name"]');
    if (nameInput) nameInput.focus();
  }

  function closeModal() {
    if (typeof modal.close === "function") {
      modal.close();
    } else {
      modal.removeAttribute("open");
    }
  }

  openButtons.forEach((btn) => {
    btn.addEventListener("click", () => openModal(btn.dataset.category || ""));
  });

  closeButtons.forEach((btn) => {
    btn.addEventListener("click", closeModal);
  });

  modal.addEventListener("click", (event) => {
    const rect = modal.getBoundingClientRect();
    const inDialog =
      rect.top <= event.clientY &&
      event.clientY <= rect.bottom &&
      rect.left <= event.clientX &&
      event.clientX <= rect.right;
    if (!inDialog) closeModal();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal.open) closeModal();
  });
})();
