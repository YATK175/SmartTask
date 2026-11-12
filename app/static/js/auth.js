document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("loginForm");
  const registerForm = document.getElementById("registerForm");
  const alertContainer = document.getElementById("authAlert");

  function showError(message) {
    alertContainer.innerHTML = `
            <div class="alert alert-danger" role="alert">
                ${escapeHtml(message)}
            </div>
        `;
  }

  function escapeHtml(value) {
    const element = document.createElement("div");
    element.textContent = value;
    return element.innerHTML;
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      const formData = new FormData(loginForm);

      const payload = {
        email: formData.get("email"),
        password: formData.get("password"),
      };

      try {
        const response = await fetch("/api/auth/login", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        const result = await response.json();

        if (!response.ok) {
          showError(result.error || "Помилка авторизації.");
          return;
        }

        window.location.href = "/dashboard";
      } catch (error) {
        showError("Не вдалося з'єднатися із сервером.");
      }
    });
  }

  if (registerForm) {
    registerForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      const formData = new FormData(registerForm);

      const payload = {
        username: formData.get("username"),
        email: formData.get("email"),
        password: formData.get("password"),
      };

      try {
        const response = await fetch("/api/auth/register", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        const result = await response.json();

        if (!response.ok) {
          showError(result.error || "Помилка реєстрації.");
          return;
        }

        window.location.href = "/dashboard";
      } catch (error) {
        showError("Не вдалося з'єднатися із сервером.");
      }
    });
  }
});
