const DB_NAME = 'floki_db';
const DB_VERSION = 1;

// Initialize IndexedDB
async function initDB() {
    return idb.openDB(DB_NAME, DB_VERSION, {
        upgrade(db) {
            // Product Cache
            if (!db.objectStoreNames.contains('products')) {
                db.createObjectStore('products', { keyPath: 'id' });
            }
            // Pending Sales
            if (!db.objectStoreNames.contains('pending_sales')) {
                const store = db.createObjectStore('pending_sales', { keyPath: 'id', autoIncrement: true });
                store.createIndex('synced', 'synced');
            }
            // Sync Log
            if (!db.objectStoreNames.contains('sync_log')) {
                db.createObjectStore('sync_log', { keyPath: 'id', autoIncrement: true });
            }
            // Offline Auth
            if (!db.objectStoreNames.contains('auth')) {
                db.createObjectStore('auth', { keyPath: 'id' });
            }
        },
    });
}

// Product Cache Logic
async function cacheProducts(products) {
    console.log(`Caching ${products.length} products...`);
    const db = await initDB();
    const tx = db.transaction('products', 'readwrite');
    await tx.objectStore('products').clear();
    for (const p of products) {
        await tx.objectStore('products').put(p);
    }
    await tx.done;
    console.log('Cache update complete');
}

async function getProductsFromCache() {
    try {
        const db = await initDB();
        const products = await db.getAll('products');
        console.log(`Retrieved ${products.length} products from IndexedDB`);
        return products;
    } catch (e) {
        console.error('Failed to get products from IndexedDB:', e);
        return [];
    }
}

async function searchProductsOffline(query, categoryId = 'all') {
    const products = await getProductsFromCache();
    return products.filter(p => {
        const matchesQuery = !query || 
            p.name.toLowerCase().includes(query.toLowerCase()) ||
            (p.barcode && p.barcode.includes(query)) ||
            (p.sku && p.sku.toLowerCase().includes(query.toLowerCase()));
        
        const matchesCategory = categoryId === 'all' || String(p.category_id) === String(categoryId);
        
        return matchesQuery && matchesCategory;
    });
}

// Sales Queue Logic
async function queueSale(saleData) {
    const db = await initDB();
    const sale = {
        ...saleData,
        timestamp: new Date().toISOString(),
        synced: false
    };
    const id = await db.add('pending_sales', sale);
    
    // Register Background Sync if available
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
        const reg = await navigator.serviceWorker.ready;
        try {
            await reg.sync.register('floki-sales-sync');
        } catch (e) {
            console.warn('Background Sync registration failed, falling back to manual trigger');
        }
    }
    
    return id;
}

async function getUnsyncedSales() {
    const db = await initDB();
    const sales = await db.getAll('pending_sales');
    return sales.filter(s => !s.synced);
}

async function markSaleSynced(id, serverResponse) {
    const db = await initDB();
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

// Global Exports
window.FlokiOffline = {
    cacheProducts,
    getProductsFromCache,
    searchProductsOffline,
    queueSale,
    getUnsyncedSales,
    markSaleSynced
};
