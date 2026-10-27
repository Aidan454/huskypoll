import { useState } from 'react'
import { useOutletContext } from 'react-router'
import { api } from '../../api.js'
import { Loaded, Modal } from '../../components/ui.jsx'
import { useApi } from '../../hooks.js'

const COLUMNS = [
  ['last_name', 'Name'],
  ['net_id', 'NetID'],
  ['answered', 'Answered'],
]

export default function GradesTab() {
  const { course } = useOutletContext()
  const rows = useApi(`/courses/${course.id}/participation`)
  const sessions = useApi(`/courses/${course.id}/participation/sessions`)
  const [sort, setSort] = useState({ key: 'last_name', desc: false })
  const [exportOpen, setExportOpen] = useState(false)
  const [deselected, setDeselected] = useState(() => new Set())

  function toggleDate(date) {
    setDeselected((current) => {
      const next = new Set(current)
      if (next.has(date)) next.delete(date)
      else next.add(date)
      return next
    })
  }

  function download() {
    const selected = (sessions.data || []).filter((s) => !deselected.has(s.date)).map((s) => s.date)
    if (!selected.length) return
    window.location.href = api.participationUrl(course.id, selected)
    setExportOpen(false)
  }

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
        </div>
        <div className="row">
          <button type="button" className="btn btn-primary" onClick={() => setExportOpen(true)}>
            Download participation (CSV)
          </button>
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </Loaded>

      <Modal open={exportOpen} onClose={() => setExportOpen(false)} title="Download participation CSV">
        <Loaded state={sessions}>
          {(list) => {
            const selected = list.filter((s) => !deselected.has(s.date))
            return list.length === 0 ? (
              <p className="empty">No closed polls yet. Close a poll before exporting participation.</p>
            ) : (
              <>
                <p className="muted">
                  All lecture dates are selected. Untick any date you do not want in the CSV.
                </p>
                <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
                  <span className="small muted">
                    {selected.length} of {list.length} selected
                  </span>
                  <div className="row">
                    <button type="button" className="linkbtn" onClick={() => setDeselected(new Set())}>
                      Select all
                    </button>
                    <button
                      type="button"
                      className="linkbtn"
                      onClick={() => setDeselected(new Set(list.map((s) => s.date)))}
                    >
                      Clear all
                    </button>
                  </div>
                </div>
                <div className="stack">
                  {list.map((s) => (
                    <label key={s.date} className="check">
                      <input
                        type="checkbox"
                        checked={!deselected.has(s.date)}
                        onChange={() => toggleDate(s.date)}
                      />
                      <span>{s.column}</span>
                    </label>
                  ))}
                </div>
                <div className="form-actions">
                  <button type="button" className="btn" onClick={() => setExportOpen(false)}>
                    Cancel
                  </button>
                  <button type="button" className="btn btn-primary" onClick={download} disabled={!selected.length}>
                    Download CSV
                  </button>
                </div>
              </>
            )
          }}
        </Loaded>
      </Modal>
    </div>
  )
}
