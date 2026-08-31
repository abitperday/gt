import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import LiveDDU from './live/LiveDDU.tsx'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={new QueryClient()}>
    <StrictMode>
      {window.location.pathname === '/live' ? <LiveDDU /> : <App />}
    </StrictMode>
  </QueryClientProvider>
)
