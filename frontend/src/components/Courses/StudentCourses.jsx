import { useState } from 'react';
import './StudentCourses.css';

export default function StudentCourses() {
  // fetch these courses from backend/database.
  const [courses] = useState([
    { id: 1, code: 'CSE 4939W 001', title: 'Computer Science and Engineering Design Project' },
    { id: 2, code: 'CSE 3666 002', title: 'Introduction to Computer Architecture' },
    { id: 3, code: 'CSE 4701 003', title: 'Principles of Databases' },
  ]);

  return (
    <div className="cm-page">
      <div className="cm-shell">
        {/* Header and profile initials */}
        <header className="cm-topbar">
          <span className="cm-avatar" aria-label="Profile: PR">PR</span>
        </header>

        <main className="cm-main">
          {/* Page heading */}
          <div className="cm-heading">
            <h1>Courses</h1>
          </div>

          {/* Render one card for each course */}
          <ul className="cm-list">
            {courses.map(course => (
              <li key={course.id} className="cm-card">
                <div>
                  <p className="cm-code">{course.code}</p>
                  <p className="cm-title">{course.title}</p>
                </div>
              </li>
            ))}
          </ul>

          {/* Empty state after all courses have been deleted */}
          {courses.length === 0 && (
            <p className="cm-empty">Empty.</p>
          )}
        </main>
      </div>
    </div>
  );
}