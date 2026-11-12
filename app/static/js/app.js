document.addEventListener("DOMContentLoaded", () => {
  const logoutButton = document.getElementById("logoutButton");

  if (!logoutButton) {
    return;
  }

  logoutButton.addEventListener("click", async () => {
    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
      });

      if (response.ok) {
        window.location.href = "/login";
        return;
      }

      alert("Не вдалося завершити сесію.");
    } catch (error) {
      alert("Помилка з'єднання із сервером.");
    }
  });
});
