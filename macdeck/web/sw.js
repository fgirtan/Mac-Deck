// Service worker: aplicația se deschide instant (chiar dacă Mac-ul e oprit) și se actualizează singură.
var VERSION = 'macdeck-__VERSION__';
var SHELL = ['/', '/app.js', '/app.css', '/pages.js', '/glyphs.js', '/manifest.webmanifest',
  '/apple-touch-icon.png', '/icon-192.png', '/icon-512.png', '/nosleep.mp4'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function timeout(ms) { return new Promise(function (_, rej) { setTimeout(function () { rej(new Error('timeout')); }, ms); }); }

self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.indexOf('/api/') === 0 || url.pathname === '/config' || url.pathname === '/setup') return; // mereu live

  // iconițele butoanelor: din cache, actualizate în fundal
  if (url.pathname.indexOf('/icons/') === 0 || url.pathname.indexOf('/splash-') === 0) {
    e.respondWith(caches.open(VERSION).then(function (c) {
      return c.match(req).then(function (hit) {
        var net = fetch(req).then(function (r) { if (r.ok) c.put(req, r.clone()); return r; }).catch(function () { return hit; });
        return hit || net;
      });
    }));
    return;
  }

  // aplicația: întâi rețeaua (pentru actualizări), apoi cache-ul dacă Mac-ul nu răspunde
  var key = req.mode === 'navigate' ? '/' : req;
  e.respondWith(Promise.race([fetch(req), timeout(3000)]).then(function (r) {
    if (r && r.ok) { var copy = r.clone(); caches.open(VERSION).then(function (c) { c.put(key, copy); }); }
    return r;
  }).catch(function () {
    return caches.match(key).then(function (hit) { return hit || caches.match('/'); });
  }));
});
