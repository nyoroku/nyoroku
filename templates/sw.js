importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.4.1/workbox-sw.js');

if (workbox) {
  console.log('Workbox is loaded');

  // Precache static assets
  workbox.precaching.precacheAndRoute([
    // These will be populated or handled via runtime caching for now
    { url: '/pos/', revision: '1' },
    { url: '/offline.html', revision: '1' },
  ]);

  // Cache static assets (CSS, JS, Fonts)
  workbox.routing.registerRoute(
    ({request}) => request.destination === 'style' ||
                   request.destination === 'script' ||
                   request.destination === 'font' ||
                   request.destination === 'image',
    new workbox.strategies.CacheFirst({
      cacheName: 'floki-assets',
    })
  );

  // POS UI Shell - NetworkFirst with Cache Fallback
  workbox.routing.registerRoute(
    ({url}) => url.pathname.startsWith('/pos/'),
    new workbox.strategies.NetworkFirst({
      cacheName: 'floki-ui-shell',
    })
  );

  // Product API - StaleWhileRevalidate
  workbox.routing.registerRoute(
    ({url}) => url.pathname.startsWith('/api/products/'),
    new workbox.strategies.StaleWhileRevalidate({
      cacheName: 'floki-product-api',
    })
  );

  // Offline Fallback
  workbox.routing.setCatchHandler(async ({event}) => {
    if (event.request.destination === 'document') {
      return caches.match('/offline.html');
    }
    return Response.error();
  });

  // Background Sync for Sales
  const bgSyncPlugin = new workbox.backgroundSync.BackgroundSyncPlugin('floki-sales-sync', {
    maxRetentionTime: 24 * 60, // Retry for max 24 Hours
    onSync: async ({queue}) => {
      // Custom sync logic if needed, but we'll use a sync event listener for more control
      // because we need to update IndexedDB status.
    }
  });

  self.addEventListener('sync', (event) => {
    if (event.tag === 'floki-sales-sync') {
      event.waitUntil(syncSales());
    }
  });

  async function syncSales() {
    // This requires idb library inside SW. We can use importScripts or a bundled version.
    // Since we're using CDNs, let's assume we can import idb.
    importScripts('https://unpkg.com/idb/build/iife/index-min.js');
    
    const db = await idb.openDB('floki_db', 1);
    const unsynced = await db.getAllFromIndex('pending_sales', 'synced', 0); // Need an index for this
    
    if (unsynced.length === 0) return;

    const resp = await fetch('/pos/api/sync/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sales: unsynced })
    });

    if (resp.ok) {
      const result = await resp.json();
      const tx = db.transaction('pending_sales', 'readwrite');
      for (const res of result.results) {
        if (res.status === 'synced') {
           const sale = await tx.objectStore('pending_sales').get(res.offline_id);
           if (sale) {
             sale.synced = true;
             await tx.objectStore('pending_sales').put(sale);
           }
        }
      }
      await tx.done;
      
      // Notify UI
      const channel = new BroadcastChannel('floki-sync');
      channel.postMessage({ type: 'SYNC_COMPLETE' });
    }
  }

  workbox.routing.registerRoute(
    ({url}) => url.pathname.startsWith('/api/sales/') || url.pathname.startsWith('/pos/checkout/'),
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin],
    }),
    'POST'
  );
}
