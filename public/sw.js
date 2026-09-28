/* NovaeonTradingAI service worker: makes the app installable and shows a friendly page when offline.
   It never caches bot data (/api), so everything you see is always live. */
const OFFLINE_CACHE = 'nova-offline-v2';
const OFFLINE_URL = '/offline.html';

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(OFFLINE_CACHE).then((c) => c.addAll([OFFLINE_URL, '/icon-192.png'])));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== OFFLINE_CACHE).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname === '/icon-192.png') {
    // the offline page shows this icon: network first, cached copy when offline
    event.respondWith(fetch(event.request).catch(() => caches.match('/icon-192.png')));
    return;
  }
  if (event.request.mode !== 'navigate') return; // API, assets: straight to the network
  event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE_URL)));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow('/home'));
});
