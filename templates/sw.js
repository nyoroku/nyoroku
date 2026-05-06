{% load static %}importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.4.1/workbox-sw.js');

if (workbox) {
  console.log('Workbox is loaded');

  // Precache critical assets (these MUST work offline)
  workbox.precaching.precacheAndRoute([
    { url: '/offline.html', revision: 'v2' },
    { url: '{% static "js/idb.min.js" %}', revision: 'v1' },
    { url: '{% static "js/offline.js" %}', revision: 'v5' },
  ]);

  // Cache static assets (CSS, JS, Fonts, Images) — CacheFirst
  workbox.routing.registerRoute(
    ({request}) => request.destination === 'style' ||
                   request.destination === 'script' ||
                   request.destination === 'font' ||
                   request.destination === 'image',
    new workbox.strategies.CacheFirst({
      cacheName: 'floki-assets',
    })
  );

  // POS UI Shell — NetworkFirst with Cache Fallback
  workbox.routing.registerRoute(
    ({url}) => url.pathname.startsWith('/pos/') && !url.pathname.startsWith('/pos/api/'),
    new workbox.strategies.NetworkFirst({
      cacheName: 'floki-ui-shell',
    })
  );

  // Product API — StaleWhileRevalidate (correct path)
  workbox.routing.registerRoute(
    ({url}) => url.pathname.startsWith('/pos/api/products/'),
    new workbox.strategies.StaleWhileRevalidate({
      cacheName: 'floki-product-api',
    })
  );

  // Offline Fallback — serve offline.html for any uncached navigation
  workbox.routing.setCatchHandler(async ({event}) => {
    if (event.request.destination === 'document') {
      return caches.match('/offline.html');
    }
    return Response.error();
  });

  // Background Sync for Sales
  const bgSyncPlugin = new workbox.backgroundSync.BackgroundSyncPlugin('floki-sales-sync', {
    maxRetentionTime: 24 * 60,
  });

  workbox.routing.registerRoute(
    ({url}) => url.pathname.startsWith('/pos/api/sync/') || url.pathname.startsWith('/pos/checkout/'),
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    'POST'
  );
}
