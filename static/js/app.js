window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    window.location.replace("/");
  }
});

const form = document.querySelector("#factory-form");
const calculatorForm = document.querySelector(".calculator-form");
const calculatorOutput = document.querySelector("#calculator-output");
const statusBox = document.querySelector("#factory-status");
const resetButton = document.querySelector("#reset-demo-button");
let pollTimer = null;
let epochTimer = null;
let shouldPollStatus = false;
let activeJobId = null;
const statusPollIntervalMs = 1000;
const epochPollIntervalMs = 5000;
const activeJobStorageKey = "softwareFactoryActiveJobId";

function loadActiveJobId() {
  try {
    return window.sessionStorage.getItem(activeJobStorageKey);
  } catch (error) {
    return null;
  }
}

function saveActiveJobId(jobId) {
  activeJobId = jobId || null;
  try {
    if (activeJobId) {
      window.sessionStorage.setItem(activeJobStorageKey, activeJobId);
    } else {
      window.sessionStorage.removeItem(activeJobStorageKey);
    }
  } catch (error) {
    // Ignore storage failures; polling still works until the page reloads.
  }
}

function hasCalculatorOutput() {
  return document.querySelector(".result") !== null;
}

function clearBrowserRestoredCalculatorState() {
  if (!calculatorForm || hasCalculatorOutput()) {
    return;
  }

  const leftInput = calculatorForm.querySelector('[name="left"]');
  const rightInput = calculatorForm.querySelector('[name="right"]');
  const operationInput = calculatorForm.querySelector('[name="operation"]');

  if (leftInput) {
    leftInput.value = "";
  }
  if (rightInput) {
    rightInput.value = "";
  }
  if (operationInput) {
    operationInput.value = "divide";
  }
}

function renderCalculatorOutput(payload) {
  if (!calculatorOutput) {
    return;
  }

  calculatorOutput.replaceChildren();

  if (payload.result === undefined && !payload.error) {
    return;
  }

  const result = document.createElement("div");
  result.className = payload.error ? "result failure" : "result success";

  const label = document.createElement("span");
  label.textContent = payload.error ? "Calculator blew up" : "Result";

  const value = document.createElement("strong");
  value.textContent = payload.error || payload.result;

  result.append(label, value);
  calculatorOutput.append(result);
}

async function ensureFreshDemoEpoch() {
  const renderedEpoch = document.body.dataset.demoEpoch || "";
  if (!renderedEpoch) {
    return;
  }

  const response = await fetch(`/factory/demo-epoch/?t=${Date.now()}`, { cache: "no-store" });
  const payload = await response.json();
  if (payload.epoch && payload.epoch !== renderedEpoch) {
    window.location.replace(`/?t=${Date.now()}`);
  }
}

function scheduleEpochPoll() {
  if (epochTimer) {
    window.clearTimeout(epochTimer);
  }
  epochTimer = window.setTimeout(() => {
    ensureFreshDemoEpoch().finally(scheduleEpochPoll);
  }, epochPollIntervalMs);
}

function displayState(state) {
  if (!state) {
    return "Unknown";
  }
  return state.charAt(0).toUpperCase() + state.slice(1).replaceAll("_", " ");
}

function statusDetail(payload) {
  if (payload.state === "completed") {
    return payload.detail || "";
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
  pollTimer = window.setTimeout(fetchStatus, statusPollIntervalMs);
}

function isStaleStatus(payload) {
  return activeJobId && payload.job_id !== activeJobId;
}

async function fetchStatus() {
  try {
    const params = new URLSearchParams({ t: Date.now().toString() });
    if (activeJobId) {
      params.set("job_id", activeJobId);
    }

    const response = await fetch(`/factory/status/?${params.toString()}`, { cache: "no-store" });
    const payload = await response.json();

    if (isStaleStatus(payload)) {
      statusBox.querySelector("strong").textContent = "Running";
      statusBox.querySelector("p").textContent = "Factory is still running.";
      shouldPollStatus = true;
    } else {
      renderStatus(payload);
      shouldPollStatus = payload.state === "running";
      if (payload.state === "completed" || payload.state === "failed" || payload.state === "unknown") {
        saveActiveJobId(null);
      }
    }
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

    saveActiveJobId(null);
    window.location.replace("/");
  });
}

if (form) {
  saveActiveJobId(loadActiveJobId());
  clearBrowserRestoredCalculatorState();

  if (calculatorForm) {
    calculatorForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(calculatorForm);
      const token = data.get("csrfmiddlewaretoken");

      const response = await fetch("/calculate/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": token,
        },
        body: JSON.stringify({
          left: data.get("left"),
          right: data.get("right"),
          operation: data.get("operation"),
        }),
        cache: "no-store",
      });

      renderCalculatorOutput(await response.json());
    });
  }

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

    const payload = await response.json();
    saveActiveJobId(payload.job_id || null);
    renderStatus(payload);
    scheduleStatusPoll();
  });

  ensureFreshDemoEpoch().finally(() => {
    shouldPollStatus = Boolean(activeJobId);
    fetchStatus();
    scheduleEpochPoll();
  });
}
