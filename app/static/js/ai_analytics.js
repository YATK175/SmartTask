document.addEventListener("DOMContentLoaded", () => {
  const elements = {
    total: document.getElementById("aiTotalTasks"),
    analyzed: document.getElementById("aiAnalyzedTasks"),
    highRisk: document.getElementById("aiHighRisk"),
    unanalyzed: document.getElementById("aiUnanalyzed"),
    chart: document.getElementById("riskChart"),
    metrics: document.getElementById("modelMetrics"),
    table: document.getElementById("aiTasksTable"),
    alert: document.getElementById("aiAlert"),
    recommendationPanel: document.getElementById("recommendationPanel"),
    recommendationContent: document.getElementById("recommendationContent"),
    refreshButton: document.getElementById("refreshAiButton"),
  };

  function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML;
  }

  function formatDate(value) {
    if (!value) {
      return "Не встановлено";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "Некоректна дата";
    }

    return date.toLocaleString("uk-UA", {
      dateStyle: "short",
      timeStyle: "short",
    });
  }

  function showAlert(message, type = "success") {
    elements.alert.innerHTML = `
            <div class="alert alert-${type}" role="alert">
                ${escapeHtml(message)}
            </div>
        `;
  }

  async function apiRequest(url, options = {}) {
    const response = await fetch(url, options);

    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Необхідна авторизація.");
    }

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Помилка виконання запиту.");
    }

    return result;
  }

  function statusLabel(status) {
    const labels = {
      NEW: "Нове",
      IN_PROGRESS: "У процесі",
      COMPLETED: "Виконано",
      CANCELLED: "Скасовано",
    };

    return labels[status] || status;
  }

  // Побудова графіка розподілу ризиків.
  function renderChart(summary) {
    const values = [summary.low_risk, summary.medium_risk, summary.high_risk];

    const total = values.reduce((sum, value) => sum + value, 0);

    // Порожній стан, якщо прогнозів ще немає.
    if (total === 0) {
      if (window.Plotly) {
        window.Plotly.purge(elements.chart);
      }

      elements.chart.innerHTML = `
                <div class="d-flex flex-column
                            align-items-center
                            justify-content-center
                            text-center h-100 p-4">

                    <div style="font-size: 38px;">📊</div>

                    <h6 class="mt-3">
                        Поки немає прогнозів
                    </h6>

                    <p class="text-secondary small">
                        Створіть активне завдання та запустіть
                        інтелектуальний аналіз, щоб побачити
                        розподіл ризиків.
                    </p>

                </div>
            `;

      return;
    }

    // Резервне відображення без Plotly.
    if (!window.Plotly) {
      elements.chart.innerHTML = `
                <div class="p-4">
                    <p>LOW: ${values[0]}</p>
                    <p>MEDIUM: ${values[1]}</p>
                    <p>HIGH: ${values[2]}</p>
                </div>
            `;

      return;
    }

    const chartData = [
      {
        x: ["LOW", "MEDIUM", "HIGH"],
        y: values,
        type: "bar",

        marker: {
          color: ["#16A36A", "#E5A72D", "#DC6262"],
        },

        text: values,
        textposition: "auto",

        hovertemplate: "%{x}: %{y} завдань<extra></extra>",
      },
    ];

    const layout = {
      margin: {
        t: 20,
        r: 20,
        b: 50,
        l: 50,
      },

      yaxis: {
        title: "Кількість завдань",
        rangemode: "tozero",
        dtick: 1,
      },

      xaxis: {
        title: "Рівень ризику",
      },

      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",

      font: {
        family: "Arial",
        color: "#354052",
      },
    };

    window.Plotly.purge(elements.chart);

    window.Plotly.newPlot(elements.chart, chartData, layout, {
      responsive: true,
      displayModeBar: false,
    }).catch((error) => {
      console.error("Plotly error:", error);

      elements.chart.textContent = "Не вдалося побудувати графік.";
    });
  }

  // Відображення метрик навченої моделі.
  function renderMetrics(metrics) {
    const items = [
      ["Accuracy", metrics.accuracy],
      ["Precision", metrics.precision],
      ["Recall", metrics.recall],
      ["F1-score", metrics.f1_score],
      ["ROC-AUC", metrics.roc_auc],
    ];

    elements.metrics.innerHTML = `
            <div class="mb-3">
                <strong>Модель:</strong>
                ${escapeHtml(metrics.model_version)}
            </div>

            ${items
              .map(
                ([label, value]) => `
                <div class="d-flex justify-content-between
                            border-bottom py-2">
                    <span>${label}</span>

                    <strong>
                        ${(Number(value) * 100).toFixed(2)}%
                    </strong>
                </div>
            `
              )
              .join("")}

            <div class="small text-secondary mt-3">
                Тип датасету:
                ${escapeHtml(metrics.dataset_type)}
            </div>
        `;
  }

  // Відображення таблиці завдань та прогнозів.
  function renderTasks(tasks) {
    if (tasks.length === 0) {
      elements.table.innerHTML = `
                <tr>
                    <td colspan="6"
                        class="text-center text-secondary">
                        Завдань поки немає.
                    </td>
                </tr>
            `;

      return;
    }

    elements.table.innerHTML = tasks
      .map((task) => {
        const prediction = task.latest_prediction;

        let riskHtml = `
                <span class="text-secondary">
                    Не проаналізовано
                </span>
            `;

        if (prediction) {
          const riskColors = {
            LOW: "success",
            MEDIUM: "warning",
            HIGH: "danger",
          };

          const color = riskColors[prediction.risk_level] || "secondary";

          riskHtml = `
                    <span class="badge text-bg-${color}">
                        ${escapeHtml(prediction.risk_level)}
                    </span>
                `;
        }

        let scoreHtml = "—";

        if (prediction) {
          scoreHtml = `
                    <strong>
                        ${Number(prediction.risk_percentage).toFixed(2)}%
                    </strong>

                    <div class="small text-secondary">
                        Оцінка моделі
                    </div>
                `;
        }

        const isFinal = ["COMPLETED", "CANCELLED"].includes(task.status);

        const buttonLabel = prediction ? "Повторити аналіз" : "Проаналізувати";

        return `
                <tr>
                    <td>
                        <strong>
                            ${escapeHtml(task.title)}
                        </strong>

                        <div class="small text-secondary">
                            Дедлайн: ${formatDate(task.deadline)}
                        </div>
                    </td>

                    <td>${escapeHtml(task.priority)}</td>

                    <td>
                        ${escapeHtml(statusLabel(task.status))}
                    </td>

                    <td>${scoreHtml}</td>

                    <td>${riskHtml}</td>

                    <td>
                        <button
                            class="btn btn-sm btn-outline-primary"
                            data-action="analyze"
                            data-id="${Number(task.id)}"
                            ${isFinal ? "disabled" : ""}>
                            ${isFinal ? "Недоступно" : buttonLabel}
                        </button>
                    </td>
                </tr>
            `;
      })
      .join("");
  }

  // Завантаження загальної аналітики.
  async function loadAnalytics() {
    elements.table.innerHTML = `
            <tr>
                <td colspan="6"
                    class="text-center text-secondary">
                    Завантаження...
                </td>
            </tr>
        `;

    try {
      const summary = await apiRequest("/api/ai-analytics/summary");

      const data = summary.summary;

      elements.total.textContent = data.total_tasks;
      elements.analyzed.textContent = data.analyzed_tasks;
      elements.highRisk.textContent = data.high_risk;
      elements.unanalyzed.textContent = data.unanalyzed_tasks;

      renderChart(data);
      renderTasks(summary.tasks);
    } catch (error) {
      showAlert(error.message, "danger");
    }

    try {
      const metrics = await apiRequest("/api/ai-analytics/model-metrics");

      renderMetrics(metrics);
    } catch (error) {
      elements.metrics.textContent = "Не вдалося завантажити метрики моделі.";
    }
  }

  // Відображення результату прогнозування.
  function renderRecommendations(result) {
    const analysis = result.analysis;
    const prediction = result.prediction;
    const factors = analysis.contextual_factors || [];

    const levelLabels = {
      HIGH: "Високий",
      MEDIUM: "Середній",
      LOW: "Низький",
    };

    const levelClasses = {
      HIGH: "danger",
      MEDIUM: "warning",
      LOW: "success",
    };

    elements.recommendationPanel.hidden = false;

    elements.recommendationContent.innerHTML = `
            <div class="mb-3">

                <h5>
                    ${escapeHtml(analysis.summary)}
                </h5>

                <div class="d-flex flex-wrap gap-2">

                    <span class="badge text-bg-primary">
                        ${escapeHtml(prediction.risk_level)}
                    </span>

                    <span class="badge text-bg-light">
                        Оцінка:
                        ${Number(prediction.risk_percentage).toFixed(2)}%
                    </span>

                    <span class="badge text-bg-light">
                        ${escapeHtml(
                          prediction.model_version || prediction.source
                        )}
                    </span>

                </div>
            </div>

            <h6>Рекомендації:</h6>

            <ul>
                ${analysis.recommendations
                  .map(
                    (item) => `
                    <li class="mb-2">
                        ${escapeHtml(item)}
                    </li>
                `
                  )
                  .join("")}
            </ul>

            <p class="small text-secondary mb-0">
                ${escapeHtml(result.notice || "")}
            </p>
            <h6 class="mt-4">Фактори уваги:</h6>

<div class="d-flex flex-column gap-3">
    ${factors
      .map(
        (factor) => `
        <div class="border rounded p-3">

            <div class="d-flex flex-wrap justify-content-between gap-2">

                <strong>${escapeHtml(factor.name)}</strong>

                <span class="badge text-bg-${
                  levelClasses[factor.level] || "secondary"
                }">
                    ${levelLabels[factor.level] || "Не визначено"}
                </span>

            </div>

            <div class="small text-secondary mt-1">
                Значення: ${escapeHtml(factor.value)}
            </div>

            <div class="small mt-2">
                ${escapeHtml(factor.explanation)}
            </div>

        </div>
    `
      )
      .join("")}
</div>
        `;
  }

  // Обробник кнопки запуску прогнозування.
  elements.table.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action='analyze']");

    if (!button) {
      return;
    }

    const taskId = Number(button.dataset.id);

    button.disabled = true;
    button.textContent = "Аналіз...";

    try {
      const result = await apiRequest(`/api/predictions/tasks/${taskId}`, {
        method: "POST",
      });

      renderRecommendations(result);

      showAlert("Інтелектуальний аналіз успішно виконано.");

      await loadAnalytics();
    } catch (error) {
      showAlert(error.message, "danger");

      button.disabled = false;
      button.textContent = "Повторити аналіз";
    }
  });

  // Оновлення статистики.
  elements.refreshButton.addEventListener("click", loadAnalytics);

  // Початкове завантаження.
  loadAnalytics();
});
