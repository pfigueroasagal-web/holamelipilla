// sw.js — Hola Melipilla Service Worker
const CACHE_NAME = 'holamelipilla-v2';

// Archivos que se guardan para uso sin internet
const ARCHIVOS_CACHE = [
  '/',
  '/index.html',
  '/farmacias',
  '/salud',
  '/seguridad',
  '/ferias',
  '/colegios',
  '/styles.css',
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

// Activación: limpia cachés viejos
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

// Fetch: primero red, luego caché (para tener siempre datos frescos)
self.addEventListener('fetch', event => {
  // Solo manejar GET
  if (event.request.method !== 'GET') return;

  // No interceptar peticiones externas (mapas, fuentes, etc.)
  const url = new URL(event.request.url);
  if (url.origin !== location.origin) return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Guardar copia fresca en caché
        const copia = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, copia));
        return response;
      })
      .catch(() => {
        // Sin internet: servir desde caché
        return caches.match(event.request)
          .then(cached => cached || caches.match('/'));
      })
  );
});
