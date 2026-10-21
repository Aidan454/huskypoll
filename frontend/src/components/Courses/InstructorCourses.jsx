import { useRef, useState } from 'react';
import {useNavigate} from 'react-router';
import './InstructorCourses.css';

export default function InstructorCourses() {
  // fetch these courses from backend/database.
  const [courses, setCourses] = useState([
    { id: 1, code: 'CSE 4939W 001', title: 'Computer Science and Engineering Design Project' },
    { id: 2, code: 'CSE 3666 002', title: 'Introduction to Computer Architecture' },
    { id: 3, code: 'CSE 4701 003', title: 'Principles of Databases' },
    ]);
  // The ID of the course whose options menu is open.
  const [openMenuId, setOpenMenuId] = useState(null);
  const [editingCourse, setEditingCourse] = useState(null);
  const dialogRef = useRef(null);
  const formRef = useRef(null);
  const createButtonRef = useRef(null);
  const navigate = useNavigate();

  // Close any open course options menu.
  function closeMenu() {
    setOpenMenuId(null);
  }

  // Toggle the options menu for the selected course.
  function toggleMenu(event, courseId) {
    // Prevent the page's onClick handler from immediately closing the menu.
    event.stopPropagation();
    setOpenMenuId(currentId => {
      return currentId === courseId ? null : courseId;
    });
  }
  // Open the form for either creating or editing a course.
  function openEditor(course = null) {
    setEditingCourse(course);
    closeMenu();
    formRef.current.elements.code.value = course?.code ?? '';
    formRef.current.elements.title.value = course?.title ?? '';
    // Open the native HTML dialog as a modal.
    dialogRef.current.showModal();
  }
  function closeEditor() {
    dialogRef.current.close();
  }

  // Handle both new course creation and existing course updates.
  function saveCourse(event) {
    event.preventDefault();

    // Read inputs using their "name" attributes.
    const formData = new FormData(event.currentTarget);
    const code = formData.get('code').trim();
    const title = formData.get('title').trim();

    if (editingCourse) {
      // Replace the selected course while keeping the others.
      setCourses(currentCourses =>
        currentCourses.map(course => {
          if (course.id === editingCourse.id) {
            return { ...course, code, title };
          }

          return course;
        })
      );} 
    else {
      // Append a new course -- does not modify the existing array.
      const newCourse = {id: Date.now(), code, title};
      setCourses(currentCourses => [...currentCourses, newCourse]);
    }
    closeEditor();
  }

  function deleteCourse(courseId) {
    // Keep every course except the one selected for deletion.
    setCourses(currentCourses =>
      currentCourses.filter(course => course.id !== courseId)
    );
    closeMenu();
    createButtonRef.current.focus();
  }

  return (
    // Clicking elsewhere on the page closes an open options menu.
    <div className="cm-page" onClick={closeMenu}>
      <div className="cm-shell">
        {/* Header and profile initials */}
        <header className="cm-topbar">
          <span className="cm-avatar" aria-label="Profile: PR">PR</span>
        </header>

        <main className="cm-main">
          {/* Page heading and create button */}
          <div className="cm-heading">
            <h1>Courses</h1>

            <button ref={createButtonRef} type="button" className="cm-primary" onClick={() => openEditor()}>Create Course</button>
          </div>

          {/* Render one card for each course */}
          <ul>
            {courses.map(course => (       
              <div className="cm-card">
                <button key={course.id} className="cm-link" onClick={() => navigate('/Polls')}>   
                  <div>
                    <p className="cm-code">{course.code}</p>
                    <p className="cm-title">{course.title}</p>
                  </div>
                </button>
                  {/* Three-dot options button */}
                <button //overlay element
                  type="button" className="cm-more" aria-label={`Options for ${course.code}`} aria-expanded={openMenuId === course.id}
                  onClick={event => toggleMenu(event, course.id)} onKeyDown={event => {
                    if (event.key === 'Escape') {closeMenu()};
                  }}>⋯</button>
                {/* Only show the menu for the selected course */}
                {openMenuId === course.id && (
                  <div className="cm-menu">
                    <button type="button" onClick={() => openEditor(course)}>Edit course</button>
                    <button type="button" className="cm-delete" onClick={() => deleteCourse(course.id)}>Delete course</button>
                  </div>
                )}
              </div>
            ))}
          </ul>

          {/* Empty state after all courses have been deleted */}
          {courses.length === 0 && (
            <p className="cm-empty">Empty.</p>
          )}
        </main>
      </div>

      {/* Shared modal for creating and editing courses */}
      <dialog ref={dialogRef} className="cm-dialog" aria-labelledby="cm-dialog-title">
        <form ref={formRef} onSubmit={saveCourse}>
          <h2 id="cm-dialog-title">{editingCourse ? 'Edit Course' : 'Create Course'}</h2>
          <label>Course code<input name="code" placeholder="Course Title" required autoFocus maxLength={60}/></label>

          <label>Course title<input name="title" placeholder="Course Code" required maxLength={200}/></label>

          <div className="cm-actions">
            <button type="button" className="cm-cancel" onClick={closeEditor}>Cancel</button>
            <button type="submit" className="cm-primary">{editingCourse ? 'Save Changes' : 'Create Course'}</button>
          </div>
        </form>
      </dialog>
    </div>
  );
}