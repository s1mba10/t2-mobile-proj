document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("scan-btn");
  const target = document.getElementById("scan-results");
  if (!button || !target) return;

  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Сканируем сеть…";
    const response = await fetch("/coverage/scan");
    target.innerHTML = await response.text();
    button.disabled = false;
    button.textContent = "Запустить асинхронное сканирование";
  });
});
