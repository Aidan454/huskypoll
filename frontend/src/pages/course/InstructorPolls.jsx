import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../../api.js'
import QuestionEditor from '../../components/QuestionEditor.jsx'
import { ErrorBox, Field, Loaded, Loading, Modal, StatusBadge } from '../../components/ui.jsx'
import { formatDate, formatTime, QUESTION_TYPE_SHORT, snippet } from '../../format.js'
import { useAction, useApi } from '../../hooks.js'
import { connectCourse } from '../../live.js'

function SessionSelect({ sessions, value, onChange }) {
  return (
    <Field label="Lecture" hint="Leave on “Today” to use today's lecture (created if needed).">
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Today</option>
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>
            {formatDate(s.session_date)} {s.title ? `· ${s.title}` : ''}
          </option>
        ))}
      </select>
    </Field>
  )
}

/** Pick a question from a bank and open it as a poll. */
function OpenFromBank({ course, sessions, onOpened, onCancel }) {
  const banks = useApi('/banks')
  const [bankId, setBankId] = useState('')
  const bank = useApi(bankId ? `/banks/${bankId}` : null)
  const [questionId, setQuestionId] = useState(null)
  const [sessionId, setSessionId] = useState('')
  const [showResults, setShowResults] = useState(false)

  const [open, busy, error] = useAction(async () => {
    const poll = await api.post(`/courses/${course.id}/polls`, {
      question_id: questionId,
      session_id: sessionId ? Number(sessionId) : null,
      show_results: showResults,
    })
    onOpened(poll)
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
                  setQuestionId(null)
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
                <span>Question</span>
                <div style={{ maxHeight: 280, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 8, padding: '0 10px' }}>
                  <ul className="list">
                    {b.questions.map((q) => (
                      <li key={q.id}>
                        <label className="check grow">
                          <input type="radio" name="q" checked={questionId === q.id} onChange={() => setQuestionId(q.id)} />
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
      <SessionSelect sessions={sessions} value={sessionId} onChange={setSessionId} />
      <label className="check">
        <input type="checkbox" checked={showResults} onChange={(e) => setShowResults(e.target.checked)} />
        Show live results to students
      </label>
      <ErrorBox error={error} />
      <div className="form-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="btn btn-primary" disabled={!questionId || busy} onClick={() => open()}>
          {busy ? 'Opening…' : 'Open poll'}
        </button>
      </div>
    </>
  )
}

/** Write a question on the spot and open it right away. */
function QuickPoll({ course, sessions, onOpened, onCancel }) {
  const [sessionId, setSessionId] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [open, busy, error] = useAction(async (body) => {
    const poll = await api.post(`/courses/${course.id}/polls/quick`, {
      ...body,
      session_id: sessionId ? Number(sessionId) : null,
      show_results: showResults,
    })
    onOpened(poll)
  })
  return (
    <QuestionEditor
      onSubmit={open}
      busy={busy}
      error={error}
      submitLabel="Open poll"
      onCancel={onCancel}
      extra={
        <>
          <SessionSelect sessions={sessions} value={sessionId} onChange={setSessionId} />
          <label className="check" style={{ marginBottom: 8 }}>
            <input type="checkbox" checked={showResults} onChange={(e) => setShowResults(e.target.checked)} />
            Show live results to students
          </label>
        </>
      }
    />
  )
}

export default function InstructorPolls({ course }) {
  const navigate = useNavigate()
  const polls = useApi(`/courses/${course.id}/polls`)
  const sessions = useApi(`/courses/${course.id}/sessions`)
  const [modal, setModal] = useState(null) // 'bank' | 'quick'
  const { reload: reloadPolls } = polls
  const { reload: reloadSessions } = sessions

  useEffect(
    () =>
      connectCourse(course.id, (msg) => {
        if (msg.type === 'poll_opened' || msg.type === 'poll_closed') {
          reloadPolls()
          reloadSessions()
        }
      }),
    [course.id, reloadPolls, reloadSessions],
  )

  const [closePoll, , closeError] = useAction(async (poll) => {
    await api.post(`/polls/${poll.id}/close`)
    reloadPolls()
  })

  function opened(poll) {
    setModal(null)
    navigate(`/polls/${poll.id}`)
  }

  if (polls.error || sessions.error) return <ErrorBox error={polls.error || sessions.error} />
  if (!polls.data || !sessions.data) return <Loading />

  const live = polls.data.filter((p) => p.status === 'open')
  const bySession = new Map(sessions.data.map((s) => [s.id, { session: s, polls: [] }]))
  for (const p of polls.data) bySession.get(p.session_id)?.polls.push(p)
  const groups = [...bySession.values()].filter((g) => g.polls.length)

  return (
    <>
      <div className="card">
        <div className="card-head">
          <h2>Start a poll</h2>
          <div className="row">
            <button type="button" className="btn btn-primary" onClick={() => setModal('bank')} disabled={Boolean(course.archived_at)}>
              Open from question bank
            </button>
            <button type="button" className="btn" onClick={() => setModal('quick')} disabled={Boolean(course.archived_at)}>
              Quick poll
            </button>
          </div>
        </div>
        {course.archived_at && <p className="small muted">This course is archived. Unarchive it in Settings to run polls.</p>}
        {live.length === 0 ? (
          <p className="muted small" style={{ margin: 0 }}>
            No poll is open right now.
          </p>
        ) : (
          <ul className="list">
            {live.map((p) => (
              <li key={p.id}>
                <StatusBadge status="open" />
                <span className="grow">
                  <Link to={`/polls/${p.id}`}>{snippet(p.question.body_md)}</Link>
                  <span className="small muted"> · code {p.access_code} · opened {formatTime(p.opened_at)}</span>
                </span>
                <Link to={`/polls/${p.id}`} className="btn btn-sm btn-primary">
                  Present
                </Link>
                <button type="button" className="btn btn-sm btn-danger" onClick={() => closePoll(p)}>
                  Close
                </button>
              </li>
            ))}
          </ul>
        )}
        <ErrorBox error={closeError} />
      </div>

      <h2>All polls</h2>
      {groups.length === 0 && <div className="card empty">No polls yet.</div>}
      {groups.map(({ session, polls: list }) => (
        <div className="card" key={session.id}>
          <div className="card-head">
            <h3>
              {formatDate(session.session_date)}
              {session.title && <span className="muted"> · {session.title}</span>}
            </h3>
            <span className="small muted">{list.length} {list.length === 1 ? 'poll' : 'polls'}</span>
          </div>
          <ul className="list">
            {[...list].sort((a, b) => a.position - b.position).map((p) => (
              <li key={p.id}>
                <span className="muted small" style={{ width: 22 }}>
                  {p.position + 1}.
                </span>
                <span className="grow">
                  <Link to={`/polls/${p.id}`}>{snippet(p.question.body_md)}</Link>
                </span>
                <span className="badge">{QUESTION_TYPE_SHORT[p.question.type]}</span>
                <StatusBadge status={p.status} />
              </li>
            ))}
          </ul>
        </div>
      ))}

      <Modal open={modal === 'bank'} onClose={() => setModal(null)} title="Open a poll" wide>
        <OpenFromBank course={course} sessions={sessions.data} onOpened={opened} onCancel={() => setModal(null)} />
      </Modal>
      <Modal open={modal === 'quick'} onClose={() => setModal(null)} title="Quick poll" wide>
        <QuickPoll course={course} sessions={sessions.data} onOpened={opened} onCancel={() => setModal(null)} />
      </Modal>
    </>
  )
}
