export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'lulia.auth.token';

// ---------------------------------------------------------------------------
// Token helpers — localStorage with a guarded read/write so SSR doesn't crash
// ---------------------------------------------------------------------------

export function getAuthToken() {
  if (typeof window === 'undefined') return null;
  try { return window.localStorage.getItem(TOKEN_KEY) || null; } catch { return null; }
}

export function setAuthToken(token) {
  if (typeof window === 'undefined') return;
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch { /* private mode etc. */ }
}

export function clearAuthToken() { setAuthToken(null); }

// ---------------------------------------------------------------------------
// apiFetch — JSON requests with Authorization header attached automatically
// ---------------------------------------------------------------------------

export async function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const token = getAuthToken();
  if (token && !headers.Authorization) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // 401 means our token is stale or unset — clear it so the next page load
  // routes through /login. Skip on /auth/* (login itself can 401).
  if (res.status === 401 && !path.startsWith('/api/v1/auth/')) {
    clearAuthToken();
    if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// apiUpload — multipart form (FormData), Authorization header attached but
// NO Content-Type (browser sets it with the boundary).
// ---------------------------------------------------------------------------

export async function apiUpload(path, formData) {
  const headers = {};
  const token = getAuthToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST', body: formData, headers,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload ${res.status}: ${text}`);
  }
  return res.json();
}
