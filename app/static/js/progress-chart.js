(() => {
  const canvas = document.getElementById("progress-chart");
  if (!canvas || typeof Chart === "undefined") return;

  const labels = JSON.parse(canvas.dataset.labels || "[]");
  const attempted = JSON.parse(canvas.dataset.attempted || "[]");
  const done = JSON.parse(canvas.dataset.done || "[]");

  // Keep ticks readable for longer ranges.
  const maxTicks = labels.length > 30 ? 8 : labels.length > 14 ? 10 : labels.length;

  function themeColors() {
    const styles = getComputedStyle(document.documentElement);
    const read = (name, fallback) =>
      styles.getPropertyValue(name).trim() || fallback;
    return {
      accent: read("--accent", "#0f766e"),
      medium: read("--medium", "#b45309"),
      muted: read("--muted", "#6b7280"),
      line: read("--line", "#e5e7eb"),
      grid: read("--chart-grid", "rgba(17, 24, 39, 0.06)"),
      tooltip: read("--tooltip-bg", "#111827"),
      mediumFill: read("--medium-bg", "rgba(180, 83, 9, 0.12)"),
      accentFill: read("--accent-soft", "rgba(15, 118, 110, 0.12)"),
    };
  }

  const colors = themeColors();

  const chart = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Attempted",
          data: attempted,
          borderColor: colors.medium,
          backgroundColor: colors.mediumFill,
          fill: false,
          tension: 0.25,
          pointRadius: labels.length > 40 ? 0 : 2.5,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
        {
          label: "Solved",
          data: done,
          borderColor: colors.accent,
          backgroundColor: colors.accentFill,
          fill: false,
          tension: 0.25,
          pointRadius: labels.length > 40 ? 0 : 2.5,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: colors.tooltip,
          titleFont: { family: "Outfit", size: 12 },
          bodyFont: { family: "Outfit", size: 12 },
          padding: 10,
          displayColors: true,
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: colors.muted,
            font: { family: "Outfit", size: 11 },
            maxTicksLimit: maxTicks,
            maxRotation: 0,
          },
          border: { color: colors.line },
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: colors.muted,
            font: { family: "Outfit", size: 11 },
            precision: 0,
          },
          grid: { color: colors.grid },
          border: { display: false },
        },
      },
    },
  });

  function refreshChartTheme() {
    const next = themeColors();
    const attemptedDs = chart.data.datasets[0];
    const doneDs = chart.data.datasets[1];
    attemptedDs.borderColor = next.medium;
    attemptedDs.backgroundColor = next.mediumFill;
    doneDs.borderColor = next.accent;
    doneDs.backgroundColor = next.accentFill;
    chart.options.plugins.tooltip.backgroundColor = next.tooltip;
    chart.options.scales.x.ticks.color = next.muted;
    chart.options.scales.x.border.color = next.line;
    chart.options.scales.y.ticks.color = next.muted;
    chart.options.scales.y.grid.color = next.grid;
    chart.update("none");
  }

  document.addEventListener("themechange", refreshChartTheme);
})();
