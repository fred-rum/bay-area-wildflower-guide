var URL_CACHE_NAME = 'url-cache-v1';
var BASE64_CACHE_NAME = 'base64-cache-v1';
var url_to_base64 = [
/* insert code here */
];

self.addEventListener('install', function(event) {
  // Perform install steps
/*
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
*/
  return 1;
});

self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // Cache hit - return response
        if (response) {
          return response;
        }
        return fetch(event.request);
      }
    )
  );
});
