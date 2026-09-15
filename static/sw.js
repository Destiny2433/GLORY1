// Simple service worker for admin notifications
// Does not cache to avoid intercepting authenticated requests

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  self.clients.claim();
});

self.addEventListener('push', event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (error) {
    data = { body: 'There is a new Glory Concert update.' };
  }
  event.waitUntil(self.registration.showNotification(data.title || 'GLORY update', { body: data.body || 'There is a new Glory Concert update.', icon: '/static/images/logo.png', badge: '/static/images/logo.png', data: { url: data.url || '/' } }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url || '/'));
});
