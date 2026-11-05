import { useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { useCourses } from '../../context/CoursesContext.jsx';
import './CourseEditor.css';

const HEADER_ALIASES = new Map([
  ['last name', 'lastName'],
  ['first name', 'firstName'],
  ['name', 'name'],
  ['username', 'netId'],
  ['netid', 'netId'],
  ['net id', 'netId'],
  ['student id', 'studentId'],
  ['id', 'studentId'],
  ['email address', 'email'],
  ['e mail address', 'email'],
  ['email', 'email'],
  ['section', 'section'],
]);

const NETID_PATTERN = /^[a-z]{3}\d{5}$/;
const STUDENT_ID_PATTERN = /^\d{7,9}$/;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function makeStudentId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `student-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function normalizeHeader(value) {
  return value
    .replace(/^\uFEFF/, '')
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ');
}

// Split CSV text into rows, honouring quoted fields and quoted commas.
function parseCsvRows(text) {
  const rows = [];
  let row = [];
  let field = '';
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];

    if (inQuotes) {
      if (character === '"') {
        if (text[index + 1] === '"') {
          field += '"';
          index += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += character;
      }
    } else if (character === '"') {
      inQuotes = true;
    } else if (character === ',') {
      row.push(field);
      field = '';
    } else if (character === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else if (character !== '\r') {
      field += character;
    }
  }

  if (field !== '' || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  return rows.filter(cells => cells.some(cell => cell.trim() !== ''));
}

function findHeaderRow(rows) {
  const limit = Math.min(rows.length, 20);

  for (let index = 0; index < limit; index += 1) {
    const map = {};

    rows[index].forEach((cell, cellIndex) => {
      const field = HEADER_ALIASES.get(normalizeHeader(cell));
      if (field && map[field] === undefined) {
        map[field] = cellIndex;
      }
    });

    const recognized = Object.keys(map);
    const hasIdentity =
      map.name !== undefined ||
      map.netId !== undefined ||
      map.studentId !== undefined ||
      map.email !== undefined;

    // Single-column identifier files (for example a lone NetID column) are valid too.
    if (hasIdentity && (recognized.length >= 2 || rows[index].length === 1)) {
      return { index, map };
    }
  }

  return null;
}

// Read a StudentAdmin-style export into roster entries.
function parseRosterCsv(text) {
  const rows = parseCsvRows(text);
  const header = findHeaderRow(rows);

  if (!header) {
    throw new Error(
      'Could not find a roster header row. Expected columns such as "Last Name", "First Name", "Username", "Student ID", and "Email Address".'
    );
  }

  const students = [];
  const skipped = [];
  const seen = new Set();

  for (let index = header.index + 1; index < rows.length; index += 1) {
    const row = rows[index];
    const value = field =>
      header.map[field] !== undefined ? (row[header.map[field]] ?? '').trim() : '';

    let firstName = value('firstName');
    let lastName = value('lastName');
    const fullName = value('name');

    if (!firstName && !lastName && fullName) {
      if (fullName.includes(',')) {
        const [last, first] = fullName.split(',', 2);
        lastName = last.trim();
        firstName = (first ?? '').trim();
      } else {
        const parts = fullName.split(/\s+/);
        firstName = parts.slice(0, -1).join(' ');
        lastName = parts[parts.length - 1] ?? '';
      }
    }

    let netId = value('netId').toLowerCase();
    let studentId = value('studentId');
    const email = value('email').toLowerCase();
    const section = value('section');

    if (studentId.endsWith('.0')) {
      studentId = studentId.slice(0, -2);
    }
    if (/^\d+$/.test(studentId)) {
      studentId = studentId.padStart(7, '0');
    }

    // A completely empty roster row is not an error; just skip it.
    if (!firstName && !lastName && !netId && !studentId && !email) {
      continue;
    }

    if (netId && !NETID_PATTERN.test(netId)) {
      skipped.push(`Row ${index + 1}: invalid NetID "${netId}"`);
      continue;
    }
    if (studentId && !STUDENT_ID_PATTERN.test(studentId)) {
      skipped.push(`Row ${index + 1}: invalid student ID "${studentId}"`);
      continue;
    }
    if (email && !EMAIL_PATTERN.test(email)) {
      skipped.push(`Row ${index + 1}: invalid email "${email}"`);
      continue;
    }

    const key = netId || studentId || email;
    if (!key) {
      skipped.push(`Row ${index + 1}: missing NetID, student ID, and email`);
      continue;
    }
    if (seen.has(key)) {
      skipped.push(`Row ${index + 1}: duplicate entry for "${key}"`);
      continue;
    }
    seen.add(key);

    students.push({
      id: makeStudentId(),
      firstName,
      lastName,
      netId,
      studentId,
      email,
      section,
    });
  }

  return { students, skipped };
}

function studentName(student) {
  return [student.firstName, student.lastName].filter(Boolean).join(' ') || '—';
}

export default function CourseEditor() {
  const { courseId } = useParams();
  const { courses, addCourse, updateCourse, deleteCourse } = useCourses();
  const navigate = useNavigate();

  const course = courseId ? courses.find(item => String(item.id) === String(courseId)) : null;
  const isNewCourse = !courseId;

  const [name, setName] = useState(course?.name ?? '');
  const [description, setDescription] = useState(course?.description ?? '');
  const [students, setStudents] = useState(course?.students ?? []);
  const [saveError, setSaveError] = useState('');
  const [importStatus, setImportStatus] = useState(null);
  const [addError, setAddError] = useState('');
  const [newStudent, setNewStudent] = useState({
    firstName: '',
    lastName: '',
    netId: '',
    studentId: '',
    email: '',
  });

  // An edit URL that does not match a course (for example after a page refresh).
  if (courseId && !course) {
    return (
      <div className="ce-page">
        <main className="ce-main">
          <button type="button" className="ce-back" onClick={() => navigate('/InstructorHome')}>
            ← Back to Courses
          </button>
          <h1>Course not found</h1>
          <p className="ce-empty">
            This course is no longer available. It may have been deleted, or the page was refreshed and the
            in-memory course list was reset.
          </p>
        </main>
      </div>
    );
  }

  function goBack() {
    navigate('/InstructorHome');
  }

  function saveCourse(event) {
    event.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      setSaveError('Course name is required.');
      return;
    }

    const changes = {
      name: trimmedName,
      description: description.trim(),
      students,
    };

    if (isNewCourse) {
      addCourse(changes);
    } else {
      updateCourse(course.id, changes);
    }

    goBack();
  }

  function handleDelete() {
    if (!course) {
      return;
    }

    const confirmed = window.confirm(
      `Delete "${course.name}"? This removes the course and its roster and cannot be undone.`
    );
    if (!confirmed) {
      return;
    }

    deleteCourse(course.id);
    goBack();
  }

  function handleCsvFile(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      try {
        const { students: imported, skipped } = parseRosterCsv(String(reader.result));

        if (imported.length === 0) {
          setImportStatus({
            type: 'error',
            text: skipped.length > 0 ? skipped.join(' ') : 'No students were found in that file.',
          });
          return;
        }

        setStudents(imported);
        setAddError('');
        setImportStatus({
          type: skipped.length > 0 ? 'warning' : 'success',
          text:
            `${imported.length} student${imported.length === 1 ? '' : 's'} imported.` +
            (skipped.length > 0 ? ` ${skipped.length} row(s) skipped: ${skipped.join(' ')}` : ''),
        });
      } catch (error) {
        setImportStatus({ type: 'error', text: error.message });
      }
    };

    reader.onerror = () => {
      setImportStatus({ type: 'error', text: 'Could not read that file. Please try again.' });
    };

    reader.readAsText(file);
    // Reset the input so selecting the same file again still triggers onChange.
    event.target.value = '';
  }

  function updateNewStudent(field, value) {
    setNewStudent(current => ({ ...current, [field]: value }));
    setAddError('');
  }

  function addStudent() {
    let netId = newStudent.netId.trim().toLowerCase();
    let studentId = newStudent.studentId.trim();
    const email = newStudent.email.trim().toLowerCase();
    const firstName = newStudent.firstName.trim();
    const lastName = newStudent.lastName.trim();

    if (!netId && !studentId && !email) {
      setAddError('Enter a NetID, student ID, or email address.');
      return;
    }
    if (netId && !NETID_PATTERN.test(netId)) {
      setAddError('NetID must be 3 letters followed by 5 digits (for example abc12345).');
      return;
    }
    if (studentId) {
      if (!/^\d+$/.test(studentId)) {
        setAddError('Student ID must contain digits only.');
        return;
      }
      studentId = studentId.padStart(7, '0');
      if (!STUDENT_ID_PATTERN.test(studentId)) {
        setAddError('Student ID must be 7 to 9 digits.');
        return;
      }
    }
    if (email && !EMAIL_PATTERN.test(email)) {
      setAddError('Enter a valid email address.');
      return;
    }

    const duplicate = students.some(student =>
      (netId && student.netId === netId) ||
      (studentId && student.studentId === studentId) ||
      (email && student.email === email)
    );

    if (duplicate) {
      setAddError('That student is already on the roster.');
      return;
    }

    setStudents(currentStudents => [
      ...currentStudents,
      {
        id: makeStudentId(),
        firstName,
        lastName,
        netId,
        studentId,
        email,
        section: '',
      },
    ]);
    setNewStudent({ firstName: '', lastName: '', netId: '', studentId: '', email: '' });
    setAddError('');
  }

  function handleAddKeyDown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      addStudent();
    }
  }

  function removeStudent(studentId) {
    setStudents(currentStudents => currentStudents.filter(student => student.id !== studentId));
  }

  return (
    <div className="ce-page">
      <main className="ce-main">
        <button type="button" className="ce-back" onClick={goBack}>
          ← Back to Courses
        </button>

        <div className="ce-heading">
          <h1>{isNewCourse ? 'Create Course' : 'Edit Course'}</h1>
          {!isNewCourse && <span className="ce-badge">{course.name}</span>}
        </div>

        <form className="ce-form" onSubmit={saveCourse}>
          <section className="ce-card" aria-labelledby="ce-details-title">
            <h2 id="ce-details-title">Course details</h2>

            <label className="ce-field">
              <span>Course name</span>
              <input
                name="name"
                value={name}
                onChange={event => {
                  setName(event.target.value);
                  setSaveError('');
                }}
                placeholder="e.g. CSE3666-001"
                maxLength={60}
                required
                autoFocus
              />
            </label>

            <label className="ce-field">
              <span>Description</span>
              <textarea
                name="description"
                value={description}
                onChange={event => setDescription(event.target.value)}
                placeholder="What is this course about?"
                rows={4}
                maxLength={1000}
              />
            </label>
          </section>

          <section className="ce-card" aria-labelledby="ce-roster-title">
            <div className="ce-section-heading">
              <h2 id="ce-roster-title">Roster</h2>
              <span className="ce-count">
                {students.length} student{students.length === 1 ? '' : 's'}
              </span>
            </div>

            <div className="ce-upload">
              <label className="ce-file">
                <span className="ce-file-button">Upload CSV</span>
                <input type="file" accept=".csv,text/csv" onChange={handleCsvFile} />
              </label>
              <p className="ce-hint">
                Accepts a StudentAdmin export with Last Name, First Name, Username, Student ID, and Email
                Address columns. Uploading replaces the current roster.
              </p>
            </div>

            {importStatus && (
              <p className={`ce-status ce-status-${importStatus.type}`} role="status">
                {importStatus.text}
              </p>
            )}

            {students.length > 0 ? (
              <div className="ce-table-wrap">
                <table className="ce-table">
                  <thead>
                    <tr>
                      <th scope="col">Name</th>
                      <th scope="col">NetID</th>
                      <th scope="col">Student ID</th>
                      <th scope="col">Email</th>
                      <th scope="col">
                        <span className="ce-sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {students.map(student => (
                      <tr key={student.id}>
                        <td>{studentName(student)}</td>
                        <td>{student.netId || '—'}</td>
                        <td>{student.studentId || '—'}</td>
                        <td>{student.email || '—'}</td>
                        <td className="ce-table-action">
                          <button
                            type="button"
                            className="ce-remove"
                            aria-label={`Remove ${studentName(student)} from the roster`}
                            onClick={() => removeStudent(student.id)}
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="ce-empty">No students in this roster yet. Upload a CSV or add students below.</p>
            )}

            <div className="ce-add">
              <h3>Add a student</h3>
              <div className="ce-add-grid">
                <input
                  aria-label="First name"
                  placeholder="First name"
                  value={newStudent.firstName}
                  onChange={event => updateNewStudent('firstName', event.target.value)}
                  onKeyDown={handleAddKeyDown}
                />
                <input
                  aria-label="Last name"
                  placeholder="Last name"
                  value={newStudent.lastName}
                  onChange={event => updateNewStudent('lastName', event.target.value)}
                  onKeyDown={handleAddKeyDown}
                />
                <input
                  aria-label="NetID"
                  placeholder="NetID (abc12345)"
                  value={newStudent.netId}
                  onChange={event => updateNewStudent('netId', event.target.value)}
                  onKeyDown={handleAddKeyDown}
                />
                <input
                  aria-label="Student ID"
                  placeholder="Student ID"
                  value={newStudent.studentId}
                  onChange={event => updateNewStudent('studentId', event.target.value)}
                  onKeyDown={handleAddKeyDown}
                />
                <input
                  aria-label="Email address"
                  placeholder="Email address"
                  type="email"
                  value={newStudent.email}
                  onChange={event => updateNewStudent('email', event.target.value)}
                  onKeyDown={handleAddKeyDown}
                />
                <button type="button" className="ce-secondary" onClick={addStudent}>
                  Add student
                </button>
              </div>
              <p className="ce-hint">A NetID, student ID, or email address is required.</p>
              {addError && (
                <p className="ce-status ce-status-error" role="alert">
                  {addError}
                </p>
              )}
            </div>
          </section>

          {saveError && (
            <p className="ce-status ce-status-error" role="alert">
              {saveError}
            </p>
          )}

          <div className="ce-actions">
            {!isNewCourse && (
              <button type="button" className="ce-danger" onClick={handleDelete}>
                Delete Course
              </button>
            )}
            <div className="ce-actions-right">
              <button type="button" className="ce-cancel" onClick={goBack}>
                Cancel
              </button>
              <button type="submit" className="ce-primary">
                {isNewCourse ? 'Create Course' : 'Save Changes'}
              </button>
            </div>
          </div>
        </form>
      </main>
    </div>
  );
}
