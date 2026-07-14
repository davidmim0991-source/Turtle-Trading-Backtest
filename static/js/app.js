(() => {
  const form = document.getElementById("backtest-form");
  const fileInput = document.getElementById("csv-file");
  const fileLabel = document.getElementById("file-label");
  const fileDrop = document.getElementById("file-drop");
  const emaToggle = document.getElementById("use_ema_filter");
  const emaLength = document.getElementById("ema_length");
  const runBtn = document.getElementById("run-btn");
  const exportBtn = document.getElementById("export-btn");
  const alertEl = document.getElementById("alert");
  const emptyState = document.getElementById("empty-state");
  const results = document.getElementById("results");
  const metrics = document.getElementById("metrics");
  const noTrades = document.getElementById("no-trades");
  const statusBadge = document.getElementById("status-badge");
  const equityCard = document.getElementById("equity-card");
  const tradesBody = document.querySelector("#trades-table tbody");
  const monthlyBody = document.querySelector("#monthly-table tbody");
  const tradesEmpty = document.getElementById("trades-empty");
  const monthlyEmpty = document.getElementById("monthly-empty");
  const sidebar = document.getElementById("sidebar");
  const sidebarToggle = document.getElementById("sidebar-toggle");

  const chartLayoutBase = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Source Sans 3, sans-serif", color: "#94A3B8" },
    margin: { l: 45, r: 20, t: 20, b: 40 },
  };

  function formatDetail(detail) {
    if (!detail) return "Request failed.";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
    return String(detail);
  }

  function showAlert(message, type = "error") {
    alertEl.hidden = false;
    alertEl.textContent = message;
    alertEl.classList.toggle("alert--info", type === "info");
  }

  function clearAlert() {
    alertEl.hidden = true;
    alertEl.textContent = "";
  }

  function setLoading(isLoading) {
    runBtn.disabled = isLoading;
    const label = runBtn.querySelector(".btn__label");
    const spinner = runBtn.querySelector(".btn__spinner");
    label.textContent = isLoading ? "Running…" : "Run backtest";
    spinner.hidden = !isLoading;
  }

  function buildFormData() {
    if (!fileInput.files || !fileInput.files[0]) {
      throw new Error("Please upload a CSV file first.");
    }

    const data = new FormData();
    data.append("file", fileInput.files[0]);
    data.append("entry_lookback", document.getElementById("entry_lookback").value);
    data.append("exit_lookback", document.getElementById("exit_lookback").value);
    data.append("atr_length", document.getElementById("atr_length").value);
    data.append("use_filter", document.getElementById("use_filter").checked ? "true" : "false");
    data.append("use_ema_filter", emaToggle.checked ? "true" : "false");
    data.append("ema_length", emaLength.value);
    data.append("buffer", document.getElementById("buffer").value);
    return data;
  }

  function formatNumber(value, digits = 2) {
    return Number(value).toFixed(digits);
  }

  function formatSigned(value, digits = 2) {
    const n = Number(value);
    const body = Math.abs(n).toFixed(digits);
    return `${n >= 0 ? "+" : "-"}${body}`;
  }

  function renderMetrics(stats) {
    const cards = [
      { label: "Net ATR", value: formatNumber(stats.net_atr) },
      { label: "Max drawdown", value: formatNumber(stats.max_drawdown) },
      { label: "Win rate", value: `${formatNumber(stats.win_rate, 1)}%` },
      { label: "Weekly win rate", value: `${formatNumber(stats.weekly_win_rate, 1)}%` },
      { label: "Avg winning week", value: formatNumber(stats.avg_winning_week) },
      { label: "Avg losing week", value: formatNumber(stats.avg_losing_week) },
      { label: "Avg week (all)", value: formatNumber(stats.avg_week) },
      { label: "Number of trades", value: String(stats.number_of_trades) },
    ];

    metrics.innerHTML = cards
      .map(
        (card, index) => `
        <article class="metric" style="animation-delay:${index * 40}ms">
          <p class="metric__label">${card.label}</p>
          <p class="metric__value">${card.value}</p>
        </article>`
      )
      .join("");
  }

  function renderBadge(netAtr) {
    statusBadge.hidden = false;
    statusBadge.className = "badge";
    if (netAtr > 0) {
      statusBadge.classList.add("badge--good");
      statusBadge.textContent = "Profitable";
    } else if (netAtr < 0) {
      statusBadge.classList.add("badge--bad");
      statusBadge.textContent = "Unprofitable";
    } else {
      statusBadge.classList.add("badge--flat");
      statusBadge.textContent = "Break-even";
    }
  }

  function renderEquity(equityCurve) {
    if (!equityCurve.length) {
      equityCard.hidden = true;
      return;
    }
    equityCard.hidden = false;
    const x = equityCurve.map((_, i) => i + 1);
    Plotly.newPlot(
      "equity-chart",
      [
        {
          x,
          y: equityCurve,
          type: "scatter",
          mode: "lines+markers",
          fill: "tozeroy",
          line: { color: "#2DD4BF", width: 2.5 },
          marker: { size: 6, color: "#5EEAD4" },
          fillcolor: "rgba(45, 212, 191, 0.18)",
          name: "Equity (ATR)",
          hovertemplate: "Trade %{x}<br>Equity %{y:.2f} ATR<extra></extra>",
        },
      ],
      {
        ...chartLayoutBase,
        xaxis: { title: "Trade", showgrid: false, zeroline: false },
        yaxis: {
          title: "Equity (ATR)",
          showgrid: true,
          gridcolor: "rgba(148, 163, 184, 0.15)",
          zeroline: false,
        },
        shapes: [
          {
            type: "line",
            x0: 0.5,
            x1: equityCurve.length + 0.5,
            y0: 0,
            y1: 0,
            line: { color: "rgba(148,163,184,0.4)", width: 1, dash: "dot" },
          },
        ],
        hovermode: "x unified",
      },
      { responsive: true, displayModeBar: false }
    );
  }

  function renderTrades(trades) {
    tradesBody.innerHTML = "";
    if (!trades.length) {
      tradesEmpty.hidden = false;
      return;
    }
    tradesEmpty.hidden = true;
    const frag = document.createDocumentFragment();
    for (const trade of trades) {
      const tr = document.createElement("tr");
      const resultClass = trade.atr_result > 0 ? "pos" : trade.atr_result < 0 ? "neg" : "";
      tr.innerHTML = `
        <td class="mono">${trade.trade_number}</td>
        <td>${trade.direction}</td>
        <td>${trade.entry_time}</td>
        <td>${trade.exit_time}</td>
        <td class="mono">${formatNumber(trade.entry_price, 4)}</td>
        <td class="mono">${formatNumber(trade.exit_price, 4)}</td>
        <td class="mono">${formatNumber(trade.entry_atr, 4)}</td>
        <td class="mono ${resultClass}">${formatSigned(trade.atr_result)}</td>
        <td class="mono">${trade.bars_held}</td>
        <td>${trade.exit_reason}</td>`;
      frag.appendChild(tr);
    }
    tradesBody.appendChild(frag);
  }

  function renderMonthly(monthly) {
    monthlyBody.innerHTML = "";
    const chartEl = document.getElementById("monthly-chart");
    if (!monthly.length) {
      monthlyEmpty.hidden = false;
      chartEl.innerHTML = "";
      return;
    }
    monthlyEmpty.hidden = true;
    const frag = document.createDocumentFragment();
    for (const row of monthly) {
      const tr = document.createElement("tr");
      const cls = row.net_atr > 0 ? "pos" : row.net_atr < 0 ? "neg" : "";
      tr.innerHTML = `
        <td>${row.month}</td>
        <td class="mono ${cls}">${formatSigned(row.net_atr)}</td>`;
      frag.appendChild(tr);
    }
    monthlyBody.appendChild(frag);

    if (monthly.length > 1) {
      Plotly.newPlot(
        "monthly-chart",
        [
          {
            x: monthly.map((r) => r.month),
            y: monthly.map((r) => r.net_atr),
            type: "bar",
            marker: {
              color: monthly.map((r) => (r.net_atr >= 0 ? "#34D399" : "#FB7185")),
            },
            hovertemplate: "%{x}<br>Net ATR %{y:.2f}<extra></extra>",
          },
        ],
        {
          ...chartLayoutBase,
          height: 320,
          xaxis: { showgrid: false, title: null },
          yaxis: {
            title: "Net ATR",
            showgrid: true,
            gridcolor: "rgba(148, 163, 184, 0.15)",
          },
        },
        { responsive: true, displayModeBar: false }
      );
    } else {
      chartEl.innerHTML = "";
    }
  }

  function renderResult(payload) {
    emptyState.hidden = true;
    results.hidden = false;
    exportBtn.disabled = false;

    const stats = payload.statistics || {};
    const trades = payload.trades || [];
    const equity = payload.equity_curve || [];
    const monthly = payload.monthly_performance || [];

    if (!stats.number_of_trades) {
      noTrades.hidden = false;
      metrics.hidden = true;
      statusBadge.hidden = true;
    } else {
      noTrades.hidden = true;
      metrics.hidden = false;
      renderBadge(stats.net_atr);
      renderMetrics(stats);
    }

    renderEquity(equity);
    renderTrades(trades);
    renderMonthly(monthly);
  }

  async function runBacktest(event) {
    event.preventDefault();
    clearAlert();
    setLoading(true);
    try {
      const data = buildFormData();
      const response = await fetch("/api/backtest", {
        method: "POST",
        body: data,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(formatDetail(payload.detail) || "Backtest failed.");
      }
      renderResult(payload);
      if (window.matchMedia("(max-width: 900px)").matches) {
        sidebar.classList.remove("is-open");
      }
    } catch (err) {
      showAlert(err.message || "Backtest failed.");
    } finally {
      setLoading(false);
    }
  }

  async function exportExcel() {
    clearAlert();
    try {
      const data = buildFormData();
      const response = await fetch("/api/export", {
        method: "POST",
        body: data,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(formatDetail(payload.detail) || "Export failed.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "turtle_backtest_results.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      showAlert(err.message || "Export failed.");
    }
  }

  function syncEmaField() {
    emaLength.disabled = !emaToggle.checked;
  }

  function syncFileLabel() {
    const file = fileInput.files && fileInput.files[0];
    fileLabel.textContent = file ? file.name : "Drop OHLC CSV or click to browse";
  }

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((el) => {
        el.classList.toggle("is-active", el === tab);
        el.setAttribute("aria-selected", el === tab ? "true" : "false");
      });
      document.querySelectorAll(".tab-panel").forEach((panel) => {
        const active = panel.id === `panel-${tab.dataset.tab}`;
        panel.hidden = !active;
        panel.classList.toggle("is-active", active);
      });
      window.dispatchEvent(new Event("resize"));
    });
  });

  ["dragenter", "dragover"].forEach((evt) => {
    fileDrop.addEventListener(evt, (e) => {
      e.preventDefault();
      fileDrop.classList.add("is-dragover");
    });
  });
  ["dragleave", "drop"].forEach((evt) => {
    fileDrop.addEventListener(evt, (e) => {
      e.preventDefault();
      fileDrop.classList.remove("is-dragover");
    });
  });
  fileDrop.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      fileInput.files = files;
      syncFileLabel();
    }
  });

  fileInput.addEventListener("change", syncFileLabel);
  emaToggle.addEventListener("change", syncEmaField);
  form.addEventListener("submit", runBacktest);
  exportBtn.addEventListener("click", exportExcel);
  sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("is-open");
  });

  syncEmaField();
  syncFileLabel();
})();
