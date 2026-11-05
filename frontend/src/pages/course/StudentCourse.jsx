import { useEffect, useState } from 'react'
import { AnswerForm, ResultsView } from '../../components/PollParts.jsx'
import { Loaded } from '../../components/ui.jsx'
import { useApi } from '../../hooks.js'
import { connectCourse } from '../../live.js'

export default function StudentCourse({ course }) {
  const openPolls = useApi(`/courses/${course.id}/polls?status=open`)
  const [results, setResults] = useState({}) // poll_id -> results, when the instructor shares them
  const { reload: reloadOpen } = openPolls

  useEffect(
    () =>
      connectCourse(course.id, (msg) => {
        if (msg.type === 'poll_opened' || msg.type === 'poll_closed') {
          reloadOpen()
        } else if (msg.type === 'results') {
          setResults((r) => ({ ...r, [msg.results.poll_id]: msg.results }))
        }
      }),
    [course.id, reloadOpen],
  )

  return (
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
