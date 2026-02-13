const fileInput = document.getElementById("fileInput");
const fileName = document.getElementById("fileName");
const prompt = document.getElementById("prompt");
const charCount = document.getElementById("charCount");
const statusText = document.getElementById("statusText");
const convertBtn = document.getElementById("convertBtn");
const askBtn = document.getElementById("askBtn");

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  fileName.textContent = file ? file.name : "No .slx file selected";
  statusText.textContent = file
    ? "File selected. Ready for conversion (placeholder)."
    : "Ready (UI-only mode)";
});

prompt.addEventListener("input", () => {
  charCount.textContent = `${prompt.value.length} chars`;
});

convertBtn.addEventListener("click", () => {
  statusText.textContent = "Convert requested. Hook your SLX extraction logic here.";
  window.alert(
    "Conversion is not implemented yet.\n\nConnect this action to your .slx extraction script when ready.",
  );
});

askBtn.addEventListener("click", () => {
  statusText.textContent = "Model query requested. Hook your AI model logic here.";
  window.alert(
    "AI querying is not implemented yet.\n\nConnect this action to your model client when ready.",
  );
});
