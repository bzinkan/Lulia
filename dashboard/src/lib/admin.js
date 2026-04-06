const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function getAdminToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('admin_token');
}

export function setAdminToken(token) {
  localStorage.setItem('admin_token', token);
}

export function clearAdminToken() {
  localStorage.removeItem('admin_token');
}

export async function adminFetch(path, options = {}) {
  const token = getAdminToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': token || '',
      ...options.headers,
    },
  });
  if (res.status === 401 || res.status === 403) {
    clearAdminToken();
    if (typeof window !== 'undefined') window.location.href = '/admin';
    throw new Error('Admin session expired');
  }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
