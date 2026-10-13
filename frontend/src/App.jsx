import { useState } from 'react'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import './App.css'
import Login from './components/LoginCard/LoginCard.jsx'
import { createBrowserRouter, RouterProvider } from 'react-router'
import Home from './pages/home.jsx'
import LoginPage from './pages/LoginPage.jsx'

const router = createBrowserRouter([
  {path: '/', element: <LoginPage />},
  {path: '/Home', element: <Home />},
  
])

function App() {
  return (
    <>
      <RouterProvider router={router} />
    </>
  )
}

export default App
