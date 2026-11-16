export function parseTags(text) {
  const seen = new Set()
  return text.split(',').map((tag) => tag.trim().replace(/\s+/g, ' ')).filter((tag) => {
    if (!tag || seen.has(tag.toLowerCase())) return false
    seen.add(tag.toLowerCase())
    return true
  })
}


export function matchesQuestion(q, search, tags, type = '') {
  const text = [q.body_md, q.explanation_md, q.text_answer, q.numeric_answer, ...(q.tags || []),
    ...q.options.map((o) => o.text_md)].join(' ').toLowerCase()
  return (!type || q.type === type) && search.toLowerCase().split(/\s+/).filter(Boolean).every((word) => text.includes(word)) &&
    tags.every((tag) => (q.tags || []).some((t) => t.toLowerCase() === tag.toLowerCase()))
}

