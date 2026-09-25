// STV Novel Studio - High Performance PWA Service Worker (Grok-like Instant Cache-First)
const CACHE_NAME = 'stv-novel-pwa-v3';
const STATIC_ASSETS = [
    '/',
    '/manifest.json',
    '/icon.png'
];

// 1. Install Event: Cache App Shell immediately and skip waiting
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// 2. Activate Event: Clean up old caches and claim all clients instantly
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// 3. Fetch Event: Instant App Shell Loading (Cache-First with Background Revalidation)
self.addEventListener('fetch', (event) => {
    const req = event.request;
    if (req.method !== 'GET') return;

    const url = new URL(req.url);

    // [RULE 1] Navigation & App Shell (/) - INSTANT LAUNCH (< 5ms)
    // Always serve from cache first so the app opens instantly on iPhone Home Screen like Grok
    if (req.mode === 'navigate' || url.pathname === '/' || req.headers.get('accept')?.includes('text/html')) {
        event.respondWith(
            caches.match('/').then((cachedResponse) => {
                // Background update: Revalidate app shell in the background without blocking UI
                const networkFetch = fetch(req).then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const copy = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put('/', copy));
                    }
                    return networkResponse;
                }).catch(() => {
                    // Offline or server sleeping, perfectly fine
                });

                // Return instant cached shell if available, otherwise wait for network
                return cachedResponse || networkFetch;
            })
        );
        return;
    }

    // [RULE 2] Static Assets (/icon.png, /manifest.json) - Cache First
    if (STATIC_ASSETS.includes(url.pathname)) {
        event.respondWith(
            caches.match(req).then((cached) => {
                if (cached) return cached;
                return fetch(req).then((response) => {
                    if (response && response.status === 200) {
                        const copy = response.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
                    }
                    return response;
                });
            })
        );
        return;
    }

    // [RULE 3] API Requests (/api/...) - Network First with Graceful Fallback
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(req).catch(() => {
                // Return offline JSON message instead of letting browser hang
                return new Response(JSON.stringify({
                    error: "offline",
                    message: "Đang ở chế độ ngoại tuyến hoặc máy chủ đang khởi động lại."
                }), {
                    headers: { 'Content-Type': 'application/json' }
                });
            })
        );
        return;
    }

    // Default fallback: Try network, then cache
    event.respondWith(
        fetch(req).catch(() => caches.match(req))
    );
});
