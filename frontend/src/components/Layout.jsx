import { Link, NavLink, Outlet, useNavigate } from 'react-router'
import { canTeach, initials } from '../format.js'
import { useAuth } from '../hooks.js'
import { RoleBadge } from './ui.jsx'

/** Top bar and page frame for every logged-in page. */
export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function signOut() {
    await logout()
    navigate('/login')
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/courses" className="brand">
            Husky<span>Poll</span>
          </Link>
          <nav className="topnav">
            <NavLink to="/courses">Courses</NavLink>
            <NavLink to="/join">Join a poll</NavLink>
            {canTeach(user) && <NavLink to="/banks">Question banks</NavLink>}
            {user?.role === 'admin' && <NavLink to="/admin/users">Users</NavLink>}
          </nav>
          <div className="usermenu">
            <span className="avatar" title={user?.display_name}>
              {initials(user)}
            </span>
            <span className="username">
              {user?.display_name} <RoleBadge role={user?.role} />
            </span>
            <button type="button" className="btn btn-sm" onClick={signOut}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <Outlet />
    </>
  )
}
