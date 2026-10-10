import { MantineProvider, createTheme } from '@mantine/core'
import '@mantine/core/styles.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

const theme = createTheme({
  primaryColor: 'teal',
  fontFamily: 'system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif',
  defaultRadius: 'sm',
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="light">
      <App />
    </MantineProvider>
  </StrictMode>,
)
