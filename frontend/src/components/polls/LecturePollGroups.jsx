import { Link } from 'react-router'
import { StatusBadge } from '../ui.jsx'
import { formatDate, QUESTION_TYPE_SHORT, snippet } from '../../format.js'

export default function LecturePollGroups({ groups, course, reopenPoll }) {
  return (
    <>
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
                {p.status === 'closed' && !course.archived_at && (
                  <button type="button" className="btn btn-sm" onClick={() => reopenPoll(p)} title="Let students answer again">
                    Reopen
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </>
  )
}
