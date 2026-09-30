// Telefona "uygulama" olarak eklenebilmesi için basit servis çalışanı. Veriler her zaman sunucudan gelir.
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());
self.addEventListener('fetch', () => {});
