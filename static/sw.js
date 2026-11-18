// Minimal Service Worker for PWA installability
const CACHE_NAME = 'xauusd-cache-v1';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', (e) => {
  // Let network handle dynamic API/data calls
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
