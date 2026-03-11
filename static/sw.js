const CACHE_NAME = 'netra-v4';
const ASSETS_TO_CACHE = [
    '/',
    '/landing',
    '/static/js/translations.js',
    'https://cdn.tailwindcss.com',
    'https://cdn.jsdelivr.net/npm/chart.js',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
    'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
    'https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js'
];

// Routes the SW must NEVER intercept (auth-critical)
const BYPASS_ROUTES = ['/logout', '/login', '/register', '/auth/'];

function shouldBypass(url) {
    const path = new URL(url).pathname;
    return BYPASS_ROUTES.some(route => path.startsWith(route));
}

self.addEventListener('install', (event) => {
    console.log('[SW] Installing v4...');
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Caching Assets');
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

self.addEventListener('activate', (event) => {
    console.log('[SW] Activating v4...');
    event.waitUntil(
        Promise.all([
            self.clients.claim(),
            caches.keys().then((keys) => {
                return Promise.all(
                    keys.map((key) => {
                        if (key !== CACHE_NAME) {
                            console.log('[SW] Deleting old cache:', key);
                            return caches.delete(key);
                        }
                    })
                );
            })
        ])
    );
});

self.addEventListener('fetch', (event) => {
    // Only handle GET requests
    if (event.request.method !== 'GET') return;

    // CRITICAL: Never intercept auth-related routes
    if (shouldBypass(event.request.url)) {
        console.log('[SW] Bypassing auth route:', event.request.url);
        return; // Let browser handle it directly, no SW involvement
    }

    const url = new URL(event.request.url);
    const dashboardRoutes = ['/dashboard_officer', '/dashboard_admin'];

    // Network First for dashboard pages
    if (dashboardRoutes.some(route => url.pathname.startsWith(route))) {
        event.respondWith(
            fetch(event.request, { cache: 'no-store' }).then((response) => {
                // If server redirected (e.g. session expired → /login), follow the redirect
                if (response.redirected || response.status === 302 || response.status === 301) {
                    return response;
                }
                if (response.status === 200 && response.type === 'basic') {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            }).catch(() => {
                // Offline fallback — only return cached dashboard, never fake a login redirect
                return caches.match(event.request);
            })
        );
        return;
    }

    // Cache First for static assets only
    event.respondWith(
        caches.match(event.request).then((cached) => {
            if (cached) return cached;
            return fetch(event.request).then((response) => {
                if (!response || response.status !== 200 || response.type !== 'basic') {
                    return response;
                }
                const clone = response.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                return response;
            });
        })
    );
});
