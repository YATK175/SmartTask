document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("categoryForm");
  const list = document.getElementById("categoryList");
  const alertContainer = document.getElementById("categoriesAlert");

  const categoryId = document.getElementById("categoryId");
  const categoryName = document.getElementById("categoryName");
  const categoryDescription = document.getElementById("categoryDescription");
  const categoryColor = document.getElementById("categoryColor");

  const formTitle = document.getElementById("categoryFormTitle");
  const cancelButton = document.getElementById("cancelCategoryEdit");

  let categoriesCache = [];

  function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value ?? "";
    return element.innerHTML;
  }

  function showAlert(message, type = "success") {
    alertContainer.innerHTML = `
            <div class="alert alert-${type}">
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
      throw new Error(result.error || "Не вдалося виконати операцію.");
    }

    return result;
  }

  function resetForm() {
    form.reset();

    categoryId.value = "";
    categoryColor.value = "#4361EE";

    formTitle.textContent = "Створити категорію";
    cancelButton.hidden = true;
  }

  async function loadCategories() {
    try {
      const result = await apiRequest("/api/categories");

      categoriesCache = result.categories || [];

      renderCategories();
    } catch (error) {
      list.innerHTML = `
                <div class="alert alert-danger">
                    ${escapeHtml(error.message)}
                </div>
            `;
    }
  }

  function renderCategories() {
    if (categoriesCache.length === 0) {
      list.innerHTML = `
                <p class="text-secondary mb-0">
                    Категорій поки немає. Створіть першу категорію.
                </p>
            `;
      return;
    }

    list.innerHTML = categoriesCache
      .map(
        (category) => `
            <div class="d-flex flex-wrap justify-content-between
                        align-items-center gap-3 p-3 border-bottom">

                <div class="d-flex align-items-center gap-3">

                    <div
                        style="
                            width: 13px;
                            height: 42px;
                            background: ${escapeHtml(category.color)};
                            border-radius: 5px;
                        ">
                    </div>

                    <div>
                        <strong>${escapeHtml(category.name)}</strong>

                        <div class="small text-secondary">
                            ${escapeHtml(category.description || "Без опису")}
                        </div>
                    </div>

                </div>

                <div class="d-flex gap-2">

                    <button
                        class="btn btn-sm btn-outline-primary"
                        data-action="edit"
                        data-id="${category.id}">
                        Редагувати
                    </button>

                    <button
                        class="btn btn-sm btn-outline-danger"
                        data-action="delete"
                        data-id="${category.id}">
                        Видалити
                    </button>

                </div>

            </div>
        `
      )
      .join("");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const id = categoryId.value;

    const payload = {
      name: categoryName.value.trim(),
      description: categoryDescription.value.trim(),
      color: categoryColor.value.toUpperCase(),
    };

    try {
      const result = await apiRequest(
        id ? `/api/categories/${id}` : "/api/categories",
        {
          method: id ? "PATCH" : "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );

      showAlert(result.message);

      resetForm();

      await loadCategories();

      // Оновлюємо список категорій у формі завдань,
      // якщо користувач відкрив сторінку категорій після роботи із завданнями.
    } catch (error) {
      showAlert(error.message, "danger");
    }
  });

  list.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");

    if (!button) return;

    const id = Number(button.dataset.id);
    const action = button.dataset.action;

    const category = categoriesCache.find((item) => item.id === id);

    if (!category) return;

    if (action === "edit") {
      categoryId.value = category.id;
      categoryName.value = category.name;
      categoryDescription.value = category.description || "";
      categoryColor.value = category.color;

      formTitle.textContent = "Редагувати категорію";
      cancelButton.hidden = false;

      categoryName.focus();

      return;
    }

    if (action === "delete") {
      const confirmed = confirm(`Видалити категорію "${category.name}"?`);

      if (!confirmed) return;

      try {
        const result = await apiRequest(`/api/categories/${id}`, {
          method: "DELETE",
        });

        showAlert(result.message);

        resetForm();

        await loadCategories();
      } catch (error) {
        showAlert(error.message, "danger");
      }
    }
  });

  cancelButton.addEventListener("click", resetForm);

  loadCategories();
});
