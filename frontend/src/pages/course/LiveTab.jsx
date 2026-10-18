// Classroom view for several questions asked together: one code for the class,
// live results for every open question, and Close all.
import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router'
import { api } from '../../api.js'
import { QuestionBody, ResultsView } from '../../components/PollParts.jsx'
import { ErrorBox, Loaded } from '../../components/ui.jsx'
import { QUESTION_TYPE_SHORT } from '../../format.js'
import { useAction, useApi } from '../../hooks.js'
import { connectCourse } from '../../live.js'

function OpenQuestion({ index, poll, liveResults, onClose }) {
  const initial = useApi(`/polls/${poll.id}/results`)
  const results = liveResults ?? initial.data
  return (
    <div className="card">
      <div className="card-head">
        <div className="row">
          <span className="badge badge-blue">Question {index + 1}</span>
          <span className="badge">{QUESTION_TYPE_SHORT[poll.question.type]}</span>
          <span className="small muted">{results?.responses ?? 0} answers</span>
        </div>
        <div className="row">
          <Link to={`/polls/${poll.id}`} className="btn btn-sm">
            Details
          </Link>
          <button type="button" className="btn btn-sm btn-danger" onClick={() => onClose(poll)}>
            Close
          </button>
        </div>
      </div>
      <QuestionBody question={poll.question} />
      <ResultsView question={poll.question} results={results} />
    </div>
  )
}

export default function LiveTab() {
  const { course } = useOutletContext()
  const polls = useApi(`/courses/${course.id}/polls?status=open`)
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

  const [closeOne, , closeError] = useAction(async (poll) => {
    await api.post(`/polls/${poll.id}/close`)
    reload()
  })
  const [closeAll, closingAll, closeAllError] = useAction(async (list) => {
    for (const p of list) await api.post(`/polls/${p.id}/close`)
    reload()
  })
  const [share, sharing, shareError] = useAction(async (list, show) => {
    for (const p of list) await api.patch(`/polls/${p.id}`, { show_results: show })
    reload()
  })

  return (
    <Loaded state={polls}>
      {(list) => {
        if (!list.length) {
          return (
            <div className="card empty">
              <p>No questions are open right now.</p>
              <Link to={`/courses/${course.id}`}>Back to polls</Link>
            </div>
          )
        }
        const ordered = [...list].sort((a, b) => a.session_id - b.session_id || a.position - b.position)
        const first = ordered[0]
        const allShared = ordered.every((p) => p.show_results)
        return (
          <div className="present">
            <div>
              <ErrorBox error={closeError || closeAllError || shareError} />
              {ordered.map((p, i) => (
                <OpenQuestion key={p.id} index={i} poll={p} liveResults={live[p.id]} onClose={closeOne} />
              ))}
            </div>
            <div>
              <div className="card code-box">
                <div className="stat-label">
                  Go to {first.join_url ? new URL(first.join_url).host : 'HuskyPoll'} and enter
                </div>
                <div className="code-big">{first.access_code}</div>
                <img className="qr" src={api.qrUrl(first.id)} alt={`QR code for ${first.join_url}`} />
                <p className="small muted" style={{ margin: 0 }}>
                  Students who enter this code see all {ordered.length} open questions.
                </p>
              </div>
              <div className="stack">
                <button type="button" className="btn btn-block" disabled={sharing} onClick={() => share(ordered, !allShared)}>
                  {allShared ? 'Hide results from students' : 'Show results to students'}
                </button>
                <button
                  type="button"
                  className="btn btn-block btn-solid-danger"
                  disabled={closingAll}
                  onClick={() => closeAll(ordered)}
                >
                  {closingAll ? 'Closing…' : `Close all ${ordered.length} questions`}
                </button>
              </div>
            </div>
          </div>
        )
      }}
    </Loaded>
  )
}
