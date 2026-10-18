import { useState } from 'react'
import { useOutletContext } from 'react-router'
import { api } from '../../api.js'
import { ErrorBox, Field, Loaded, RoleBadge } from '../../components/ui.jsx'
import { useAction, useApi, useAuth } from '../../hooks.js'

export default function StaffTab() {
  const { course } = useOutletContext()
  const { user } = useAuth()
  const staff = useApi(`/courses/${course.id}/instructors`)
  const [identifier, setIdentifier] = useState('')
  const [role, setRole] = useState('ta')
  const canManage = course.my_role === 'owner' || course.my_role === 'instructor' || user.is_admin

  const [add, adding, addError] = useAction(async () => {
    await api.post(`/courses/${course.id}/instructors`, { identifier: identifier.trim(), role })
    setIdentifier('')
    staff.reload()
  })
  const [remove, , removeError] = useAction(async (userId) => {
    await api.delete(`/courses/${course.id}/instructors/${userId}`)
    staff.reload()
  })

  return (
    <div className="card">
      <h2>Instructors &amp; TAs</h2>
      <p className="small muted">
        Instructors run the course. TAs can write questions and run polls but can&apos;t change the course settings.
      </p>
      <ErrorBox error={removeError} />
      <Loaded state={staff}>
        {(list) => (
          <ul className="list">
            {list.map((s) => (
              <li key={s.user.id}>
                <span className="grow">
                  <strong>{s.user.display_name}</strong>
                  <span className="muted small">
                    {' '}
                    · {s.user.net_id} {s.user.email && `· ${s.user.email}`}
                  </span>
                </span>
                <RoleBadge role={s.role} />
                {canManage && s.role !== 'owner' && (
                  <button type="button" className="btn btn-sm btn-danger" onClick={() => remove(s.user.id)}>
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Loaded>
      {canManage && (
        <form
          style={{ marginTop: 20 }}
          onSubmit={(e) => {
            e.preventDefault()
            add()
          }}
        >
          <h3>Add someone</h3>
          <div className="form-row">
            <Field label="NetID or email">
              <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder="abc12345" required />
            </Field>
            <Field label="Role">
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="ta">TA</option>
                <option value="instructor">Instructor</option>
              </select>
            </Field>
          </div>
          <ErrorBox error={addError} />
          <button type="submit" className="btn btn-primary" disabled={adding}>
            {adding ? 'Adding…' : 'Add'}
          </button>
        </form>
      )}
    </div>
  )
}
