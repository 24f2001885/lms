/*
FILE PURPOSE: Progressive enhancement that turns every canvas[data-chart-url] into
a Chart.js chart, with loading, empty and error states, an accessible data table,
and responsive small-screen legend/axis options (P8 & P10 Section 8).
*/
(function () {
  "use strict";

  var PALETTE = ["#1F4E79", "#FD7E14", "#198754", "#6F42C1", "#6C757D", "#DC3545"];
  var DASH_PATTERNS = [[], [6, 4], [2, 3], [8, 3, 2, 3], [4, 4], [10, 4]];
  var instances = {};

  function setState(canvas, card, stateEl, retryBtn, state, message) {
    canvas.setAttribute("data-chart-state", state);
    if (stateEl) {
      stateEl.textContent = message || "";
      stateEl.style.display = message ? "block" : "none";
    }
    if (retryBtn) {
      retryBtn.classList.toggle("d-none", state !== "error");
    }
  }

  function isAllEmpty(payload) {
    if (!payload || !Array.isArray(payload.labels) || payload.labels.length === 0) {
      return true;
    }
    if (!Array.isArray(payload.series) || payload.series.length === 0) {
      return true;
    }
    return payload.series.every(function (s) {
      return !Array.isArray(s.data) || s.data.every(function (v) { return Number(v) === 0; });
    });
  }

  function buildDataTable(canvas, card, payload) {
    var tableHost = document.getElementById(canvas.id + "-table");
    if (!tableHost) return;
    while (tableHost.firstChild) tableHost.removeChild(tableHost.firstChild);

    var tbl = document.createElement("table");
    tbl.className = "table table-sm table-static chart-data-table mb-0";

    var cap = document.createElement("caption");
    cap.className = "visually-hidden";
    cap.textContent = canvas.getAttribute("aria-label") || "Chart data";
    tbl.appendChild(cap);

    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    var th0 = document.createElement("th");
    th0.setAttribute("scope", "col");
    th0.textContent = "Category";
    hr.appendChild(th0);

    payload.series.forEach(function (s) {
      var th = document.createElement("th");
      th.setAttribute("scope", "col");
      th.textContent = s.name;
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    tbl.appendChild(thead);

    var tbody = document.createElement("tbody");
    payload.labels.forEach(function (lbl, idx) {
      var tr = document.createElement("tr");
      var rowTh = document.createElement("th");
      rowTh.setAttribute("scope", "row");
      rowTh.textContent = String(lbl);
      tr.appendChild(rowTh);
      payload.series.forEach(function (s) {
        var td = document.createElement("td");
        td.textContent = String(s.data[idx] !== undefined ? s.data[idx] : 0);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
    tableHost.appendChild(tbl);
  }

  function renderChart(canvas, card, payload) {
    var rawKind = canvas.getAttribute("data-chart-type") || "bar";
    var chartType = rawKind === "stacked-bar" ? "bar" : rawKind;
    var isStacked = rawKind === "stacked-bar";
    var isPercent = canvas.getAttribute("data-y-max") === "100";
    var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var isSmall = window.innerWidth < 576;

    canvas.setAttribute("data-animated", reducedMotion ? "false" : "true");

    var datasets = payload.series.map(function (s, idx) {
      var color = PALETTE[idx % PALETTE.length];
      if (chartType === "doughnut") {
        return {
          label: s.name,
          data: s.data,
          backgroundColor: payload.labels.map(function (_, i) { return PALETTE[i % PALETTE.length]; }),
          borderWidth: 2
        };
      }
      return {
        label: s.name,
        data: s.data,
        backgroundColor: color,
        borderColor: color,
        borderWidth: (idx % 3) + 1,
        borderDash: chartType === "line" ? DASH_PATTERNS[idx % DASH_PATTERNS.length] : undefined,
        tension: chartType === "line" ? 0.2 : 0
      };
    });

    var scales = chartType === "doughnut" ? {} : {
      x: {
        stacked: isStacked,
        ticks: {
          autoSkip: true,
          maxRotation: isSmall ? 45 : 45,
          minRotation: 0
        }
      },
      y: {
        stacked: isStacked,
        beginAtZero: true,
        max: isPercent ? 100 : undefined,
        ticks: {
          precision: isPercent ? 1 : 0,
          callback: function (value) {
            return isPercent ? value + "%" : value;
          }
        }
      }
    };

    if (instances[canvas.id]) {
      instances[canvas.id].destroy();
    }

    instances[canvas.id] = new window.Chart(canvas, {
      type: chartType,
      data: {
        labels: payload.labels,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: reducedMotion ? false : undefined,
        plugins: {
          legend: {
            display: chartType === "doughnut" || payload.series.length > 1,
            position: (chartType === "doughnut" || isSmall) ? "bottom" : "top",
            labels: {
              font: { size: isSmall ? 11 : 12 }
            }
          }
        },
        scales: scales
      }
    });
  }

  function loadCanvas(canvas) {
    var card = canvas.closest(".chart-card") || canvas.parentNode;
    var stateEl = card ? card.querySelector(".chart-state") : null;
    var retryBtn = card ? card.querySelector("[data-chart-retry]") : null;
    var url = canvas.getAttribute("data-chart-url");

    if (typeof window.Chart === "undefined") {
      console.error("[charts] Chart.js global missing");
      setState(canvas, card, stateEl, retryBtn, "error", "Charts are unavailable because the Chart.js file is missing.");
      return;
    }

    setState(canvas, card, stateEl, retryBtn, "loading", "Loading chart...");

    fetch(url, {
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    })
      .then(function (resp) {
        if (resp.status === 401) {
          throw new Error("Please sign in again.");
        }
        if (resp.status === 403) {
          throw new Error("You do not have access to this chart.");
        }
        if (!resp.ok) {
          throw new Error("The chart could not be loaded.");
        }
        return resp.json();
      })
      .then(function (payload) {
        if (!payload || !Array.isArray(payload.labels) || !Array.isArray(payload.series)) {
          throw new Error("The chart could not be loaded.");
        }
        buildDataTable(canvas, card, payload);
        if (isAllEmpty(payload)) {
          var emptyTxt = canvas.getAttribute("data-empty-text") || "No data yet.";
          setState(canvas, card, stateEl, retryBtn, "empty", emptyTxt);
          return;
        }
        renderChart(canvas, card, payload);
        setState(canvas, card, stateEl, retryBtn, "ready", "");
      })
      .catch(function (err) {
        var msg = (err && err.message && (err.message.indexOf("Please sign in") === 0 || err.message.indexOf("You do not") === 0))
          ? err.message
          : "The chart could not be loaded.";
        setState(canvas, card, stateEl, retryBtn, "error", msg);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var canvases = document.querySelectorAll("canvas[data-chart-url]");
    Array.prototype.forEach.call(canvases, function (canvas) {
      var card = canvas.closest(".chart-card") || canvas.parentNode;
      var retryBtn = card ? card.querySelector("[data-chart-retry]") : null;
      if (retryBtn) {
        retryBtn.addEventListener("click", function () {
          loadCanvas(canvas);
        });
      }
      loadCanvas(canvas);
    });
  });
})();
