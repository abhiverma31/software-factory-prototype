window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    window.location.replace("/");
  }
});

const form = document.querySelector("#factory-form");
const statusBox = document.querySelector("#factory-status");
const resetButton = document.querySelector("#reset-demo-button");
let pollTimer = null;
let shouldPollStatus = false;

async function ensureFreshDemoEpoch() {
  const renderedEpoch = document.body.dataset.demoEpoch || "";
  if (!renderedEpoch) {
    return;
  }

  const response = await fetch(`/factory/demo-epoch/?t=${Date.now()}`, { cache: "no-store" });
  const payload = await response.json();
  if (payload.epoch && payload.epoch !== renderedEpoch) {
    window.location.replace("/");
  }
}

function displayState(state) {
  if (!state) {
    return "Unknown";
  }
  return state.charAt(0).toUpperCase() + state.slice(1).replaceAll("_", " ");
}

function statusDetail(payload) {
  if (payload.state === "completed") {
    return "";
  }

  if (payload.state === "failed") {
    return "Factory failed. Check the terminal output.";
  }

  return payload.detail || "";
}

function renderStatus(payload) {
  statusBox.querySelector("strong").textContent = displayState(payload.state);
  statusBox.querySelector("p").textContent = statusDetail(payload);
}

function scheduleStatusPoll() {
  if (pollTimer) {
    window.clearTimeout(pollTimer);
  }
  pollTimer = window.setTimeout(fetchStatus, 1000);
}

async function fetchStatus() {
  try {
    const response = await fetch(`/factory/status/?t=${Date.now()}`, { cache: "no-store" });
    const payload = await response.json();
    renderStatus(payload);
    shouldPollStatus = payload.state === "running";
  } catch (error) {
    if (shouldPollStatus) {
      statusBox.querySelector("p").textContent = "Factory is still running. Waiting for server reload...";
    }
  }

  if (shouldPollStatus) {
    scheduleStatusPoll();
  }
}

if (resetButton) {
  resetButton.addEventListener("click", async () => {
    const data = new FormData(form);
    const token = data.get("csrfmiddlewaretoken");

    await fetch("/factory/reset/", {
      method: "POST",
      headers: {
        "X-CSRFToken": token,
      },
      cache: "no-store",
    });

    window.location.replace("/");
  });
}

if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const token = data.get("csrfmiddlewaretoken");

    shouldPollStatus = true;
    const response = await fetch("/factory/fix/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": token,
      },
      body: JSON.stringify({ task: data.get("task") }),
      cache: "no-store",
    });

    renderStatus(await response.json());
    scheduleStatusPoll();
  });

  ensureFreshDemoEpoch().finally(fetchStatus);
}
