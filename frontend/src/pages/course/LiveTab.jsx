// Step-through screen for a poll with several questions (/courses/:id/live?session=ID).
// Students see one question at a time. The instructor closes it, may show the
// results, then moves on to the next question; the class keeps the same code.
import { useEffect, useState } from 'react'
import { Link, useOutletContext, useSearchParams } from 'react-router'
import { api } from '../../api.js'
import { AnswerKey, QuestionBody, ResultsView } from '../../components/PollParts.jsx'
import { ErrorBox, Loading, StatusBadge } from '../../components/ui.jsx'
import { pct, QUESTION_TYPE_SHORT, snippet } from '../../format.js'
import { useAction, useApi } from '../../hooks.js'
import { connectCourse } from '../../live.js'

function CurrentQuestion({ poll, number, total, liveResults, children }) {
  const initial = useApi(`/polls/${poll.id}/results?s=${poll.status}`)
  const results = liveResults ?? initial.data
  return (
    <div className="card">
      <div className="card-head">
        <div className="row">
          <span className="badge badge-blue" style={{ textTransform: 'none' }}>
            Question {number} of {total}
          </span>
          <span className="badge">{QUESTION_TYPE_SHORT[poll.question.type]}</span>
          <StatusBadge status={poll.status} />
        </div>
        <span className="small muted">
          {results?.responses ?? 0} answers
          {results && results.correct > 0 && <> · {pct(results.correct, results.responses)}% correct</>}
        </span>
      </div>
      <QuestionBody question={poll.question} />
      <ResultsView question={poll.question} results={results} />
      {poll.status === 'closed' && (
        <div style={{ marginTop: 14 }}>
          <AnswerKey question={poll.question} />
        </div>
      )}
      {children}
    </div>
  )
}

export default function LiveTab() {
  const { course } = useOutletContext()
  const [params] = useSearchParams()
  const sessionId = params.get('session')
  const polls = useApi(sessionId ? `/courses/${course.id}/polls?session_id=${sessionId}` : null)
  const [live, setLive] = useState({}) // poll_id -> latest results from the WebSocket
  const { reload } = polls

  useEffect(
    () =>
      connectCourse(course.id, (msg) => {
        if (msg.type === 'results') setLive((r) => ({ ...r, [msg.results.poll_id]: msg.results }))
        if (msg.type === 'poll_opened' || msg.type === 'poll_closed') reload()
      }),
    [course.id, reload],
  )

  const [act, busy, error] = useAction(async (fn) => {
    await fn()
    reload()
  })

  if (!sessionId) {
    return (
      <div className="card empty">
        Choose a poll from the <Link to={`/courses/${course.id}`}>Polls tab</Link>.
      </div>
    )
  }
  if (polls.error) return <ErrorBox error={polls.error} />
  if (!polls.data) return <Loading />

  // every question of this lecture, in the order they are asked
  const all = [...polls.data].sort((a, b) => a.position - b.position)
  // the set starts at the first question that was queued or is still running,
  // so polls asked earlier in the same lecture don't count
  const firstOfSet = all.findIndex((p, i) => p.status !== 'closed' || all.slice(i + 1).some((q) => q.status === 'draft'))
  const from = params.get('from') // position of the poll's first question, when we know it
  const set =
    from !== null ? all.filter((p) => p.position >= Number(from)) : firstOfSet === -1 ? all : all.slice(firstOfSet)
  const current = set.find((p) => p.status === 'open')
  const next = set.find((p) => p.status === 'draft')
  const lastClosed = [...set].reverse().find((p) => p.status === 'closed')
  const shown = current ?? lastClosed
  const number = shown ? set.indexOf(shown) + 1 : 0

  return (
    <div className="present">
      <div>
        <ErrorBox error={error} />
        {!shown && next && (
          <div className="card">
            <p>The poll hasn&apos;t started yet.</p>
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => act(() => api.post(`/polls/${next.id}/open`))}>
              Start with question 1
            </button>
          </div>
        )}
        {shown && (
          <CurrentQuestion key={`${shown.id}-${shown.status}`} poll={shown} number={number} total={set.length} liveResults={live[shown.id]}>
            <div className="row" style={{ marginTop: 16 }}>
              {current ? (
                <button
                  type="button"
                  className="btn btn-solid-danger btn-lg"
                  disabled={busy}
                  onClick={() => act(() => api.post(`/polls/${current.id}/close`))}
                >
                  Close question {number}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    className="btn btn-lg"
                    disabled={busy}
                    onClick={() => act(() => api.patch(`/polls/${shown.id}`, { show_results: !shown.show_results }))}
                  >
                    {shown.show_results ? 'Hide results from students' : 'Show results to students'}
                  </button>
                  {next ? (
                    <button
                      type="button"
                      className="btn btn-primary btn-lg"
                      disabled={busy}
                      onClick={() => act(() => api.post(`/polls/${next.id}/open`))}
                    >
                      Next question →
                    </button>
                  ) : (
                    <span className="badge badge-open" style={{ fontSize: 14 }}>
                      ✓ All {set.length} questions done
                    </span>
                  )}
                </>
              )}
            </div>
          </CurrentQuestion>
        )}
      </div>

      <div>
        {current?.access_code ? (
          <div className="card code-box">
            <div className="stat-label">Go to {current.join_url ? new URL(current.join_url).host : 'HuskyPoll'} and enter</div>
            <div className="code-big">{current.access_code}</div>
            <img className="qr" src={api.qrUrl(current.id)} alt={`QR code for ${current.join_url}`} />
          </div>
        ) : (
          next && (
            <div className="card small muted">
              Students stay on the same page. The next question appears for them as soon as you open it.
            </div>
          )
        )}
        <div className="card">
          <h3>Questions</h3>
          <ul className="list small">
            {set.map((p, i) => (
              <li key={p.id} style={{ padding: '8px 0' }}>
                <span className="muted" style={{ width: 18 }}>
                  {i + 1}.
                </span>
                <span className="grow" style={p === shown ? { fontWeight: 600 } : undefined}>
                  {snippet(p.question.body_md, 60)}
                </span>
                {p.status === 'draft' ? (
                  <button
                    type="button"
                    className="btn btn-sm"
                    title="Remove from this poll"
                    aria-label={`Remove question ${i + 1}`}
                    disabled={busy}
                    onClick={() => act(() => api.delete(`/polls/${p.id}`))}
                  >
                    ✕
                  </button>
                ) : (
                  <StatusBadge status={p.status === 'closed' ? 'done' : p.status} />
                )}
              </li>
            ))}
          </ul>
          <Link to={`/courses/${course.id}`} className="small">
            ← Back to all polls
          </Link>
        </div>
      </div>
    </div>
  )
}
