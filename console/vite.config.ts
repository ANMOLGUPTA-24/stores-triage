import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Relative, so the same bundle works at the dev server root and under a
  // GitHub Pages project subpath (/stores-triage/). An absolute base would
  // 404 every asset on Pages; hardcoding the subpath would break local dev.
  base: './',
})
