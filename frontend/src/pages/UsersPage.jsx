// Admins: find accounts and change their role.
import { useState } from 'react'
import { Navigate } from 'react-router'
import { api } from '../api.js'
import { ErrorBox, Loaded } from '../components/ui.jsx'
import { useAction, useApi, useAuth } from '../hooks.js'

const ROLES = ['admin', 'instructor', 'ta', 'student', 'guest']

export default function UsersPage() {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const params = new URLSearchParams()
  if (search) params.set('q', search)
  if (role) params.set('role', role)
  const users = useApi(user.is_admin ? `/users?${params}` : null)

  const [changeRole, , roleError] = useAction(async (u, newRole) => {
    const updated = await api.patch(`/users/${u.id}/role`, { role: newRole })
    users.setData((list) => list.map((x) => (x.id === updated.id ? updated : x)))
  })

  if (!user.is_admin) return <Navigate to="/courses" replace />

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Users</h1>
          <p className="subtitle">Make professors instructors, or change anyone&apos;s account type.</p>
        </div>
      </div>
      <div className="card">
        <form
          className="row"
          style={{ marginBottom: 12 }}
          onSubmit={(e) => {
            e.preventDefault()
            setSearch(q.trim())
          }}
        >
          <input type="search" className="inline-input" style={{ flex: 1, minWidth: 200 }} placeholder="Name, NetID or email" value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="inline-input" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">All roles</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn-primary">
            Search
          </button>
        </form>
        <ErrorBox error={roleError} />
        <Loaded state={users}>
          {(list) =>
            list.length === 0 ? (
              <p className="empty">No accounts match.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>NetID</th>
                      <th>Email</th>
                      <th>Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((u) => (
                      <tr key={u.id}>
                        <td>{u.display_name}</td>
                        <td>{u.net_id}</td>
                        <td className="small">{u.email}</td>
                        <td>
                          <select className="inline-input" value={u.role} onChange={(e) => changeRole(u, e.target.value)}>
                            {ROLES.map((r) => (
                              <option key={r} value={r}>
                                {r}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </Loaded>
      </div>
    </main>
  )
}
