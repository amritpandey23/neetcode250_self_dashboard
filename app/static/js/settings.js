(function () {
  var select = document.getElementById("email-challenge-timezone");
  if (!select) return;

  var detected = "";
  try {
    detected = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch (e) {
    detected = "";
  }

  function hasOption(value) {
    return Array.prototype.some.call(select.options, function (opt) {
      return opt.value === value;
    });
  }

  function applyTimezone(value) {
    if (!value || !hasOption(value)) return false;
    select.value = value;
    return true;
  }

  var hint = document.getElementById("tz-detected");
  var btn = document.getElementById("tz-detect-btn");
  if (detected && hasOption(detected)) {
    if (hint) {
      hint.hidden = false;
      hint.textContent = "Browser detects: " + detected + ". ";
    }
    if (btn) {
      btn.hidden = false;
      btn.addEventListener("click", function () {
        applyTimezone(detected);
      });
    }
    if (select.getAttribute("data-autodetect") === "1") {
      applyTimezone(detected);
    }
  }
})();
