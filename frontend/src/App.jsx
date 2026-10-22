import './App.css'
import { createBrowserRouter, RouterProvider } from 'react-router'
import Home from './pages/Home.jsx'
import LoginPage from './pages/LoginPage.jsx'
import Polls from './pages/Polls.jsx'

const router = createBrowserRouter([
  {path: '/', element: <LoginPage />},
  {path: '/Home', element: <Home />},
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
