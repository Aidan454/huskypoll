import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useParams } from 'react-router'
import { ErrorBox, Loading, RoleBadge } from '../../components/ui.jsx'
import { isStaff } from '../../format.js'
import { useApi } from '../../hooks.js'

/** True when the current URL is this tab's page (or one of its subpages). */
function isTabActive(tab, pathname) {
  return pathname === tab.to || (!tab.end && pathname.startsWith(`${tab.to}/`))
}

/** Course header and tabs; each tab is a child route that gets { course, reloadCourse } from the outlet. */
export default function CourseLayout() {
  const { courseId } = useParams()
  const course = useApi(`/courses/${courseId}`)
  const { pathname } = useLocation()
  const navRef = useRef(null)
  const moreRef = useRef(null)
  const moreWrapRef = useRef(null)
  const [visibleCount, setVisibleCount] = useState(0)
  const [iconsOn, setIconsOn] = useState(true)
  // The pathname the menu was opened on: going anywhere closes it, and so does
  // having every tab fit again.
  const [openedPath, setOpenedPath] = useState(null)

  const data = course.data
  const studentTabs = Boolean(data) && !isStaff(data)

  const tabs = useMemo(() => {
    if (!data) return []
    const base = `/courses/${data.id}`
    if (!isStaff(data)) {
      return [
        { to: base, end: true, label: 'Polls', icon: 'polls' },
        { to: `${base}/history`, label: 'History', icon: 'history' },
        { to: `${base}/lectures`, label: 'Lectures', icon: 'lectures' },
      ]
    }
    return [
      { to: base, end: true, label: 'Polls', icon: 'polls' },
      { to: `${base}/lectures`, label: 'Lectures', icon: 'lectures' },
      { to: `${base}/roster`, label: 'Roster', icon: 'roster' },
      { to: `${base}/staff`, label: 'Instructors & TAs' },
      { to: `${base}/grades`, label: 'Grades', icon: 'grades' },
      { to: `${base}/activity`, label: 'Activity', icon: 'activity' },
      { to: `${base}/settings`, label: 'Settings', icon: 'settings' },
    ]
  }, [data])

  // Fit as many tabs on the row as possible, never shrinking them. Try with the
  // icons first so they come back as soon as there's room; then without them;
  // then move the tabs that still don't fit into the "More" menu. Hidden tabs
  // stay in the DOM so they keep a measurable width.
  const measureTabs = useCallback(() => {
    const nav = navRef.current
    const more = moreRef.current
    if (!nav || !more) return
    const links = Array.from(nav.querySelectorAll('[data-tab]'))
    if (links.length === 0) return
    const gap = Number.parseFloat(getComputedStyle(nav).columnGap) || 0
    const room = nav.clientWidth
    const moreWidth = more.getBoundingClientRect().width

    // Read both layouts in this frame, then put the current one back.
    const currentIcons = !nav.classList.contains('tab-icons-hidden')
    const measure = (withIcons) => {
      nav.classList.toggle('tab-icons-hidden', !withIcons)
      return links.map((el) => el.getBoundingClientRect().width)
    }
    const withIcons = measure(true)
    const withoutIcons = measure(false)
    nav.classList.toggle('tab-icons-hidden', !currentIcons)

    const total = (widths) => widths.reduce((sum, width, index) => sum + width + (index ? gap : 0), 0)
    if (total(withIcons) <= room) {
      setIconsOn(true)
      setVisibleCount(links.length)
      return
    }
    if (total(withoutIcons) <= room) {
      setIconsOn(false)
      setVisibleCount(links.length)
      return
    }

    const reserved = moreWidth + gap
    let used = 0
    let fits = 0
    for (let index = 0; index < withoutIcons.length; index += 1) {
      const next = used + withoutIcons[index] + (index ? gap : 0)
      if (next + reserved > room) break
      used = next
      fits = index + 1
    }
    setIconsOn(false)
    setVisibleCount(Math.min(fits, withoutIcons.length - 1))
  }, [])

  useLayoutEffect(() => {
    if (!studentTabs) measureTabs()
  }, [measureTabs, studentTabs, tabs])

  useEffect(() => {
    const nav = navRef.current
    if (!nav || studentTabs) return undefined
    const observer = new ResizeObserver(measureTabs)
    observer.observe(nav)
    return () => observer.disconnect()
  }, [measureTabs, studentTabs, tabs])

  // The student bar is two short tabs in a fixed bottom bar; it never overflows.
  const shown = studentTabs ? tabs.length : Math.min(visibleCount, tabs.length)
  const hiddenTabs = tabs.slice(shown)
  const hiddenActive = hiddenTabs.some((tab) => isTabActive(tab, pathname))
  const moreOpen = openedPath === pathname && hiddenTabs.length > 0

  useEffect(() => {
    if (!moreOpen) return undefined
    function onPointerDown(event) {
      if (!moreWrapRef.current?.contains(event.target)) setOpenedPath(null)
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        setOpenedPath(null)
        moreRef.current?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [moreOpen])

  if (course.error) {
    return (
      <main className="page">
        <ErrorBox error={course.error} />
        <Link to="/courses">← Back to courses</Link>
      </main>
    )
  }
  if (!data) {
    return (
      <main className="page">
        <Loading />
      </main>
    )
  }
  const c = data

  return (
    <main className="page">
      <div className="crumbs">
        <Link to="/courses">Courses</Link> / {c.subject} {c.catalog}
      </div>
      <div className="page-head">
        <div>
          <h1>
            {c.subject} {c.catalog}: {c.title}
          </h1>
          <p className="subtitle">
            {c.term} <RoleBadge role={c.my_role} /> {c.archived_at && <span className="badge">Archived</span>}
          </p>
        </div>
      </div>

      <nav
        ref={navRef}
        className={`tabs${studentTabs ? ' tabs-student' : ''}${studentTabs || iconsOn ? '' : ' tab-icons-hidden'}`}
        aria-label="Course sections"
      >
        {tabs.map((tab, index) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            data-tab=""
            className={index < shown ? undefined : 'tab-overflow'}
          >
            {tab.icon && <span className={`tab-icon tab-icon-${tab.icon}`} aria-hidden="true" />}
            {tab.label}
          </NavLink>
        ))}
        {!studentTabs && tabs.length > 0 && (
          <div ref={moreWrapRef} className={`tab-more-wrap${hiddenTabs.length ? '' : ' is-ghost'}`}>
            <button
              ref={moreRef}
              type="button"
              className={`tab-more${hiddenActive ? ' active' : ''}`}
              aria-expanded={moreOpen}
              onClick={() => setOpenedPath(moreOpen ? null : pathname)}
            >
              More<span className="tab-more-caret" aria-hidden="true" />
            </button>
            {moreOpen && (
              <div className="tab-more-menu">
                {hiddenTabs.map((tab) => (
                  <NavLink key={tab.to} to={tab.to} end={tab.end} onClick={() => setOpenedPath(null)}>
                    {tab.label}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        )}
      </nav>

      <Outlet context={{ course: c, reloadCourse: course.reload, setCourse: course.setData }} />
    </main>
  )
}
