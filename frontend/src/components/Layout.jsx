import { Link, NavLink, Outlet } from 'react-router'
import { canTeach } from '../format.js'
import { useAuth } from '../hooks.js'
import AvatarMenu from './Header/AvatarMenu.jsx'
import { RoleBadge } from './ui.jsx'

/** Top bar and page frame for every logged-in page. */
export default function Layout() {
  const { user } = useAuth()

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/courses" className="brand">
            Husky<span>Poll</span>
          </Link>
          <nav className="topnav">
            <NavLink to="/courses">Courses</NavLink>
            {!canTeach(user) && <NavLink to="/join">Join a poll</NavLink>}
            {canTeach(user) && <NavLink to="/banks">Question banks</NavLink>}
            {user?.role === 'admin' && <NavLink to="/admin/users">Users</NavLink>}
          </nav>
          <div className="usermenu">
            <RoleBadge role={user?.role} />
            <AvatarMenu />
          </div>
        </div>
      </header>
      <Outlet />
    </>
  )
}
