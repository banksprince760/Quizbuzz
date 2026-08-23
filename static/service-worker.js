const CACHE_NAME = "quizbuzz-v1";

const FILES = [
    "/",
    "/static/style.css",
    "/static/manifest.json"
];

self.addEventListener("install", function(event) {

    event.waitUntil(

        caches.open(CACHE_NAME).then(function(cache) {

            return cache.addAll(FILES);

        })

    );

});

self.addEventListener("fetch", function(event) {

    event.respondWith(

        fetch(event.request).catch(function() {

            return caches.match(event.request);

        })

    );

});

self.addEventListener("activate", function(event) {

    event.waitUntil(

        caches.keys().then(function(keys) {

            return Promise.all(

                keys.map(function(key) {

                    if (key !== CACHE_NAME) {

                        return caches.delete(key);

                    }

                })

            );

        })

    );

});
