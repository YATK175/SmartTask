document.addEventListener("DOMContentLoaded", () => {
  const tableBody = document.getElementById("tasksTableBody");
  const taskForm = document.getElementById("taskForm");
  const taskModal = document.getElementById("taskModal");

  const modal = new bootstrap.Modal(taskModal);

  const searchInput = document.getElementById("taskSearch");
  const statusFilter = document.getElementById("statusFilter");
  const priorityFilter = document.getElementById("priorityFilter");
  const sortFilter = document.getElementById("sortFilter");

  const categorySelect = document.getElementById("taskCategory");

  const alertContainer = document.getElementById("tasksAlert");

  let tasksCache = [];

  function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML;
  }

  function showAlert(message, type = "success") {
    alertContainer.innerHTML = `
            <div class="alert alert-${type}" role="alert">
                ${escapeHtml(message)}
            </div>
        `;

    setTimeout(() => {
      alertContainer.innerHTML = "";
    }, 3500);
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

  function formatDate(value) {
    return new Date(value).toLocaleString("uk-UA", {
      dateStyle: "short",
      timeStyle: "short",
    });
  }

  function priorityLabel(value) {
    const labels = {
      LOW: "Низький",
      MEDIUM: "Середній",
      HIGH: "Високий",
      CRITICAL: "Критичний",
    };

    return labels[value] || value;
  }

  function statusLabel(value) {
    const labels = {
      NEW: "Нове",
      IN_PROGRESS: "У процесі",
      COMPLETED: "Виконано",
      CANCELLED: "Скасовано",
    };

    return labels[value] || value;
  }

  async function loadCategories() {
    const result = await apiRequest("/api/categories");

    categorySelect.innerHTML = `
            <option value="">Без категорії</option>
        `;

    result.categories.forEach((category) => {
      const option = document.createElement("option");

      option.value = category.id;
      option.textContent = category.name;

      categorySelect.appendChild(option);
    });
  }

  async function loadTasks() {
    tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-secondary">
                    Завантаження...
                </td>
            </tr>
        `;

    try {
      const params = new URLSearchParams();

      if (searchInput.value.trim()) {
        params.set("search", searchInput.value.trim());
      }

      if (statusFilter.value) {
        params.set("status", statusFilter.value);
      }

      if (priorityFilter.value) {
        params.set("priority", priorityFilter.value);
      }

      if (sortFilter.value) {
        params.set("sort_by", sortFilter.value);
      }

      const result = await apiRequest(`/api/tasks?${params.toString()}`);

      tasksCache = result.tasks || [];

      renderTasks(tasksCache);
    } catch (error) {
      tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-danger">
                        ${escapeHtml(error.message)}
                    </td>
                </tr>
            `;
    }
  }

  function renderTasks(tasks) {
    if (tasks.length === 0) {
      tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-secondary">
                        Завдань не знайдено.
                    </td>
                </tr>
            `;
      return;
    }

    tableBody.innerHTML = tasks
      .map((task) => {
        let actions = `
                <button
                    class="btn btn-sm btn-outline-primary"
                    data-action="edit"
                    data-id="${task.id}">
                    Редагувати
                </button>

                <button
                    class="btn btn-sm btn-outline-danger"
                    data-action="delete"
                    data-id="${task.id}">
                    Видалити
                </button>
            `;

        if (task.status === "NEW") {
          actions += `
                    <button
                        class="btn btn-sm btn-outline-primary"
                        data-action="start"
                        data-id="${task.id}">
                        Почати
                    </button>
                `;
        }

        if (task.status === "IN_PROGRESS") {
          actions += `
                    <button
                        class="btn btn-sm btn-outline-success"
                        data-action="complete"
                        data-id="${task.id}">
                        Завершити
                    </button>
                `;
        }

        return `
                <tr>
                    <td>
                        <strong>${escapeHtml(task.title)}</strong>

                        <div class="small text-secondary">
                            ${escapeHtml(task.description || "")}
                        </div>
                    </td>

                    <td>${escapeHtml(priorityLabel(task.priority))}</td>

                    <td>
                        <span class="badge-status">
                            ${escapeHtml(statusLabel(task.status))}
                        </span>
                    </td>

                    <td>
                        ${formatDate(task.deadline)}

                        ${
                          task.is_overdue
                            ? '<div class="text-danger small">Прострочено</div>'
                            : ""
                        }
                    </td>

                    <td>
                        <div class="d-flex flex-wrap gap-1">
                            ${actions}
                        </div>
                    </td>
                </tr>
            `;
      })
      .join("");
  }

  function resetForm() {
    taskForm.reset();

    document.getElementById("taskId").value = "";
    document.getElementById("taskModalTitle").textContent = "Нове завдання";

    document.getElementById("taskPriority").value = "MEDIUM";
    document.getElementById("taskDuration").value = 60;
  }

  async function editTask(taskId) {
    const task = tasksCache.find((item) => item.id === taskId);

    if (!task) {
      showAlert("Завдання не знайдено.", "danger");
      return;
    }

    document.getElementById("taskId").value = task.id;
    document.getElementById("taskTitle").value = task.title;
    document.getElementById("taskDescription").value = task.description || "";

    document.getElementById("taskPriority").value = task.priority;

    document.getElementById("taskDuration").value =
      task.estimated_duration_minutes;

    categorySelect.value = task.category_id ?? "";

    const localDate = new Date(task.deadline);

    const formattedDate = new Date(
      localDate.getTime() - localDate.getTimezoneOffset() * 60000
    )
      .toISOString()
      .slice(0, 16);

    document.getElementById("taskDeadline").value = formattedDate;

    document.getElementById("taskModalTitle").textContent =
      "Редагування завдання";

    modal.show();
  }

  taskForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const taskId = document.getElementById("taskId").value;
    const deadline = document.getElementById("taskDeadline").value;

    if (!deadline) {
      showAlert("Вкажіть дедлайн.", "danger");
      return;
    }

    const payload = {
      title: document.getElementById("taskTitle").value.trim(),
      description: document.getElementById("taskDescription").value,
      category_id: categorySelect.value ? Number(categorySelect.value) : null,
      priority: document.getElementById("taskPriority").value,
      estimated_duration_minutes: Number(
        document.getElementById("taskDuration").value
      ),
      deadline: new Date(deadline).toISOString(),
    };

    try {
      const url = taskId ? `/api/tasks/${taskId}` : "/api/tasks";

      const result = await apiRequest(url, {
        method: taskId ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      modal.hide();
      resetForm();

      showAlert(taskId ? "Завдання оновлено." : "Завдання створено.");

      await loadTasks();
    } catch (error) {
      showAlert(error.message, "danger");
    }
  });

  document
    .getElementById("createTaskButton")
    .addEventListener("click", resetForm);

  document.getElementById("filterButton").addEventListener("click", loadTasks);

  [searchInput, statusFilter, priorityFilter, sortFilter].forEach((element) => {
    element.addEventListener("change", loadTasks);
  });

  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      loadTasks();
    }
  });

  tableBody.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");

    if (!button) return;

    const taskId = Number(button.dataset.id);
    const action = button.dataset.action;

    try {
      if (action === "edit") {
        await editTask(taskId);
        return;
      }

      if (action === "delete") {
        if (!confirm("Видалити це завдання?")) return;

        await apiRequest(`/api/tasks/${taskId}`, {
          method: "DELETE",
        });

        showAlert("Завдання видалено.");
      }

      if (action === "start") {
        await apiRequest(`/api/tasks/${taskId}/status`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            status: "IN_PROGRESS",
          }),
        });

        showAlert("Виконання завдання розпочато.");
      }

      if (action === "complete") {
        if (!confirm("Позначити завдання як виконане?")) {
          return;
        }

        await apiRequest(`/api/tasks/${taskId}/complete`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        });

        showAlert("Завдання виконано.");
      }

      await loadTasks();
    } catch (error) {
      showAlert(error.message, "danger");
    }
  });

  loadCategories()
    .then(loadTasks)
    .catch((error) => {
      showAlert(error.message, "danger");
    });
});
