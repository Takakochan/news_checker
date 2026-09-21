const API_BASE = "http://localhost:8787";

const DEFAULTS = {
  model: null,
  maxResults: null,
  autoScore: true,
  scoreThreshold: 0.3,
};

const modelSelect = document.getElementById("model-select");
const maxResultsInput = document.getElementById("max-results");
const autoScoreCheckbox = document.getElementById("auto-score");
const scoreThresholdRow = document.getElementById("score-threshold-row");
const scoreThresholdInput = document.getElementById("score-threshold");
const scoreThresholdValue = document.getElementById("score-threshold-value");
const statusEl = document.getElementById("status");

function updateScoreRowState() {
  scoreThresholdRow.classList.toggle("disabled", autoScoreCheckbox.checked);
}

async function loadModels(selected) {
  try {
    const res = await fetch(`${API_BASE}/models`);
    const data = await res.json();
    modelSelect.innerHTML = "";
    for (const id of data.models) {
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = id;
      modelSelect.appendChild(opt);
    }
    modelSelect.value = selected || data.default;
  } catch (err) {
    modelSelect.innerHTML = `<option value="">Failed to load models (is the backend running?)</option>`;
  }
}

async function loadSettings() {
  const stored = await chrome.storage.sync.get(DEFAULTS);
  await loadModels(stored.model);
  maxResultsInput.value = stored.maxResults ?? "";
  autoScoreCheckbox.checked = stored.autoScore;
  scoreThresholdInput.value = stored.scoreThreshold;
  scoreThresholdValue.textContent = Number(stored.scoreThreshold).toFixed(2);
  updateScoreRowState();
}

scoreThresholdInput.addEventListener("input", () => {
  scoreThresholdValue.textContent = Number(scoreThresholdInput.value).toFixed(2);
});

autoScoreCheckbox.addEventListener("change", updateScoreRowState);

document.getElementById("save").addEventListener("click", async () => {
  const settings = {
    model: modelSelect.value || null,
    maxResults: maxResultsInput.value ? parseInt(maxResultsInput.value, 10) : null,
    autoScore: autoScoreCheckbox.checked,
    scoreThreshold: parseFloat(scoreThresholdInput.value),
  };
  await chrome.storage.sync.set(settings);
  statusEl.textContent = "Saved!";
  setTimeout(() => (statusEl.textContent = ""), 1500);
});

loadSettings();
