importScripts('./worker-policy.js');
const scope = self.registration.scope;
const version = 'v3';
const cacheName = `jinju-bus:${new URL(scope).pathname}:${version}`;
const policy = self.BusWorkerPolicy;
self.addEventListener('install', event => {
  event.waitUntil(caches.open(cacheName).then(cache => cache.addAll(policy.assets.map(path => new URL(path, scope).href))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => policy.obsolete(key, scope, version)).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || !policy.cacheable(event.request.url, scope)) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok && response.type === 'basic' && !response.redirected) {
      const copy = response.clone();
      event.waitUntil(caches.open(cacheName).then(cache => cache.put(event.request, copy)));
    }
    return response;
  }).catch(async () => (await caches.open(cacheName)).match(event.request)
    .then(cached => cached || new Response('오프라인에서 이 파일을 사용할 수 없습니다.', {status:503}))));
});
self.addEventListener('push', event => {
  event.waitUntil((async()=>{
    let data;try{data=event.data.json();}catch{return;}
    if(!data||typeof data.title!=='string'||typeof data.body!=='string')return;
    // Do not surface a delayed bus arrival after the short server delivery window.
    const expires=Date.parse(data.expiresAt);if(!Number.isFinite(expires)||expires<Date.now())return;
    await self.registration.showNotification(data.title,{body:data.body,icon:new URL('assets/icon.svg',scope).href,badge:new URL('assets/icon.svg',scope).href,tag:String(data.tag||'bus-arrival'),data:{url:scope},renotify:true});
  })());
});
self.addEventListener('notificationclick',event=>{
 event.notification.close();event.waitUntil((async()=>{const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});const client=windows.find(c=>c.url.startsWith(scope));if(client)return client.focus();return self.clients.openWindow(scope);})());
});
self.addEventListener('pushsubscriptionchange',event=>{
 event.waitUntil(self.registration.showNotification('버스 알림 수신 설정 확인',{body:'앱을 열어 저장한 알림을 수정·저장하면 수신 설정을 갱신할 수 있습니다.',tag:'bus-subscription',data:{url:scope}}));
});
