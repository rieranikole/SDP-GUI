const fileInput = document.getElementById("fileInput");
const fileName = document.getElementById("fileName");
const prompt = document.getElementById("prompt");
const charCount = document.getElementById("charCount");
const convertBtn = document.getElementById("convertBtn");
const askBtn = document.getElementById("askBtn");

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  fileName.textContent = file ? file.name : "No .slx file selected";
});

prompt.addEventListener("input", () => {
  charCount.textContent = `${prompt.value.length} chars`;
});

convertBtn.addEventListener("click", () => {
  window.alert(
    "Conversion is not implemented yet.\n\nConnect this action to your .slx extraction script when ready.",
  );
});

askBtn.addEventListener("click", () => {
  window.alert(
    "AI querying is not implemented yet.\n\nConnect this action to your model client when ready.",
  );
});
