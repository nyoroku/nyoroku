/**
 * Floki Offline Module
 * Handles IndexedDB operations for products cache, sales queue, and auth.
 * Uses the 'idb' library if available, falls back to raw IndexedDB.
 */

const DB_NAME = 'floki_db';
const DB_VERSION = 2; // Bumped to force re-creation of all stores

// Initialize IndexedDB
async function initDB() {
    // Use idb wrapper if available
    if (typeof idb !== 'undefined' && idb.openDB) {
        return idb.openDB(DB_NAME, DB_VERSION, {
            upgrade(db) {
                if (!db.objectStoreNames.contains('products')) {
                    db.createObjectStore('products', { keyPath: 'id' });
                }
                if (!db.objectStoreNames.contains('pending_sales')) {
                    const store = db.createObjectStore('pending_sales', { keyPath: 'id', autoIncrement: true });
                    store.createIndex('synced', 'synced');
                }
                if (!db.objectStoreNames.contains('sync_log')) {
                    db.createObjectStore('sync_log', { keyPath: 'id', autoIncrement: true });
                }
                if (!db.objectStoreNames.contains('auth')) {
                    db.createObjectStore('auth', { keyPath: 'id' });
                }
            },
        });
    }

    // Fallback: raw IndexedDB
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('products')) {
                db.createObjectStore('products', { keyPath: 'id' });
            }
            if (!db.objectStoreNames.contains('pending_sales')) {
                const store = db.createObjectStore('pending_sales', { keyPath: 'id', autoIncrement: true });
                store.createIndex('synced', 'synced');
            }
            if (!db.objectStoreNames.contains('sync_log')) {
                db.createObjectStore('sync_log', { keyPath: 'id', autoIncrement: true });
            }
            if (!db.objectStoreNames.contains('auth')) {
                db.createObjectStore('auth', { keyPath: 'id' });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

// Detect if we're using the idb wrapper or raw IndexedDB
function isIdbWrapper(db) {
    return typeof db.getAll === 'function' && typeof db.transaction === 'function' && db.constructor.name !== 'IDBDatabase';
}

// ─── Product Cache ───

async function cacheProducts(products) {
    console.log(`[Floki Offline] Caching ${products.length} products...`);
    try {
        const db = await initDB();

        if (isIdbWrapper(db)) {
            const tx = db.transaction('products', 'readwrite');
            await tx.objectStore('products').clear();
            for (const p of products) {
                await tx.objectStore('products').put(p);
            }
            await tx.done;
        } else {
            // Raw IndexedDB
            await new Promise((resolve, reject) => {
                const tx = db.transaction('products', 'readwrite');
                const store = tx.objectStore('products');
                store.clear();
                for (const p of products) {
                    store.put(p);
                }
                tx.oncomplete = resolve;
                tx.onerror = () => reject(tx.error);
            });
        }
        console.log('[Floki Offline] Cache update complete');
    } catch (e) {
        console.error('[Floki Offline] Failed to cache products:', e);
    }
}

async function getProductsFromCache() {
    try {
        const db = await initDB();

        if (isIdbWrapper(db)) {
            const products = await db.getAll('products');
            console.log(`[Floki Offline] Retrieved ${products.length} products from IndexedDB`);
            return products;
        } else {
            // Raw IndexedDB
            return new Promise((resolve, reject) => {
                const tx = db.transaction('products', 'readonly');
                const store = tx.objectStore('products');
                const req = store.getAll();
                req.onsuccess = () => {
                    console.log(`[Floki Offline] Retrieved ${req.result.length} products from IndexedDB (raw)`);
                    resolve(req.result);
                };
                req.onerror = () => reject(req.error);
            });
        }
    } catch (e) {
        console.error('[Floki Offline] Failed to get products from IndexedDB:', e);
        return [];
    }
}

async function searchProductsOffline(query, categoryId = 'all') {
    const products = await getProductsFromCache();
    return products.filter(p => {
        let matchesQuery = true;
        if (query) {
            const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
            matchesQuery = tokens.every(token =>
                p.name.toLowerCase().includes(token) ||
                (p.barcode && p.barcode.includes(token)) ||
                (p.sku && p.sku.toLowerCase().includes(token))
            );
        }

        const matchesCategory = categoryId === 'all' || String(p.category_id) === String(categoryId);

        return matchesQuery && matchesCategory;
    });
}

// ─── Sales Queue ───

async function queueSale(saleData) {
    try {
        const db = await initDB();
        const sale = {
            ...saleData,
            timestamp: new Date().toISOString(),
            synced: false
        };

        if (isIdbWrapper(db)) {
            const id = await db.add('pending_sales', sale);
            console.log('[Floki Offline] Sale queued with ID:', id);
        } else {
            await new Promise((resolve, reject) => {
                const tx = db.transaction('pending_sales', 'readwrite');
                const req = tx.objectStore('pending_sales').add(sale);
                req.onsuccess = () => { console.log('[Floki Offline] Sale queued (raw)'); resolve(req.result); };
                req.onerror = () => reject(req.error);
            });
        }

        // Register Background Sync if available
        if ('serviceWorker' in navigator && 'SyncManager' in window) {
            const reg = await navigator.serviceWorker.ready;
            try {
                await reg.sync.register('floki-sales-sync');
            } catch (e) {
                console.warn('[Floki Offline] Background Sync registration failed');
            }
        }
    } catch (e) {
        console.error('[Floki Offline] Failed to queue sale:', e);
    }
}

async function getUnsyncedSales() {
    try {
        const db = await initDB();

        if (isIdbWrapper(db)) {
            const sales = await db.getAll('pending_sales');
            return sales.filter(s => !s.synced);
        } else {
            return new Promise((resolve, reject) => {
                const tx = db.transaction('pending_sales', 'readonly');
                const req = tx.objectStore('pending_sales').getAll();
                req.onsuccess = () => resolve((req.result || []).filter(s => !s.synced));
                req.onerror = () => reject(req.error);
            });
        }
    } catch (e) {
        console.error('[Floki Offline] Failed to get unsynced sales:', e);
        return [];
    }
}

async function markSaleSynced(id, serverResponse) {
    try {
        const db = await initDB();

        if (isIdbWrapper(db)) {
            const tx = db.transaction(['pending_sales', 'sync_log'], 'readwrite');
            const sale = await tx.objectStore('pending_sales').get(id);
            if (sale) {
                sale.synced = true;
                await tx.objectStore('pending_sales').put(sale);
                await tx.objectStore('sync_log').add({
                    sale_id: id,
                    synced_at: new Date().toISOString(),
                    response: serverResponse
                });
            }
            await tx.done;
        }
    } catch (e) {
        console.error('[Floki Offline] Failed to mark sale synced:', e);
    }
}

// ─── Export ───

window.FlokiOffline = {
    cacheProducts,
    getProductsFromCache,
    searchProductsOffline,
    queueSale,
    getUnsyncedSales,
    markSaleSynced
};

console.log('[Floki Offline] Module loaded');
