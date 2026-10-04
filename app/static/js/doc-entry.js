(() => {
  const form = document.getElementById("doc-entry-form");
  const titleInput = document.getElementById("entry-title");
  const bodyInput = document.getElementById("md-input");
  const saveBtn = document.getElementById("doc-save-btn");
  const saveState = document.getElementById("doc-save-state");
  if (!form || !titleInput || !bodyInput || !saveBtn) return;

  const initial = {
    title: titleInput.value,
    body: bodyInput.value,
  };

  function isDirty() {
    return titleInput.value !== initial.title || bodyInput.value !== initial.body;
  }

  function updateSaveUi() {
    const dirty = isDirty();
    saveBtn.disabled = !dirty && Boolean(initial.title);
    if (!saveState) return;
    if (dirty) {
      saveState.innerHTML =
        '<i data-lucide="dot" class="icon"></i><span>Unsaved changes</span>';
      saveState.classList.add("is-dirty");
    } else if (initial.title || initial.body) {
      if (!saveState.dataset.locked) {
        saveState.innerHTML =
          '<i data-lucide="check" class="icon"></i><span>Saved</span>';
      }
      saveState.classList.remove("is-dirty");
    }
    if (typeof window.refreshIcons === "function") window.refreshIcons();
  }

  titleInput.addEventListener("input", updateSaveUi);
  bodyInput.addEventListener("input", updateSaveUi);

  form.addEventListener("submit", () => {
    saveBtn.disabled = true;
    if (saveState) {
      saveState.dataset.locked = "1";
      saveState.innerHTML =
        '<i data-lucide="loader-circle" class="icon"></i><span>Saving…</span>';
      saveState.classList.remove("is-dirty");
      if (typeof window.refreshIcons === "function") window.refreshIcons();
    }
  });

  updateSaveUi();
  if (saveState && saveState.textContent.includes("Saved")) {
    saveState.dataset.locked = "1";
  }
})();
