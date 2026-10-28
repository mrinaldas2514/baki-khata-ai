/*
 * Baki Khata's service worker: the app opens without internet (an installable PWA).
 *
 * Built by vite.config.ts (serviceWorker plugin), which fills in PRECACHE with every file of
 * the build and VERSION with a hash of that list, so each new build is a new service worker
 * that replaces the old one by itself.
 *
 * - The app's own files are kept on the phone (precached at install) and served from there:
 *   the app opens at once, with good, weak or no internet.
 * - Requests to other origins (the API) are never touched or cached: answers with customers'
 *   names and money stay out of the cache (the API also says Cache-Control: no-store).
 *   Entries written offline wait in IndexedDB instead (src/offline/queue.ts).
 */
const VERSION = '__VERSION__'
const CACHE = `baki-khata-${VERSION}`
const PRECACHE = self.__PRECACHE__
// The app's script and styles are requested with an Origin header (Vite marks them crossorigin)
// and servers may answer "Vary: Origin"; the files kept at install were fetched without one.
// They are the same files (hashed names), so the Vary header is ignored when looking them up.
const MATCH = { ignoreVary: true }

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k.startsWith('baki-khata-') && k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return

  if (request.mode === 'navigate') {
    // The app is one page (it routes by #hash): always its kept index.html.
    event.respondWith(caches.match('/index.html', MATCH).then((cached) => cached || fetch(request)))
    return
  }
  event.respondWith(
    caches.match(request, MATCH).then(
      (cached) =>
        cached ||
        fetch(request).then((response) => {
          // A file not kept at install (e.g. a font format this browser picked): keep it now.
          if (response.ok && url.pathname.startsWith('/assets/')) {
            const copy = response.clone()
            caches.open(CACHE).then((cache) => cache.put(request, copy))
          }
          return response
        }),
    ),
  )
})
