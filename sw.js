// sw.js — Service Worker for Blank PWA
// Handles Web Push notification display and notification click routing.

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('push', event => {
  if (!event.data) return;
  let data = {};
  try { data = event.data.json(); } catch { data = { title: event.data.text() }; }

  const title = data.title || 'Blank';
  const opts  = {
    body:      data.body || 'New picks are available.',
    tag:       data.tag  || 'blank-notification',
    renotify:  true,
    icon:      'icon-192.png',
    badge:     'icon-192.png',
    data:      { url: data.url || self.registration.scope },
  };
  event.waitUntil(self.registration.showNotification(title, opts));
});

// Open the app when a notification is clicked
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data?.url || self.registration.scope;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
      for (const client of clients) {
        if (client.url.startsWith(self.registration.scope) && 'focus' in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
