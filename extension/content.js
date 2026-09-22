let checkButton = null;
let panel = null;

function removeButton() {
  if (checkButton) {
    checkButton.remove();
    checkButton = null;
  }
}

function removePanel() {
  if (panel) {
    panel.remove();
    panel = null;
  }
}

document.addEventListener("mouseup", (e) => {
  if (panel && panel.contains(e.target)) return;
  if (checkButton && checkButton.contains(e.target)) return;

  const selection = window.getSelection();
  const text = selection ? selection.toString().trim() : "";

  removeButton();

  if (!text || text.length < 2) return;

  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();

  checkButton = document.createElement("button");
  checkButton.id = "news-checker-btn";
  checkButton.textContent = "Fact Check";
  checkButton.style.top = `${window.scrollY + rect.bottom + 6}px`;
  checkButton.style.left = `${window.scrollX + rect.left}px`;

  checkButton.addEventListener("mousedown", (evt) => {
    evt.preventDefault();
    evt.stopPropagation();
    runFactCheck(text, rect);
  });

  document.body.appendChild(checkButton);
});

document.addEventListener("mousedown", (e) => {
  if (checkButton && !checkButton.contains(e.target)) removeButton();
  if (panel && !panel.contains(e.target) && e.target !== checkButton) removePanel();
});

const SEVERITY_LABELS = { low: "Low severity", medium: "Medium severity", high: "High severity" };

function renderLoadingPanel(rect) {
  removePanel();
  panel = document.createElement("div");
  panel.id = "news-checker-panel";
  panel.style.top = `${window.scrollY + rect.bottom + 6}px`;
  panel.style.left = `${window.scrollX + rect.left}px`;
  panel.innerHTML = `
    <button class="nc-close">&times;</button>
    <h3>Checking the facts...</h3>
    <div class="nc-loading"><span class="nc-spinner"></span>Judging severity and searching for sources.</div>
  `;
  panel.querySelector(".nc-close").addEventListener("click", removePanel);
  document.body.appendChild(panel);
}

function renderResultPanel(data, rect) {
  removePanel();
  panel = document.createElement("div");
  panel.id = "news-checker-panel";
  panel.style.top = `${window.scrollY + rect.bottom + 6}px`;
  panel.style.left = `${window.scrollX + rect.left}px`;

  const sourcesHtml = (data.sources || [])
    .map(
      (s) => `
      <div class="nc-source">
        <div class="nc-source-top">
          <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.title || s.url)}</a>
          <span class="nc-score">match ${Math.round(s.score * 100)}%</span>
        </div>
        <div class="nc-source-excerpt">${escapeHtml((s.content || "").slice(0, 160))}...</div>
      </div>`
    )
    .join("");

  const truthScoreHtml =
    typeof data.truth_score === "number"
      ? `<div class="nc-truth-score">Truth score: <strong>${data.truth_score}%</strong></div>`
      : "";

  panel.innerHTML = `
    <button class="nc-close">&times;</button>
    <h3>News Checker</h3>
    <span class="nc-badge ${data.severity}">${SEVERITY_LABELS[data.severity] || data.severity}</span>
    <div class="nc-reasoning">${escapeHtml(data.severity_reasoning)}</div>
    ${truthScoreHtml}
    <div class="nc-block">
      <div class="nc-label">Summary</div>
      <div>${escapeHtml(data.summary).replace(/\n/g, "<br/>")}</div>
    </div>
    <div class="nc-block">
      <div class="nc-label">Sources</div>
      ${sourcesHtml || '<div class="nc-source-excerpt">No sources were found for this claim.</div>'}
    </div>
    ${data.result_url ? `<a class="nc-result-link" href="${escapeHtml(data.result_url)}" target="_blank" rel="noopener noreferrer">Open full result page &rarr;</a>` : ""}
  `;
  panel.querySelector(".nc-close").addEventListener("click", removePanel);
  document.body.appendChild(panel);
}

function renderErrorPanel(message, rect) {
  removePanel();
  panel = document.createElement("div");
  panel.id = "news-checker-panel";
  panel.style.top = `${window.scrollY + rect.bottom + 6}px`;
  panel.style.left = `${window.scrollX + rect.left}px`;
  panel.innerHTML = `
    <button class="nc-close">&times;</button>
    <h3>Error</h3>
    <div class="nc-error">${escapeHtml(message)}</div>
  `;
  panel.querySelector(".nc-close").addEventListener("click", removePanel);
  document.body.appendChild(panel);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function getSettings() {
  const stored = await chrome.storage.sync.get({
    model: null,
    maxResults: null,
    autoScore: true,
    scoreThreshold: 0.3,
  });
  return {
    model: stored.model,
    max_results: stored.maxResults,
    auto_score: stored.autoScore,
    score_threshold: stored.scoreThreshold,
  };
}

async function runFactCheck(text, rect) {
  removeButton();
  renderLoadingPanel(rect);

  try {
    const settings = await getSettings();
    const result = await chrome.runtime.sendMessage({
      type: "FACT_CHECK",
      payload: { text, ...settings },
    });
    if (!result || !result.ok) {
      throw new Error((result && result.error) || "A network error occurred.");
    }
    renderResultPanel(result.data, rect);
  } catch (err) {
    renderErrorPanel(err.message || "A network error occurred.", rect);
  }
}
