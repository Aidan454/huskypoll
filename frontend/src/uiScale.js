/** Page scale (accessibility "text size"), saved per browser like the theme. */
export const SCALE_STORAGE_KEY = 'huskypoll-scale'
const CHANGE_EVENT = 'huskypoll-scale-change'

export const SCALE_OPTIONS = [
  { value: 1, label: '100%', name: 'Default size' },
  { value: 1.25, label: '125%', name: 'Large' },
  { value: 1.5, label: '150%', name: 'Larger' },
]

let scale = 1
let initialized = false

export function normalizeScale(value) {
  const number = Number(value)
  return SCALE_OPTIONS.some((option) => option.value === number) ? number : 1
}

function applyScale() {
  // Styles are written in px, so the whole page is zoomed (see `--ui-scale` and `body` in index.css).
  document.documentElement.style.setProperty('--ui-scale-choice', String(scale))
  window.dispatchEvent(new Event(CHANGE_EVENT))
}

function readPreference() {
  try { scale = normalizeScale(localStorage.getItem(SCALE_STORAGE_KEY)) } catch { /* Keep the in-memory choice. */ }
}

export function setScale(value) {
  scale = normalizeScale(value)
  try { localStorage.setItem(SCALE_STORAGE_KEY, String(scale)) } catch { /* Still works for this visit. */ }
  applyScale()
}

export function getScaleSnapshot() {
  return scale
}

export function subscribeScale(listener) {
  window.addEventListener(CHANGE_EVENT, listener)
  return () => window.removeEventListener(CHANGE_EVENT, listener)
}

export function initializeScale() {
  readPreference()
  applyScale()
  if (!initialized) {
    initialized = true
    window.addEventListener('storage', (event) => {
      if (event.key === SCALE_STORAGE_KEY || event.key === null) {
        readPreference()
        applyScale()
      }
    })
  }
  return scale
}
