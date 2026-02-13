const fileInput = document.getElementById("fileInput");
const fileName = document.getElementById("fileName");
const prompt = document.getElementById("prompt");
const charCount = document.getElementById("charCount");
const convertBtn = document.getElementById("convertBtn");
const askBtn = document.getElementById("askBtn");
const readable = document.getElementById("readable");
const response = document.getElementById("response");
const requestStatus = document.getElementById("requestStatus");
const modelName = document.getElementById("modelName");
const baseUrl = document.getElementById("baseUrl");
const apiKey = document.getElementById("apiKey");

function setStatus(message, isError = false) {
  requestStatus.textContent = message;
  requestStatus.classList.toggle("error", isError);
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

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  fileName.textContent = file ? file.name : "No .slx file selected";
});

prompt.addEventListener("input", () => {
  charCount.textContent = `${prompt.value.length} chars`;
});

convertBtn.addEventListener("click", async () => {
  const file = fileInput.files?.[0];
  if (!file) {
    setStatus("Select a .slx file first.", true);
    return;
  }

  if (!file.name.toLowerCase().endsWith(".slx")) {
    setStatus("Only .slx files are supported.", true);
    return;
  }

  try {
    convertBtn.disabled = true;
    setStatus("Converting .slx file...");

    const content_b64 = await toBase64(file);
    const data = await postJson("/api/convert", {
      filename: file.name,
      content_b64,
    });

    readable.value = data.readable_text || "";
    const stats = data.stats || {};
    setStatus(`Converted successfully: ${stats.blocks ?? 0} blocks, ${stats.lines ?? 0} lines.`);
  } catch (err) {
    setStatus(err.message || "Conversion failed.", true);
  } finally {
    convertBtn.disabled = false;
  }
});

askBtn.addEventListener("click", async () => {
  const promptText = prompt.value.trim();
  const readableText = readable.value.trim();

  if (!promptText) {
    setStatus("Enter a prompt before asking the model.", true);
    return;
  }

  if (!readableText) {
    setStatus("Convert the .slx file first (or provide readable text).", true);
    return;
  }

  try {
    askBtn.disabled = true;
    setStatus("Querying model...");

    const data = await postJson("/api/ask", {
      prompt: promptText,
      readable_text: readableText,
      model_config: {
        model: modelName.value.trim(),
        base_url: baseUrl.value.trim(),
        api_key: apiKey.value.trim(),
      },
    });

    response.value = data.answer || "";
    setStatus("Model response received.");
  } catch (err) {
    setStatus(err.message || "Model request failed.", true);
  } finally {
    askBtn.disabled = false;
  }
});
