const CACHE_NAME = "bd-editorials-v3";
const APP_SHELL = [
  "./",
  "./index.html",
  "./css/styles.css",
  "./js/app.js",
  "./manifest.webmanifest",
  "./assets/icon.svg",
  "./assets/logos/prothom-alo.svg",
  "./assets/logos/kaler-kantho.svg",
  "./assets/logos/jugantor.svg",
  "./assets/logos/samakal.svg",
  "./assets/logos/ittefaq.svg",
  "./assets/logos/bd-pratidin.svg",
  "./assets/logos/naya-diganta.svg",
  "./assets/logos/manabzamin.svg",
  "./assets/logos/janakantha.svg",
  "./assets/logos/amader-shomoy.svg",
  "./assets/logos/dhaka-post.svg",
  "./assets/logos/bonik-barta.svg",
  "./assets/logos/sangbad.svg",
  "./assets/logos/inqilab.svg",
  "./assets/logos/jago-news-24.svg",
  "./assets/logos/bangla-tribune.svg",
  "./assets/logos/bdnews24-bn.svg",
  "./assets/logos/daily-star.svg",
  "./assets/logos/dhaka-tribune.svg",
  "./assets/logos/new-age.svg",
  "./assets/logos/tbs.svg",
  "./assets/logos/financial-express.svg",
  "./assets/logos/daily-sun.svg",
  "./assets/logos/the-independent.svg",
  "./assets/logos/daily-observer.svg",
  "./assets/logos/bdnews24-en.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.pathname.endsWith(".json") || url.pathname.endsWith(".xml")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const networkFetch = fetch(request)
        .then((response) => {
          if (response.ok && url.origin === self.location.origin) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => cached);
      return cached || networkFetch;
    })
  );
});
