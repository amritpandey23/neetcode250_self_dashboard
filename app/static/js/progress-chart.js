(() => {
  const canvas = document.getElementById("progress-chart");
  if (!canvas || typeof Chart === "undefined") return;

  const labels = JSON.parse(canvas.dataset.labels || "[]");
  const attempted = JSON.parse(canvas.dataset.attempted || "[]");
  const done = JSON.parse(canvas.dataset.done || "[]");

  const styles = getComputedStyle(document.documentElement);
  const accent = styles.getPropertyValue("--accent").trim() || "#0f766e";
  const medium = styles.getPropertyValue("--medium").trim() || "#b45309";
  const muted = styles.getPropertyValue("--muted").trim() || "#6b7280";
  const line = styles.getPropertyValue("--line").trim() || "#e5e7eb";

  // Keep ticks readable for longer ranges.
  const maxTicks = labels.length > 30 ? 8 : labels.length > 14 ? 10 : labels.length;

  new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Attempted",
          data: attempted,
          borderColor: medium,
          backgroundColor: "rgba(180, 83, 9, 0.12)",
          fill: false,
          tension: 0.25,
          pointRadius: labels.length > 40 ? 0 : 2.5,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
        {
          label: "Solved",
          data: done,
          borderColor: accent,
          backgroundColor: "rgba(15, 118, 110, 0.12)",
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
          backgroundColor: "#111827",
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
            color: muted,
            font: { family: "Outfit", size: 11 },
            maxTicksLimit: maxTicks,
            maxRotation: 0,
          },
          border: { color: line },
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: muted,
            font: { family: "Outfit", size: 11 },
            precision: 0,
          },
          grid: { color: "rgba(17, 24, 39, 0.06)" },
          border: { display: false },
        },
      },
    },
  });
})();
