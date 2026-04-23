// Centralized proxy base URL + auth header construction.
// Every fetch to the Lambda proxy should go through one of these helpers so
// we don't forget the Bearer token on new call sites.

export const PROXY_URL: string = import.meta.env.VITE_PROXY_URL || '';
const PROXY_TOKEN: string = import.meta.env.VITE_PROXY_TOKEN || '';

/** Merge the Bearer token into a headers object (only if token is set). */
export function authHeaders(init?: HeadersInit): Headers {
  const h = new Headers(init);
  if (PROXY_TOKEN) h.set('Authorization', `Bearer ${PROXY_TOKEN}`);
  return h;
}

/** Wrapper around fetch that auto-adds the Authorization header. */
export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = authHeaders(init.headers);
  return fetch(`${PROXY_URL}${path}`, { ...init, headers });
}
