// Renders the "simple Markdown" questions are written in: **bold**, *italic*, `code`
// and line breaks. Builds React elements (never raw HTML), so it is safe for any text.
const TOKEN = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)/g

function inline(text, keyPrefix) {
  return text.split(TOKEN).map((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={key}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return <code key={key}>{part.slice(1, -1)}</code>
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <em key={key}>{part.slice(1, -1)}</em>
    return part
  })
}

export default function Markdown({ text }) {
  if (!text) return null
  const lines = text.split('\n')
  return lines.map((line, i) => (
    <span key={i}>
      {inline(line, i)}
      {i < lines.length - 1 && <br />}
    </span>
  ))
}

