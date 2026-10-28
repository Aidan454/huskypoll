// Small wrapper around fetch for the HuskyPoll API.
//   const courses = await api.get('/courses')
//   await api.post('/courses', { term: 'Spring 2027', ... })
// Every call sends the login cookie. Errors throw ApiError with .status and a
// readable .message (the API's "detail").
import { API_BASE } from './config.js'

export class ApiError extends Error {
  constructor(status, message, body) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

function readableDetail(body, status) {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  // FastAPI validation errors: [{loc: [...], msg: "..."}]
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const field = (d.loc || []).filter((p) => p !== 'body').join('.')
        return field ? `${field}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  if (status === 0) return "Can't reach the server. Is the backend running?"
  return `Request failed (HTTP ${status})`
}

async function request(method, path, { json, form, query } = {}) {
  let url = `${API_BASE}${path}`
  if (query) {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') params.set(k, v)
    }
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }
  const options = { method, credentials: 'include', headers: {} }
  if (json !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(json)
  } else if (form) {
    options.body = form
  }

  let resp
  try {
    resp = await fetch(url, options)
  } catch {
    throw new ApiError(0, readableDetail(null, 0))
  }
  if (resp.status === 204) return null
  const type = resp.headers.get('Content-Type') || ''
  const body = type.includes('application/json') ? await resp.json().catch(() => null) : await resp.text()
  if (!resp.ok) throw new ApiError(resp.status, readableDetail(body, resp.status), body)
  return body
}

export const api = {
  get: (path, query) => request('GET', path, { query }),
  post: (path, json, query) => request('POST', path, { json: json ?? {}, query }),
  patch: (path, json) => request('PATCH', path, { json }),
  delete: (path, query) => request('DELETE', path, { query }),
  /** Upload a file as multipart form data (field name "file"). */
  upload: (path, file, query) => {
    const form = new FormData()
    form.append('file', file)
    return request('POST', path, { form, query })
  },

  me: () => request('GET', '/me'),
  logout: () => request('POST', '/auth/logout'),
  devLogin: (body) => request('POST', '/auth/dev-login', { json: body }),

  /** Address of the UConn login. `next` is a page path relative to the site, e.g. '/courses/3'. */
  loginUrl: (next = '/') => `${API_BASE}/auth/login?next=${encodeURIComponent(next)}`,
  qrUrl: (pollId, fmt = 'svg') => `${API_BASE}/polls/${pollId}/qr.${fmt}`,
  participationUrl: (courseId, dates = []) => {
    const params = new URLSearchParams()
    for (const date of dates) params.append('dates', date)
    const query = params.toString()
    return `${API_BASE}/courses/${courseId}/export/participation.csv${query ? `?${query}` : ''}`
  },
}
