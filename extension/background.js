importScripts("config.js");

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "FACT_CHECK") return false;

  (async () => {
    try {
      const { backendUrl, backendToken } = await getBackendConfig();
      const response = await fetch(`${backendUrl}/check`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(backendToken ? { Authorization: `Bearer ${backendToken}` } : {}),
        },
        body: JSON.stringify(message.payload),
      });
      if (!response.ok) {
        const detail = await response.text().catch(() => "");
        throw new Error(`Server error: ${response.status} ${detail}`.trim());
      }
      const data = await response.json();
      sendResponse({ ok: true, data });
    } catch (err) {
      sendResponse({ ok: false, error: err.message || "A network error occurred." });
    }
  })();

  return true;
});
