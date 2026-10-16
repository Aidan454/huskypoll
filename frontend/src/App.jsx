import { useState } from 'react'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import './App.css'
import Login from './components/LoginCard/LoginCard.jsx'
import { createBrowserRouter, RouterProvider } from 'react-router'
import InstructorHome from './pages/InstructorHome.jsx'
import StudentHome from './pages/StudentHome.jsx'
import LoginPage from './pages/LoginPage.jsx'
import Polls from './pages/Polls.jsx'

const router = createBrowserRouter([
  {path: '/', element: <LoginPage />},
  {path: '/InstructorHome', element: <InstructorHome />},
  {path: '/StudentHome', element: <StudentHome />},
  {path: '/Polls', element: <Polls />},
  
])

function App() {
  return (
    <>
      <RouterProvider router={router} />
    </>
  )
}

export default App
