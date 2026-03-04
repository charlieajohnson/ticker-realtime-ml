/**
 * REST API wrappers for the Ticker backend.
 */

const BASE = "/api";

async function fetchJSON(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

export async function fetchSymbols() {
  return fetchJSON("/symbols");
}

export async function fetchModelStats() {
  return fetchJSON("/model/stats");
}

export async function fetchAlerts(limit = 50) {
  return fetchJSON(`/alerts?limit=${limit}`);
}

export async function fetchPipelineStatus() {
  return fetchJSON("/pipeline/status");
}
