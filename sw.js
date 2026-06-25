// sw.js — Hola Melipilla Service Worker
const CACHE_NAME = 'holamelipilla-v4';

// Archivos que se guardan para uso sin internet
const ARCHIVOS_CACHE = [
  '/',
  '/index.html',
  '/farmacias',
  '/salud',
  '/seguridad',
  '/ferias',
  '/colegios',
  '/404.html',
  '/styles.css?v=2',
  '/og-image.svg',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

// Instalación: guarda archivos en caché
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(ARCHIVOS_CACHE))
      .then(() => self.skipWaiting())
  );
});

// Activación: limpia TODOS los cachés viejos y toma control inmediato
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => {
            console.log('[SW] Eliminando caché viejo:', key);
            return caches.delete(key);
          })
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch: estrategia network-first para HTML y CSS, cache-first para imágenes
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  if (url.origin !== location.origin) return;

  const esCSS = url.pathname.endsWith('.css') || url.search.includes('v=');
  const esHTML = url.pathname.endsWith('.html') || url.pathname === '/' ||
                 ['/farmacias','/salud','/seguridad','/ferias','/colegios'].includes(url.pathname);

  if (esCSS || esHTML) {
    // Network-first: siempre intenta la red primero (garantiza contenido fresco)
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const copia = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copia));
          return response;
        })
        .catch(() => caches.match(event.request).then(c => c || caches.match('/')))
    );
  } else {
    // Cache-first para imágenes y otros assets estáticos
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          const copia = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copia));
          return response;
        });
      })
    );
  }
});
