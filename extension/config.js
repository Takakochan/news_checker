const CONFIG_DEFAULTS = {
  backendUrl: "http://localhost:8787",
  backendToken: "",
};

async function getBackendConfig() {
  const stored = await chrome.storage.sync.get(CONFIG_DEFAULTS);
  return {
    backendUrl: (stored.backendUrl || CONFIG_DEFAULTS.backendUrl).replace(/\/$/, ""),
    backendToken: stored.backendToken || "",
  };
}
