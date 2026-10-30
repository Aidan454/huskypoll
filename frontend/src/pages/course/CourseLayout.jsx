import { Link, NavLink, Outlet, useParams } from 'react-router'
import { ErrorBox, Loading, RoleBadge } from '../../components/ui.jsx'
import { isStaff } from '../../format.js'
import { useApi } from '../../hooks.js'

/** Course header and tabs; each tab is a child route that gets { course, reloadCourse } from the outlet. */
export default function CourseLayout() {
  const { courseId } = useParams()
  const course = useApi(`/courses/${courseId}`)

  if (course.error) {
    return (
      <main className="page">
        <ErrorBox error={course.error} />
        <Link to="/courses">← Back to courses</Link>
      </main>
    )
  }
  if (!course.data) {
    return (
      <main className="page">
        <Loading />
      </main>
    )
  }
  const c = course.data
  const staff = isStaff(c)
  const base = `/courses/${c.id}`

  return (
    <main className="page">
      <div className="crumbs">
        <Link to="/courses">Courses</Link> / {c.subject} {c.catalog}
      </div>
      <div className="page-head">
        <div>
          <h1>
            {c.subject} {c.catalog}
            {c.section ? `-${c.section}` : ''}: {c.title}
          </h1>
          <p className="subtitle">
            {c.term} <RoleBadge role={c.my_role} /> {c.archived_at && <span className="badge">Archived</span>}
          </p>
        </div>
      </div>

      <nav className="tabs">
        <NavLink to={base} end>
          <span className="tab-icon tab-icon-polls" aria-hidden="true" />
          {staff ? 'Polls' : 'Polls & history'}
        </NavLink>
        {staff && (
          <NavLink to={`${base}/lectures`}>
            <span className="tab-icon tab-icon-lectures" aria-hidden="true" />
            Lectures
          </NavLink>
        )}
        {staff && (
          <NavLink to={`${base}/roster`}>
            <span className="tab-icon tab-icon-roster" aria-hidden="true" />
            Roster
          </NavLink>
        )}
        {staff && <NavLink to={`${base}/staff`}>Instructors & TAs</NavLink>}
        {staff && (
          <NavLink to={`${base}/grades`}>
            <span className="tab-icon tab-icon-grades" aria-hidden="true" />
            Grades
          </NavLink>
        )}
        {staff && (
          <NavLink to={`${base}/activity`}>
            <span className="tab-icon tab-icon-activity" aria-hidden="true" />
            Activity
          </NavLink>
        )}
        {staff && (
          <NavLink to={`${base}/settings`}>
            <span className="tab-icon tab-icon-settings" aria-hidden="true" />
            Settings
          </NavLink>
        )}
      </nav>

      <Outlet context={{ course: c, reloadCourse: course.reload, setCourse: course.setData }} />
    </main>
  )
}
