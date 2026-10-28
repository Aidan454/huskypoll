import { useState } from 'react'
import { useOutletContext } from 'react-router'
import { api } from '../../api.js'
import { ErrorBox, Loaded } from '../../components/ui.jsx'
import { formatDateTime } from '../../format.js'
import { useAction, useApi } from '../../hooks.js'

const PAGE = 100

function describe(e) {
  const d = e.details && Object.keys(e.details).length ? JSON.stringify(e.details) : ''
  return d.length > 120 ? `${d.slice(0, 119)}…` : d
}

export default function ActivityTab() {
  const { course } = useOutletContext()
  const first = useApi(`/courses/${course.id}/events?limit=${PAGE}`)
  const [more, setMore] = useState([])
  const [done, setDone] = useState(false)

  const [loadMore, busy, error] = useAction(async (beforeId) => {
    const page = await api.get(`/courses/${course.id}/events`, { limit: PAGE, before_id: beforeId })
    setMore((m) => [...m, ...page])
    if (page.length < PAGE) setDone(true)
  })

  return (
    <div className="card">
      <h2>Activity log</h2>
      <p className="small muted">Logins, polls, answers and roster changes in this course, newest first.</p>
      <Loaded state={first}>
        {(events) => {
          const all = [...events, ...more]
          if (!all.length) return <p className="empty">Nothing yet.</p>
          return (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>What</th>
                      <th>Who</th>
                      <th>Poll</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {all.map((e) => (
                      <tr key={e.id}>
                        <td className="small" style={{ whiteSpace: 'nowrap' }}>
                          {formatDateTime(e.occurred_at)}
                        </td>
                        <td>
                          <code>{e.event_type}</code>
                        </td>
                        <td>{e.net_id}</td>
                        <td>{e.poll_id}</td>
                        <td className="small muted">{describe(e)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ErrorBox error={error} />
              {!done && events.length === PAGE && (
                <button type="button" className="btn" style={{ marginTop: 12 }} disabled={busy} onClick={() => loadMore(all[all.length - 1].id)}>
                  {busy ? 'Loading…' : 'Load older'}
                </button>
              )}
            </>
          )
        }}
      </Loaded>
    </div>
  )
}
