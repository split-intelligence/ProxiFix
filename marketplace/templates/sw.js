const CACHE_NAME = 'handigo-pwa-v2';
const PRECACHE_URLS = [
  '/',
  '/static/marketplace/css/app.css',
  '/static/marketplace/images/handigo-logo.png',
  '/static/marketplace/images/proxifix-logo.png',
  '/static/marketplace/manifest.json',
  '/static/marketplace/offline.html'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('push', event => {
  if (!event.data) return;
  
  let payload = {};
  try {
    payload = event.data.json();
  } catch (e) {
    payload = { title: 'ProxiFix Notification', body: event.data.text() };
  }

  const options = {
    badge: '/static/marketplace/images/handigo-logo.png',
    icon: '/static/marketplace/images/handigo-logo.png',
    title: payload.title || 'ProxiFix',
    body: payload.body || 'You have a new notification',
    data: { url: payload.url || '/' },
  };

  event.waitUntil(self.registration.showNotification(options.title, options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(clientList => {
      for (let client of clientList) {
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const requestURL = new URL(event.request.url);

  // Navigation requests: try network first, fall back to offline page
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Put a copy in the cache for offline use
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match('/static/marketplace/offline.html'))
    );
    return;
  }

  // For same-origin resources, respond with cache-first then network, and cache new responses
  if (requestURL.origin === location.origin) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(resp => {
          if (!resp || resp.status !== 200) return resp;
          const respClone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, respClone));
          return resp;
        }).catch(() => {
          // optional: could return a fallback image for images here
        });
      })
    );
  }
});
