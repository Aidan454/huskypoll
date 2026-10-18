// Display helpers shared by the pages.

export const QUESTION_TYPES = {
  mc_single: 'Multiple choice (one answer)',
  mc_multi: 'Multiple choice (several answers)',
  free_text: 'Short text',
  numeric: 'Number',
}

export const QUESTION_TYPE_SHORT = {
  mc_single: 'Single choice',
  mc_multi: 'Multiple choice',
  free_text: 'Text',
  numeric: 'Number',
}

export const STAFF_ROLES = ['owner', 'instructor', 'ta']

export function isStaff(course) {
  return STAFF_ROLES.includes(course?.my_role)
}

/** Can this account create courses and question banks? */
export function canTeach(user) {
  return ['admin', 'instructor', 'ta'].includes(user?.role)
}

export function initials(user) {
  const a = user?.first_name?.[0] || user?.net_id?.[0] || '?'
  const b = user?.last_name?.[0] || ''
  return (a + b).toUpperCase()
}

export function formatDate(value) {
  if (!value) return ''
  // Plain dates ("2027-01-20") are calendar days: don't shift them by time zone.
  const d = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value)
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatDateTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

export function todayIso() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function pct(part, whole) {
  return whole ? Math.round((100 * part) / whole) : 0
}

export function points(n) {
  return Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
}

/** One line of a question for lists. */
export function snippet(text, max = 110) {
  const t = stripMarkdown(text).replace(/\s+/g, ' ').trim()
  return t.length > max ? `${t.slice(0, max - 1)}…` : t || '(picture question)'
}

/** Text form of a student's answer. */
export function answerText(question, response) {
  if (!response) return ''
  if (question.type === 'numeric') return response.numeric_answer ?? ''
  if (question.type === 'free_text') return response.text_answer ?? ''
  const letters = question.options.filter((o) => response.option_ids.includes(o.id)).map((o) => o.letter)
  return letters.join(', ')
}

/** Plain text without the simple-Markdown markers (**bold**, *italic*, `code`). */
export function stripMarkdown(text) {
  return (text || '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*\s][^*]*)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
}
