import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'
import menuIcon from '../assets/menu.svg'
import { canTeach } from '../format.js'
import { useApi, useAuth } from '../hooks.js'
import AvatarMenu from './Header/AvatarMenu.jsx'
import { RoleBadge } from './ui.jsx'

function Navigation({ user, onNavigate }) {
  return (
    <>
      <NavLink to="/courses" onClick={onNavigate}>Courses</NavLink>
      {!canTeach(user) && <NavLink to="/join" onClick={onNavigate}>Join a poll</NavLink>}
      {canTeach(user) && <NavLink to="/banks" onClick={onNavigate}>Question banks</NavLink>}
      {user?.role === 'admin' && <NavLink to="/admin/users" onClick={onNavigate}>Users</NavLink>}
    </>
  )
}

/** Top bar and page frame for every logged-in page. */
export default function Layout() {
  const { user } = useAuth()
  const courses = useApi('/courses')
  const [menuOpen, setMenuOpen] = useState(false)
  const drawerRef = useRef(null)
  const triggerRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return
    function onPointerDown(event) {
      const target = event.target
      if (drawerRef.current?.contains(target) || triggerRef.current?.contains(target)) return
      setMenuOpen(false)
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        setMenuOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 641px)')
    function onChange(event) {
      if (event.matches) setMenuOpen(false)
    }
    desktop.addEventListener('change', onChange)
    return () => desktop.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    if (!menuOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [menuOpen])

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <button
            ref={triggerRef}
            type="button"
            className="nav-toggle"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-haspopup="true"
            aria-expanded={menuOpen}
            aria-controls="mobile-nav"
            onClick={() => setMenuOpen((value) => !value)}
          >
            <img className="nav-toggle-icon" src={menuIcon} alt="" />
          </button>
          <Link to="/courses" className="brand">
            Husky<span>Poll</span>
          </Link>
          <nav className="topnav" aria-label="Main navigation">
            <Navigation user={user} />
          </nav>
          <div className="usermenu">
            <RoleBadge role={user?.role} />
            <AvatarMenu />
          </div>
        </div>
        <div
          className={`nav-backdrop${menuOpen ? ' is-open' : ''}`}
          aria-hidden="true"
          onClick={() => setMenuOpen(false)}
        />
        <nav
          ref={drawerRef}
          id="mobile-nav"
          className={`mobile-drawer${menuOpen ? ' is-open' : ''}`}
          aria-label="Main navigation"
          aria-hidden={!menuOpen}
        >
          <div className="mobile-drawer-head">
            <Link to="/courses" className="brand" onClick={() => setMenuOpen(false)}>
              Husky<span>Poll</span>
            </Link>
          </div>
          <Navigation user={user} onNavigate={() => setMenuOpen(false)} />
          <div className="drawer-section">
            <div className="drawer-section-label">Your courses</div>
            {courses.loading && <p className="drawer-note">Loading courses…</p>}
            {courses.error && <p className="drawer-note">Couldn&apos;t load courses.</p>}
            {courses.data?.length === 0 && <p className="drawer-note">No courses yet.</p>}
            {courses.data?.map((course) => (
              <NavLink
                key={course.id}
                to={`/courses/${course.id}`}
                className="drawer-course"
                onClick={() => setMenuOpen(false)}
              >
                <span className="drawer-course-code">
                  {course.subject} {course.catalog}
                  {course.section ? `-${course.section}` : ''}
                </span>
                <span className="drawer-course-title">{course.title}</span>
              </NavLink>
            ))}
          </div>
        </nav>
      </header>
      <Outlet />
    </>
  )
}
