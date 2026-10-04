(() => {
  const form = document.getElementById("problem-form");
  const statusSelect = document.getElementById("status-select");
  const statusControl = document.querySelector(".status-control");
  const notesInput = document.getElementById("notes-input");
  const saveBtn = document.getElementById("save-notes-btn");
  const saveState = document.getElementById("save-state");
  if (!form || !statusSelect || !notesInput || !saveBtn) return;

  const initial = {
    status: statusSelect.value,
    notes: notesInput.value,
  };

  function syncStatusChrome() {
    if (!statusControl) return;
    statusControl.classList.remove(
      "status-control-todo",
      "status-control-attempted",
      "status-control-done"
    );
    statusControl.classList.add(`status-control-${statusSelect.value}`);
    const iconHost = statusControl.querySelector(".status-control-icon");
    if (!iconHost) return;
    const name =
      statusSelect.value === "done"
        ? "check"
        : statusSelect.value === "attempted"
          ? "circle-dot"
          : "circle";
    iconHost.innerHTML = `<i data-lucide="${name}" class="icon"></i>`;
    if (typeof window.refreshIcons === "function") window.refreshIcons();
  }

  function isDirty() {
    return (
      statusSelect.value !== initial.status || notesInput.value !== initial.notes
    );
  }

  function updateSaveUi() {
    const dirty = isDirty();
    saveBtn.disabled = !dirty;
    if (!saveState) return;
    if (dirty) {
      saveState.innerHTML =
        '<i data-lucide="dot" class="icon"></i><span>Unsaved changes</span>';
      saveState.classList.add("is-dirty");
    } else if (initial.notes || initial.status) {
      // Keep server-rendered last-saved text if present; otherwise mark saved.
      if (!saveState.dataset.locked) {
        const existing = saveState.querySelector("span");
        if (!existing || existing.textContent === "Unsaved changes" || existing.textContent === "Not saved yet") {
          saveState.innerHTML =
            '<i data-lucide="check" class="icon"></i><span>Saved</span>';
        }
      }
      saveState.classList.remove("is-dirty");
    }
    if (typeof window.refreshIcons === "function") window.refreshIcons();
  }

  statusSelect.addEventListener("change", () => {
    syncStatusChrome();
    updateSaveUi();
  });
  notesInput.addEventListener("input", updateSaveUi);

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

  syncStatusChrome();
  updateSaveUi();
  if (saveState && saveState.textContent.includes("Last saved")) {
    saveState.dataset.locked = "1";
  }
})();
