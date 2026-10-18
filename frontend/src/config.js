// Where the site and the API live. Never hard-code "/" or a domain anywhere else.
//
// In production the backend serves index.html and adds
//   window.__HUSKYPOLL__ = { basePath: "/cse1010", apiBase: "https://host/cse1010/api" }
// so one build works under any path prefix.
// In development VITE_API_BASE (compose.yml) or the Vite proxy for /api is used.

const injected = typeof window !== 'undefined' ? window.__HUSKYPOLL__ : undefined

function trimSlash(s) {
  return s.replace(/\/+$/, '')
}

/** The router's basename, e.g. "" or "/cse1010". */
export const BASE_PATH = trimSlash(injected?.basePath || '')

/** Full address of the API without a trailing slash. */
export const API_BASE = trimSlash(
  injected?.apiBase || import.meta.env.VITE_API_BASE || `${window.location.origin}${BASE_PATH}/api`,
)

/** A page path relative to the site: pagePath('/courses/3') -> '/cse1010/courses/3'. */
export function pagePath(path) {
  return `${BASE_PATH}/${path.replace(/^\/+/, '')}`
}

/** The WebSocket version of API_BASE. */
export const WS_BASE = API_BASE.replace(/^http/, 'ws')
