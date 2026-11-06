import { createContext, useContext, useState } from 'react';

const CoursesContext = createContext(null);

// Temporary seed data until the backend exposes a courses API.
const INITIAL_COURSES = [
  {
    id: 1,
    name: 'CSE4939W-001',
    description:
      'Computer Science and Engineering Design Project. Capstone team project covering requirements, design, implementation, testing, and presentation.',
    students: [
      {
        id: 's-1-1',
        firstName: 'Chloe',
        lastName: 'Baker',
        netId: 'cb23028',
        studentId: '3000028',
        email: 'chloe.baker@uconn.edu',
        section: '001',
      },
      {
        id: 's-1-2',
        firstName: 'Owen',
        lastName: 'Baker',
        netId: 'ob23017',
        studentId: '3000017',
        email: 'owen.baker@uconn.edu',
        section: '001',
      },
      {
        id: 's-1-3',
        firstName: 'Jack',
        lastName: 'Brown',
        netId: 'jb23015',
        studentId: '3000015',
        email: 'jack.brown@uconn.edu',
        section: '001',
      },
      {
        id: 's-1-4',
        firstName: 'Sofia',
        lastName: 'Brown',
        netId: 'sb23026',
        studentId: '3000026',
        email: 'sofia.brown@uconn.edu',
        section: '001',
      },
    ],
  },
  {
    id: 2,
    name: 'CSE3666-002',
    description:
      'Introduction to Computer Architecture. Instruction sets, pipelining, memory hierarchy, and performance analysis.',
    students: [
      {
        id: 's-2-1',
        firstName: 'Maya',
        lastName: 'Patel',
        netId: 'mp23031',
        studentId: '3000031',
        email: 'maya.patel@uconn.edu',
        section: '002',
      },
      {
        id: 's-2-2',
        firstName: 'Ethan',
        lastName: 'Nguyen',
        netId: 'en23042',
        studentId: '3000042',
        email: 'ethan.nguyen@uconn.edu',
        section: '002',
      },
      {
        id: 's-2-3',
        firstName: 'Priya',
        lastName: 'Shah',
        netId: 'ps23055',
        studentId: '3000055',
        email: 'priya.shah@uconn.edu',
        section: '002',
      },
    ],
  },
  {
    id: 3,
    name: 'CSE4701-003',
    description:
      'Principles of Databases. Relational modeling, SQL, transactions, indexing, and database application development.',
    students: [
      {
        id: 's-3-1',
        firstName: 'Liam',
        lastName: 'Martinez',
        netId: 'lm23063',
        studentId: '3000063',
        email: 'liam.martinez@uconn.edu',
        section: '003',
      },
      {
        id: 's-3-2',
        firstName: 'Ava',
        lastName: 'Thompson',
        netId: 'at23074',
        studentId: '3000074',
        email: 'ava.thompson@uconn.edu',
        section: '003',
      },
    ],
  },
];

export function CoursesProvider({ children }) {
  const [courses, setCourses] = useState(INITIAL_COURSES);

  function addCourse(course) {
    const newCourse = { ...course, id: Date.now() };
    setCourses(currentCourses => [...currentCourses, newCourse]);
    return newCourse;
  }

  function updateCourse(courseId, changes) {
    setCourses(currentCourses =>
      currentCourses.map(course => (course.id === courseId ? { ...course, ...changes } : course))
    );
  }

  function deleteCourse(courseId) {
    setCourses(currentCourses => currentCourses.filter(course => course.id !== courseId));
  }

  return (
    <CoursesContext.Provider value={{ courses, addCourse, updateCourse, deleteCourse }}>
      {children}
    </CoursesContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCourses() {
  const context = useContext(CoursesContext);

  if (!context) {
    throw new Error('useCourses must be used inside a CoursesProvider');
  }

  return context;
}
