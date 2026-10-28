/// <reference types="vitest/config" />
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync } from 'node:fs'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { type Plugin, defineConfig } from 'vite'

/**
 * Writes dist/sw.js from pwa/sw.js with the list of every file the app needs (to keep on the
 * phone) and a version made from that list, so each build gets a new service worker.
 * Only .woff2 fonts are listed (every browser that has service workers reads them).
 */
function serviceWorker(): Plugin {
  return {
    name: 'baki-khata-service-worker',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const publicFiles = readdirSync('public', { recursive: true, withFileTypes: true })
        .filter((entry) => entry.isFile())
        .map((entry) => `${entry.parentPath.replace(/^public/, '')}/${entry.name}`.replace(/\\/g, '/'))
      const built = Object.keys(bundle).filter((file) => !file.endsWith('.woff') && !file.endsWith('.map'))
      const files = [...new Set(['/index.html', ...built.map((file) => `/${file}`), ...publicFiles])].sort()
      const version = createHash('sha256').update(files.join('\n')).digest('hex').slice(0, 12)
      const source = readFileSync('pwa/sw.js', 'utf8')
        .replace('self.__PRECACHE__', JSON.stringify(files))
        .replace('__VERSION__', version)
      this.emitFile({ type: 'asset', fileName: 'sw.js', source })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), serviceWorker()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
