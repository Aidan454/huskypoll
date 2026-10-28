import { useEffect, useState } from 'react'
import { AnswerForm, AnswerKey, Mark, QuestionBody, ResultsView } from '../../components/PollParts.jsx'
import { Loaded } from '../../components/ui.jsx'
import { answerText, formatDate, pct, points, snippet } from '../../format.js'
import { useApi } from '../../hooks.js'
import { connectCourse } from '../../live.js'
import Markdown from '../../components/Markdown.jsx'

function Participation({ courseId, version }) {
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

export default function StudentCourse({ course }) {
  const openPolls = useApi(`/courses/${course.id}/polls?status=open`)
  const history = useApi(`/courses/${course.id}/history`)
  const [results, setResults] = useState({}) // poll_id -> results, when the instructor shares them
  const [version, setVersion] = useState(0)
  const { reload: reloadOpen } = openPolls
  const { reload: reloadHistory } = history

  useEffect(
    () =>
      connectCourse(course.id, (msg) => {
        if (msg.type === 'poll_opened' || msg.type === 'poll_closed') {
          reloadOpen()
          reloadHistory()
          setVersion((v) => v + 1)
        } else if (msg.type === 'results') {
          setResults((r) => ({ ...r, [msg.results.poll_id]: msg.results }))
        }
      }),
    [course.id, reloadOpen, reloadHistory],
  )

  return (
    <>
      <Loaded state={openPolls}>
        {(list) =>
          list.length === 0 ? (
            <div className="card empty">
              <p style={{ margin: 0 }}>No poll is open right now. This page updates by itself when your instructor starts one.</p>
            </div>
          ) : (
            list.map((p) => (
              <div className="card" key={p.id} style={{ borderTop: '4px solid var(--green)' }}>
                <div className="card-head">
                  <h2>Live poll</h2>
                  <span className="badge badge-open">● Open</span>
                </div>
                <AnswerForm key={p.id} poll={p} onSaved={() => reloadHistory()} />
                {p.show_results && results[p.id] && (
                  <div style={{ marginTop: 20 }}>
                    <h3>Class results</h3>
                    <ResultsView question={p.question} results={results[p.id]} revealCorrect={false} />
                  </div>
                )}
              </div>
            ))
          )
        }
      </Loaded>

      <h2 style={{ marginTop: 28 }}>My participation</h2>
      <Participation courseId={course.id} version={version} />

      <h2>History</h2>
      <Loaded state={history}>
        {(items) => {
          const closed = items.filter((i) => i.poll.status === 'closed')
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
        }}
      </Loaded>
    </>
  )
}
