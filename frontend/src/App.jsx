import { createBrowserRouter, Link, Navigate, Outlet, RouterProvider } from 'react-router'
import { AuthProvider, RequireLogin } from './components/AuthProvider.jsx'
import Layout from './components/Layout.jsx'
import { BASE_PATH } from './config.js'
import BankPage from './pages/BankPage.jsx'
import BanksPage from './pages/BanksPage.jsx'
import ActivityTab from './pages/course/ActivityTab.jsx'
import CourseHome from './pages/course/CourseHome.jsx'
import CourseLayout from './pages/course/CourseLayout.jsx'
import GradesTab from './pages/course/GradesTab.jsx'
import LecturesTab from './pages/course/LecturesTab.jsx'
import RosterTab from './pages/course/RosterTab.jsx'
import SettingsTab from './pages/course/SettingsTab.jsx'
import StaffTab from './pages/course/StaffTab.jsx'
import CoursesPage from './pages/CoursesPage.jsx'
import JoinPage from './pages/JoinPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import PollPage from './pages/PollPage.jsx'
import UsersPage from './pages/UsersPage.jsx'

function NotFound() {
  return (
    <main className="page">
      <h1>Page not found</h1>
      <Link to="/courses">Go to your courses</Link>
    </main>
  )
}

function Root() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}

const router = createBrowserRouter(
  [
    {
      element: <Root />,
      children: [
        { path: '/login', element: <LoginPage /> },
        {
          element: (
            <RequireLogin>
              <Layout />
            </RequireLogin>
          ),
          children: [
            { path: '/', element: <Navigate to="/courses" replace /> },
            { path: '/courses', element: <CoursesPage /> },
            {
              path: '/courses/:courseId',
              element: <CourseLayout />,
              children: [
                { index: true, element: <CourseHome /> },
                { path: 'lectures', element: <LecturesTab /> },
                { path: 'roster', element: <RosterTab /> },
                { path: 'staff', element: <StaffTab /> },
                { path: 'grades', element: <GradesTab /> },
                { path: 'activity', element: <ActivityTab /> },
                { path: 'settings', element: <SettingsTab /> },
              ],
            },
            { path: '/polls/:pollId', element: <PollPage /> },
            { path: '/join', element: <JoinPage /> },
            { path: '/join/:code', element: <JoinPage /> },
            { path: '/banks', element: <BanksPage /> },
            { path: '/banks/:bankId', element: <BankPage /> },
            { path: '/admin/users', element: <UsersPage /> },
            { path: '*', element: <NotFound /> },
          ],
        },
      ],
    },
  ],
  { basename: BASE_PATH || undefined },
)

export default function App() {
  return <RouterProvider router={router} />
}
