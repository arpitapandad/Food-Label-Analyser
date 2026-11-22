import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The frontend always calls the API with same-origin relative URLs ("/verify",
// "/claims", ...). That works identically in both modes:
//
//   * `npm run dev`  -> Vite proxies those paths to the FastAPI server on :8000
//   * `npm run build` -> FastAPI serves the built files itself, so the API is
//                        already on the same origin
//
// This avoids CORS entirely and means no environment variables to configure.
const API_TARGET = 'http://localhost:8000'
const API_PREFIXES = ['/health', '/claims', '/categories', '/dataset', '/ocr', '/verify']

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_PREFIXES.map((prefix) => [prefix, { target: API_TARGET, changeOrigin: true }]),
    ),
  },
  build: {
    // FastAPI mounts this folder at "/" (see backend/main.py).
    outDir: 'dist',
    emptyOutDir: true,
  },
})
