import { useEffect, useState } from 'react'
import { AnswerForm, AnswerKey, Mark, PollCountdown, QuestionBody, ResultsView } from '../../components/PollParts.jsx'
import { Loaded } from '../../components/ui.jsx'
import { useApi } from '../../hooks.js'
import { connectCourse } from '../../live.js'

export default function StudentCourse({ course }) {
  const openPolls = useApi(`/courses/${course.id}/polls?status=open`)
  const [results, setResults] = useState({}) // poll_id -> results, when the instructor shares them
  const [expired, setExpired] = useState({}) // poll_id -> the local countdown hit zero before the server closed it
  const [version, setVersion] = useState(0)
  const { reload: reloadOpen } = openPolls

  useEffect(
    () =>
      connectCourse(course.id, (msg) => {
        if (msg.type === 'poll_opened' || msg.type === 'poll_closed') {
          // A reopened poll starts a fresh timer, so drop any local "time is up" flag.
          if (msg.type === 'poll_opened') setExpired((e) => ({ ...e, [msg.poll.id]: false }))
          reloadOpen()
          reloadHistory()
          setVersion((v) => v + 1)
        } else if (msg.type === 'poll_extended') {
          setExpired((e) => ({ ...e, [msg.poll_id]: false }))
          reloadOpen()
        } else if (msg.type === 'results') {
          setResults((r) => ({ ...r, [msg.results.poll_id]: msg.results }))
        }
      }),
    [course.id, reloadOpen],
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
                  <div className="row">
                    <span className="badge badge-open">● Open</span>
                    <PollCountdown
                      seconds={p.seconds_remaining}
                      onExpire={() => setExpired((e) => ({ ...e, [p.id]: true }))}
                    />
                  </div>
                </div>
                <AnswerForm
                  key={p.id}
                  poll={p}
                  expired={Boolean(expired[p.id])}
                  onSaved={() => reloadHistory()}
                />
                {p.show_results && results[p.id] && (
                  <div style={{ marginTop: 20 }}>
                    <h3>Class results</h3>
                    <ResultsView question={p.question} results={results[p.id]} revealCorrect={false} />
                  </div>
                )}
              </div>
              <AnswerForm key={p.id} poll={p} />
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
  )
}
