import { DurationField } from './DurationField.jsx'
import { minutesToSeconds } from './pollDuration.js'
import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { ErrorBox, Field, Loaded } from '../ui.jsx'
import { QUESTION_TYPE_SHORT, snippet } from '../../format.js'
import { useAction, useApi } from '../../hooks.js'
import SessionSelect from './SessionSelect.jsx'

/** Pick one question to open, or several to ask one at a time in the order chosen. */
export default function OpenFromBank({ course, sessions, onOpened, onCancel, initialSessionId = '' }) {
  const banks = useApi('/banks')
  const [bankId, setBankId] = useState('')
  const bank = useApi(bankId ? `/banks/${bankId}` : null)
  const [questionIds, setQuestionIds] = useState([]) // in the order they were ticked
  const [sessionId, setSessionId] = useState(String(initialSessionId))
  const [showResults, setShowResults] = useState(false)
  const [minutes, setMinutes] = useState('')

  function toggle(id) {
    setQuestionIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]))
  }

  function move(id, by) {
    setQuestionIds((ids) => {
      const i = ids.indexOf(id)
      const j = i + by
      if (j < 0 || j >= ids.length) return ids
      const next = [...ids]
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }

  const [open, busy, error] = useAction(async () => {
    const session_id = sessionId ? Number(sessionId) : null
    const duration_seconds = minutesToSeconds(minutes)
    if (questionIds.length === 1) {
      const poll = await api.post(`/courses/${course.id}/polls`, {
        question_id: questionIds[0],
        session_id,
        show_results: showResults,
        duration_seconds,
      })
      onOpened([poll])
    } else {
      // one poll, asked a question at a time: the first opens now, the rest wait
      const polls = await api.post(`/courses/${course.id}/polls/set`, {
        question_ids: questionIds,
        session_id,
        show_results: showResults,
        duration_seconds,
      })
      onOpened(polls)
    }
  })

  return (
    <>
      <Loaded state={banks}>
        {(list) =>
          list.length === 0 ? (
            <div className="alert alert-info">
              You have no question banks yet. <Link to="/banks">Create one</Link>, or use Quick poll.
            </div>
          ) : (
            <Field label="Question bank">
              <select
                value={bankId}
                onChange={(e) => {
                  setBankId(e.target.value)
                  setQuestionIds([])
                }}
              >
                <option value="">Choose a bank…</option>
                {list.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} ({b.question_count})
                  </option>
                ))}
              </select>
            </Field>
          )
        }
      </Loaded>
      {bankId && (
        <Loaded state={bank}>
          {(b) =>
            b.questions.length === 0 ? (
              <p className="muted">This bank has no questions.</p>
            ) : (
              <div className="field">
                <span>Questions — tick one, or several to ask one after another</span>
                <div style={{ maxHeight: 280, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 8, padding: '0 10px' }}>
                  <ul className="list">
                    {b.questions.map((q) => (
                      <li key={q.id}>
                        <label className="check grow">
                          <input type="checkbox" checked={questionIds.includes(q.id)} onChange={() => toggle(q.id)} />
                          {questionIds.includes(q.id) && <span className="badge badge-blue">{questionIds.indexOf(q.id) + 1}</span>}
                          <span className="grow">{snippet(q.body_md)}</span>
                          <span className="badge">{QUESTION_TYPE_SHORT[q.type]}</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )
          }
        </Loaded>
      )}
      {questionIds.length > 1 && bank.data && (
        <div className="field">
          <span>Order — students see one question at a time, starting at the top</span>
          <ol className="list" style={{ paddingLeft: 0 }}>
            {questionIds.map((id, i) => {
              const q = bank.data.questions.find((x) => x.id === id)
              return (
                <li key={id} style={{ padding: '6px 0' }}>
                  <span className="badge badge-blue">{i + 1}</span>
                  <span className="grow small">{snippet(q?.body_md, 80)}</span>
                  <button type="button" className="btn btn-sm" aria-label="Move up" disabled={i === 0} onClick={() => move(id, -1)}>
                    ↑
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm"
                    aria-label="Move down"
                    disabled={i === questionIds.length - 1}
                    onClick={() => move(id, 1)}
                  >
                    ↓
                  </button>
                </li>
              )
            })}
          </ol>
        </div>
      )}
      <SessionSelect sessions={sessions} value={sessionId} onChange={setSessionId} />
      <DurationField value={minutes} onChange={setMinutes} />
      <label className="check">
        <input type="checkbox" checked={showResults} onChange={(e) => setShowResults(e.target.checked)} />
        Show live results to students
      </label>
      <ErrorBox error={error} />
      <div className="form-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="btn btn-primary" disabled={!questionIds.length || busy} onClick={() => open()}>
          {busy ? 'Opening…' : questionIds.length > 1 ? `Start poll (${questionIds.length} questions)` : 'Open poll'}
        </button>
      </div>
    </>
  )
}

