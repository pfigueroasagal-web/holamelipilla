// sw.js — Hola Melipilla Service Worker v5
// IMPORTANTE: Cambiar CACHE_NAME fuerza al navegador a descartar TODOS los caches viejos
const CACHE_NAME = 'holamelipilla-v5';

const ARCHIVOS_CACHE = [
  '/',
  '/index.html',
  '/farmacias',
  '/salud',
  '/seguridad',
  '/ferias',
  '/colegios',
  '/404.html',
  '/styles.css?v=3',
  '/og-image.svg',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

self.addEventListener('install', event => {
  // skipWaiting fuerza activación inmediata sin esperar que se cierren tabs viejas
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(ARCHIVOS_CACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

// Network-first para TODO: siempre intenta la red, cae a caché solo si no hay red
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== location.origin) return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        const copia = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, copia));
        return response;
      })
      .catch(() =>
        caches.match(event.request).then(cached => cached || caches.match('/'))
      )
  );
});
