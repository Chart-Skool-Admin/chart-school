/* Chart School offline support.
   The app's own files: try the network first (so updates arrive), fall back to the saved copy when offline.
   Fonts: use the saved copy, refresh it in the background.
   Everything else (live prices, sync) goes straight to the network. */
const CACHE = "chartschool-v21-desk";
/* A hanging connection never fails on its own, so give up waiting after a few seconds and use the saved copy. */
const late = ms => new Promise(r => setTimeout(() => r(null), ms));
const CORE = ["./", "./index.html", "./manifest.json", "./icon-180.png", "./icon-192.png", "./icon-512.png", "./rw-data.js", "./rw-more.js"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  if (url.origin === location.origin) {
    const saved = () => caches.match(req, { ignoreSearch: true })
      .then(hit => hit || (req.mode === "navigate" ? caches.match("./index.html") : undefined));
    const net = fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    });
    e.respondWith(
      Promise.race([net.catch(() => null), late(4000)]).then(res => res ||
        saved().then(hit => hit || net.catch(() => Response.error())))
    );
    return;
  }

  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    e.respondWith(caches.open(CACHE).then(c => c.match(req).then(hit => {
      const net = fetch(req).then(res => { if (res.ok || res.type === "opaque") c.put(req, res.clone()); return res; }).catch(() => hit);
      return hit || Promise.race([net, late(3000)]).then(res => res ||
        new Response(req.destination === "style" || /css/.test(url.pathname) ? "" : null, { status: 504 }));
    })));
  }
});
