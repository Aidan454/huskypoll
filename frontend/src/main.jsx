import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { initializeTheme } from './theme.js'
import { initializeScale } from './uiScale.js'
import { pagePath } from './config.js'

initializeScale()
initializeTheme({ loginPage: window.location.pathname.replace(/\/+$/, '') === pagePath('/login') })

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
