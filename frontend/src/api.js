// Single place that talks to the backend. Reads the JWT from localStorage
// and adds it to every request automatically.

const BASE_URL = "http://localhost:8000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  const text = await res.text();

  // Try to parse JSON, but tolerate plain-text responses (e.g. "Internal Server Error")
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text }; // wrap the plain text as a detail string
    }
  }

  if (!res.ok) {
    const message =
      (data && typeof data === "object" && data.detail) ||
      (typeof data === "string" && data) ||
      `Server error (HTTP ${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  register: (body) =>
    request("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body) =>
    request("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => request("/auth/me"),
  listPolicies: () => request("/documents/policies"),
  listContracts: () => request("/documents/contracts"),
  uploadPolicy: (file) => uploadFile("/documents/policies/upload", file),
  uploadContract: (file) => uploadFile("/documents/contracts/upload", file),
  preview: (kind, name) =>
    request(`/documents/preview?kind=${kind}&name=${encodeURIComponent(name)}`),
  indexPolicies: () => request("/rag/index", { method: "POST" }),
  runAudit: (contractName) =>
    request("/audit/run", {
      method: "POST",
      body: JSON.stringify({ contract_name: contractName }),
    }),
  chat: ({ contractName, auditReport, history, message }) =>
    request("/audit/chat", {
      method: "POST",
      body: JSON.stringify({
        contract_name: contractName,
        audit_report: auditReport,
        history,
        message,
      }),
    }),
};

async function uploadFile(path, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: authHeaders(), // no Content-Type — browser sets multipart boundary
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
