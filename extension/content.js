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

function severityLabel(severity) {
  const map = { low: "Severity: Low", medium: "Severity: Medium", high: "Severity: High" };
  return map[severity] || severity;
}

function renderLoadingPanel(rect) {
  removePanel();
  panel = document.createElement("div");
  panel.id = "news-checker-panel";
  panel.style.top = `${window.scrollY + rect.bottom + 6}px`;
  panel.style.left = `${window.scrollX + rect.left}px`;
  panel.innerHTML = `
    <button class="nc-close">&times;</button>
    <h3>Fact-checking...</h3>
    <div class="nc-loading">Judging severity with LLM and searching with Tavily.</div>
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

  const sourcesHtml = data.sources
    .map(
      (s) => `
      <div class="nc-source">
        <span class="nc-score">score ${s.score.toFixed(2)}</span>
        <a href="${s.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.title || s.url)}</a>
        <div>${escapeHtml((s.content || "").slice(0, 160))}...</div>
      </div>`
    )
    .join("");

  panel.innerHTML = `
    <button class="nc-close">&times;</button>
    <h3><span class="nc-badge ${data.severity}">${severityLabel(data.severity)}</span></h3>
    <div>${escapeHtml(data.severity_reasoning)}</div>
    <div class="nc-settings">
      <strong>Tavily Settings</strong><br/>
      search_depth: ${data.tavily_settings.search_depth}<br/>
      max_results: ${data.tavily_settings.max_results}<br/>
      score_threshold: ${data.tavily_settings.score_threshold}<br/>
      Reason: ${escapeHtml(data.tavily_settings.reason)}
    </div>
    <div><strong>Summary</strong><br/>${escapeHtml(data.summary).replace(/\n/g, "<br/>")}</div>
    <div style="margin-top:8px;"><strong>Sources</strong>${sourcesHtml}</div>
    <div class="nc-settings" style="margin-top:8px;">
      <strong>Token Usage</strong><br/>
      prompt: ${data.token_usage.prompt_tokens} / completion: ${data.token_usage.completion_tokens} / total: ${data.token_usage.total_tokens}
    </div>
    ${data.result_url ? `<div style="margin-top:8px;"><a href="${escapeHtml(data.result_url)}" target="_blank" rel="noopener noreferrer">View result page</a></div>` : ""}
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
    <div>${escapeHtml(message)}</div>
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
