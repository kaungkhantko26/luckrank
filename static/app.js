const form = document.querySelector("#problem-form");
const input = document.querySelector("#problem");
const chat = document.querySelector("#chat");
const submitButton = document.querySelector("#submit-button");
const userTemplate = document.querySelector("#user-message-template");
const reportTemplate = document.querySelector("#report-template");

function formatPercent(value) {
  return `${Math.round(Number(value) * 100)}%`;
}

function formatNumber(value, digits = 1) {
  return Number(value).toFixed(digits);
}

function submitProblem() {
  form.requestSubmit();
}

function addUserMessage(problem) {
  const node = userTemplate.content.cloneNode(true);
  node.querySelector("p").textContent = problem;
  chat.append(node);
  chat.scrollTop = chat.scrollHeight;
}

function addStatusMessage(text) {
  const article = document.createElement("article");
  article.className = "message assistant";
  article.dataset.status = "true";
  const meta = document.createElement("div");
  const paragraph = document.createElement("p");
  meta.className = "message-meta";
  meta.textContent = "Advisor";
  paragraph.textContent = text;
  article.append(meta, paragraph);
  chat.append(article);
  chat.scrollTop = chat.scrollHeight;
  return article;
}

function metric(label, value) {
  const block = document.createElement("div");
  block.className = "metric";
  const strong = document.createElement("strong");
  const span = document.createElement("span");
  strong.textContent = value;
  span.textContent = label;
  block.append(strong, span);
  return block;
}

function addReport(data) {
  const node = reportTemplate.content.cloneNode(true);
  const best = data.best_route;

  node.querySelector(".understanding").textContent = data.understanding || data.problem;
  node.querySelector(".data-note").textContent =
    data.data_note || "User input is real; scores are estimates.";
  const assumptions = node.querySelector(".assumptions");
  (data.assumptions || []).forEach((assumption) => {
    const item = document.createElement("li");
    item.textContent = assumption;
    assumptions.append(item);
  });

  node.querySelector("h2").textContent = best.name;
  node.querySelector(".reason").textContent = best.reason;

  const metrics = node.querySelector(".metrics");
  metrics.append(metric("Success", formatPercent(best.adjusted_probability)));
  metrics.append(metric("Score", formatNumber(best.score, 4)));
  metrics.append(metric("Luck", formatNumber(best.luck)));
  metrics.append(metric("Rule", "P x R / C T R"));

  const tbody = node.querySelector("tbody");
  data.routes.forEach((route) => {
    const row = document.createElement("tr");
    [
      route.name,
      formatPercent(route.adjusted_probability),
      formatNumber(route.reward),
      formatNumber(route.cost),
      formatNumber(route.time),
      formatNumber(route.risk),
      formatNumber(route.do),
      formatNumber(route.show),
      formatNumber(route.luck),
      formatNumber(route.score, 4),
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    tbody.append(row);
  });

  const plan = node.querySelector("ol");
  best.action_plan.forEach((step) => {
    const item = document.createElement("li");
    item.textContent = step;
    plan.append(item);
  });

  chat.append(node);
  chat.scrollTop = chat.scrollHeight;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const problem = input.value.trim();
  if (!problem) return;

  addUserMessage(problem);
  input.value = "";
  submitButton.disabled = true;
  submitButton.querySelector("span").textContent = "Thinking";
  const status = addStatusMessage("Thinking...");

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ problem }),
    });
    const data = await response.json();
    status.remove();

    if (!response.ok) {
      addStatusMessage(data.error || "The analysis failed.");
      return;
    }

    addReport(data);
  } catch (error) {
    status.remove();
    addStatusMessage(error.message);
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span").textContent = "Analyze";
    input.focus();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey) {
    return;
  }

  event.preventDefault();
  if (!submitButton.disabled) {
    submitProblem();
  }
});
