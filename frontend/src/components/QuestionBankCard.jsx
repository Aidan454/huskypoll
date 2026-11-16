import { useState } from 'react'
import { QuestionBody } from './PollParts.jsx'
import { QUESTION_TYPE_SHORT } from '../format.js'
import Markdown from './Markdown.jsx'
import './QuestionBank.css'

export default function QuestionCard({ q, onEdit, onCopy, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const answer =
    q.type.startsWith('mc')
      ? q.options.filter((o) => o.is_correct).map((o) => o.letter).join(', ')
      : q.type === 'numeric'
        ? q.numeric_answer ?? ''
        : q.text_answer ?? ''
  return (
    <div className="card">
      <div className="card-head">
        <div className="row">
          <span className="badge">{QUESTION_TYPE_SHORT[q.type]}</span>
          {q.is_locked && <span className="badge badge-amber" title="Already polled: wording is locked">🔒 Polled</span>}
          {answer !== '' ? <span className="badge badge-open">Answer: {String(answer)}</span> : <span className="badge">No answer key</span>}
        </div>
        <div className="row">
          <button type="button" className="btn btn-sm" onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Less' : 'More'}
          </button>
          <button type="button" className="btn btn-sm" onClick={onEdit}>
            Edit
          </button>
          <button type="button" className="btn btn-sm" onClick={onCopy}>
            Copy
          </button>
          {!q.is_locked && (
            <button type="button" className="btn btn-sm btn-danger" onClick={onDelete}>
              Delete
            </button>
          )}
        </div>
      </div>
      {q.tags?.length > 0 && <div className="bank-tags">{q.tags.map((tag) => <span key={tag} className="badge badge-blue">{tag}</span>)}</div>}
      <QuestionBody question={q} />
      {q.options.length > 0 && (
        <ul className="list small">
          {q.options.map((o) => (
            <li key={o.id} style={{ justifyContent: 'flex-start', padding: '6px 0' }}>
              <span className="letter" style={o.is_correct ? { background: 'var(--green)', color: 'var(--on-accent)' } : undefined}>
                {o.letter}
              </span>
              <span>
                <Markdown text={o.text_md} />
              </span>
            </li>
          ))}
        </ul>
      )}
      {expanded && (
        <div className="small muted" style={{ marginTop: 8 }}>
          {q.explanation_md ? <p>
              Explanation: <Markdown text={q.explanation_md} />
            </p> : <p>No explanation.</p>}
          {q.numeric_tolerance != null && <p>Tolerance: ±{q.numeric_tolerance}</p>}
          {q.copied_from_id && <p>Copied from question #{q.copied_from_id}</p>}
        </div>
      )}
    </div>
  )
}

