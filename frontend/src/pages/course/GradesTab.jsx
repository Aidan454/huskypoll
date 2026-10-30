import { useState } from 'react'
import { useOutletContext } from 'react-router'
import { api } from '../../api.js'
import { Loaded, Modal } from '../../components/ui.jsx'
import { formatDate, formatDateTime } from '../../format.js'
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
  // Dates the instructor unticked. null means "not chosen yet": start with the
  // dates that were already exported unticked, so the default is only new dates.
  const [deselected, setDeselected] = useState(null)
  const list = sessions.data || []
  const off = deselected ?? new Set(list.filter((s) => s.exported_at).map((s) => s.date))

  function openExport() {
    setDeselected(null)
    sessions.reload()
    setExportOpen(true)
  }

  function toggleDate(date) {
    setDeselected(() => {
      const next = new Set(off)
      if (next.has(date)) next.delete(date)
      else next.add(date)
      return next
    })
  }

  function download() {
    const selected = list.filter((s) => !off.has(s.date)).map((s) => s.date)
    if (!selected.length) return
    window.location.href = api.participationUrl(course.id, selected)
    setExportOpen(false)
    // The download is logged on the server; refresh so these dates show as exported next time.
    setTimeout(sessions.reload, 1500)
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
          <button type="button" className="btn btn-primary" onClick={openExport}>
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
                      <td>{r.last_name || r.first_name ? [r.last_name, r.first_name].filter(Boolean).join(', ') : <span className="muted">—</span>}</td>
                      <td className="netid">{r.net_id?.toUpperCase()}</td>
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
            const selected = list.filter((s) => !off.has(s.date))
            const exported = list.filter((s) => s.exported_at)
            const fresh = list.filter((s) => !s.exported_at)
            return list.length === 0 ? (
              <p className="empty">No closed polls yet. Close a poll before exporting participation.</p>
            ) : (
              <>
                <p className="muted">
                  {exported.length === 0
                    ? 'Choose the lecture dates to include in the CSV.'
                    : fresh.length === 0
                      ? 'Every date has already been exported. Tick any date you want to download again.'
                      : `${fresh.length} new ${fresh.length === 1 ? 'date is' : 'dates are'} selected. Dates you already exported are unticked.`}
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
                      Deselect all
                    </button>
                    {exported.length > 0 && fresh.length > 0 && (
                      <button
                        type="button"
                        className="linkbtn"
                        onClick={() => setDeselected(new Set(exported.map((s) => s.date)))}
                      >
                        Only new dates
                      </button>
                    )}
                  </div>
                </div>
                <div className="stack export-dates">
                  {list.map((s) => (
                    <label key={s.date} className="check export-date">
                      <input type="checkbox" checked={!off.has(s.date)} onChange={() => toggleDate(s.date)} />
                      <span className="export-date-text">
                        <span>{formatDate(s.date)}</span>
                        <span className="small muted">{s.column}</span>
                      </span>
                      {s.exported_at ? (
                        <span className="badge" title={`Last exported ${formatDateTime(s.exported_at)}`}>
                          Exported {formatDateTime(s.exported_at)}
                        </span>
                      ) : (
                        <span className="badge badge-blue">New</span>
                      )}
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
