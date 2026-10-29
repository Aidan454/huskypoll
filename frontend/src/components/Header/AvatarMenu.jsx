import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { initials } from '../../format.js'
import { useAuth } from '../../hooks.js'
import ThemeToggle from '../ThemeToggle.jsx'

/** Avatar button with the account details, theme switch and sign-out menu. */
export default function AvatarMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)
  const triggerRef = useRef(null)

  useEffect(() => {
    if (!open) return
    function onPointerDown(event) {
      if (!menuRef.current?.contains(event.target)) setOpen(false)
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  async function signOut() {
    setOpen(false)
    await logout()
    navigate('/login')
  }

  const name = [user?.first_name, user?.last_name].filter(Boolean).join(' ')

  return (
    <div className="avatar-menu" ref={menuRef}>
      <button
        ref={triggerRef}
        type="button"
        className="avatar avatar-trigger"
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="Account menu"
        title={user?.display_name}
        onClick={() => setOpen((value) => !value)}
      >
        {initials(user)}
      </button>
      {open && (
        <div className="avatar-dropdown">
          <div className="avatar-profile">
            <span className="avatar avatar-large" aria-hidden="true">{initials(user)}</span>
            <div className="avatar-details">
              {name && <div className="avatar-name">{name}</div>}
              {user?.email && <div className="avatar-detail">{user.email}</div>}
              {user?.net_id && <div className="avatar-detail">NetID: {user.net_id}</div>}
            </div>
          </div>
          <div className="avatar-divider" />
          <ThemeToggle />
          <button type="button" className="avatar-signout" onClick={signOut}>
            <span className="avatar-signout-icon" aria-hidden="true" />
            Log out
          </button>
        </div>
      )}
    </div>
  )
}
