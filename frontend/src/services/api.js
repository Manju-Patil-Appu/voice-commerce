const base = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");
let authToken = localStorage.getItem("auth_token") || "";

export function assetUrl(path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  const normalized = String(path).replace(/^\/+/, "");
  return `${base}/${normalized}`;
}

export function setAuthToken(token) {
  authToken = token || "";
  if (authToken) {
    localStorage.setItem("auth_token", authToken);
  } else {
    localStorage.removeItem("auth_token");
  }
}

async function parseResponse(res) {
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function withAuthHeaders(headers = {}) {
  return authToken ? { ...headers, Authorization: `Bearer ${authToken}` } : headers;
}

export async function apiGet(path) {
  const res = await fetch(`${base}${path}`, { headers: withAuthHeaders() });
  return parseResponse(res);
}

export async function apiPost(path, payload) {
  const res = await fetch(`${base}${path}`, {
    method: "POST",
    headers: withAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload ?? {}),
  });
  return parseResponse(res);
}

export async function apiDelete(path) {
  const res = await fetch(`${base}${path}`, { method: "DELETE", headers: withAuthHeaders() });
  return parseResponse(res);
}

export async function apiFormPost(path, formData) {
  const res = await fetch(`${base}${path}`, {
    method: "POST",
    headers: withAuthHeaders(),
    body: formData,
  });
  return parseResponse(res);
}
