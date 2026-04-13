/**
 * Build the correct WebSocket URL for game sessions, across environments.
 *
 * Priority:
 *   1. NEXT_PUBLIC_WS_URL env var (set in production — e.g. wss://school-pilot.net)
 *   2. Dev fallback:
 *        - localhost/127.0.0.1 → ws://host:8000 (API runs on 8000 locally)
 *        - any other hostname  → same-origin (reverse proxy assumed)
 */
export function getGameWebSocketUrl(pin) {
  const envUrl = process.env.NEXT_PUBLIC_WS_URL;
  if (envUrl) {
    return `${envUrl.replace(/\/$/, '')}/ws/games/${pin}`;
  }
  if (typeof window === 'undefined') return '';
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.hostname;
  const isLocal = host === 'localhost' || host === '127.0.0.1';
  const port = isLocal ? ':8000' : '';
  return `${proto}://${host}${port}/ws/games/${pin}`;
}
