/*
 * charts.js - Progressive enhancement for Chart.js canvases with loading,
 * empty, error states, and accessible HTML table fallbacks.
 */
(function () {
  "use strict";

  const PALETTE = ["#1F4E79", "#FD7E14", "#198754", "#6F42C1", "#6C757D", "#DC3545"];
  const DASHES = [[], [6, 6], [2, 2], [6, 2, 2, 2], [10, 4]];

  function updateState(card, canvas, state, message, showRetry) {
    canvas.setAttribute("data-chart-state", state);
    const stateEl = card.querySelector(".chart-state");
    const textEl = card.querySelector(".chart-state-text");
    const retryBtn = card.querySelector(".chart-retry-btn");

    if (state === "ready") {
      if (stateEl) stateEl.classList.add("d-none");
      canvas.classList.remove("d-none");
    } else {
      if (stateEl) stateEl.classList.remove("d-none");
      canvas.classList.add("d-none");
      if (textEl && message) textEl.textContent = message;
      if (retryBtn) retryBtn.classList.toggle("d-none", !showRetry);
    }
  }

  function renderTable(container, title, labels, series) {
    if (!container) return;
    container.textContent = "";

    const table = document.createElement("table");
    table.className = "table table-sm table-bordered table-striped";

    const caption = document.createElement("caption");
    caption.textContent = title;
    table.appendChild(caption);

    const thead = document.createElement("thead");
    const trHead = document.createElement("tr");

    const thLabel = document.createElement("th");
    thLabel.setAttribute("scope", "col");
    thLabel.textContent = "Label";
    trHead.appendChild(thLabel);

    series.forEach(function (s) {
      const th = document.createElement("th");
      th.setAttribute("scope", "col");
      th.textContent = s.name;
      trHead.appendChild(th);
    });
    thead.appendChild(trHead);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    labels.forEach(function (label, idx) {
      const tr = document.createElement("tr");
      const thRow = document.createElement("th");
      thRow.setAttribute("scope", "row");
      thRow.textContent = label;
      tr.appendChild(thRow);

      series.forEach(function (s) {
        const td = document.createElement("td");
        td.textContent = s.data && s.data[idx] !== undefined ? s.data[idx] : "";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }

  function initChart(canvas) {
    const card = canvas.closest(".chart-card") || canvas.parentElement.parentElement;
    const url = canvas.dataset.chartUrl;
    const chartType = canvas.dataset.chartType || "bar";
    const chartTitle = canvas.dataset.chartTitle || "Chart";
    const emptyText = canvas.dataset.emptyText || "No data yet.";
    const isPercent = canvas.dataset.yMax === "100";
    const tableContainer = document.getElementById(canvas.id + "-table");
    const retryBtn = card.querySelector(".chart-retry-btn");

    if (retryBtn && !retryBtn._bound) {
      retryBtn._bound = true;
      retryBtn.addEventListener("click", function () {
        loadData();
      });
    }

    function loadData() {
      if (canvas._chartInstance) {
        canvas._chartInstance.destroy();
        canvas._chartInstance = null;
      }

      updateState(card, canvas, "loading", "Loading chart...", false);

      if (typeof window.Chart === "undefined") {
        console.error("Chart.js vendor library is missing.");
        updateState(card, canvas, "error", "Charts are unavailable because the Chart.js file is missing.", false);
        return;
      }

      fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json" }
      })
        .then(function (res) {
          if (res.status === 401) {
            updateState(card, canvas, "error", "Please sign in again.", false);
            throw new Error("401");
          }
          if (res.status === 403) {
            updateState(card, canvas, "error", "You do not have access to this chart.", false);
            throw new Error("403");
          }
          if (!res.ok) {
            updateState(card, canvas, "error", "The chart could not be loaded.", true);
            throw new Error("HTTP " + res.status);
          }
          return res.json();
        })
        .then(function (data) {
          const labels = data.labels || [];
          const series = data.series || [];

          let allZero = true;
          series.forEach(function (s) {
            (s.data || []).forEach(function (val) {
              if (val !== 0) allZero = false;
            });
          });

          if (labels.length === 0 || allZero) {
            updateState(card, canvas, "empty", emptyText, false);
            return;
          }

          renderTable(tableContainer, chartTitle, labels, series);

          const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          canvas.setAttribute("data-animated", prefersReduced ? "false" : "true");

          const datasets = [];
          if (chartType === "doughnut") {
            const doughnutData = (series[0] && series[0].data) || [];
            datasets.push({
              data: doughnutData,
              backgroundColor: PALETTE.slice(0, labels.length)
            });
          } else {
            series.forEach(function (s, sIdx) {
              const color = PALETTE[sIdx % PALETTE.length];
              const ds = {
                label: s.name,
                data: s.data,
                backgroundColor: color,
                borderColor: color,
                borderWidth: chartType === "line" ? 2 : 1 + (sIdx % 2),
                borderDash: chartType === "line" ? DASHES[sIdx % DASHES.length] : []
              };
              if (chartType === "line") {
                ds.tension = 0.2;
                ds.fill = false;
                ds.pointRadius = 3;
              }
              datasets.push(ds);
            });
          }

          const scales = {};
          if (chartType !== "doughnut") {
            scales.x = { stacked: chartType === "stacked-bar" };
            scales.y = {
              stacked: chartType === "stacked-bar",
              beginAtZero: true,
              ticks: {
                precision: isPercent ? undefined : 0,
                callback: function (val) {
                  return isPercent ? val + "%" : val;
                }
              }
            };
            if (isPercent) {
              scales.y.min = 0;
              scales.y.max = 100;
            }
          }

          const config = {
            type: chartType === "stacked-bar" ? "bar" : chartType,
            data: { labels: labels, datasets: datasets },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              animation: prefersReduced ? false : undefined,
              plugins: {
                legend: {
                  display: chartType === "doughnut" || series.length > 1,
                  position: chartType === "doughnut" ? "bottom" : "top"
                }
              },
              scales: scales
            }
          };

          canvas._chartInstance = new window.Chart(canvas, config);
          updateState(card, canvas, "ready", null, false);
        })
        .catch(function (err) {
          if (err.message !== "401" && err.message !== "403") {
            updateState(card, canvas, "error", "The chart could not be loaded.", true);
          }
        });
    }

    loadData();
  }

  document.addEventListener("DOMContentLoaded", function () {
    const canvases = document.querySelectorAll("canvas[data-chart-url]");
    canvases.forEach(initChart);
  });
})();
