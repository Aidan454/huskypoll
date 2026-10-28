import { useOutletContext } from 'react-router'
import { isStaff } from '../../format.js'
import InstructorPolls from './InstructorPolls.jsx'
import StudentCourse from './StudentCourse.jsx'

export default function CourseHome() {
  const { course } = useOutletContext()
  return isStaff(course) ? <InstructorPolls course={course} /> : <StudentCourse course={course} />
}
