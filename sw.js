/**
 * Prompt 2 Jam - Service Worker
 * Enables offline functionality and caching for PWA
 */

const CACHE_VERSION = 'v1';
const CACHE_NAME = `prompt-2-jam-${CACHE_VERSION}`;

// Assets to cache on install
const STATIC_ASSETS = [
  '/',
  '/index.html',
];

/**
 * Install event - cache static assets
 */
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching static assets');
      return cache.addAll(STATIC_ASSETS).catch(() => {
        console.log('[SW] Could not cache all static assets (ok for dynamic routes)');
      });
    })
  );
  self.skipWaiting();
});

/**
 * Activate event - clean up old caches
 */
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName.startsWith('prompt-2-jam-')) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

/**
 * Fetch event - serve from cache, fallback to network
 * Network first for API calls (music generation)
 * Cache first for static assets
 */
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }
  
  // Network first for API calls (music generation endpoints)
  if (url.pathname.includes('/api/') || url.pathname.includes('/call/')) {
    return event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Don't cache error responses
          if (!response || response.status !== 200) {
            return response;
          }
          
          // Clone and cache successful responses
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
          
          return response;
        })
        .catch(() => {
          // Return cached version if network fails
          return caches.match(event.request);
        })
    );
  }
  
  // Cache first for static assets
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      
      return fetch(event.request)
        .then((response) => {
          // Don't cache error responses
          if (!response || response.status !== 200) {
            return response;
          }
          
          // Clone and cache successful responses
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
          
          return response;
        })
        .catch(() => {
          // Offline fallback
          return new Response(
            JSON.stringify({
              error: 'Offline - no cached response available'
            }),
            {
              status: 503,
              statusText: 'Service Unavailable',
              headers: new Headers({
                'Content-Type': 'application/json'
              })
            }
          );
        });
    })
  );
});

/**
 * Background sync for music generation requests (future feature)
 */
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-music-generation') {
    console.log('[SW] Background sync triggered for music generation');
    // Implement background sync for queued generation requests
  }
});

console.log('[SW] Service worker loaded');
