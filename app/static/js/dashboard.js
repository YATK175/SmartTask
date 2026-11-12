document.addEventListener("DOMContentLoaded", () => {
  const elements = {
    total: document.getElementById("totalTasks"),
    active: document.getElementById("activeTasks"),
    completed: document.getElementById("completedTasks"),
    overdue: document.getElementById("overdueTasks"),
    tasks: document.getElementById("dashboardTasks"),
    alert: document.getElementById("dashboardAlert"),
  };

  function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML;
  }

  function formatDate(value) {
    if (!value) return "Не встановлено";

    return new Date(value).toLocaleString("uk-UA", {
      dateStyle: "short",
      timeStyle: "short",
    });
  }

  async function loadDashboard() {
    try {
      const response = await fetch("/api/tasks");

      if (response.status === 401) {
        window.location.href = "/login";
        return;
      }

      if (!response.ok) {
        throw new Error("Не вдалося отримати завдання.");
      }

      const result = await response.json();
      const tasks = result.tasks || [];

      // Розрахунок статистики
      elements.total.textContent = tasks.length;

      elements.active.textContent = tasks.filter(
        (task) => task.status === "IN_PROGRESS"
      ).length;

      elements.completed.textContent = tasks.filter(
        (task) => task.status === "COMPLETED"
      ).length;

      elements.overdue.textContent = tasks.filter(
        (task) => task.is_overdue
      ).length;

      // Останні п'ять завдань
      const recentTasks = [...tasks]
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        .slice(0, 5);

      if (recentTasks.length === 0) {
        elements.tasks.innerHTML = `
                    <p class="text-secondary mb-0">
                        У вас поки немає завдань.
                        Створіть своє перше завдання!
                    </p>
                `;
        return;
      }

      elements.tasks.innerHTML = recentTasks
        .map(
          (task) => `
                <div class="d-flex flex-wrap justify-content-between
                            align-items-center gap-2 py-3 border-bottom">

                    <div>
                        <strong>${escapeHtml(task.title)}</strong>

                        <div class="small text-secondary mt-1">
                            Дедлайн: ${formatDate(task.deadline)}
                        </div>
                    </div>

                    <div class="d-flex gap-2 align-items-center">
                        <span class="badge-status">
                            ${escapeHtml(task.status)}
                        </span>
                        <span class="small text-secondary">
                            ${escapeHtml(task.priority)}
                        </span>
                    </div>

                </div>
            `
        )
        .join("");
    } catch (error) {
      elements.alert.innerHTML = `
                <div class="alert alert-danger">
                    ${escapeHtml(error.message)}
                </div>
            `;

      elements.tasks.textContent = "Не вдалося завантажити завдання.";
    }
  }

  loadDashboard();
});
