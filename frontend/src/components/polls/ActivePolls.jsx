import { Link } from 'react-router'
import { StatusBadge } from '../ui.jsx'
import { formatTime, snippet } from '../../format.js'

export default function ActivePolls({ course, polls, running, live, closePoll }) {
  return (
    <>
        {running.map((sid) => {
          const set = polls.filter((p) => p.session_id === sid && p.status !== 'closed')
          const current = set.find((p) => p.status === 'open')
          return (
            <div className="row" key={sid} style={{ marginBottom: 10 }}>
              <StatusBadge status={current ? 'open' : 'draft'} />
              <span className="grow">
                Poll in progress: {set.filter((p) => p.status === 'draft').length} questions still to ask
              </span>
              <Link to={`/courses/${course.id}/live?session=${sid}`} className="btn btn-sm btn-primary">
                Continue
              </Link>
            </div>
          )
        })}
        {live.length === 0 ? (
          running.length > 0 ? null : (
          <p className="muted small" style={{ margin: 0 }}>
            No poll is open right now.
          </p>
          )
        ) : (
          <>
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
          </>
        )}

    </>
  )
}
