// Service Worker per PWA Kangourou Trainer
const CACHE_NAME = 'kangourou-trainer-v2.29.0';
const urlsToCache = [
  './',
  './index.html',
  './admin.html',
  './gara.html',
  './demo.html',
  './manifest.json',
  './index.json'
];

// Installazione - skipWaiting: prende subito il controllo senza aspettare
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Cache aperta');
        return cache.addAll(urlsToCache);
      })
  );
  self.skipWaiting();
});

// Attivazione - claim: controlla subito tutti i tab aperti
self.addEventListener('activate', event => {
  event.waitUntil(
    Promise.all([
      caches.keys().then(cacheNames =>
        Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== CACHE_NAME) {
              console.log('Rimuovo vecchia cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        )
      ),
      self.clients.claim()
    ])
  );
});

// Fetch - Strategia Network First, poi Cache
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Se la risposta è valida, clona e salva in cache
        if (response && response.status === 200) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // Se fetch fallisce, cerca in cache
        return caches.match(event.request);
      })
  );
});
