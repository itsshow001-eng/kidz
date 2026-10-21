// 이츠쇼 ERP 서비스워커 — 인터넷이 끊겨도 앱이 열리게 합니다.
// 규칙: ① 이 사이트 파일만 다룬다(구글 시트 통신은 절대 건드리지 않음) ② 인터넷이 되면 항상 최신 파일을 먼저 받는다
//       ③ 인터넷이 안 될 때만 저장해 둔 파일을 보여 준다. 데이터(공연·고객 등)는 여기에 저장하지 않는다.
const CACHE = 'itsshow-erp-v2';
const CORE = ['./', './index.html', './manifest.webmanifest', './apple-touch-icon.png', './icon-192.png', './icon-512.png'];
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  e.respondWith(
    fetch(new Request(req.url, { cache: 'no-cache' }))
      .then((res) => {
        if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
        return res;
      })
      .catch(() => caches.match(req, { ignoreSearch: true }).then((r) => r || caches.match('./index.html')))
  );
});
