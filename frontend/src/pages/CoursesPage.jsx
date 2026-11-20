import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../api.js'
import { ErrorBox, Field, Loaded, Modal, RoleBadge } from '../components/ui.jsx'
import { canTeach, isStaff } from '../format.js'
import { useAction, useApi, useAuth } from '../hooks.js'

function CourseCard({ course }) {
  return (
    <Link to={`/courses/${course.id}`} className="course-card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="course-code">
          {course.subject} {course.catalog}
        </span>
        <RoleBadge role={course.my_role} />
      </div>
      <p className="course-title">{course.title}</p>
      <div className="row small muted">
        <span>{course.term}</span>
        {course.archived_at && <span className="badge">Archived</span>}
      </div>
    </Link>
  )
}

function guessTerm() {
  const d = new Date()
  const y = d.getFullYear()
  return d.getMonth() >= 6 ? `Fall ${y}` : `Spring ${y}`
}

export function CourseForm({ initial, onSubmit, busy, error, submitLabel, onCancel }) {
  const [form, setForm] = useState(
    initial ?? {
      term: guessTerm(),
      subject: '',
      catalog: '',
      title: '',
    },
  )
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  function submit(e) {
    e.preventDefault()
    const body = {
      ...form,
      term: form.term.trim(),
      subject: form.subject.trim().toUpperCase(),
      catalog: form.catalog.trim().toUpperCase(),
    }
    onSubmit(body)
  }

  return (
    <form onSubmit={submit}>
      <div className="form-row">
        <Field label="Term">
          <input value={form.term} onChange={set('term')} required placeholder="Spring 2027" />
        </Field>
        <Field label="Subject">
          <input value={form.subject} onChange={set('subject')} required placeholder="CSE" maxLength={4} type="text" />
        </Field>
        <Field label="Catalog #">
          <input value={form.catalog} onChange={set('catalog')} required placeholder="2050" maxLength={5} />
        </Field>
      </div>
      <Field label="Course title">
        <input value={form.title} onChange={set('title')} required placeholder="Data Structures" maxLength={200} />
      </Field>
      <ErrorBox error={error} />
      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  )
}

export default function CoursesPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [showArchived, setShowArchived] = useState(false)
  const [search, setSearch] = useState('')
  const [term, setTerm] = useState('')
  const [subject, setSubject] = useState('')
  const courses = useApi(`/courses${showArchived ? '?include_archived=true' : ''}`)
  const [creating, setCreating] = useState(false)
  const teach = canTeach(user)

  const allCourses = courses.data ?? []
  const terms = [...new Set(allCourses.map((course) => course.term).filter(Boolean))].sort()
  const subjects = [...new Set(allCourses.map((course) => course.subject).filter(Boolean))].sort()
  const hasFilters = Boolean(search || (teach && (term || subject)))
  const clearFilters = () => { setSearch(''); setTerm(''); setSubject('') }

  const [create, busy, error] = useAction(async (body) => {
    const course = await api.post('/courses', body)
    navigate(`/courses/${course.id}`)
  })

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Courses</h1>
          <p className="subtitle">Hi {user.first_name || user.display_name}. Pick a course to get started.</p>
        </div>
        <div className="row">
          <label className="check small">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
            Show archived
          </label>
          {teach && (
            <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
              + New course
            </button>
          )}
        </div>
      </div>

      <div className="course-filters" role="search" aria-label="Filter courses">
        <input
          type="search"
          aria-label="Search courses"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name or code"
        />
        {teach && (
          <>
            <select aria-label="Filter by term" value={term} onChange={(e) => setTerm(e.target.value)}>
              <option value="">All terms</option>
              {terms.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <select aria-label="Filter by subject" value={subject} onChange={(e) => setSubject(e.target.value)}>
              <option value="">All subjects</option>
              {subjects.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </>
        )}
        {hasFilters && (
          <button type="button" className="linkbtn" onClick={clearFilters}>Clear</button>
        )}
      </div>

      <Loaded state={courses}>
        {(list) => {
          const query = search.trim().toLowerCase().replace(/\s+/g, ' ')
          const matching = list.filter((course) => {
            const code = `${course.subject} ${course.catalog}`.toLowerCase()
            const title = (course.title || '').toLowerCase()
            return `${code} ${title}`.includes(query)
              && (!teach || !term || course.term === term)
              && (!teach || !subject || course.subject === subject)
          })
          const teaching = matching.filter(isStaff)
          const enrolled = matching.filter((c) => !isStaff(c))
          if (!list.length) {
            return (
              <div className="card empty">
                <p>You aren&apos;t in any courses yet.</p>
                <p className="small">
                  {teach
                    ? 'Create one with “New course”.'
                    : 'Your instructor adds you from the class roster. If you have a poll code, use “Join a poll”.'}
                </p>
              </div>
            )
          }
          if (!matching.length) {
            return (
              <div className="card empty" role="status">
                <p>No courses found.</p>
                <p className="small">Try a different search or filter.</p>
                <button type="button" className="btn" onClick={clearFilters}>
                  Clear search and filters
                </button>
              </div>
            )
          }
          return (
            <>
              {teaching.length > 0 && (
                <section style={{ marginBottom: 28 }}>
                  {enrolled.length > 0 && <h2>Teaching</h2>}
                  <div className="grid">
                    {teaching.map((c) => (
                      <CourseCard key={c.id} course={c} />
                    ))}
                  </div>
                </section>
              )}
              {enrolled.length > 0 && (
                <section>
                  {teaching.length > 0 && <h2>Enrolled</h2>}
                  <div className="grid">
                    {enrolled.map((c) => (
                      <CourseCard key={c.id} course={c} />
                    ))}
                  </div>
                </section>
              )}
            </>
          )
        }}
      </Loaded>

      <Modal open={creating} onClose={() => setCreating(false)} title="New course">
        <CourseForm onSubmit={create} busy={busy} error={error} submitLabel="Create course" onCancel={() => setCreating(false)} />
      </Modal>
    </main>
  )
}
