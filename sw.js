// sw.js — Hola Melipilla Service Worker v8
// v8: capa de profundidad/armonía y pulido móvil (styles v12)
const CACHE_NAME = 'holamelipilla-v8';

const ARCHIVOS_CACHE = [
  '/',
  '/index.html',
  '/config.js',
  '/eventos.json',
  '/farmacias',
  '/salud',
  '/seguridad',
  '/ferias',
  '/colegios',
  '/noticias',
  '/trabajos',
  '/juegos',
  '/apoyar',
  '/sugerencias',
  '/404.html',
  '/styles.css?v=11',
  '/og-image.svg',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

self.addEventListener('install', event => {
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

// Network-first para todo lo del mismo origen
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

// ─── Notificaciones push (frontend listo) ───
// Cuando llegue un push desde un backend, esto lo muestra
self.addEventListener('push', event => {
  let data = { title: 'Hola Melipilla', body: 'Tienes un aviso nuevo.' };
  if (event.data) {
    try { data = event.data.json(); } catch(e) { data.body = event.data.text(); }
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'Hola Melipilla', {
      body: data.body || '',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      tag: data.tag || 'general',
      data: { url: data.url || '/' }
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url.indexOf(url) >= 0 && 'focus' in c) return c.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
