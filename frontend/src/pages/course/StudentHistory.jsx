import { useEffect, useState } from 'react'
import { Navigate, useOutletContext } from 'react-router'
import { AnswerKey, Mark, QuestionBody } from '../../components/PollParts.jsx'
import { Loaded, SortSelect } from '../../components/ui.jsx'
import { answerText, formatDate, isStaff, pct, points, snippet } from '../../format.js'
import { useApi, useSortOrder } from '../../hooks.js'
import { connectCourse } from '../../live.js'
import Markdown from '../../components/Markdown.jsx'

export function Participation({ courseId, version }) {
  const p = useApi(`/courses/${courseId}/my-participation?v=${version}`)
  return (
    <Loaded state={p}>
      {(d) => (
        <div className="stats" style={{ marginBottom: 20 }}>
          <div className="card">
            <div className="stat">
              {d.answered}/{d.polls}
            </div>
            <div className="stat-label">Polls answered</div>
          </div>
          <div className="card">
            <div className="stat">{d.correct}</div>
            <div className="stat-label">Correct answers</div>
          </div>
          <div className="card">
            <div className="stat">
              {points(d.points)}
              <span className="muted" style={{ fontSize: 18 }}>
                /{points(d.points_possible)}
              </span>
            </div>
            <div className="stat-label">Points ({pct(d.points, d.points_possible)}%)</div>
          </div>
        </div>
      )}
    </Loaded>
  )
}

function HistoryItem({ item }) {
  const [open, setOpen] = useState(false)
  const { poll } = item
  const q = poll.question
  return (
    <li style={{ display: 'block' }}>
      <div className="row">
        <button type="button" className="linkbtn grow" style={{ textAlign: 'left', textDecoration: 'none' }} onClick={() => setOpen(!open)}>
          {open ? '▾' : '▸'} {snippet(q.body_md)}
        </button>
        {poll.my_response && <span className="small muted">Your answer: {String(answerText(q, poll.my_response))}</span>}
        <Mark response={poll.my_response} />
      </div>
      {open && (
        <div style={{ marginTop: 12, paddingLeft: 18 }}>
          <QuestionBody question={q} />
          {q.options.length > 0 && (
            <ul className="list small">
              {q.options.map((o) => (
                <li key={o.id} style={{ justifyContent: 'flex-start' }}>
                  <span className="letter" style={o.is_correct ? { background: 'var(--green)', color: 'var(--on-accent)' } : undefined}>
                    {o.letter}
                  </span>
                  <span className="grow">
                    <Markdown text={o.text_md} />
                  </span>
                  {poll.my_response?.option_ids.includes(o.id) && <span className="badge badge-blue">Your choice</span>}
                </li>
              ))}
            </ul>
          )}
          <AnswerKey question={q} />
        </div>
      )}
    </li>
  )
}

/** Closed polls grouped by lecture day. `items` come from the API newest first. */
export function HistoryList({ items, order = 'newest' }) {
  const closed = items.filter((i) => i.poll.status === 'closed')
  if (order === 'oldest') closed.reverse()
  if (!closed.length) return <div className="card empty">No finished polls yet.</div>
  const byDay = []
  for (const item of closed) {
    const last = byDay[byDay.length - 1]
    if (last && last.date === item.session_date) last.items.push(item)
    else byDay.push({ date: item.session_date, title: item.session_title, items: [item] })
  }
  return byDay.map((g) => (
    <div className="card" key={g.date + g.title}>
      <h3>
        {formatDate(g.date)}
        {g.title && <span className="muted"> · {g.title}</span>}
      </h3>
      <ul className="list">
        {g.items.map((item) => (
          <HistoryItem key={item.poll.id} item={item} />
        ))}
      </ul>
    </div>
  ))
}

/** Student History tab: participation stats and finished polls. */
export default function StudentHistory() {
  const { course } = useOutletContext()
  const history = useApi(`/courses/${course.id}/history`)
  const [version, setVersion] = useState(0)
  const [order, setOrder] = useSortOrder('history')
  const { reload: reloadHistory } = history

  useEffect(
    () =>
      connectCourse(course.id, (msg) => {
        if (msg.type === 'poll_opened' || msg.type === 'poll_closed') {
          reloadHistory()
          setVersion((v) => v + 1)
        }
      }),
    [course.id, reloadHistory],
  )

  if (isStaff(course)) return <Navigate to={`/courses/${course.id}`} replace />

  return (
    <>
      <h2>My participation</h2>
      <Participation courseId={course.id} version={version} />

      <div className="card-head" style={{ marginTop: 28 }}>
        <h2>History</h2>
        <SortSelect value={order} onChange={setOrder} />
      </div>
      <Loaded state={history}>{(items) => <HistoryList items={items} order={order} />}</Loaded>
    </>
  )
}
