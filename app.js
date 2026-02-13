const fileInput = document.getElementById("fileInput");
const fileName = document.getElementById("fileName");
const prompt = document.getElementById("prompt");
const charCount = document.getElementById("charCount");
const convertBtn = document.getElementById("convertBtn");
const askBtn = document.getElementById("askBtn");
const workflowBtn = document.getElementById("workflowBtn");

const readable = document.getElementById("readable");
const generatedScript = document.getElementById("generatedScript");
const response = document.getElementById("response");
const requestStatus = document.getElementById("requestStatus");

const provider = document.getElementById("provider");
const modelName = document.getElementById("modelName");
const baseUrl = document.getElementById("baseUrl");
const apiKey = document.getElementById("apiKey");
const matlabCmd = document.getElementById("matlabCmd");
const timeoutSec = document.getElementById("timeoutSec");

function setStatus(message, isError = false) {
  requestStatus.textContent = message;
  requestStatus.classList.toggle("error", isError);
}

function setBusy(isBusy) {
  convertBtn.disabled = isBusy;
  askBtn.disabled = isBusy;
  workflowBtn.disabled = isBusy;
}

function currentModelConfig() {
  return {
    provider: provider.value,
    model: modelName.value.trim(),
    base_url: baseUrl.value.trim(),
    api_key: apiKey.value.trim(),
  };
}

function applyProviderDefaults() {
  if (provider.value === "ollama") {
    if (!modelName.value.trim() || modelName.value.trim() === "gpt-4o-mini") {
      modelName.value = "mistral:7b-instruct";
    }
    if (!baseUrl.value.trim() || baseUrl.value.trim() === "https://api.openai.com/v1") {
      baseUrl.value = "http://localhost:11434";
    }
    apiKey.value = "";
    apiKey.disabled = true;
    apiKey.placeholder = "Not required for local Ollama";
    return;
  }

  if (!modelName.value.trim() || modelName.value.trim() === "mistral:7b-instruct") {
    modelName.value = "gpt-4o-mini";
  }
  if (!baseUrl.value.trim() || baseUrl.value.trim() === "http://localhost:11434") {
    baseUrl.value = "https://api.openai.com/v1";
  }
  apiKey.disabled = false;
  apiKey.placeholder = "Paste API key";
}

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const idx = result.indexOf(",");
      resolve(idx >= 0 ? result.slice(idx + 1) : "");
    };
    reader.onerror = () => reject(new Error("Failed to read file."));
    reader.readAsDataURL(file);
  });
}

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

async function convertIfNeeded(force = false) {
  const file = fileInput.files?.[0];
  if (!file) {
    throw new Error("Select a .slx file first.");
  }
  if (!file.name.toLowerCase().endsWith(".slx")) {
    throw new Error("Only .slx files are supported.");
  }
  if (!force && readable.value.trim()) {
    return;
  }

  const content_b64 = await toBase64(file);
  const data = await postJson("/api/convert", {
    filename: file.name,
    content_b64,
  });

  readable.value = data.readable_text || "";
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  fileName.textContent = file ? file.name : "No .slx file selected";
});

prompt.addEventListener("input", () => {
  charCount.textContent = `${prompt.value.length} chars`;
});

provider.addEventListener("change", applyProviderDefaults);
applyProviderDefaults();

convertBtn.addEventListener("click", async () => {
  try {
    setBusy(true);
    setStatus("Converting .slx file...");
    await convertIfNeeded(true);
    setStatus("Conversion completed.");
  } catch (err) {
    setStatus(err.message || "Conversion failed.", true);
  } finally {
    setBusy(false);
  }
});

askBtn.addEventListener("click", async () => {
  const promptText = prompt.value.trim();
  if (!promptText) {
    setStatus("Enter a prompt before asking the model.", true);
    return;
  }

  try {
    setBusy(true);
    setStatus("Preparing readable model data...");
    await convertIfNeeded(false);

    setStatus("Querying model...");
    const data = await postJson("/api/ask", {
      prompt: promptText,
      readable_text: readable.value.trim(),
      model_config: currentModelConfig(),
    });

    response.value = data.answer || "";
    setStatus("Model response received.");
  } catch (err) {
    setStatus(err.message || "Model request failed.", true);
  } finally {
    setBusy(false);
  }
});

workflowBtn.addEventListener("click", async () => {
  const promptText = prompt.value.trim();
  if (!promptText) {
    setStatus("Enter a prompt before running MATLAB workflow.", true);
    return;
  }

  try {
    setBusy(true);
    setStatus("Preparing readable model data...");
    await convertIfNeeded(false);

    setStatus("Generating MATLAB script and executing in batch mode...");
    const data = await postJson("/api/workflow", {
      prompt: promptText,
      readable_text: readable.value.trim(),
      model_config: currentModelConfig(),
      matlab_cmd: matlabCmd.value.trim() || "matlab",
      timeout_sec: Number(timeoutSec.value || 300),
    });

    generatedScript.value = data.generated_script || "";
    response.value = data.report || "";

    const runInfo = data.matlab || {};
    const state = runInfo.status === "success" ? "completed" : "failed";
    setStatus(`Workflow ${state}. Run ID: ${runInfo.run_id || "n/a"}`);
  } catch (err) {
    setStatus(err.message || "Workflow failed.", true);
  } finally {
    setBusy(false);
  }
});
