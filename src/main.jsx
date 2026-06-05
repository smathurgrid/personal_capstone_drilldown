// main.jsx
// This is the entry point. It finds the <div id="root"> in index.html
// and renders your React app inside it. You rarely need to edit this file.

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
)
