import { useState } from 'react'
import { useOutletContext } from 'react-router'
import { api } from '../../api.js'
import { Loaded } from '../../components/ui.jsx'
import { pct, points } from '../../format.js'
import { useApi } from '../../hooks.js'

const COLUMNS = [
  ['last_name', 'Name'],
  ['net_id', 'NetID'],
  ['answered', 'Answered'],
  ['correct', 'Correct'],
  ['points', 'Points'],
]

export default function GradesTab() {
  const { course } = useOutletContext()
  const rows = useApi(`/courses/${course.id}/participation`)
  const [sort, setSort] = useState({ key: 'last_name', desc: false })

  function sorted(list) {
    const { key, desc } = sort
    return [...list].sort((a, b) => {
      const x = a[key] ?? ''
      const y = b[key] ?? ''
      const cmp = typeof x === 'number' ? x - y : String(x).localeCompare(String(y))
      return desc ? -cmp : cmp
    })
  }

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h2>Grades</h2>
          <p className="small muted" style={{ margin: 0 }}>
            {points(course.points_participation)} pt for answering each closed poll, plus {points(course.points_correct)} pt
            when correct (polls with an answer key).
          </p>
        </div>
        <div className="row">
          <a className="btn btn-primary" href={api.exportUrl(course.id, 'huskyct')} download>
            Download for HuskyCT
          </a>
          <a className="btn" href={api.exportUrl(course.id, 'sessions')} download>
            By lecture (CSV)
          </a>
        </div>
      </div>
      <Loaded state={rows}>
        {(list) =>
          list.length === 0 ? (
            <p className="empty">No students on the roster yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {COLUMNS.map(([key, label]) => (
                      <th key={key} className={key === 'last_name' || key === 'net_id' ? '' : 'num'}>
                        <button
                          type="button"
                          className="linkbtn"
                          style={{ color: 'inherit', textDecoration: 'none', textTransform: 'inherit', fontWeight: 600 }}
                          onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== 'last_name' && key !== 'net_id' }))}
                        >
                          {label} {sort.key === key ? (sort.desc ? '▾' : '▴') : ''}
                        </button>
                      </th>
                    ))}
                    <th className="num">%</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted(list).map((r) => (
                    <tr key={r.net_id || r.email || r.student_id}>
                      <td>
                        {r.last_name}, {r.first_name}
                      </td>
                      <td>{r.net_id}</td>
                      <td className="num">
                        {r.answered}/{r.polls}
                      </td>
                      <td className="num">{r.correct}</td>
                      <td className="num">
                        {points(r.points)}/{points(r.points_possible)}
                      </td>
                      <td className="num">{pct(r.points, r.points_possible)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </Loaded>
    </div>
  )
}
