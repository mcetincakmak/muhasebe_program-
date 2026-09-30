/* e-Fatura arayüzü: tek sayfa, bağımlılıksız. */
const $ = (s, k = document) => k.querySelector(s);
const $$ = (s, k = document) => [...k.querySelectorAll(s)];
const kok = $('#uygulama');
let BIRIMLER = {}, TEVKIFAT = {}, PARALAR = ['TRY'];
let MOD = 'deneme';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const para = x => Number(x || 0).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const tl = x => para(x) + ' TL';
const pb = (x, p) => para(x) + ' ' + (!p || p === 'TRY' ? 'TL' : p);
const tarihTR = t => t ? esc(String(t).split('-').reverse().join('.')) : '';
const bugun = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
const gunEkle = (t, n) => { const d = new Date(t + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const gecikmeGun = v => v ? Math.round((new Date(bugun() + 'T00:00:00Z') - new Date(v + 'T00:00:00Z')) / 86400000) : 0;
const gecikmeRozet = g => g > 0 ? `<span class="rozet HATA">${g} gün gecikti</span>` : g === 0 ? '<span class="rozet TASLAK">Bugün</span>' : `<span class="rozet">${-g} gün var</span>`;
const DURUM = { TASLAK: 'Taslak', GONDERILDI: 'Gönderildi', ONAYLANDI: 'Tamamlandı', HATA: 'Hata' };
const IDURUM = { KONTROL: 'Kontrol gerekli', ONERI: 'Onay bekliyor', BEKLIYOR: 'Fatura bekleniyor', ESLESTI: 'Faturayla eşleşti' };
const IROZET = { KONTROL: 'TASLAK', ONERI: 'TASLAK', BEKLIYOR: '', ESLESTI: 'ONAYLANDI' };
const CTUR = { musteri: 'Müşteri', tedarikci: 'Tedarikçi', ikisi: 'Müşteri + tedarikçi' };
const TIP = { EFATURA: 'e-Fatura', EARSIV: 'e-Arşiv' };
const MODAD = { deneme: 'Deneme modu – gerçek fatura kesilmez', test: 'QNB test ortamı', canli: '' };

const IK = {
  ozet: '<path d="M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-4H4zM14 4v4h6V4z"/>',
  fatura: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6M9 16h3"/>',
  gelen: '<path d="M4 13l3-8h10l3 8v6H4zM4 13h5l1 2h4l1-2h5"/>',
  cari: '<path d="M16 19v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1M9.5 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM21 19v-1a4 4 0 0 0-3-3.9M15.5 4.1a3 3 0 0 1 0 5.8"/>',
  urun: '<path d="M21 8l-9-5-9 5 9 5zM3 8v8l9 5 9-5V8M12 13v8"/>',
  ayar: '<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-2.9-1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 2.9-1.2V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0 1.2 2.9H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  arti: '<path d="M12 5v14M5 12h14"/>',
  sil: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  irs: '<path d="M3 7h11v9H3zM14 10h4l3 3v3h-7zM7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/>',
  vade: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  kasa: '<path d="M3 7h18v12H3zM3 11h18M7 15h3M16 4l-4 3-4-3"/>',
  rapor: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  yonetim: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  kamera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
};
const ik = ad => `<svg class="ik" viewBox="0 0 24 24" aria-hidden="true">${IK[ad]}</svg>`;

// ------------------------------------------------------------------ API
async function api(yol, secenek = {}) {
  const r = await fetch('/api' + yol, {
    method: secenek.method || 'GET',
    headers: secenek.body ? { 'Content-Type': 'application/json' } : {},
    body: secenek.body ? JSON.stringify(secenek.body) : undefined,
    credentials: 'same-origin',
  });
  if (r.status === 401 && !yol.startsWith('/giris') && !yol.startsWith('/kurulum')) { BEN = null; baslat(); throw new Error('Oturum kapandı, tekrar giriş yapın.'); }
  const veri = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof veri.detail === 'string' ? veri.detail : 'İşlem tamamlanamadı.');
  return veri;
}

let bildirimZaman;
function bildir(mesaj, hata = false) {
  const b = $('#bildirim');
  b.textContent = mesaj; b.className = 'goster' + (hata ? ' hata' : '');
  clearTimeout(bildirimZaman); bildirimZaman = setTimeout(() => b.className = '', hata ? 6000 : 3000);
}

async function calis(dugme, is) {
  if (dugme) dugme.disabled = true;
  try { return await is(); } catch (e) { bildir(e.message, true); } finally { if (dugme) dugme.disabled = false; }
}

// ------------------------------------------------------------------ Giriş / kurulum
let BEN = null;
const izin = ad => !!BEN && ad.split('|').some(i => BEN.izinler.includes(i));
const ROLAD = () => BEN?.roller || {};

async function baslat() {
  const d = await fetch('/api/durum').then(r => r.json());
  BIRIMLER = d.birimler; TEVKIFAT = d.tevkifat || {}; PARALAR = d.para_birimleri || ['TRY'];
  if (d.kurulum_gerekli) return girisEkrani(true);
  const r = await fetch('/api/ben', { credentials: 'same-origin' });
  if (!r.ok) return girisEkrani(false);
  BEN = await r.json();
  if (!BEN.firma) return firmaYokEkrani();
  kabuk(); modGuncelle(BEN.mod);
  if ((!location.hash || location.hash === '#/') && !izin('okuma')) location.hash = '#/irsaliyeler';
  yonlendir();
}

function girisEkrani(kurulum) {
  kok.innerHTML = `<div class="giris"><form class="panel">
    <img src="/static/icon.svg" alt="">
    <h1>${kurulum ? 'Hoş geldiniz' : 'Giriş yapın'}</h1>
    <p>${kurulum ? 'İlk firmanızı ve yönetici hesabınızı oluşturun.' : 'Kullanıcı adınız ve şifrenizle giriş yapın.'}</p>
    ${kurulum ? `<label for="unvan">Firma ünvanı</label><input id="unvan" required autocomplete="organization">
      <label for="ad" style="margin-top:12px">Adınız</label><input id="ad" autocomplete="name">` : ''}
    <label for="kadi" style="margin-top:12px">Kullanıcı adı</label>
    <input id="kadi" required autocomplete="username" autocapitalize="none" value="${kurulum ? 'yonetici' : ''}">
    <label for="sifre" style="margin-top:12px">Şifre</label>
    <input id="sifre" type="password" autocomplete="${kurulum ? 'new-password' : 'current-password'}" required minlength="${kurulum ? 8 : 1}">
    ${kurulum ? '<p class="ipucu">En az 8 karakter.</p>' : ''}
    <button class="dugme ana" style="width:100%;justify-content:center;margin-top:18px">${kurulum ? 'Başla' : 'Giriş yap'}</button>
  </form></div>`;
  $(kurulum ? '#unvan' : '#kadi').focus();
  $('form', kok).onsubmit = e => {
    e.preventDefault();
    calis(e.submitter, async () => {
      const govde = { kullanici_adi: $('#kadi').value, sifre: $('#sifre').value };
      if (kurulum) Object.assign(govde, { firma_unvan: $('#unvan').value, ad: $('#ad').value });
      await api(kurulum ? '/kurulum' : '/giris', { method: 'POST', body: govde });
      location.hash = kurulum ? '#/ayarlar' : '#/';
      baslat();
    });
  };
}

function firmaYokEkrani() {
  kok.innerHTML = `<div class="giris"><div class="panel"><h1>Firma seçilmedi</h1>
    <p>Hesabınıza bağlı etkin bir firma yok.${BEN.kullanici.sistem_yoneticisi ? ' Yönetim ekranından firma ekleyebilirsiniz.' : ' Yöneticinize başvurun.'}</p>
    <div class="dugmeler">${BEN.kullanici.sistem_yoneticisi ? '<button class="dugme ana" id="firmaEkle">Firma ekle</button>' : ''}
    <button class="dugme" id="cikisF">Çıkış yap</button></div></div></div>`;
  $('#cikisF').onclick = async () => { await api('/cikis', { method: 'POST' }); baslat(); };
  if ($('#firmaEkle')) $('#firmaEkle').onclick = () => firmaFormu(async f => { await api('/firma-sec', { method: 'POST', body: { firma_id: f.id } }); baslat(); });
}

// ------------------------------------------------------------------ Kabuk ve yönlendirme
const MENU = [
  ['#/', 'Özet', 'ozet', 'okuma'], ['#/faturalar', 'Satış faturaları', 'fatura', 'okuma'], ['#/alis', 'Alış faturaları', 'gelen', 'okuma'],
  ['#/irsaliyeler', 'İrsaliyeler', 'irs', 'irsaliye|okuma'], ['#/cariler', 'Cariler', 'cari', 'okuma'], ['#/vade', 'Vade takibi', 'vade', 'okuma'],
  ['#/hesaplar', 'Kasa ve banka', 'kasa', 'okuma'], ['#/urunler', 'Stok ve ürünler', 'urun', 'okuma|irsaliye'],
  ['#/raporlar', 'Raporlar', 'rapor', 'rapor'], ['#/ayarlar', 'Ayarlar', 'ayar', 'ayar'], ['#/yonetim', 'Yönetim', 'yonetim', 'yonetim|sistem'],
];
const gorunenMenu = () => MENU.filter(m => izin(m[3]));

function kabuk() {
  const k = BEN.kullanici, l = BEN.lisans;
  const lisansUyari = !l.gecerli ? `Lisans süresi doldu; program salt okuma modunda.`
    : l.kalan_gun <= 7 ? `${l.tur === 'deneme' ? 'Deneme sürenizin' : 'Lisansınızın'} bitmesine ${l.kalan_gun} gün kaldı.` : '';
  kok.innerHTML = `<div class="kabuk">
    <nav class="yan" aria-label="Ana menü">
      <div class="marka"><img src="/static/icon.svg" alt="">e-Fatura</div>
      ${BEN.firmalar.length > 1 ? `<select id="firmaSec" class="firma-sec" aria-label="Firma">${BEN.firmalar.map(f => `<option value="${f.id}"${f.id === BEN.firma.id ? ' selected' : ''}>${esc(f.unvan)}</option>`).join('')}</select>`
        : `<div class="firma-ad">${esc(BEN.firma.unvan)}</div>`}
      ${izin('fatura') ? `<a href="#/fatura/yeni" class="yeni">${ik('arti')}Yeni fatura</a>` : ''}
      ${izin('irsaliye') ? `<a href="#" class="yeni ikinci" data-yukle>${ik('kamera')}İrsaliye yükle</a>` : ''}
      ${gorunenMenu().map(([h, a, i]) => `<a href="${h}" data-m="${h}">${ik(i)}${a}</a>`).join('')}
      <div class="alt"><div class="mod-etiketi" id="modEtiketi" hidden></div>
      <a href="#" id="hesabim" style="margin-top:8px">${ik('cari')}${esc(k.ad || k.kullanici_adi)}</a>
      <a href="#" id="cikis">Çıkış yap</a></div>
    </nav>
    <main class="icerik"><div id="lisansUyari">${lisansUyari ? `<div class="uyari-seridi"><span>${lisansUyari}</span>${izin('sistem') ? '<a class="dugme kucuk" href="#/yonetim?s=lisans">Lisans</a>' : ''}</div>` : ''}</div><div id="sayfa"></div></main>
    <nav class="alt-menu" aria-label="Ana menü">
      ${izin('okuma') ? `<a href="#/" data-m="#/">${ik('ozet')}Özet</a><a href="#/faturalar" data-m="#/faturalar">${ik('fatura')}Faturalar</a>`
        : `<a href="#/urunler" data-m="#/urunler">${ik('urun')}Stok</a><span></span>`}
      <a href="#" class="yeni" id="yeniMenu">${ik('arti')}Yeni</a>
      <a href="#/irsaliyeler" data-m="#/irsaliye">${ik('irs')}İrsaliye</a>
      <a href="#/menu" data-m="#/menu">${ik('ayar')}Diğer</a>
    </nav></div>`;
  $('#cikis').onclick = async e => { e.preventDefault(); await api('/cikis', { method: 'POST' }); BEN = null; baslat(); };
  $('#hesabim').onclick = e => { e.preventDefault(); sifreFormu(); };
  if ($('#firmaSec')) $('#firmaSec').onchange = e => calis(null, async () => { await api('/firma-sec', { method: 'POST', body: { firma_id: +e.target.value } }); location.hash = '#/'; baslat(); });
  $$('[data-yukle]').forEach(a => a.onclick = e => { e.preventDefault(); irsaliyeYukleSec(); });
  $('#yeniMenu').onclick = e => {
    e.preventDefault();
    const secenek = [
      ['irsaliye', 'foto', `${ik('kamera')}İrsaliye fotoğrafı çek`, true], ['irsaliye', 'galeri', 'İrsaliye fotoğrafı seç (galeri)'],
      ['fatura', '#/fatura/yeni', 'Yeni satış faturası'], ['fatura', '#/fatura/yeni/iade', 'İade faturası'],
      ['alis', '#/alis/yeni', 'Alış faturası gir'], ['irsaliye', '#/irsaliye/yeni', 'İrsaliyeyi elle gir']].filter(x => izin(x[0]));
    const { p, kapat } = pencere(`<h2>Ne eklemek istiyorsunuz?</h2><div class="secenekler">
      ${secenek.map(([, s, a, ana]) => `<button class="dugme${ana ? ' ana' : ''}" data-s="${s}">${a}</button>`).join('')}
      <button class="dugme" data-kapat>Vazgeç</button></div>`);
    $$('[data-s]', p).forEach(b => b.onclick = () => {
      kapat(); const h = b.dataset.s;
      if (h === 'foto') irsaliyeYukleSec(true); else if (h === 'galeri') irsaliyeYukleSec(false); else location.hash = h;
    });
  };
}

function sifreFormu() {
  const { p, kapat } = pencere(`<form>${baslik('Şifremi değiştir', esc(BEN.kullanici.kullanici_adi) + ' – ' + esc(ROLAD()[BEN.kullanici.rol] || ''))}
    <div class="izgara">
      <div class="tam"><label for="s1">Mevcut şifre</label><input id="s1" type="password" autocomplete="current-password" required></div>
      <div class="tam"><label for="s2">Yeni şifre (en az 8 karakter)</label><input id="s2" type="password" autocomplete="new-password" minlength="8" required></div>
    </div><p class="ipucu">Şifre değişince diğer cihazlardaki oturumlarınız kapanır.</p>
    <div class="pencere-alt"><div></div><div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Değiştir</button></div></div></form>`);
  $('form', p).onsubmit = e => { e.preventDefault(); calis(e.submitter, async () => {
    await api('/sifre', { method: 'POST', body: { eski: $('#s1', p).value, yeni: $('#s2', p).value } }); kapat(); bildir('Şifreniz değişti.'); }); };
}

function modGuncelle(mod) {
  MOD = mod || MOD;
  const et = $('#modEtiketi'); if (!et) return;
  et.hidden = !MODAD[MOD]; et.textContent = MODAD[MOD];
}

const ROTALAR = [
  [/^#?\/?$/, ozetSayfa], [/^#\/faturalar$/, faturalarSayfa], [/^#\/fatura\/yeni$/, () => faturaDuzenle(null)],
  [/^#\/fatura\/(\d+)\/duzenle$/, m => faturaDuzenle(+m[1])], [/^#\/fatura\/(\d+)$/, m => faturaDetay(+m[1])],
  [/^#\/fatura\/yeni\/iade$/, () => faturaDuzenle(null, true)],
  [/^#\/alis$/, alisSayfa], [/^#\/alis\/yeni$/, alisElle], [/^#\/alis\/(\d+)$/, m => alisDetay(+m[1])],
  [/^#\/irsaliyeler(\?.*)?$/, irsaliyelerSayfa], [/^#\/irsaliye\/yeni$/, () => irsaliyeDetay(null)],
  [/^#\/irsaliye\/(\d+)$/, m => irsaliyeDetay(+m[1])], [/^#\/cariler$/, carilerSayfa], [/^#\/urunler(\?.*)?$/, urunlerSayfa],
  [/^#\/urun\/(\d+)$/, m => urunDetay(+m[1])], [/^#\/raporlar(\?.*)?$/, raporlarSayfa],
  [/^#\/cari\/(\d+)(\?.*)?$/, m => cariDetay(+m[1])], [/^#\/hesaplar$/, hesaplarSayfa], [/^#\/hesap\/(\d+)$/, m => hesapDetay(+m[1])],
  [/^#\/vade(\?.*)?$/, vadeSayfa], [/^#\/ayarlar$/, ayarlarSayfa], [/^#\/yonetim(\?.*)?$/, yonetimSayfa], [/^#\/menu$/, menuSayfa],
];
function yonlendir() {
  const h = location.hash || '#/';
  $$('[data-m]').forEach(a => {
    const m = a.dataset.m;
    a.classList.toggle('aktif', m === '#/' ? h === '#/' || h === '' : h.startsWith(m) || (m === '#/faturalar' && h.startsWith('#/fatura/') && !h.includes('yeni')) || (m === '#/cariler' && h.startsWith('#/cari/')) || (m === '#/hesaplar' && h.startsWith('#/hesap/')) || (m === '#/urunler' && h.startsWith('#/urun/')));
  });
  const s = $('#sayfa'); if (!s) return;
  for (const [re, fn] of ROTALAR) {
    const m = h.match(re);
    if (m) { window.scrollTo(0, 0); return Promise.resolve(fn(m)).catch(e => { s.innerHTML = `<div class="bos"><p>${esc(e.message)}</p><a class="dugme" href="#/">Ana sayfa</a></div>`; }); }
  }
  s.innerHTML = '<div class="bos"><p>Sayfa bulunamadı.</p><a class="dugme" href="#/">Özete dön</a></div>';
}
window.addEventListener('hashchange', yonlendir);

const sayfa = html => { $('#sayfa').innerHTML = html; return $('#sayfa'); };
const baslik = (b, alt = '', sag = '') => `<div class="baslik"><div><h1>${b}</h1>${alt ? `<p>${alt}</p>` : ''}</div>${sag ? `<div class="dugmeler">${sag}</div>` : ''}</div>`;
const rozet = d => `<span class="rozet ${d}">${DURUM[d] || d}</span>`;

// ------------------------------------------------------------------ Özet
async function ozetSayfa() {
  sayfa(baslik('Özet'));
  const o = await api('/ozet'); modGuncelle(o.mod);
  const ay = new Date(o.ay + '-01').toLocaleDateString('tr-TR', { month: 'long', year: 'numeric' });
  sayfa(`${baslik('Özet', ay)}
    ${!o.firma_tamam ? `<div class="uyari-seridi"><span>Fatura kesebilmek için önce firma bilgilerinizi girin.</span><a class="dugme kucuk" href="#/ayarlar">Ayarlara git</a></div>` : ''}
    ${o.mod === 'deneme' ? `<div class="uyari-seridi"><span>Program deneme modunda: faturalar entegratöre gönderilmez. Hazır olduğunuzda Ayarlar'dan entegratörünüzü seçin.</span></div>` : ''}
    <div class="rakamlar">
      <div class="rakam vurgu"><div class="etiket">Bu ay satış</div><div class="deger sayi">${tl(o.kesilen_toplam)}</div><div class="alt">${o.kesilen_adet} fatura</div></div>
      <div class="rakam"><div class="etiket">Bu ay alış</div><div class="deger sayi">${o.gelen_adet}</div><div class="alt ikincil sayi">${tl(o.gelen_toplam)}</div></div>
      <div class="rakam"><div class="etiket">Bekleyen</div><div class="deger sayi">${o.taslak + o.hatali}</div><div class="alt">${o.taslak} taslak${o.hatali ? `, ${o.hatali} hatalı` : ''}</div></div>
    </div>
    ${o.vade?.alacak.vadesi_gecen ? `<div class="uyari-seridi"><span>Vadesi geçmiş alacak: <strong class="sayi">${tl(o.vade.alacak.vadesi_gecen)}</strong> (${o.vade.alacak.vadesi_gecen_adet} kalem)</span><a class="dugme kucuk" href="#/vade">Vade takibi</a></div>` : ''}
    ${o.vade?.borc.vadesi_gecen ? `<div class="uyari-seridi"><span>Vadesi geçmiş borcunuz: <strong class="sayi">${tl(o.vade.borc.vadesi_gecen)}</strong> (${o.vade.borc.vadesi_gecen_adet} kalem)</span><a class="dugme kucuk" href="#/vade?y=borc">Borçları gör</a></div>` : ''}
    ${o.kritik_stok ? `<div class="uyari-seridi"><span>${o.kritik_stok} ürün kritik stok seviyesinde veya altında.</span><a class="dugme kucuk" href="#/urunler?k=1">Ürünleri gör</a></div>` : ''}
    <div class="rakamlar ucu">
      <a class="rakam" href="#/cariler"><div class="etiket">Alacaklarımız</div><div class="deger sayi">${tl(o.alacak_toplam)}</div><div class="alt">${o.alacakli_cari} cari size borçlu</div></a>
      <a class="rakam" href="#/cariler"><div class="etiket">Borçlarımız</div><div class="deger sayi">${tl(o.borc_toplam)}</div><div class="alt">${o.borclu_oldugumuz} cariye borçlusunuz</div></a>
      <a class="rakam" href="#/hesaplar"><div class="etiket">Kasa ve banka</div><div class="deger sayi${o.kasa_banka < 0 ? ' eksi' : ''}">${tl(o.kasa_banka)}</div><div class="alt">Toplam mevcut</div></a>
    </div>
    <div class="panel" style="margin-bottom:24px"><div class="baslik" style="margin-bottom:10px"><div><h2 style="margin:0">İrsaliyeler</h2>
      <p class="ipucu">${o.son_tarama ? 'Son e-fatura taraması: ' + new Date(o.son_tarama).toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' }) : 'Henüz tarama yapılmadı.'}</p></div>
      <div class="dugmeler"><button class="dugme" id="tara">Şimdi tara</button><button class="dugme ana" data-yukle2>${ik('kamera')}İrsaliye yükle</button></div></div>
      <div class="irs-ozet">${['KONTROL', 'ONERI', 'BEKLIYOR', 'ESLESTI'].map(d => `<a href="#/irsaliyeler?d=${d}" class="${d !== 'ESLESTI' && d !== 'BEKLIYOR' && (o.irsaliye[d] || 0) ? 'dikkat' : ''}"><strong class="sayi">${o.irsaliye[d] || 0}</strong><span>${IDURUM[d]}</span></a>`).join('')}</div></div>
    <h2>Son satış faturaları</h2>${faturaTablosu(o.son, 'Henüz fatura yok. İlk faturanızı kesin.')}`);
  $('[data-yukle2]').onclick = () => irsaliyeYukleSec();
  $('#tara').onclick = e => calis(e.currentTarget, async () => { const r = await api('/tarama', { method: 'POST' }); bildir(r.mesaj); ozetSayfa(); });
}

function faturaTablosu(liste, bosMesaj) {
  if (!liste.length) return `<div class="panel bos"><p>${bosMesaj}</p><a class="dugme ana" href="#/fatura/yeni">${ik('arti')}Yeni fatura</a></div>`;
  setTimeout(() => $$('tr[data-id]').forEach(tr => tr.onclick = () => location.hash = '#/fatura/' + tr.dataset.id));
  return `<div class="tablo-kap"><table class="liste"><thead><tr><th>Müşteri</th><th class="gizle-m">Fatura no</th><th class="gizle-m">Tarih</th><th>Durum</th><th class="s">Tutar</th></tr></thead><tbody>
    ${liste.map(f => `<tr class="tik" data-id="${f.id}"><td>${esc(f.cari_unvan)}<div class="ikincil">${f.fatura_turu === 'IADE' ? 'İade – ' : ''}${f.tip ? TIP[f.tip] : ''}</div></td>
      <td class="gizle-m sayi">${esc(f.fatura_no || '—')}</td><td class="gizle-m">${tarihTR(f.tarih)}</td><td>${rozet(f.durum)}</td><td class="s sayi">${pb(f.genel_toplam, f.para_birimi)}</td></tr>`).join('')}
  </tbody></table></div>`;
}

// ------------------------------------------------------------------ Faturalar
async function faturalarSayfa() {
  const s = sayfa(`${baslik('Faturalar', 'Kestiğiniz ve taslak halindeki faturalar', `<a class="dugme ana" href="#/fatura/yeni">${ik('arti')}Yeni fatura</a>`)}
    <div class="dugmeler" style="margin-bottom:14px"><input class="arama" id="ara" type="search" placeholder="Müşteri veya fatura no ara">
    <select id="durumSec" style="width:auto"><option value="">Tüm durumlar</option>${Object.entries(DURUM).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></div>
    <div id="tablo"></div>`);
  let z;
  const yukle = async () => { $('#tablo', s).innerHTML = faturaTablosu(await api(`/faturalar?q=${encodeURIComponent($('#ara').value)}&durum=${$('#durumSec').value}`), 'Aramanıza uyan fatura yok.'); };
  $('#ara').oninput = () => { clearTimeout(z); z = setTimeout(yukle, 250); };
  $('#durumSec').onchange = yukle;
  await yukle();
}

async function faturaDetay(id) {
  sayfa(baslik('Fatura'));
  const f = await api('/faturalar/' + id);
  const taslak = f.durum === 'TASLAK', hatali = f.durum === 'HATA';
  const s = sayfa(`${baslik(esc(f.cari.unvan), `${f.fatura_no ? esc(f.fatura_no) + ' – ' : ''}${tarihTR(f.tarih)}${f.tip ? ' – ' + TIP[f.tip] : ''}`,
    `${taslak ? `<a class="dugme" href="#/fatura/${id}/duzenle">Düzenle</a>` : ''}
     <a class="dugme" href="/goruntule/fatura/${id}" target="_blank" rel="noopener">Görüntüle / yazdır</a>
     ${f.fatura_no && !taslak ? `<a class="dugme" href="/api/faturalar/${id}/xml">XML indir</a>` : ''}
     ${taslak || hatali ? `<button class="dugme ana" id="gonder">${hatali ? 'Tekrar gönder' : 'Faturayı kes ve gönder'}</button>` : ''}
     ${f.durum === 'GONDERILDI' && f.tip === 'EFATURA' ? `<button class="dugme" id="sorgula">Durumu yenile</button>` : ''}
     ${['GONDERILDI', 'ONAYLANDI'].includes(f.durum) ? `<button class="dugme" id="tahsil">${f.fatura_turu === 'IADE' ? 'İade bedelini tahsil et' : 'Tahsilat al'}</button><a class="dugme" href="#/cari/${f.cari_id}">Cari hesap</a>` : ''}`)}
    <div class="panel"><div class="detay-ust">${rozet(f.durum)}<span>${esc(f.durum_aciklama || (taslak ? 'Bu fatura henüz kesilmedi. Kontrol edip gönderin.' : ''))}</span></div>
      ${!taslak ? `<p class="vade-satir">Vade: <strong>${f.vade_tarihi ? tarihTR(f.vade_tarihi) : 'Peşin'}</strong> ${f.durum !== 'HATA' ? gecikmeRozet(gecikmeGun(f.vade_tarihi || f.tarih)) : ''} <button class="dugme kucuk" id="vadeD">Vadeyi değiştir</button></p>` : f.vade_tarihi ? `<p class="ipucu">Vade: ${tarihTR(f.vade_tarihi)}</p>` : ''}
      ${f.fatura_turu === 'IADE' ? `<p class="ipucu">İade faturası – iade edilen fatura: ${f.iade_ref.map(r => esc(r.no) + ' (' + tarihTR(r.tarih) + ')').join(', ')}</p>` : ''}</div>
    <div class="panel"><div class="tablo-kap" style="border:0"><table class="liste"><thead><tr><th>Açıklama</th><th class="s">Miktar</th><th class="s gizle-m">Birim fiyat</th><th class="s gizle-m">KDV</th><th class="s">Tutar</th></tr></thead><tbody>
      ${f.satirlar.map(r => `<tr><td>${esc(r.ad)}${r.iskonto_tutar ? `<div class="ikincil">%${r.iskonto} iskonto</div>` : ''}${r.tevkifat_kod ? `<div class="ikincil">Tevkifat ${r.tevkifat_kod} – ${TEVKIFAT[r.tevkifat_kod]?.pay}/10</div>` : ''}</td><td class="s sayi">${r.miktar} ${esc(BIRIMLER[r.birim] || r.birim)}</td><td class="s sayi gizle-m">${para(r.birim_fiyat)}</td><td class="s gizle-m">%${r.kdv}</td><td class="s sayi">${para(r.matrah)}</td></tr>`).join('')}
    </tbody></table></div>
    <table class="toplamlar" style="max-width:340px;margin:16px 0 0 auto">
      <tr><td>Mal/hizmet toplamı</td><td class="sayi">${pb(f.brut_toplam, f.para_birimi)}</td></tr>
      ${f.iskonto_toplam ? `<tr><td>İskonto</td><td class="sayi">−${pb(f.iskonto_toplam, f.para_birimi)}</td></tr>` : ''}
      <tr><td>KDV</td><td class="sayi">${pb(f.kdv_toplam, f.para_birimi)}</td></tr>
      ${f.tevkifat_toplam ? `<tr><td>Tevkif edilen KDV</td><td class="sayi">−${pb(f.tevkifat_toplam, f.para_birimi)}</td></tr>` : ''}
      <tr class="genel"><td>Ödenecek</td><td class="sayi">${pb(f.genel_toplam, f.para_birimi)}</td></tr>
      ${f.para_birimi && f.para_birimi !== 'TRY' ? `<tr><td class="ipucu">TL karşılığı (kur ${f.kur})</td><td class="sayi ipucu">${tl(f.genel_toplam * f.kur)}</td></tr>` : ''}</table>
    ${f.notlar ? `<p class="ipucu">${esc(f.notlar)}</p>` : ''}</div>
    ${taslak ? `<div style="margin-top:16px"><button class="dugme tehlike" id="silF">${ik('sil')}Taslağı sil</button></div>` : ''}`);
  if ($('#gonder')) $('#gonder').onclick = e => {
    if (!confirm(MOD === 'canli' ? 'Fatura kesilip GİB\'e gönderilecek. Bu işlem geri alınamaz. Devam edilsin mi?' : 'Fatura gönderilsin mi?')) return;
    calis(e.currentTarget, async () => { const y = await api(`/faturalar/${id}/gonder`, { method: 'POST' }); bildir(`${y.fatura_no} numaralı fatura kesildi.`); })
      .then(() => faturaDetay(id));
  };
  if ($('#tahsil')) $('#tahsil').onclick = () => hareketFormu('TAHSILAT', { cari_id: f.cari_id, cari_unvan: f.cari.unvan, tutar: Math.round(f.genel_toplam * (f.kur || 1) * 100) / 100, fatura_ref: 'satis:' + id, belge_no: f.fatura_no }, () => faturaDetay(id));
  if ($('#vadeD')) $('#vadeD').onclick = () => vadeFormu(f.vade_tarihi, f.tarih, `/faturalar/${id}/vade`, () => faturaDetay(id));
  if ($('#sorgula')) $('#sorgula').onclick = e => calis(e.currentTarget, async () => { await api(`/faturalar/${id}/durum-sorgula`, { method: 'POST' }); faturaDetay(id); });
  if ($('#silF')) $('#silF').onclick = e => confirm('Taslak silinsin mi?') && calis(e.currentTarget, async () => { await api('/faturalar/' + id, { method: 'DELETE' }); bildir('Taslak silindi.'); location.hash = '#/faturalar'; });
}

// ------------------------------------------------------------------ Fatura düzenleyici
async function faturaDuzenle(id, iadeMi = false) {
  sayfa(baslik(id ? 'Taslağı düzenle' : 'Yeni fatura'));
  const [cariler, urunler, mevcut] = await Promise.all([api('/cariler'), api('/stok'), id ? api('/faturalar/' + id) : null]);
  const f = mevcut ? { cari_id: mevcut.cari_id, tarih: mevcut.tarih, vade_tarihi: mevcut.vade_tarihi || '', notlar: mevcut.notlar, senaryo: mevcut.senaryo, satirlar: mevcut.satirlar, fatura_turu: mevcut.fatura_turu, iade_ref: mevcut.iade_ref, para_birimi: mevcut.para_birimi || 'TRY', kur: mevcut.kur }
    : { cari_id: null, tarih: bugun(), vade_tarihi: '', notlar: '', senaryo: 'TEMELFATURA', fatura_turu: iadeMi ? 'IADE' : 'SATIS', iade_ref: [], para_birimi: 'TRY', kur: '', satirlar: [{ ad: '', miktar: 1, birim: 'C62', birim_fiyat: '', kdv: 20, iskonto: 0 }] };
  const ref = (f.iade_ref && f.iade_ref[0]) || { no: '', tarih: '' };
  const birimSec = b => Object.entries(BIRIMLER).map(([k, v]) => `<option value="${k}"${k === b ? ' selected' : ''}>${v}</option>`).join('');
  const kdvSec = k => [20, 10, 1, 0].map(o => `<option value="${o}"${+k === o ? ' selected' : ''}>%${o}</option>`).join('');

  const s = sayfa(`${baslik(id ? 'Taslağı düzenle' : (f.fatura_turu === 'IADE' ? 'Yeni iade faturası' : 'Yeni fatura'), 'Karşı taraf e-Fatura mükellefiyse e-Fatura, değilse e-Arşiv fatura otomatik seçilir.')}
    <form class="fatura-kagidi" id="form" novalidate>
      <div class="ust">
        <div class="oneri"><label for="cariAra">Cari (müşteri / tedarikçi)</label>
          <input id="cariAra" autocomplete="off" placeholder="Ünvan veya VKN yazın">
          <div class="oneri-liste" id="cariListe" hidden></div>
          <div class="tip-bilgi" id="tipBilgi"></div></div>
        <div class="izgara" style="grid-template-columns:1fr 1fr">
          <div><label for="tur">Fatura türü</label><select id="tur"><option value="SATIS">Satış</option><option value="IADE"${f.fatura_turu === 'IADE' ? ' selected' : ''}>İade</option></select></div>
          <div><label for="tarih">Fatura tarihi</label><input id="tarih" type="date" value="${f.tarih}"></div>
          <div><label for="vade">Vade tarihi</label><input id="vade" type="date" value="${f.vade_tarihi}"><div class="ipucu" id="vadeBilgi"></div></div>
          <div><label for="pb">Para birimi</label><select id="pb">${PARALAR.map(p => `<option${p === f.para_birimi ? ' selected' : ''}>${p}</option>`).join('')}</select></div>
          <div id="kurKap"><label for="kur">Kur (1 birim = ? TL)</label><div class="kur-satir"><input id="kur" type="number" step="0.0001" min="0" inputmode="decimal" value="${f.para_birimi !== 'TRY' ? f.kur ?? '' : ''}"><button type="button" class="dugme kucuk" id="tcmb">TCMB</button></div></div>
          <div id="refKap1"><label for="refNo">İade edilen fatura no</label><input id="refNo" value="${esc(ref.no)}" placeholder="ör. ABC2026000000012"></div>
          <div id="refKap2"><label for="refTarih">İade edilen fatura tarihi</label><input id="refTarih" type="date" value="${ref.tarih}"></div>
          <div id="senaryoKap"><label for="senaryo">Senaryo</label><select id="senaryo">
            <option value="TEMELFATURA"${f.senaryo === 'TEMELFATURA' ? ' selected' : ''}>Temel</option>
            <option value="TICARIFATURA"${f.senaryo === 'TICARIFATURA' ? ' selected' : ''}>Ticari</option></select></div>
        </div>
      </div>
      <table class="satirlar"><thead><tr><th>Ürün / hizmet</th><th class="n">Miktar</th><th class="b">Birim</th><th class="f">Birim fiyat</th><th class="k">KDV</th><th class="k">İsk. %</th><th class="tv tev-sutun">Tevkifat</th><th class="t">Tutar</th><th class="sil"></th></tr></thead><tbody id="satirlar"></tbody></table>
      <div class="satir-ekle"><button type="button" class="dugme kucuk" id="satirEkle">${ik('arti')}Satır ekle</button>
        <label class="onay"><input type="checkbox" id="tevAc"${f.satirlar.some(r => r.tevkifat_kod) ? ' checked' : ''}> Tevkifatlı</label>
        ${urunler.length ? `<select id="urunEkle" style="width:auto"><option value="">Kayıtlı üründen ekle…</option>${urunler.map(u => `<option value="${u.id}">${esc(u.ad)} – ${para(u.fiyat)}${u.miktar !== null ? ' – stok ' + u.miktar : ''}</option>`).join('')}</select>` : ''}</div>
      <div class="alt-kisim">
        <div><label for="notlar">Not (faturada görünür)</label><textarea id="notlar" placeholder="Örn. ödeme bilgisi, IBAN">${esc(f.notlar)}</textarea></div>
        <table class="toplamlar" id="toplamlar"></table>
      </div>
    </form>
    <div class="dugmeler" style="margin-top:18px;justify-content:flex-end">
      <button class="dugme" id="kaydet">Taslak olarak kaydet</button>
      <button class="dugme ana" id="kaydetGonder">Kaydet ve gönder</button></div>
    <div class="yapiskan-toplam"><span>Ödenecek</span><strong class="sayi" id="yapiskan"></strong></div>`);

  const turGoster = () => { const iade = $('#tur').value === 'IADE'; $('#refKap1').hidden = $('#refKap2').hidden = !iade; };
  $('#tur').onchange = turGoster; turGoster();
  // --- müşteri seçimi
  if (!id && window.ONSECILI_CARI) { f.cari_id = window.ONSECILI_CARI; window.ONSECILI_CARI = null; }
  let secili = cariler.find(c => c.id === f.cari_id) || null;
  const cariAra = $('#cariAra'), cariListe = $('#cariListe');
  // Vade elle girilmediyse carinin vade gününden hesaplanır; boşsa fatura peşin sayılır
  let vadeElle = !!f.vade_tarihi;
  const vadeGuncelle = () => {
    const g = +(secili?.vade_gun || 0), t = $('#tarih').value;
    if (!vadeElle) $('#vade').value = g > 0 && t ? gunEkle(t, g) : '';
    $('#vadeBilgi').textContent = vadeElle ? 'Elle girildi' : g > 0 ? `Carinin vadesi: ${g} gün` : 'Boş: peşin';
  };
  $('#vade').oninput = () => { vadeElle = !!$('#vade').value; vadeGuncelle(); };
  $('#tarih').addEventListener('change', vadeGuncelle);
  const tipYaz = () => {
    vadeGuncelle();
    const tb = $('#tipBilgi');
    $('#senaryoKap').style.visibility = secili?.efatura_mukellefi ? 'visible' : 'hidden';
    if (!secili) { tb.innerHTML = ''; return; }
    cariAra.value = secili.unvan;
    tb.innerHTML = `${secili.vkn ? `${secili.vkn.length === 11 ? 'TCKN' : 'VKN'} ${esc(secili.vkn)}` : 'Kimlik no yok'} –
      <strong>${secili.efatura_mukellefi ? 'e-Fatura' : 'e-Arşiv'}</strong>
      ${secili.vkn ? `<button type="button" class="dugme kucuk" id="sorgu">${secili.mukellef_sorgu ? 'Tekrar sorgula' : 'Mükellefiyet sorgula'}</button>` : ''}`;
    if ($('#sorgu')) $('#sorgu').onclick = e => calis(e.currentTarget, async () => {
      secili = await api(`/cariler/${secili.id}/mukellef-sorgula`, { method: 'POST' });
      const i = cariler.findIndex(c => c.id === secili.id); cariler[i] = secili; tipYaz();
      bildir(secili.efatura_mukellefi ? 'Müşteri e-Fatura mükellefi.' : 'Müşteri e-Fatura mükellefi değil, e-Arşiv kesilecek.');
    });
  };
  const cariGoster = () => {
    const q = cariAra.value.toLocaleLowerCase('tr');
    const eslesen = cariler.filter(c => c.unvan.toLocaleLowerCase('tr').includes(q) || (c.vkn || '').includes(q)).slice(0, 8);
    cariListe.innerHTML = eslesen.map(c => `<button type="button" data-id="${c.id}">${esc(c.unvan)}<small>${esc(c.vkn || '')} ${c.il ? '– ' + esc(c.il) : ''}</small></button>`).join('')
      + `<button type="button" data-yeni="1"><strong>+ Yeni müşteri ekle</strong>${q ? `<small>“${esc(cariAra.value)}”</small>` : ''}</button>`;
    cariListe.hidden = false;
  };
  cariAra.onfocus = cariGoster; cariAra.oninput = () => { secili = null; tipYaz(); cariGoster(); };
  cariListe.onmousedown = e => e.preventDefault();
  cariListe.onclick = e => {
    const b = e.target.closest('button'); if (!b) return;
    cariListe.hidden = true;
    if (b.dataset.yeni) return cariFormu({ unvan: cariAra.value, tur: $('#tur').value === 'IADE' ? 'tedarikci' : 'musteri' }, yeni => { if (!yeni) return; cariler.push(yeni); secili = yeni; tipYaz(); });
    secili = cariler.find(c => c.id === +b.dataset.id); tipYaz();
  };
  cariAra.onblur = () => setTimeout(() => cariListe.hidden = true, 150);
  tipYaz();

  // --- satırlar
  const tbody = $('#satirlar');
  const satirHtml = r => `<tr>
    <td><input data-a="ad" value="${esc(r.ad)}" placeholder="Açıklama" aria-label="Ürün veya hizmet"><input type="hidden" data-a="urun_id" value="${r.urun_id || ''}"></td>
    <td class="n" data-e="Miktar"><input data-a="miktar" type="number" inputmode="decimal" step="any" min="0" value="${r.miktar}"></td>
    <td class="b" data-e="Birim"><select data-a="birim">${birimSec(r.birim)}</select></td>
    <td class="f" data-e="Birim fiyat"><input data-a="birim_fiyat" type="number" inputmode="decimal" step="any" min="0" value="${r.birim_fiyat}" placeholder="0,00"></td>
    <td class="k" data-e="KDV"><select data-a="kdv">${kdvSec(r.kdv)}</select></td>
    <td class="k" data-e="İskonto %"><input data-a="iskonto" type="number" inputmode="decimal" step="any" min="0" max="100" value="${r.iskonto || 0}"></td>
    <td class="tv tev-sutun" data-e="Tevkifat"><select data-a="tevkifat_kod"><option value="">Yok</option>${Object.entries(TEVKIFAT).map(([k, v]) => `<option value="${k}"${r.tevkifat_kod === k ? ' selected' : ''} title="${esc(v.ad)}">${k} – ${v.pay}/10 ${esc(v.ad.slice(0, 28))}</option>`).join('')}</select></td>
    <td class="t sayi" data-e="Tutar"></td>
    <td class="sil"><button type="button" class="sil-dugme" aria-label="Satırı sil">${ik('sil')}</button></td></tr>`;
  const satirlariOku = () => $$('tr', tbody).map(tr => {
    const r = Object.fromEntries($$('[data-a]', tr).map(i => [i.dataset.a, i.value]));
    if (!$('#tevAc').checked) r.tevkifat_kod = '';
    return r;
  });
  const kurus = x => Math.round((x + Number.EPSILON) * 100) / 100;
  const hesapla = () => {
    let brut = 0, isk = 0, kdv = 0, tev = 0;
    const tevAcik = $('#tevAc').checked, p = $('#pb').value, kur = +$('#kur').value || 0;
    $('#form').classList.toggle('tevkifatli', tevAcik);
    $('#kurKap').hidden = p === 'TRY';
    $$('tr', tbody).forEach(tr => {
      const r = Object.fromEntries($$('[data-a]', tr).map(i => [i.dataset.a, i.value]));
      const b = kurus((+r.miktar || 0) * (+r.birim_fiyat || 0)), is = kurus(b * (+r.iskonto || 0) / 100), m = b - is, k = kurus(m * (+r.kdv) / 100);
      const t = tevAcik && TEVKIFAT[r.tevkifat_kod] ? kurus(k * TEVKIFAT[r.tevkifat_kod].pay / 10) : 0;
      brut += b; isk += is; kdv += k; tev += t; $('.t', tr).textContent = para(m);
    });
    const genel = brut - isk + kdv - tev;
    $('#toplamlar').innerHTML = `<tr><td>Mal/hizmet toplamı</td><td class="sayi">${pb(brut, p)}</td></tr>
      ${isk ? `<tr><td>İskonto</td><td class="sayi">−${pb(isk, p)}</td></tr>` : ''}
      <tr><td>KDV</td><td class="sayi">${pb(kdv, p)}</td></tr>
      ${tev ? `<tr><td>Tevkif edilen KDV</td><td class="sayi">−${pb(tev, p)}</td></tr>` : ''}
      <tr class="genel"><td>Ödenecek</td><td class="sayi">${pb(genel, p)}</td></tr>
      ${p !== 'TRY' ? `<tr><td class="ipucu">TL karşılığı</td><td class="sayi ipucu">${kur ? tl(genel * kur) : 'kur girin'}</td></tr>` : ''}`;
    $('#yapiskan').textContent = pb(genel, p);
  };
  $('#tevAc').onchange = hesapla; $('#pb').onchange = hesapla; $('#kur').oninput = hesapla;
  $('#tcmb').onclick = e => calis(e.currentTarget, async () => {
    const k = await api(`/kur?para=${$('#pb').value}&tarih=${$('#tarih').value}`);
    $('#kur').value = k.kur; hesapla(); bildir(`${k.kaynak}: ${k.kur} (${tarihTR(k.tarih)})`);
  });
  const satirEkle = r => { tbody.insertAdjacentHTML('beforeend', satirHtml(r)); hesapla(); };
  f.satirlar.forEach(r => tbody.insertAdjacentHTML('beforeend', satirHtml(r))); hesapla();
  tbody.oninput = hesapla; tbody.onchange = hesapla;
  tbody.onclick = e => { const b = e.target.closest('.sil-dugme'); if (b) { b.closest('tr').remove(); if (!tbody.children.length) satirEkle({ ad: '', miktar: 1, birim: 'C62', birim_fiyat: '', kdv: 20 }); hesapla(); } };
  $('#satirEkle').onclick = () => { satirEkle({ ad: '', miktar: 1, birim: 'C62', birim_fiyat: '', kdv: 20 }); $('tr:last-child input', tbody).focus(); };
  if ($('#urunEkle')) $('#urunEkle').onchange = e => {
    const u = urunler.find(x => x.id === +e.target.value); if (!u) return;
    const ilk = $('tr:first-child', tbody);
    if (tbody.children.length === 1 && !$('[data-a="ad"]', ilk).value) ilk.remove();
    satirEkle({ ad: u.ad, miktar: 1, birim: u.birim, birim_fiyat: u.fiyat, kdv: u.kdv, urun_id: u.id }); e.target.value = '';
  };

  const kaydet = async gonder => {
    if (!secili) { cariAra.focus(); throw new Error('Lütfen bir müşteri seçin.'); }
    const govde = { cari_id: secili.id, tarih: $('#tarih').value, vade_tarihi: $('#vade').value, notlar: $('#notlar').value, senaryo: $('#senaryo').value, satirlar: satirlariOku(),
      fatura_turu: $('#tur').value, iade_ref: [{ no: $('#refNo').value, tarih: $('#refTarih').value }],
      para_birimi: $('#pb').value, kur: $('#kur').value };
    const k = await api(id ? '/faturalar/' + id : '/faturalar', { method: id ? 'PUT' : 'POST', body: govde });
    if (gonder) {
      if (!confirm(MOD === 'canli' ? 'Fatura kesilip GİB\'e gönderilecek. Bu işlem geri alınamaz. Devam edilsin mi?' : 'Fatura gönderilsin mi?')) { location.hash = '#/fatura/' + k.id; return; }
      try { const y = await api(`/faturalar/${k.id}/gonder`, { method: 'POST' }); bildir(`${y.fatura_no} numaralı fatura kesildi.`); }
      finally { location.hash = '#/fatura/' + k.id; }
    } else { bildir('Taslak kaydedildi.'); location.hash = '#/fatura/' + k.id; }
  };
  $('#kaydet').onclick = e => calis(e.currentTarget, () => kaydet(false));
  $('#kaydetGonder').onclick = e => calis(e.currentTarget, () => kaydet(true));
  $('#form').onsubmit = e => e.preventDefault();
  if (!secili) cariAra.focus();
}

// ------------------------------------------------------------------ Pencere yardımcısı
function pencere(icerik) {
  const p = document.createElement('div'); p.className = 'perde';
  p.innerHTML = `<div class="pencere" role="dialog" aria-modal="true">${icerik}</div>`;
  document.body.appendChild(p);
  const kapat = () => { p.remove(); document.removeEventListener('keydown', esc_); };
  const esc_ = e => e.key === 'Escape' && kapat();
  document.addEventListener('keydown', esc_);
  p.onmousedown = e => e.target === p && kapat();
  $$('[data-kapat]', p).forEach(b => b.onclick = kapat);
  setTimeout(() => $('input, select, textarea', p)?.focus());
  return { p, kapat };
}
const alan = (ad, etiket, deger = '', ek = '') => `<div ${ek.includes('tam') ? 'class="tam"' : ''}><label for="a_${ad}">${etiket}</label><input id="a_${ad}" name="${ad}" value="${esc(deger)}" ${ek.replace('tam', '')}></div>`;
const formOku = p => Object.fromEntries($$('[name]', p).map(i => [i.name, i.value]));

// ------------------------------------------------------------------ Müşteriler
function cariFormu(c = {}, sonra) {
  const { p, kapat } = pencere(`<form>${baslik(c.id ? 'Cariyi düzenle' : 'Yeni cari')}
    <div class="izgara">
      ${alan('unvan', 'Ünvan / ad soyad', c.unvan, 'required tam')}
      <div><label for="a_tur">Cari türü</label><select id="a_tur" name="tur">${Object.entries(CTUR).map(([k, v]) => `<option value="${k}"${k === (c.tur || 'musteri') ? ' selected' : ''}>${v}</option>`).join('')}</select></div>
      ${alan('vkn', 'VKN veya TCKN', c.vkn, 'inputmode="numeric" maxlength="11"')}
      ${alan('vergi_dairesi', 'Vergi dairesi', c.vergi_dairesi)}
      ${alan('adres', 'Adres', c.adres, 'tam')}
      ${alan('ilce', 'İlçe', c.ilce)}${alan('il', 'İl', c.il)}
      ${alan('telefon', 'Telefon', c.telefon, 'type="tel"')}${alan('eposta', 'E-posta', c.eposta, 'type="email"')}
      ${alan('vade_gun', 'Vade (gün)', c.vade_gun || 0, 'type="number" min="0" max="365" inputmode="numeric"')}
    </div>
    <p class="ipucu">Vade: faturaya vade tarihi girilmezse fatura tarihine bu kadar gün eklenir. 0: peşin.</p>
    <p class="ipucu">Şahıslar için TCKN girin; e-Arşiv fatura e-posta adresine gönderilir.</p>
    <div class="pencere-alt"><div>${c.id ? `<button type="button" class="dugme tehlike" id="silC">Sil</button>` : ''}</div>
    <div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Kaydet</button></div></div></form>`);
  $('form', p).onsubmit = e => {
    e.preventDefault();
    calis(e.submitter, async () => {
      let k = await api(c.id ? '/cariler/' + c.id : '/cariler', { method: c.id ? 'PUT' : 'POST', body: formOku(p) });
      if (k.vkn && !k.mukellef_sorgu) k = await api(`/cariler/${k.id}/mukellef-sorgula`, { method: 'POST' }).catch(() => k);
      kapat(); bildir('Cari kaydedildi.'); sonra && sonra(k);
    });
  };
  if ($('#silC', p)) $('#silC', p).onclick = e => confirm('Cari silinsin mi?') && calis(e.currentTarget, async () => { await api('/cariler/' + c.id, { method: 'DELETE' }); kapat(); bildir('Cari silindi.'); sonra && sonra(null); });
}

async function carilerSayfa() {
  const s = sayfa(`${baslik('Cariler', 'Müşterileriniz ve tedarikçileriniz. Tedarikçiler irsaliye ve e-faturalardan otomatik eklenir.', `<button class="dugme ana" id="yeniC">${ik('arti')}Yeni cari</button>`)}
    <div class="dugmeler" style="margin-bottom:14px"><input class="arama" id="ara" type="search" placeholder="Ünvan veya VKN ara">
    <div class="sekmeler" id="turSec"><button data-t="" class="aktif">Tümü</button><button data-t="musteri">Müşteriler</button><button data-t="tedarikci">Tedarikçiler</button></div></div>
    <div id="tablo"></div>`);
  let z, tur = '';
  const yukle = async () => {
    const l = await api(`/cariler?q=${encodeURIComponent($('#ara').value)}&tur=${tur}`);
    $('#tablo', s).innerHTML = !l.length ? `<div class="panel bos"><p>Cari bulunamadı.</p></div>`
      : `<div class="tablo-kap"><table class="liste"><thead><tr><th>Ünvan</th><th class="gizle-m">VKN / TCKN</th><th class="gizle-m">Tür</th><th class="gizle-m">Fatura türü</th><th class="s">Bakiye</th></tr></thead><tbody>
      ${l.map(c => `<tr class="tik" data-id="${c.id}"><td>${esc(c.unvan)}<div class="ikincil">${esc(c.telefon || c.eposta || ((c.notlar || '').startsWith('Otomatik') ? c.notlar : ''))}</div></td><td class="gizle-m sayi">${esc(c.vkn)}</td><td class="gizle-m">${CTUR[c.tur] || ''}</td>
        <td class="gizle-m"><span class="rozet${c.efatura_mukellefi ? ' ONAYLANDI' : ''}">${c.efatura_mukellefi ? 'e-Fatura' : 'e-Arşiv'}</span></td>
        <td class="s">${bakiyeHtml(c.bakiye)}</td></tr>`).join('')}</tbody></table></div>`;
    $$('tr[data-id]', s).forEach(tr => tr.onclick = () => location.hash = '#/cari/' + tr.dataset.id);
  };
  $$('#turSec button', s).forEach(b => b.onclick = () => { tur = b.dataset.t; $$('#turSec button', s).forEach(x => x.classList.toggle('aktif', x === b)); yukle(); });
  $('#yeniC').onclick = () => cariFormu({}, k => k && (location.hash = '#/cari/' + k.id));
  $('#ara').oninput = () => { clearTimeout(z); z = setTimeout(yukle, 250); };
  await yukle();
}

// ------------------------------------------------------------------ Stok ve ürünler
const STUR = { ACILIS: 'Açılış stoku', SAYIM: 'Sayım düzeltmesi', IRSALIYE: 'İrsaliye girişi', ALIS: 'Alış faturası girişi', SATIS: 'Satış', ALIS_IADE: 'Tedarikçiye iade', GELEN_IADE: 'Müşteri iadesi' };
const birimAd = b => BIRIMLER[b] || b || '';
const miktarYaz = m => Number(m || 0).toLocaleString('tr-TR', { maximumFractionDigits: 3 });

function urunFormu(u = {}, sonra) {
  const hizmetMi = u.id ? !u.stok_takibi : false;
  const { p, kapat } = pencere(`<form>${baslik(u.id ? 'Ürünü düzenle' : 'Yeni ürün / hizmet')}
    <div class="izgara">
      ${alan('ad', 'Ad', u.ad, 'required tam')}
      ${alan('kod', 'Stok kodu', u.kod, 'placeholder="ör. KGT80"')}
      <div><label for="a_stok_takibi">Türü</label><select id="a_stok_takibi" name="stok_takibi">
        <option value="1"${!hizmetMi ? ' selected' : ''}>Stoklu ürün</option><option value="0"${hizmetMi ? ' selected' : ''}>Hizmet (stok tutulmaz)</option></select></div>
      <div><label for="a_birim">Birim</label><select id="a_birim" name="birim">${Object.entries(BIRIMLER).map(([k, v]) => `<option value="${k}"${k === (u.birim || 'C62') ? ' selected' : ''}>${v}</option>`).join('')}</select></div>
      ${alan('fiyat', 'Satış fiyatı (KDV hariç)', u.fiyat ?? '', 'type="number" step="any" min="0" inputmode="decimal"')}
      <div><label for="a_kdv">KDV</label><select id="a_kdv" name="kdv">${[20, 10, 1, 0].map(o => `<option value="${o}"${+(u.kdv ?? 20) === o ? ' selected' : ''}>%${o}</option>`).join('')}</select></div>
      <div class="stoklu">${alan('alis_fiyat', 'Alış fiyatı (KDV hariç)', u.alis_fiyat ?? '', 'type="number" step="any" min="0" inputmode="decimal"')}</div>
      <div class="stoklu">${alan('kritik', 'Kritik stok seviyesi', u.kritik || '', 'type="number" step="any" min="0" inputmode="decimal" placeholder="0 = uyarı yok"')}</div>
    </div>
    <p class="ipucu stoklu">Stok kodu, faturadaki satırlarda geçerse ürün otomatik tanınır. Alış fiyatı, irsaliye ve faturalardan otomatik güncellenir.</p>
    <div class="pencere-alt"><div>${u.id ? `<button type="button" class="dugme tehlike" id="silU">Sil</button>` : ''}</div>
    <div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Kaydet</button></div></div></form>`);
  const tg = () => $$('.stoklu', p).forEach(x => x.hidden = $('#a_stok_takibi', p).value === '0');
  $('#a_stok_takibi', p).onchange = tg; tg();
  $('form', p).onsubmit = e => { e.preventDefault(); calis(e.submitter, async () => { const k = await api(u.id ? '/urunler/' + u.id : '/urunler', { method: u.id ? 'PUT' : 'POST', body: formOku(p) }); kapat(); bildir('Kaydedildi.'); sonra(k); }); };
  if ($('#silU', p)) $('#silU', p).onclick = e => confirm('Ürün listeden kaldırılsın mı? Geçmiş hareketleri korunur.') && calis(e.currentTarget, async () => { await api('/urunler/' + u.id, { method: 'DELETE' }); kapat(); bildir('Ürün kaldırıldı.'); location.hash = '#/urunler'; });
}

async function urunlerSayfa() {
  const kritikFiltre = new URLSearchParams(location.hash.split('?')[1] || '').get('k') === '1';
  const s = sayfa(`${baslik('Stok ve ürünler', 'Stok, onaylanan irsaliyelerle artar, kesilen faturalarla azalır.', `<button class="dugme ana" id="yeniU">${ik('arti')}Yeni ürün</button>`)}
    <div class="dugmeler" style="margin-bottom:14px"><input class="arama" id="ara" type="search" placeholder="Ürün adı veya kodu ara">
    <div class="sekmeler" id="fSec"><button data-f="">Tümü</button><button data-f="k">Kritik stok</button><button data-f="h">Hizmetler</button></div></div>
    <div id="toplam" class="ipucu" style="margin:-4px 0 10px"></div><div id="tablo"></div>`);
  const l = await api('/stok');
  let f = kritikFiltre ? 'k' : '';
  const ciz = () => {
    $$('#fSec button', s).forEach(b => b.classList.toggle('aktif', b.dataset.f === f));
    const q = $('#ara').value.toLocaleLowerCase('tr');
    const g = l.filter(u => (!q || u.ad.toLocaleLowerCase('tr').includes(q) || (u.kod || '').toLocaleLowerCase('tr').includes(q))
      && (f === 'k' ? u.kritik_durum : f === 'h' ? !u.stok_takibi : true));
    const deger = l.reduce((t, u) => t + (u.deger || 0), 0);
    $('#toplam', s).innerHTML = `Stok değeri (ortalama maliyetle): <strong class="sayi">${tl(deger)}</strong>`;
    $('#tablo', s).innerHTML = !g.length ? `<div class="panel bos"><p>${l.length ? 'Bu filtrede ürün yok.' : 'Henüz ürün yok. Sattığınız veya aldığınız ürünleri ekleyin; irsaliyedeki satırlardan “Yeni ürün olarak ekle” ile de oluşturabilirsiniz.'}</p></div>`
      : `<div class="tablo-kap"><table class="liste"><thead><tr><th>Ürün</th><th class="s">Stok</th><th class="s gizle-m">Ort. maliyet</th><th class="s gizle-m">Satış fiyatı</th></tr></thead><tbody>
      ${g.map(u => `<tr class="tik" data-id="${u.id}"><td>${esc(u.ad)}<div class="ikincil">${esc(u.kod || '')}${!u.stok_takibi ? ' Hizmet' : ''}</div></td>
        <td class="s sayi">${u.stok_takibi ? `<span class="${u.kritik_durum ? 'borclu' : ''}">${miktarYaz(u.miktar)} ${esc(birimAd(u.birim))}</span>${u.kritik_durum ? '<div class="ikincil borclu">kritik</div>' : ''}` : '<span class="ikincil">—</span>'}</td>
        <td class="s sayi gizle-m">${u.maliyet !== null ? para(u.maliyet) : ''}</td><td class="s sayi gizle-m">${para(u.fiyat)}</td></tr>`).join('')}</tbody></table></div>`;
    $$('tr[data-id]', s).forEach(tr => tr.onclick = () => location.hash = '#/urun/' + tr.dataset.id);
  };
  $$('#fSec button', s).forEach(b => b.onclick = () => { f = b.dataset.f; ciz(); });
  $('#ara').oninput = ciz;
  $('#yeniU').onclick = () => urunFormu({}, k => location.hash = '#/urun/' + k.id);
  ciz();
}

async function urunDetay(id) {
  sayfa(baslik('Ürün'));
  const r = await api(`/urunler/${id}/hareketler`);
  const u = r.urun, stoklu = !!u.stok_takibi, kritik = stoklu && u.kritik > 0 && r.miktar <= u.kritik;
  const git = h => h.kaynak === 'fatura' ? '#/fatura/' + h.kaynak_id : h.kaynak === 'irsaliye' ? '#/irsaliye/' + h.kaynak_id : h.kaynak === 'alis' ? '#/alis/' + h.kaynak_id : '';
  const s = sayfa(`${baslik(esc(u.ad), `${u.kod ? esc(u.kod) + ' – ' : ''}Satış fiyatı ${tl(u.fiyat)} + %${u.kdv} KDV${u.alis_fiyat ? ' – alış ' + tl(u.alis_fiyat) : ''}`, `<button class="dugme" id="duzenle">Düzenle</button>`)}
    ${stoklu ? `<div class="bakiye-kart ${kritik ? 'borclu' : ''}"><div><div class="etiket">${kritik ? 'Kritik seviyede – stok' : 'Stok'}</div><div class="deger sayi">${miktarYaz(r.miktar)} ${esc(birimAd(u.birim))}</div>
      ${u.kritik ? `<div class="ipucu">Kritik seviye: ${miktarYaz(u.kritik)}</div>` : ''}</div>
      <div class="dugmeler"><button class="dugme" id="sayim">Sayım yap</button><button class="dugme" id="acilis">Açılış stoku gir</button></div></div>
    <h2 style="margin:22px 0 12px">Stok hareketleri</h2>
    <div class="tablo-kap"><table class="liste"><thead><tr><th>Tarih</th><th>İşlem</th><th class="s">Miktar</th><th class="s gizle-m">Birim fiyat</th><th class="s">Kalan</th><th></th></tr></thead><tbody>
      ${r.hareketler.map(h => `<tr${git(h) ? ` class="tik" data-git="${git(h)}"` : ''}><td>${tarihTR(h.tarih)}</td><td>${esc(h.tur_ad)}<div class="ikincil">${esc(h.aciklama || (h.satir_ad !== u.ad ? h.satir_ad || '' : ''))}</div></td>
        <td class="s sayi ${h.miktar < 0 ? 'borclu' : 'alacakli'}">${h.miktar > 0 ? '+' : ''}${miktarYaz(h.miktar)}</td><td class="s sayi gizle-m">${h.birim_fiyat ? para(h.birim_fiyat) : ''}</td>
        <td class="s sayi">${miktarYaz(h.kalan)}</td><td class="s">${h.kaynak === 'manuel' ? `<button class="sil-dugme" data-sil="${h.id}" aria-label="Kaydı sil">${ik('sil')}</button>` : ''}</td></tr>`).join('')
        || '<tr><td colspan="6" class="ipucu">Henüz stok hareketi yok. Mevcut stoğunuzu “Açılış stoku gir” ile ekleyin.</td></tr>'}
    </tbody></table></div>` : `<div class="panel"><p class="ipucu" style="margin:0">Bu bir hizmet; stok tutulmuyor. Stoklu ürüne çevirmek için Düzenle'den türünü değiştirin.</p></div>`}`);
  const yenile = () => urunDetay(id);
  $('#duzenle').onclick = () => urunFormu(u, yenile);
  $$('tr[data-git]', s).forEach(tr => tr.onclick = () => location.hash = tr.dataset.git);
  $$('[data-sil]', s).forEach(x => x.onclick = ev => { ev.stopPropagation(); confirm('Kayıt silinsin mi?') && calis(x, async () => { await api('/stok-hareketleri/' + x.dataset.sil, { method: 'DELETE' }); yenile(); }); });
  const form = (tur) => {
    const sayim = tur === 'SAYIM';
    const { p, kapat } = pencere(`<form>${baslik(sayim ? 'Sayım yap' : 'Açılış stoku', esc(u.ad))}<div class="izgara">
      ${alan('tarih', 'Tarih', bugun(), 'type="date" required')}
      ${alan('miktar', sayim ? 'Sayılan miktar' : 'Miktar', '', 'type="number" step="any" min="0" inputmode="decimal" required')}
      ${sayim ? '' : alan('birim_fiyat', 'Birim alış fiyatı (maliyet için)', u.alis_fiyat ?? '', 'type="number" step="any" min="0" inputmode="decimal"')}
      ${alan('aciklama', 'Açıklama', '', 'tam')}</div>
      <p class="ipucu">${sayim ? `Programdaki stok: ${miktarYaz(r.miktar)}. Aradaki fark düzeltme olarak kaydedilir.` : 'Programa başladığınız gün elinizde olan miktar.'}</p>
      <div class="pencere-alt"><div></div><div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Kaydet</button></div></div></form>`);
    $('form', p).onsubmit = e => { e.preventDefault(); calis(e.submitter, async () => {
      const k = await api(`/urunler/${id}/stok-duzelt`, { method: 'POST', body: { ...formOku(p), tur } });
      kapat(); bildir(sayim ? (k.fark ? `Fark kaydedildi: ${k.fark > 0 ? '+' : ''}${miktarYaz(k.fark)}` : 'Sayım programla aynı, düzeltme gerekmedi.') : 'Açılış stoku kaydedildi.'); yenile(); }); };
  };
  if ($('#sayim')) $('#sayim').onclick = () => form('SAYIM');
  if ($('#acilis')) $('#acilis').onclick = () => form('ACILIS');
}

async function stokaAlFormu(gid, sonra) {
  const [d, urunler] = await Promise.all([api(`/gelen/${gid}/stok`), api('/urunler')]);
  const secenek = r => `<option value="0">Stoka girmesin</option>${urunler.filter(u => u.stok_takibi).map(u => `<option value="${u.id}"${+r.urun_id === u.id ? ' selected' : ''}>${esc(u.ad)}</option>`).join('')}<option value="yeni"${!r.urun_id ? ' selected' : ''}>+ Yeni ürün olarak ekle</option>`;
  const { p, kapat } = pencere(`<form>${baslik('Stoka al', d.stoka_alindi ? 'Bu fatura daha önce stoka alındı; kaydederseniz yeniden yazılır.' : 'Her satırın hangi ürüne gireceğini seçin.')}
    <div class="tablo-kap"><table class="liste"><thead><tr><th>Faturadaki satır</th><th class="s">Miktar</th><th>Stok ürünü</th></tr></thead><tbody>
    ${d.satirlar.map((r, i) => `<tr><td>${esc(r.ad)}</td><td class="s sayi">${esc(r.miktar)} ${esc(r.birim || '')}</td><td><select data-i="${i}">${secenek(r)}</select></td></tr>`).join('')}
    </tbody></table></div><p class="ipucu">Hizmet kalemleri (kargo, internet vb.) için “Stoka girmesin” seçin. Seçimleriniz bu tedarikçi için hatırlanır.</p>
    <div class="pencere-alt"><div></div><div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Stoka al</button></div></div></form>`);
  $('form', p).onsubmit = e => { e.preventDefault(); calis(e.submitter, async () => {
    const k = await api(`/gelen/${gid}/stoka-al`, { method: 'POST', body: { urunler: $$('select[data-i]', p).map(x => x.value) } });
    kapat(); bildir(k.adet ? `${k.adet} kalem stoka alındı.` : 'Stoka giren kalem olmadı.'); sonra(); }); };
}

// ------------------------------------------------------------------ Raporlar
function grafik(aylik) {
  const W = 720, H = 260, sol = 56, alt = 28, ust = 12;
  const ham = Math.max(1, ...aylik.flatMap(a => [a.satis, a.alis]));
  const kat = 10 ** Math.floor(Math.log10(ham)), enb = [1, 2, 2.5, 4, 5, 8, 10].map(x => x * kat).find(x => x >= ham);
  const olcek = v => (H - alt - ust) * Math.max(0, v) / enb;
  const gw = (W - sol - 8) / aylik.length, bw = Math.min(22, gw / 2.6);
  const kisa = v => v >= 1e6 ? (v / 1e6).toLocaleString('tr-TR', { maximumFractionDigits: 2 }) + ' mn' : v >= 1e3 ? (v / 1e3).toLocaleString('tr-TR', { maximumFractionDigits: 1 }) + ' bin' : Math.round(v);
  const cizgiler = [0, 0.25, 0.5, 0.75, 1].map(t => { const y = H - alt - (H - alt - ust) * t; return `<line x1="${sol}" x2="${W}" y1="${y}" y2="${y}" class="g-cizgi"/><text x="${sol - 6}" y="${y + 4}" class="g-yazi" text-anchor="end">${kisa(enb * t)}</text>`; }).join('');
  const cubuklar = aylik.map((a, i) => {
    const x = sol + i * gw + gw / 2;
    return `<rect x="${x - bw - 1}" y="${H - alt - olcek(a.satis)}" width="${bw}" height="${olcek(a.satis)}" class="g-satis"><title>${a.etiket} satış: ${tl(a.satis)}</title></rect>
      <rect x="${x + 1}" y="${H - alt - olcek(a.alis)}" width="${bw}" height="${olcek(a.alis)}" class="g-alis"><title>${a.etiket} alış: ${tl(a.alis)}</title></rect>
      <text x="${x}" y="${H - 8}" class="g-yazi" text-anchor="middle">${a.etiket}</text>`;
  }).join('');
  return `<div class="grafik-kap"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Aylık satış ve alış">${cizgiler}${cubuklar}</svg></div>
    <div class="lejant"><span><i class="g-satis"></i>Net satış</span><span><i class="g-alis"></i>Net alış</span></div>`;
}

async function raporlarSayfa() {
  const q = new URLSearchParams(location.hash.split('?')[1] || '');
  const y = new Date().getFullYear();
  const bas = q.get('bas') || `${y}-01-01`, bit = q.get('bit') || bugun();
  sayfa(baslik('Raporlar'));
  const r = await api(`/rapor?bas=${bas}&bit=${bit}`);
  const o = r.ozet, k = r.kdv;
  const eksi = v => Math.abs(v) < 0.005 ? tl(0) : '−' + tl(v);
  const liste = (b, l, alanAd = 'tutar') => `<div class="panel"><h2>${b}</h2>${l.length ? `<table class="toplamlar">${l.map(x => `<tr><td>${esc(x.ad)}${x.miktar !== undefined ? `<span class="ikincil"> – ${miktarYaz(x.miktar)}</span>` : ''}</td><td class="sayi">${tl(x[alanAd])}</td></tr>`).join('')}</table>` : '<p class="ipucu">Bu dönemde kayıt yok.</p>'}</div>`;
  const s = sayfa(`${baslik('Raporlar', `${tarihTR(r.bas)} – ${tarihTR(r.bit)}`, `<a class="dugme ana" href="/api/disa-aktar?bas=${r.bas}&bit=${r.bit}">Excel'e aktar</a>`)}
    <div class="dugmeler tarih-filtre" style="margin-bottom:16px"><input type="date" id="bas" value="${r.bas}" aria-label="Başlangıç"><input type="date" id="bit" value="${r.bit}" aria-label="Bitiş">
      <button class="dugme kucuk" id="goster">Göster</button><button class="dugme kucuk" data-d="ay">Bu ay</button><button class="dugme kucuk" data-d="gecen">Geçen ay</button><button class="dugme kucuk" data-d="yil">Bu yıl</button></div>
    <div class="rakamlar dortlu">
      <div class="rakam vurgu"><div class="etiket">Net satış</div><div class="deger sayi">${tl(o.net_satis)}</div><div class="alt">${o.satis_adet} fatura, KDV hariç</div></div>
      <div class="rakam"><div class="etiket">Net alış</div><div class="deger sayi">${tl(o.net_alis)}</div><div class="alt">${o.alis_adet} fatura</div></div>
      <div class="rakam"><div class="etiket">Brüt kâr</div><div class="deger sayi${o.brut_kar < 0 ? ' eksi' : ''}">${tl(o.brut_kar)}</div><div class="alt">Satış − satılan malın maliyeti</div></div>
      <div class="rakam"><div class="etiket">KDV farkı</div><div class="deger sayi">${tl(Math.abs(k.net))}</div><div class="alt">${k.net >= 0 ? 'ödenecek (tahmini)' : 'devreden (tahmini)'}</div></div>
    </div>
    <div class="panel"><h2>Aylık satış ve alış (KDV hariç)</h2>${grafik(r.aylik)}</div>
    <div class="rapor-izgara">
      <div class="panel"><h2>Kâr</h2><table class="toplamlar">
        <tr><td>Net satış</td><td class="sayi">${tl(o.net_satis)}</td></tr>
        <tr><td>Satılan malın maliyeti</td><td class="sayi">${eksi(o.smm)}</td></tr>
        <tr class="ara"><td>Brüt kâr</td><td class="sayi">${tl(o.brut_kar)}</td></tr>
        <tr><td>Masraflar</td><td class="sayi">${eksi(o.masraf)}</td></tr>
        <tr><td>Diğer gelirler</td><td class="sayi">${tl(o.diger_gelir)}</td></tr>
        <tr class="genel"><td>Faaliyet sonucu</td><td class="sayi">${tl(o.faaliyet_sonucu)}</td></tr></table>
        <p class="ipucu">Maliyet, stoklu ürünlerin ortalama alış fiyatıyla hesaplanır; hizmet satışlarının maliyeti yoktur.${o.maliyetsiz_urun ? ` ${o.maliyetsiz_urun} ürünün alış fiyatı bilinmediği için maliyeti sıfır sayıldı.` : ''}</p></div>
      <div class="panel"><h2>KDV</h2><table class="toplamlar">
        <tr><td>Hesaplanan KDV (satışlar)</td><td class="sayi">${tl(k.hesaplanan)}</td></tr>
        ${k.musteri_iadesi ? `<tr><td>Müşteri iadeleri</td><td class="sayi">${eksi(k.musteri_iadesi)}</td></tr>` : ''}
        <tr><td>İndirilecek KDV (alışlar)</td><td class="sayi">${eksi(k.indirilecek)}</td></tr>
        ${k.tedarikci_iadesi ? `<tr><td>Tedarikçiye iadeler</td><td class="sayi">${tl(k.tedarikci_iadesi)}</td></tr>` : ''}
        <tr class="genel"><td>${k.net >= 0 ? 'Ödenecek' : 'Devreden'}</td><td class="sayi">${tl(Math.abs(k.net))}</td></tr></table>
        <p class="ipucu">Tahmini hesaptır; beyanname için mali müşavirinizin kayıtları esastır.${k.kdv_bilinmeyen_alis ? ` ${k.kdv_bilinmeyen_alis} alış faturası KDV'siz (toplam olarak) girildiği için hesaba katılmadı.` : ''}</p></div>
      <div class="panel"><h2>Nakit hareketi</h2><table class="toplamlar">
        <tr><td>Tahsilatlar</td><td class="sayi">${tl(r.nakit.tahsilat)}</td></tr><tr><td>Diğer gelirler</td><td class="sayi">${tl(r.nakit.gelir)}</td></tr>
        <tr><td>Ödemeler</td><td class="sayi">${eksi(r.nakit.odeme)}</td></tr><tr><td>Masraflar</td><td class="sayi">${eksi(r.nakit.masraf)}</td></tr>
        <tr class="genel"><td>Net nakit</td><td class="sayi">${tl(r.nakit.tahsilat + r.nakit.gelir - r.nakit.odeme - r.nakit.masraf)}</td></tr></table></div>
      ${liste('En çok satış yapılan müşteriler', r.musteriler)}
      ${liste('En çok satılan ürün/hizmetler', r.urunler)}
      ${liste('En çok alış yapılan tedarikçiler', r.tedarikciler)}
      ${r.masraflar.length ? liste('Masraflar', r.masraflar) : ''}
    </div>`);
  const git = (b, e) => location.hash = `#/raporlar?bas=${b}&bit=${e}`;
  $('#goster').onclick = () => git($('#bas').value, $('#bit').value);
  $$('[data-d]', s).forEach(x => x.onclick = () => {
    const d = new Date(), iso = t => new Date(t - t.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    if (x.dataset.d === 'ay') git(iso(new Date(d.getFullYear(), d.getMonth(), 1)), bugun());
    else if (x.dataset.d === 'gecen') git(iso(new Date(d.getFullYear(), d.getMonth() - 1, 1)), iso(new Date(d.getFullYear(), d.getMonth(), 0)));
    else git(`${d.getFullYear()}-01-01`, bugun());
  });
}

// ------------------------------------------------------------------ Ayarlar
async function ayarlarSayfa() {
  sayfa(baslik('Ayarlar'));
  const [a, entler] = await Promise.all([api('/ayarlar'), api('/entegratorler')]);
  const entAlan = (ent) => ent.alanlar.map(al => al.tur === 'sifre'
    ? `<div${al.genis ? ' class="tam"' : ''}><label for="a_${al.anahtar}">${esc(al.etiket)}</label><input id="a_${al.anahtar}" name="${al.anahtar}" type="password" autocomplete="new-password" placeholder="${a[al.anahtar + '_var'] ? 'Kayıtlı – değiştirmek için yazın' : ''}"></div>`
    : alan(al.anahtar, esc(al.etiket), a[al.anahtar] ?? al.varsayilan ?? '', al.genis ? 'tam autocomplete="off"' : 'autocomplete="off"')).join('');
  const s = sayfa(`${baslik('Ayarlar', esc(BEN.firma.unvan))}
  <form id="form">
    <div class="panel"><h2>Firma bilgileri</h2><p class="ipucu" style="margin:-6px 0 14px">Faturalarda satıcı olarak görünür.</p><div class="izgara">
      ${alan('firma_unvan', 'Ticari ünvan', a.firma_unvan, 'tam')}
      ${alan('firma_vkn', 'VKN / TCKN', a.firma_vkn, 'inputmode="numeric" maxlength="11"')}
      ${alan('firma_vergi_dairesi', 'Vergi dairesi', a.firma_vergi_dairesi)}
      ${alan('firma_mersis', 'MERSİS no', a.firma_mersis)}
      ${alan('firma_adres', 'Adres', a.firma_adres, 'tam')}
      ${alan('firma_ilce', 'İlçe', a.firma_ilce)}${alan('firma_il', 'İl', a.firma_il)}
      ${alan('firma_telefon', 'Telefon', a.firma_telefon)}${alan('firma_eposta', 'E-posta', a.firma_eposta)}
    </div></div>
    <div class="panel"><h2>Fatura serileri</h2><div class="izgara">
      ${alan('seri_efatura', 'e-Fatura serisi', a.seri_efatura, 'maxlength="3" style="text-transform:uppercase"')}
      ${alan('seri_earsiv', 'e-Arşiv serisi', a.seri_earsiv, 'maxlength="3" style="text-transform:uppercase"')}
    </div><p class="ipucu">3 karakter. Numaralar SERİ + YIL + 9 hane sıra şeklinde verilir (ör. ${esc(a.seri_efatura || 'EFT')}${new Date().getFullYear()}000000001). Başka programdan geçiyorsanız aynı yıl içinde çakışmaması için farklı bir seri seçin.</p></div>
    <div class="panel"><h2>e-Fatura entegratörü</h2><div class="izgara">
      <div><label for="a_entegrator">Entegratör</label><select id="a_entegrator" name="entegrator">${entler.map(e => `<option value="${e.kod}"${e.kod === (a.entegrator || 'deneme') ? ' selected' : ''}>${esc(e.ad)}</option>`).join('')}</select></div>
      <div id="ortamKap"><label for="a_ent_ortam">Ortam</label><select id="a_ent_ortam" name="ent_ortam">
        <option value="test"${a.ent_ortam !== 'canli' ? ' selected' : ''}>Test ortamı</option><option value="canli"${a.ent_ortam === 'canli' ? ' selected' : ''}>Canlı – gerçek fatura keser</option></select></div>
    </div><div class="izgara" id="entAlanlar" style="margin-top:14px"></div>
    <p class="ipucu">Kullanıcı bilgileri entegratörünüzden alınır. Önce test ortamında deneyin.</p>
    <div class="dugmeler"><button type="button" class="dugme" id="entTest">Bağlantıyı test et</button></div><div id="entSonuc"></div></div>
    <div class="panel"><h2>İrsaliye okuma ve otomatik tarama</h2><div class="izgara">
      <div class="tam"><label for="a_okuma_yontemi">Fotoğraf okuma yöntemi</label><select id="a_okuma_yontemi" name="okuma_yontemi">
        <option value="ocr"${(a.okuma_yontemi || 'ocr') === 'ocr' ? ' selected' : ''}>OCR (Tesseract) – ücretsiz, bu bilgisayarda çalışır</option>
        <option value="ai"${a.okuma_yontemi === 'ai' ? ' selected' : ''}>Yapay zekâ (Claude API) – ücretli, el yazısında daha iyi</option></select>
        <p class="ipucu">${a.tesseract_bulundu ? 'Tesseract bu bilgisayarda bulundu.' : '<strong>Tesseract bulunamadı.</strong> Kurulumu tekrar çalıştırın veya tesseract.exe yolunu yazın.'}</p></div>
      ${alan('tesseract_yolu', 'tesseract.exe yolu (boşsa otomatik bulunur)', a.tesseract_yolu, 'tam')}
      <div><label for="a_claude_api_anahtari">Claude API anahtarı (isteğe bağlı)</label><input id="a_claude_api_anahtari" name="claude_api_anahtari" type="password" autocomplete="off" placeholder="${a.claude_anahtar_var ? 'Kayıtlı – değiştirmek için yazın' : 'sk-ant-...'}"></div>
      ${alan('claude_model', 'Claude modeli', a.claude_model || 'claude-sonnet-5-5')}
      ${alan('tarama_saati', 'Günlük e-fatura tarama saati', a.tarama_saati || '09:00', 'type="time"')}
    </div><p class="ipucu">Her gün bu saatte gelen e-faturalar alınır ve irsaliyelerle eşleştirilir. Bilgisayar o saatte kapalıysa açıldığında yapılır.</p></div>
    <div class="dugmeler" style="margin-top:18px;justify-content:flex-end"><button class="dugme ana">Ayarları kaydet</button></div>
  </form>`);
  const entCiz = () => {
    const e = entler.find(x => x.kod === $('#a_entegrator').value) || entler[0];
    $('#entAlanlar').innerHTML = entAlan(e);
    $('#ortamKap').hidden = $('#entTest').hidden = e.kod === 'deneme';
  };
  $('#a_entegrator').onchange = entCiz; entCiz();
  $('#entTest').onclick = e => calis(e.currentTarget, async () => {
    $('#entSonuc').innerHTML = '<p class="ipucu">Bağlanılıyor…</p>';
    try {
      const r = await api('/entegrator-test', { method: 'POST' });
      $('#entSonuc').innerHTML = `<ul class="test-liste">${r.adimlar.map(x => `<li class="${x.ok ? 'ok' : 'hata'}"><strong>${x.ok ? '✓' : '✗'}</strong> ${esc(x.ad)}${x.not ? `<div class="ipucu">${esc(x.not)}</div>` : ''}</li>`).join('')}</ul>
        <p class="ipucu">${r.adimlar.every(x => x.ok) ? 'Bağlantı çalışıyor. Şimdi bir test müşterisine deneme faturası kesin.' : 'Hata mesajını ve entegratörün teknik dokümanını paylaşırsanız bağlantıyı düzeltebiliriz.'}</p>`;
    } catch (err) { $('#entSonuc').innerHTML = `<p class="ipucu borclu">${esc(err.message)}</p>`; throw err; }
  });
  $('#form', s).onsubmit = e => {
    e.preventDefault();
    const v = formOku(s);
    if (v.entegrator !== 'deneme' && v.ent_ortam === 'canli' && !(a.entegrator === v.entegrator && a.ent_ortam === 'canli')
        && !confirm('Canlı ortama geçiyorsunuz. Bundan sonra gönderilen faturalar resmi olarak kesilecek. Emin misiniz?')) return;
    calis(e.submitter, async () => {
      await api('/ayarlar', { method: 'PUT', body: v });
      BEN = await api('/ben'); modGuncelle(BEN.mod); bildir('Ayarlar kaydedildi.'); ayarlarSayfa();
    });
  };
}

// ------------------------------------------------------------------ Yönetim
function firmaFormu(sonra) {
  const { p, kapat } = pencere(`<form>${baslik('Yeni firma')}<div class="izgara">${alan('unvan', 'Firma ünvanı', '', 'required tam')}</div>
    <p class="ipucu">Her firmanın faturaları, carileri, stoğu ve ayarları ayrı tutulur. Firmayı ekledikten sonra ona geçip Ayarlar'dan bilgilerini girin.</p>
    <div class="pencere-alt"><div></div><div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Ekle</button></div></div></form>`);
  $('form', p).onsubmit = e => { e.preventDefault(); calis(e.submitter, async () => { const f = await api('/firmalar', { method: 'POST', body: formOku(p) }); kapat(); bildir('Firma eklendi.'); sonra(f); }); };
}

function kullaniciFormu(k, firmalar, sonra) {
  const yeni = !k.id, rolSec = fid => {
    const mevcut = (k.yetkiler || []).find(y => y.firma_id === fid)?.rol || '';
    return `<select data-firma="${fid}"><option value="">Erişim yok</option>${Object.entries(ROLAD()).map(([r, ad]) => `<option value="${r}"${r === mevcut ? ' selected' : ''}>${esc(ad)}</option>`).join('')}</select>`;
  };
  const { p, kapat } = pencere(`<form>${baslik(yeni ? 'Yeni kullanıcı' : esc(k.kullanici_adi))}<div class="izgara">
      ${yeni ? alan('kullanici_adi', 'Kullanıcı adı', '', 'required autocapitalize="none" autocomplete="off"') : ''}
      ${alan('ad', 'Ad soyad', k.ad || '')}
      <div><label for="a_sifre">${yeni ? 'Şifre' : 'Yeni şifre (değiştirmeyecekseniz boş)'}</label><input id="a_sifre" name="sifre" type="password" autocomplete="new-password" ${yeni ? 'required' : ''} minlength="8"></div>
      <div class="tam"><label class="onay" style="margin:0"><input type="checkbox" name="sistem_yoneticisi" ${k.sistem_yoneticisi ? 'checked' : ''}> Sistem yöneticisi (kullanıcı, firma ve lisans yönetebilir)</label></div>
      ${!yeni ? `<div class="tam"><label class="onay" style="margin:0"><input type="checkbox" name="aktif" ${k.aktif ? 'checked' : ''}> Hesap etkin</label></div>` : ''}
    </div>
    <h2 style="margin-top:18px">Firma yetkileri</h2>
    <div class="tablo-kap"><table class="liste"><tbody>${firmalar.filter(f => f.aktif).map(f => `<tr><td>${esc(f.unvan)}</td><td class="s">${rolSec(f.id)}</td></tr>`).join('')}</tbody></table></div>
    <p class="ipucu">Yönetici: her şey · Muhasebe: yönetim ve ayarlar hariç her şey · Personel: yalnızca irsaliye yükleme ve stok görme · Mali müşavir: salt okuma ve raporlar.</p>
    <div class="pencere-alt"><div></div><div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Kaydet</button></div></div></form>`);
  $('form', p).onsubmit = e => { e.preventDefault(); calis(e.submitter, async () => {
    const v = formOku(p);
    v.sistem_yoneticisi = $('[name=sistem_yoneticisi]', p).checked;
    if (!yeni) v.aktif = $('[name=aktif]', p).checked;
    v.yetkiler = $$('select[data-firma]', p).filter(x => x.value).map(x => ({ firma_id: +x.dataset.firma, rol: x.value }));
    await api(yeni ? '/kullanicilar' : '/kullanicilar/' + k.id, { method: yeni ? 'POST' : 'PUT', body: v });
    kapat(); bildir('Kullanıcı kaydedildi.'); sonra();
  }); };
}

async function yonetimSayfa() {
  const sekme = new URLSearchParams(location.hash.split('?')[1] || '').get('s') || (izin('sistem') ? 'kullanicilar' : 'yedek');
  const sekmeler = [['kullanicilar', 'Kullanıcılar', 'sistem'], ['firmalar', 'Firmalar', 'sistem'], ['lisans', 'Lisans', 'sistem'],
    ['yedek', 'Yedek ve günlük', 'yonetim'], ['erisim', 'Telefondan erişim', 'yonetim']].filter(x => izin(x[2]));
  const s = sayfa(`${baslik('Yönetim')}<div class="sekmeler" style="margin-bottom:16px">${sekmeler.map(([k, a]) => `<button data-s="${k}" class="${k === sekme ? 'aktif' : ''}">${a}</button>`).join('')}</div><div id="yIcerik"></div>`);
  $$('[data-s]', s).forEach(b => b.onclick = () => location.hash = '#/yonetim?s=' + b.dataset.s);
  const ic = $('#yIcerik', s);
  if (sekme === 'kullanicilar') {
    const [l, firmalar] = await Promise.all([api('/kullanicilar'), api('/firmalar')]);
    const fAd = Object.fromEntries(firmalar.map(f => [f.id, f.unvan]));
    ic.innerHTML = `<div class="dugmeler" style="margin-bottom:12px"><button class="dugme ana" id="yeniK">${ik('arti')}Yeni kullanıcı</button></div>
      <div class="tablo-kap"><table class="liste"><thead><tr><th>Kullanıcı</th><th class="gizle-m">Yetkiler</th><th class="gizle-m">Son giriş</th><th>Durum</th></tr></thead><tbody>
      ${l.map(k => `<tr class="tik" data-id="${k.id}"><td>${esc(k.kullanici_adi)}<div class="ikincil">${esc(k.ad || '')}${k.sistem_yoneticisi ? ' · sistem yöneticisi' : ''}</div></td>
        <td class="gizle-m">${k.yetkiler.map(y => `${esc(fAd[y.firma_id] || '?')}: ${esc(ROLAD()[y.rol] || y.rol)}`).join('<br>') || '<span class="ikincil">—</span>'}</td>
        <td class="gizle-m">${k.son_giris ? esc(new Date(k.son_giris + 'Z').toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' })) : '—'}</td>
        <td>${k.aktif ? '<span class="rozet ONAYLANDI">Etkin</span>' : '<span class="rozet">Pasif</span>'}</td></tr>`).join('')}</tbody></table></div>`;
    $('#yeniK').onclick = () => kullaniciFormu({ aktif: 1 }, firmalar, yonetimSayfa);
    $$('tr[data-id]', ic).forEach(tr => tr.onclick = () => kullaniciFormu(l.find(k => k.id === +tr.dataset.id), firmalar, yonetimSayfa));
  } else if (sekme === 'firmalar') {
    const firmalar = await api('/firmalar');
    ic.innerHTML = `<div class="dugmeler" style="margin-bottom:12px"><button class="dugme ana" id="yeniF">${ik('arti')}Yeni firma</button></div>
      <div class="tablo-kap"><table class="liste"><thead><tr><th>Firma</th><th>Durum</th><th></th></tr></thead><tbody>
      ${firmalar.map(f => `<tr><td>${esc(f.unvan)}${f.id === BEN.firma.id ? '<div class="ikincil">şu an açık</div>' : ''}</td><td>${f.aktif ? '<span class="rozet ONAYLANDI">Etkin</span>' : '<span class="rozet">Pasif</span>'}</td>
        <td class="s">${f.id !== BEN.firma.id ? `<button class="dugme kucuk" data-aktif="${f.id}" data-deger="${f.aktif ? 0 : 1}">${f.aktif ? 'Pasifleştir' : 'Etkinleştir'}</button>` : ''}</td></tr>`).join('')}</tbody></table></div>
      <p class="ipucu">Pasif firmanın verileri silinmez; kimse açamaz ve otomatik tarama yapılmaz.</p>`;
    $('#yeniF').onclick = () => firmaFormu(async () => { BEN = await api('/ben'); baslat(); location.hash = '#/yonetim?s=firmalar'; });
    $$('[data-aktif]', ic).forEach(b => b.onclick = () => calis(b, async () => { await api('/firmalar/' + b.dataset.aktif, { method: 'PUT', body: { aktif: b.dataset.deger === '1' } }); BEN = await api('/ben'); kabuk(); modGuncelle(BEN.mod); yonetimSayfa(); }));
  } else if (sekme === 'lisans') {
    const l = await api('/lisans');
    ic.innerHTML = `<div class="bakiye-kart ${l.gecerli ? 'alacakli' : 'borclu'}"><div><div class="etiket">${l.tur === 'deneme' ? 'Deneme sürümü' : 'Lisanslı' + (l.musteri ? ' – ' + esc(l.musteri) : '')}</div>
      <div class="deger">${l.gecerli ? `${l.kalan_gun} gün kaldı` : 'Süresi doldu'}</div><div class="ipucu">Bitiş: ${tarihTR(l.bitis)} · ${l.firma} firma · ${l.kullanici} kullanıcı</div></div></div>
      <div class="panel" style="margin-top:16px"><h2>Lisans anahtarı gir</h2>
        <p class="ipucu" style="margin:-6px 0 10px">Bu bilgisayarın makine kodu: <code>${esc(l.makine)}</code> — lisans alırken bu kodu bildirin.</p>
        <textarea id="anahtar" placeholder="Size gönderilen lisans anahtarını buraya yapıştırın" style="font-family:monospace;font-size:13px"></textarea>
        <div class="dugmeler" style="margin-top:10px"><button class="dugme ana" id="lisansGir">Lisansı etkinleştir</button></div></div>`;
    $('#lisansGir').onclick = e => calis(e.currentTarget, async () => { await api('/lisans', { method: 'POST', body: { anahtar: $('#anahtar').value } }); bildir('Lisans etkinleştirildi.'); BEN = await api('/ben'); baslat(); });
  } else if (sekme === 'yedek') {
    const g = await api('/gunluk');
    ic.innerHTML = `<div class="panel"><h2>Yedek</h2><p class="ipucu" style="margin:-6px 0 12px">Açık firmanın tüm verileri ve belge fotoğrafları tek zip dosyasına alınır. Haftada bir indirip güvenli bir yere koyun. Yedekte entegratör şifresi de bulunur; paylaşmayın.</p>
      <a class="dugme" href="/api/yedek">Yedeği indir</a></div>
      <div class="panel"><h2>Günlük</h2>${g.length ? `<table class="toplamlar">${g.map(x => `<tr><td class="ipucu" style="white-space:nowrap;vertical-align:top">${esc(new Date(x.zaman + 'Z').toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' }))}</td><td style="text-align:left">${esc(x.mesaj)}</td></tr>`).join('')}</table>` : '<p class="ipucu">Kayıt yok.</p>'}</div>`;
  } else if (sekme === 'erisim') {
    const r = await api('/erisim'), ts = r.tailscale;
    ic.innerHTML = `<div class="panel"><h2>Telefondan erişim</h2>
      <p><strong>Ofisteyken (aynı Wi-Fi):</strong> ${r.yerel.map(ip => `<code>http://${esc(ip)}:${r.port}</code>`).join(' veya ') || 'adres bulunamadı'}</p>
      <p><strong>Dışarıdayken:</strong> ${!ts.kurulu ? 'Tailscale kurulu değil. Kurulum kılavuzundaki “Her yerden erişim” adımını yapın.'
        : ts.bagli && ts.ad ? `Telefonda Tailscale açıkken <code>https://${esc(ts.ad)}</code> adresini kullanın.` : 'Tailscale kurulu ama bağlı değil; bilgisayarda Tailscale\'e giriş yapın.'}</p></div>`;
  }
}

function menuSayfa() {
  sayfa(`${baslik('Diğer', BEN.firmalar.length > 1 ? '' : esc(BEN.firma.unvan))}
    ${BEN.firmalar.length > 1 ? `<div class="panel" style="margin-bottom:14px"><label for="firmaSecM">Firma</label><select id="firmaSecM">${BEN.firmalar.map(f => `<option value="${f.id}"${f.id === BEN.firma.id ? ' selected' : ''}>${esc(f.unvan)}</option>`).join('')}</select></div>` : ''}
    <div class="tablo-kap"><table class="liste"><tbody>
    ${gorunenMenu().slice(1).map(([h, a, i]) => `<tr class="tik" data-git="${h}"><td style="display:flex;gap:12px;align-items:center">${ik(i)}${a}</td></tr>`).join('')}
    <tr class="tik" id="sifreM"><td>Şifremi değiştir</td></tr><tr class="tik" id="cikisM"><td>Çıkış yap (${esc(BEN.kullanici.kullanici_adi)})</td></tr></tbody></table></div>
    ${MODAD[MOD] ? `<p class="ipucu" style="margin-top:14px">${MODAD[MOD]}</p>` : ''}`);
  $$('tr[data-git]').forEach(tr => tr.onclick = () => location.hash = tr.dataset.git);
  $('#sifreM').onclick = sifreFormu;
  $('#cikisM').onclick = async () => { await api('/cikis', { method: 'POST' }); BEN = null; baslat(); };
  if ($('#firmaSecM')) $('#firmaSecM').onchange = e => calis(null, async () => { await api('/firma-sec', { method: 'POST', body: { firma_id: +e.target.value } }); location.hash = '#/'; baslat(); });
}

// ------------------------------------------------------------------ Fotoğraf yükleme
function fotoHazirla(dosya, enFazla = 2400) {
  // Telefon fotoğraflarını küçültüp JPEG'e çevirir (iPhone HEIC dahil, tarayıcı destekliyorsa)
  return new Promise((coz, red) => {
    const url = URL.createObjectURL(dosya), img = new Image();
    img.onload = () => {
      const oran = Math.min(1, enFazla / Math.max(img.width, img.height));
      const c = document.createElement('canvas');
      c.width = Math.round(img.width * oran); c.height = Math.round(img.height * oran);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url); coz(c.toDataURL('image/jpeg', 0.88));
    };
    img.onerror = () => { URL.revokeObjectURL(url); red(new Error(`${dosya.name} açılamadı. JPEG veya PNG fotoğraf seçin.`)); };
    img.src = url;
  });
}

function dosyaSec(kamera, coklu = true) {
  return new Promise(coz => {
    const i = document.createElement('input');
    i.type = 'file'; i.accept = 'image/*'; i.multiple = coklu;
    if (kamera) i.capture = 'environment';
    i.onchange = () => coz([...i.files]);
    i.click();
  });
}

async function irsaliyeYukleSec(kamera) {
  if (kamera === undefined) {
    const mobil = matchMedia('(max-width: 820px)').matches;
    if (mobil) {
      const secim = await new Promise(coz => {
        const { p, kapat } = pencere(`<h2>İrsaliye fotoğrafı</h2><div class="secenekler">
          <button class="dugme ana" data-k="1">${ik('kamera')}Fotoğraf çek</button>
          <button class="dugme" data-k="0">Galeriden seç</button><button class="dugme" data-kapat>Vazgeç</button></div>`);
        $$('[data-k]', p).forEach(b => b.onclick = () => { kapat(); coz(b.dataset.k === '1'); });
      });
      kamera = secim;
    } else kamera = false;
  }
  const dosyalar = await dosyaSec(kamera);
  if (!dosyalar.length) return;
  const b = $('#bildirim');
  b.textContent = `${dosyalar.length > 1 ? dosyalar.length + ' sayfa' : 'Fotoğraf'} okunuyor, lütfen bekleyin…`; b.className = 'goster';
  try {
    const fotolar = await Promise.all(dosyalar.map(d => fotoHazirla(d)));
    const i = await api('/irsaliyeler/yukle', { method: 'POST', body: { fotolar } });
    bildir(i.durum === 'KONTROL' ? 'Bazı bilgiler okunamadı, lütfen kontrol edin.' : i.durum === 'ESLESTI' ? `İrsaliye kaydedildi ve ${i.fatura_no} faturasıyla eşleşti.` : 'İrsaliye okundu ve kaydedildi.');
    location.hash = '#/irsaliye/' + i.id;
  } catch (e) { bildir(e.message, true); }
}

// ------------------------------------------------------------------ Ortak: kalem düzenleyici ve tedarikçi seçici
function kalemEditoru(kap, satirlar, fiyatli, urunler = null) {
  const urunSec = r => `<select data-a="urun_id" aria-label="Stok ürünü"><option value="">Otomatik bul</option>
    <option value="0"${r.urun_id === 0 ? ' selected' : ''}>Stoka girmesin</option>
    ${urunler.filter(u => u.stok_takibi).map(u => `<option value="${u.id}"${+r.urun_id === u.id ? ' selected' : ''}>${esc(u.ad)}</option>`).join('')}
    <option value="yeni">+ Yeni ürün olarak ekle</option></select>`;
  const birimSec = b => Object.entries(BIRIMLER).map(([k, v]) => `<option value="${k}"${k === b ? ' selected' : ''}>${v}</option>`).join('');
  const satir = r => `<tr><td><input data-a="ad" value="${esc(r.ad || '')}" placeholder="Ürün / açıklama" aria-label="Ürün"></td>
    <td class="n" data-e="Miktar"><input data-a="miktar" type="number" step="any" min="0" inputmode="decimal" value="${r.miktar ?? 1}"></td>
    <td class="b" data-e="Birim"><select data-a="birim">${birimSec(r.birim || 'C62')}</select></td>
    ${fiyatli ? `<td class="f" data-e="Birim fiyat"><input data-a="birim_fiyat" type="number" step="any" min="0" inputmode="decimal" value="${r.birim_fiyat ?? ''}"></td>
    <td class="k" data-e="KDV"><select data-a="kdv">${[20, 10, 1, 0].map(o => `<option value="${o}"${+(r.kdv ?? 20) === o ? ' selected' : ''}>%${o}</option>`).join('')}</select></td>` : ''}
    ${urunler ? `<td class="u" data-e="Stok ürünü">${urunSec(r)}</td>` : ''}
    <td class="sil"><button type="button" class="sil-dugme" aria-label="Satırı sil">${ik('sil')}</button></td></tr>`;
  kap.innerHTML = `<table class="satirlar"><thead><tr><th>Ürün</th><th class="n">Miktar</th><th class="b">Birim</th>${fiyatli ? '<th class="f">Birim fiyat (KDV hariç)</th><th class="k">KDV</th>' : ''}${urunler ? '<th class="u">Stok ürünü</th>' : ''}<th class="sil"></th></tr></thead>
    <tbody>${(satirlar.length ? satirlar : [{}]).map(satir).join('')}</tbody></table>
    <div class="satir-ekle"><button type="button" class="dugme kucuk">${ik('arti')}Satır ekle</button></div>`;
  const tb = $('tbody', kap);
  $('.satir-ekle button', kap).onclick = () => { tb.insertAdjacentHTML('beforeend', satir({})); $('tr:last-child input', tb).focus(); };
  tb.onclick = e => { const b = e.target.closest('.sil-dugme'); if (b) { b.closest('tr').remove(); if (!tb.children.length) tb.insertAdjacentHTML('beforeend', satir({})); } };
  return () => $$('tr', tb).map(tr => Object.fromEntries($$('[data-a]', tr).map(i => [i.dataset.a, i.value]))).filter(r => r.ad.trim());
}

function tedarikciSecici(kap, cariler, bas) {
  // bas: {cari_id, unvan, vkn}
  let secili = cariler.find(c => c.id === bas.cari_id) || (bas.vkn ? cariler.find(c => c.vkn && c.vkn === bas.vkn) : null) || null;
  kap.innerHTML = `<div class="izgara"><div class="oneri"><label for="tUnvan">Tedarikçi</label><input id="tUnvan" autocomplete="off" value="${esc(secili ? secili.unvan : bas.unvan || '')}" placeholder="Ünvan yazın veya seçin"><div class="oneri-liste" hidden></div></div>
    <div><label for="tVkn">VKN / TCKN</label><input id="tVkn" inputmode="numeric" maxlength="11" value="${esc(secili ? secili.vkn : bas.vkn || '')}"></div></div>
    <p class="ipucu" id="tBilgi"></p>`;
  const u = $('#tUnvan', kap), v = $('#tVkn', kap), l = $('.oneri-liste', kap), bilgi = $('#tBilgi', kap);
  const yaz = () => { bilgi.textContent = secili ? `Kayıtlı cari: ${secili.unvan}` : (u.value || v.value ? 'Kayıtlı değil; kaydedince yeni tedarikçi olarak eklenir (aynı VKN varsa ona bağlanır).' : ''); };
  const goster = () => {
    const q = u.value.toLocaleLowerCase('tr');
    const e = cariler.filter(c => c.unvan.toLocaleLowerCase('tr').includes(q) || (c.vkn || '').includes(q)).slice(0, 8);
    l.innerHTML = e.map(c => `<button type="button" data-id="${c.id}">${esc(c.unvan)}<small>${esc(c.vkn || '')} ${CTUR[c.tur] ? '– ' + CTUR[c.tur] : ''}</small></button>`).join('');
    l.hidden = !e.length;
  };
  u.onfocus = goster; u.oninput = () => { secili = null; yaz(); goster(); };
  v.oninput = () => { if (secili && v.value !== secili.vkn) { secili = null; yaz(); } };
  l.onmousedown = e => e.preventDefault();
  l.onclick = e => { const b = e.target.closest('button'); if (!b) return; secili = cariler.find(c => c.id === +b.dataset.id); u.value = secili.unvan; v.value = secili.vkn || ''; l.hidden = true; yaz(); };
  u.onblur = () => setTimeout(() => l.hidden = true, 150);
  yaz();
  return () => ({ cari_id: secili ? secili.id : null, gonderen_unvan: u.value.trim(), gonderen_vkn: v.value.replace(/\D/g, '') });
}

const fotoSeridi = fotolar => fotolar.length ? `<div class="foto-seridi">${fotolar.map((f, i) => `<a href="/belge/${esc(f)}" target="_blank" rel="noopener"><img src="/belge/${esc(f)}" alt="Belge sayfa ${i + 1}" loading="lazy"></a>`).join('')}</div>` : '';

// ------------------------------------------------------------------ İrsaliyeler
async function irsaliyelerSayfa() {
  const d = new URLSearchParams(location.hash.split('?')[1] || '').get('d') || '';
  const s = sayfa(`${baslik('İrsaliyeler', 'Fotoğrafını yüklediğiniz irsaliyeler her gün gelen e-faturalarla eşleştirilir.',
    `<a class="dugme" href="#/irsaliye/yeni">Elle gir</a><button class="dugme ana" id="yukle">${ik('kamera')}Fotoğraf yükle</button>`)}
    <div class="sekmeler" id="dSec" style="margin-bottom:14px"><button data-d="">Tümü</button>${Object.entries(IDURUM).map(([k, v]) => `<button data-d="${k}">${v}</button>`).join('')}</div>
    <div id="tablo"></div>`);
  $('#yukle').onclick = () => irsaliyeYukleSec();
  $$('#dSec button', s).forEach(b => { b.classList.toggle('aktif', b.dataset.d === d); b.onclick = () => location.hash = '#/irsaliyeler' + (b.dataset.d ? '?d=' + b.dataset.d : ''); });
  const l = await api('/irsaliyeler' + (d ? '?durum=' + d : ''));
  $('#tablo', s).innerHTML = !l.length ? `<div class="panel bos"><p>${d ? 'Bu durumda irsaliye yok.' : 'Henüz irsaliye yok. Tedarikçiden gelen irsaliyenin fotoğrafını çekip yükleyin.'}</p></div>`
    : `<div class="tablo-kap"><table class="liste"><thead><tr><th></th><th>Tedarikçi</th><th class="gizle-m">İrsaliye no</th><th class="gizle-m">Tarih</th><th>Durum</th></tr></thead><tbody>
    ${l.map(i => `<tr class="tik" data-id="${i.id}"><td class="kucuk-foto">${i.foto ? `<img src="/belge/${esc(i.foto)}" alt="" loading="lazy">` : ''}</td>
      <td>${esc(i.cari_unvan || i.gonderen_unvan || 'Tedarikçi okunamadı')}<div class="ikincil">${esc(i.irsaliye_no || '—')} ${tarihTR(i.tarih)}</div></td>
      <td class="gizle-m sayi">${esc(i.irsaliye_no || '—')}</td><td class="gizle-m">${tarihTR(i.tarih)}</td>
      <td><span class="rozet ${IROZET[i.durum]}">${IDURUM[i.durum]}</span>${i.durum === 'ESLESTI' ? `<div class="ikincil">${esc(i.fatura_no)}</div>` : i.durum === 'ONERI' ? `<div class="ikincil">${esc(i.oneri_fatura_no)}?</div>` : ''}</td></tr>`).join('')}
    </tbody></table></div>`;
  $$('tr[data-id]', s).forEach(tr => tr.onclick = () => location.hash = '#/irsaliye/' + tr.dataset.id);
}

async function irsaliyeDetay(id) {
  sayfa(baslik(id ? 'İrsaliye' : 'İrsaliyeyi elle gir'));
  const [i, cariler, alislar, urunler] = await Promise.all([
    id ? api('/irsaliyeler/' + id) : { irsaliye_no: '', tarih: bugun(), satirlar: [], fotolar: [], durum: 'YENI', okuma: {} },
    api('/cariler?tur=tedarikci'), api('/gelen'), api('/urunler')]);
  const hataMsj = i.okuma?._hata || i.okuma?.okunamayan || '';
  let eslesme = '';
  if (i.durum === 'ESLESTI') eslesme = `<div class="eslesme ok"><div><strong>Faturayla eşleşti:</strong> <a href="#/alis/${i.gelen_fatura_id}">${esc(i.fatura_no)}</a> (${tarihTR(i.fatura_tarih)})<div class="ipucu">${esc(i.eslesme_aciklama || '')}</div></div>
    <button class="dugme kucuk" data-islem="kaldir">Eşleşmeyi kaldır</button></div>`;
  else if (i.durum === 'ONERI') eslesme = `<div class="eslesme oneri-kutu"><div><strong>Bu irsaliyenin faturası bu olabilir:</strong> <a href="#/alis/${i.oneri_fatura_id}">${esc(i.oneri_fatura_no)}</a> – ${tarihTR(i.oneri_tarih)} – ${tl(i.oneri_tutar)}
    <div class="ipucu">${esc(i.eslesme_aciklama || '')} (uyum puanı ${i.eslesme_puani}/100)</div></div>
    <div class="dugmeler"><button class="dugme ana kucuk" data-islem="onayla">Evet, eşleştir</button><button class="dugme kucuk" data-islem="reddet">Hayır, bu değil</button></div></div>`;
  else if (i.durum === 'BEKLIYOR') {
    const adaylar = alislar.filter(g => !i.gonderen_vkn || g.gonderen_vkn === i.gonderen_vkn);
    eslesme = `<div class="eslesme"><div><strong>Fatura bekleniyor.</strong><div class="ipucu">Tedarikçinin e-faturası gelince otomatik eşleştirilir. İsterseniz şimdi elle seçebilirsiniz.</div></div>
      ${adaylar.length ? `<div class="dugmeler"><select id="elleSec" style="width:auto"><option value="">Fatura seçin…</option>${adaylar.map(g => `<option value="${g.id}">${esc(g.fatura_no)} – ${tarihTR(g.tarih)} – ${tl(g.tutar)}</option>`).join('')}</select><button class="dugme kucuk" data-islem="bagla">Eşleştir</button></div>` : ''}</div>`;
  }
  const s = sayfa(`${baslik(id ? esc(i.cari_unvan || i.gonderen_unvan || 'İrsaliye') : 'İrsaliyeyi elle gir', id ? `<span class="rozet ${IROZET[i.durum]}">${IDURUM[i.durum]}</span>` : 'Fotoğrafı olmayan veya okunamayan irsaliyeler için.',
      id ? `<button class="dugme tehlike" id="silI">${ik('sil')}Sil</button>` : '')}
    ${eslesme}
    ${i.durum === 'KONTROL' ? `<div class="uyari-seridi"><span>Fotoğraftan okunan bilgileri kontrol edip kaydedin.${hataMsj ? ' ' + esc(hataMsj) : ''}</span></div>` : ''}
    <div class="irs-duzen${i.fotolar.length ? '' : ' fotosuz'}">
      ${i.fotolar.length ? `<div class="irs-foto">${fotoSeridi(i.fotolar)}<p class="ipucu">Büyütmek için fotoğrafa dokunun.</p></div>` : ''}
      <form class="panel" id="form">
        <div class="izgara" style="margin-bottom:14px">
          <div><label for="no">İrsaliye no</label><input id="no" value="${esc(i.irsaliye_no)}" style="text-transform:uppercase" required></div>
          <div><label for="tarih">İrsaliye tarihi</label><input id="tarih" type="date" value="${i.tarih || ''}" required></div>
        </div>
        <div id="ted"></div>
        <h2 style="margin-top:18px">Ürünler</h2><p class="ipucu" style="margin:-8px 0 8px">Kaydedince seçilen ürünler stoka girer. Bu tedarikçi için yaptığınız eşleştirme sonraki irsaliyelerde hatırlanır.</p><div id="kalemler" class="kalem-kap"></div>
        <label for="not" style="margin-top:14px">Not</label><textarea id="not">${esc(i.notlar || '')}</textarea>
        <div class="dugmeler" style="margin-top:16px;justify-content:flex-end"><button class="dugme ana">${i.durum === 'KONTROL' ? 'Onayla ve kaydet' : 'Kaydet'}</button></div>
      </form>
    </div>`);
  const tedarikci = tedarikciSecici($('#ted', s), cariler, { cari_id: i.cari_id, unvan: i.gonderen_unvan, vkn: i.gonderen_vkn });
  const kalemler = kalemEditoru($('#kalemler', s), i.satirlar, false, urunler);
  $('#form', s).onsubmit = e => {
    e.preventDefault();
    calis(e.submitter, async () => {
      const govde = { irsaliye_no: $('#no').value, tarih: $('#tarih').value, notlar: $('#not').value, satirlar: kalemler(), ...tedarikci() };
      const k = await api(id ? '/irsaliyeler/' + id : '/irsaliyeler', { method: id ? 'PUT' : 'POST', body: govde });
      bildir(k.durum === 'ESLESTI' ? `Kaydedildi ve ${k.fatura_no} faturasıyla eşleşti.` : k.durum === 'ONERI' ? 'Kaydedildi. Olası bir fatura bulundu, onayınızı bekliyor.' : 'Kaydedildi.');
      if (id) irsaliyeDetay(id); else location.hash = '#/irsaliye/' + k.id;
    });
  };
  $$('[data-islem]', s).forEach(b => b.onclick = e => calis(e.currentTarget, async () => {
    const islem = b.dataset.islem, govde = { islem };
    if (islem === 'bagla') { govde.gelen_id = +$('#elleSec').value; if (!govde.gelen_id) throw new Error('Önce bir fatura seçin.'); }
    const k = await api(`/irsaliyeler/${id}/eslesme`, { method: 'POST', body: govde });
    bildir({ onayla: 'Eşleştirildi.', reddet: 'Öneri reddedildi.', kaldir: 'Eşleşme kaldırıldı.', bagla: 'Eşleştirildi.' }[islem]);
    irsaliyeDetay(id);
  }));
  if ($('#silI')) $('#silI').onclick = e => confirm('İrsaliye ve fotoğrafları silinsin mi?') && calis(e.currentTarget, async () => { await api('/irsaliyeler/' + id, { method: 'DELETE' }); bildir('İrsaliye silindi.'); location.hash = '#/irsaliyeler'; });
}

// ------------------------------------------------------------------ Alış faturaları
async function alisSayfa() {
  const s = sayfa(`${baslik('Alış faturaları', 'Tedarikçilerden gelen e-faturalar ve elle girdiğiniz kağıt faturalar',
    `<a class="dugme" href="#/alis/yeni">Elle gir</a><button class="dugme ana" id="yenile">Yeni faturaları al</button>`)}<div id="tablo"></div>`);
  const ciz = liste => {
    $('#tablo', s).innerHTML = !liste.length ? `<div class="panel bos"><p>Henüz alış faturası yok. QNB'deki yeni e-faturaları almak için yukarıdaki düğmeyi kullanın.</p></div>`
      : `<div class="tablo-kap"><table class="liste"><thead><tr><th>Tedarikçi</th><th class="gizle-m">Fatura no</th><th class="gizle-m">Tarih</th><th class="gizle-m">İrsaliye</th><th class="s">Tutar</th></tr></thead><tbody>
      ${liste.map(g => `<tr class="tik" data-id="${g.id}"><td>${esc(g.gonderen_unvan)}<div class="ikincil">${g.kaynak === 'manuel' ? 'Elle girildi' : 'e-Fatura'}${g.tip === 'IADE' ? ' – iade' : ''}</div></td>
        <td class="gizle-m sayi">${esc(g.fatura_no)}</td><td class="gizle-m">${tarihTR(g.tarih)}</td>
        <td class="gizle-m">${g.irsaliye_sayisi ? `<span class="rozet ONAYLANDI">${g.irsaliye_sayisi} irsaliye</span>` : (JSON.parse(g.irsaliye_nolar || '[]').length ? '<span class="rozet TASLAK">İrsaliye bekleniyor</span>' : '')}</td>
        <td class="s sayi">${para(g.tutar)} ${esc(g.para_birimi === 'TRY' ? 'TL' : g.para_birimi)}</td></tr>`).join('')}
      </tbody></table></div>`;
    $$('tr[data-id]', s).forEach(tr => tr.onclick = () => location.hash = '#/alis/' + tr.dataset.id);
  };
  ciz(await api('/gelen'));
  $('#yenile').onclick = e => calis(e.currentTarget, async () => { const r = await api('/gelen/yenile', { method: 'POST' }); ciz(r.liste); bildir(r.mesaj); });
}

async function alisDetay(id) {
  sayfa(baslik('Alış faturası'));
  const g = await api('/gelen/' + id);
  const s = sayfa(`${baslik(esc(g.gonderen_unvan), `${esc(g.fatura_no)} – ${tarihTR(g.tarih)} – ${g.kaynak === 'manuel' ? 'elle girildi' : 'e-Fatura'}`,
    `<a class="dugme" href="/goruntule/gelen/${id}" target="_blank" rel="noopener">Görüntüle / yazdır</a>
     ${g.xml_var ? `<a class="dugme" href="/api/gelen/${id}/xml">XML indir</a>` : ''}
     ${g.cari_id ? `<button class="dugme" id="odeme">Ödeme yap</button><a class="dugme" href="#/cari/${g.cari_id}">Cari hesap</a>` : ''}
     ${!g.irsaliyeler.length && g.satirlar.length ? `<button class="dugme" id="stokaAl">Stoka al</button>` : ''}
     ${g.tip !== 'IADE' ? `<button class="dugme ana" id="iade">İade faturası kes</button>` : ''}`)}
    <div class="panel"><p class="vade-satir" style="margin:0">Vade: <strong>${g.vade_tarihi ? tarihTR(g.vade_tarihi) : 'Peşin'}</strong> ${gecikmeRozet(gecikmeGun(g.vade_tarihi || g.tarih))} <button class="dugme kucuk" id="vadeD">Vadeyi değiştir</button></p></div>
    <div class="panel"><h2>İrsaliyeler</h2>
      ${g.irsaliyeler.length ? `<ul class="duz-liste">${g.irsaliyeler.map(x => `<li><a href="#/irsaliye/${x.id}">${esc(x.irsaliye_no)}</a> – ${tarihTR(x.tarih)} <span class="ipucu">${esc(x.eslesme_aciklama || '')}</span></li>`).join('')}</ul>`
        : `<p class="ipucu">Bu faturayla eşleşmiş irsaliye yok.${g.irsaliye_nolar.length ? ' Faturada geçen irsaliye no: ' + g.irsaliye_nolar.map(esc).join(', ') + '. Bu irsaliyenin fotoğrafını yüklediğinizde otomatik eşleşir.' : ''}</p>`}
    </div>
    <div class="panel"><div class="tablo-kap" style="border:0"><table class="liste"><thead><tr><th>Açıklama</th><th class="s">Miktar</th><th class="s gizle-m">Birim fiyat</th><th class="s gizle-m">KDV</th><th class="s">Tutar</th></tr></thead><tbody>
      ${g.satirlar.map(r => `<tr><td>${esc(r.ad)}</td><td class="s sayi">${esc(r.miktar)} ${esc(BIRIMLER[r.birim] || r.birim || '')}</td><td class="s sayi gizle-m">${r.birim_fiyat ? para(r.birim_fiyat) : ''}</td><td class="s gizle-m">${r.kdv !== null && r.kdv !== undefined && r.kdv !== '' ? '%' + esc(r.kdv) : ''}</td><td class="s sayi">${r.tutar ? para(r.tutar) : ''}</td></tr>`).join('') || '<tr><td colspan="5" class="ipucu">Satır bilgisi yok.</td></tr>'}
    </tbody></table></div>
    <table class="toplamlar" style="max-width:320px;margin:16px 0 0 auto">
      ${g.matrah !== null ? `<tr><td>KDV hariç</td><td class="sayi">${tl(g.matrah)}</td></tr><tr><td>KDV</td><td class="sayi">${tl(g.kdv_toplam)}</td></tr>` : ''}
      <tr class="genel"><td>Toplam</td><td class="sayi">${tl(g.tutar)}</td></tr></table></div>
    ${g.fotolar.length ? `<div class="panel"><h2>Fotoğraflar</h2>${fotoSeridi(g.fotolar)}</div>` : ''}
    ${g.iadeler.length ? `<div class="panel"><h2>Bu faturaya kesilen iadeler</h2><ul class="duz-liste">${g.iadeler.map(x => `<li><a href="#/fatura/${x.id}">${esc(x.fatura_no || 'Taslak')}</a> – ${tl(x.genel_toplam)} ${rozet(x.durum)}</li>`).join('')}</ul></div>` : ''}
    ${g.kaynak === 'manuel' ? `<div style="margin-top:16px"><button class="dugme tehlike" id="silG">${ik('sil')}Faturayı sil</button></div>` : ''}`);
  $('#vadeD').onclick = () => vadeFormu(g.vade_tarihi, g.tarih, `/gelen/${id}/vade`, () => alisDetay(id));
  if ($('#stokaAl')) $('#stokaAl').onclick = () => stokaAlFormu(id, () => alisDetay(id));
  if ($('#odeme')) $('#odeme').onclick = () => hareketFormu('ODEME', { cari_id: g.cari_id, cari_unvan: g.gonderen_unvan, tutar: g.tutar, fatura_ref: 'alis:' + id, belge_no: g.fatura_no }, () => alisDetay(id));
  if ($('#iade')) $('#iade').onclick = e => calis(e.currentTarget, async () => {
    const t = await api(`/gelen/${id}/iade-taslak`, { method: 'POST' });
    bildir('İade taslağı oluşturuldu. İade edilen ürün ve miktarları düzenleyin.');
    location.hash = `#/fatura/${t.id}/duzenle`;
  });
  if ($('#silG')) $('#silG').onclick = e => confirm('Fatura silinsin mi?') && calis(e.currentTarget, async () => { await api('/gelen/' + id, { method: 'DELETE' }); bildir('Fatura silindi.'); location.hash = '#/alis'; });
}

async function alisElle() {
  sayfa(baslik('Alış faturası gir'));
  const cariler = await api('/cariler?tur=tedarikci');
  let fotolar = [];
  const s = sayfa(`${baslik('Alış faturası gir', 'Kağıt veya e-fatura dışında gelen faturalar için. Fotoğrafını yüklerseniz bilgiler otomatik doldurulur.')}
    <div class="panel"><div class="dugmeler"><button class="dugme" id="fotoOku">${ik('kamera')}Fotoğraftan doldur</button></div><div id="fotolar"></div></div>
    <form class="panel" id="form">
      <div id="ted"></div>
      <div class="izgara" style="margin-top:14px">
        <div><label for="no">Fatura no</label><input id="no" required style="text-transform:uppercase"></div>
        <div><label for="tarih">Fatura tarihi</label><input id="tarih" type="date" value="${bugun()}" required></div>
        <div><label for="vade">Vade tarihi</label><input id="vade" type="date"><div class="ipucu">Boş bırakırsanız tedarikçinin vade günü uygulanır.</div></div>
        <div><label for="irs">İrsaliye no (varsa, virgülle)</label><input id="irs"></div>
        <div><label for="tutar">Genel toplam (satır girmeyecekseniz)</label><input id="tutar" type="number" step="any" min="0" inputmode="decimal"></div>
      </div>
      <h2 style="margin-top:18px">Satırlar</h2><div id="kalemler" class="kalem-kap"></div>
      <label for="not" style="margin-top:14px">Not</label><textarea id="not"></textarea>
      <div class="dugmeler" style="margin-top:16px;justify-content:flex-end"><button class="dugme ana">Kaydet</button></div>
    </form>`);
  let tedarikci = tedarikciSecici($('#ted', s), cariler, {});
  let kalemler = kalemEditoru($('#kalemler', s), [], true);
  $('#fotoOku').onclick = async e => {
    const dosyalar = await dosyaSec(false); if (!dosyalar.length) return;
    calis(e.currentTarget, async () => {
      bildir('Fotoğraf okunuyor…');
      const r = await api('/gelen/oku', { method: 'POST', body: { fotolar: await Promise.all(dosyalar.map(d => fotoHazirla(d))) } });
      fotolar = fotolar.concat(r.fotolar); $('#fotolar', s).innerHTML = fotoSeridi(fotolar);
      const o = r.okuma || {};
      if (o._hata) return bildir(o._hata, true);
      if (o.belge_no) $('#no').value = o.belge_no;
      if (o.tarih) $('#tarih').value = o.tarih;
      if (o.genel_toplam) $('#tutar').value = o.genel_toplam;
      const g = o.gonderen || {};
      const mevcut = cariler.find(c => g.vkn && c.vkn === g.vkn);
      tedarikci = tedarikciSecici($('#ted', s), cariler, mevcut ? { cari_id: mevcut.id } : { unvan: g.unvan, vkn: g.vkn });
      if (o.satirlar?.length) kalemler = kalemEditoru($('#kalemler', s), o.satirlar, true);
      bildir(o.okunamayan ? 'Okundu. ' + o.okunamayan + ' – lütfen kontrol edin.' : 'Okundu, lütfen kontrol edin.');
    });
  };
  $('#form', s).onsubmit = e => {
    e.preventDefault();
    calis(e.submitter, async () => {
      const g = await api('/gelen', { method: 'POST', body: { ...tedarikci(), fatura_no: $('#no').value, tarih: $('#tarih').value, vade_tarihi: $('#vade').value,
        irsaliye_nolar: $('#irs').value, tutar: $('#tutar').value, notlar: $('#not').value, satirlar: kalemler(), fotolar } });
      bildir('Alış faturası kaydedildi.'); location.hash = '#/alis/' + g.id;
    });
  };
}


// ------------------------------------------------------------------ Cari hesap
const bakiyeHtml = b => Math.abs(b) < 0.005 ? '<span class="ikincil">—</span>'
  : `<span class="sayi ${b > 0 ? 'alacakli' : 'borclu'}">${para(Math.abs(b))}</span><div class="ikincil">${b > 0 ? 'size borçlu' : 'siz borçlusunuz'}</div>`;
const ODEME_SEKILLERI = ['Nakit', 'Havale/EFT', 'Kredi kartı', 'Çek', 'Senet', 'Diğer'];
const HTUR = {
  TAHSILAT: 'Tahsilat al', ODEME: 'Ödeme yap', DEVIR_BORC: 'Açılış bakiyesi', DEVIR_ALACAK: 'Açılış bakiyesi',
  GELIR: 'Diğer gelir', MASRAF: 'Masraf gir', VIRMAN: 'Hesaplar arası transfer',
};

async function hareketFormu(tur, on = {}, sonra) {
  const [hesaplar, cariler, ekstre] = await Promise.all([
    api('/hesaplar'), ['TAHSILAT', 'ODEME'].includes(tur) && !on.cari_id ? api('/cariler') : null,
    on.cari_id && ['TAHSILAT', 'ODEME'].includes(tur) ? api(`/cariler/${on.cari_id}/ekstre`) : null]);
  const cariAlan = ['TAHSILAT', 'ODEME', 'DEVIR_BORC', 'DEVIR_ALACAK'].includes(tur);
  const devir = tur.startsWith('DEVIR');
  const faturalar = (ekstre?.faturalar || []).filter(x => (tur === 'TAHSILAT') === (x.yon === 'satis'));
  const { p, kapat } = pencere(`<form>${baslik(HTUR[tur], on.cari_unvan ? esc(on.cari_unvan) : '')}
    <div class="izgara">
      ${cariAlan && !on.cari_id ? `<div class="tam"><label for="h_cari">Cari</label><select id="h_cari" name="cari_id" required><option value="">Seçin…</option>${(cariler || []).map(c => `<option value="${c.id}">${esc(c.unvan)}</option>`).join('')}</select></div>` : ''}
      ${devir ? `<div class="tam"><label for="h_tur">Bakiye yönü</label><select id="h_tur" name="tur">
        <option value="DEVIR_BORC"${tur === 'DEVIR_BORC' ? ' selected' : ''}>Cari bize borçlu (alacağımız var)</option>
        <option value="DEVIR_ALACAK"${tur === 'DEVIR_ALACAK' ? ' selected' : ''}>Biz cariye borçluyuz</option></select>
        <p class="ipucu">Orion'dan geçerken, geçiş tarihindeki bakiyeyi girin. Önceki faturaları tekrar girmenize gerek yok.</p></div>` : `<input type="hidden" name="tur" value="${tur}">`}
      <div><label for="h_tarih">Tarih</label><input id="h_tarih" name="tarih" type="date" value="${on.tarih || bugun()}" required></div>
      <div><label for="h_tutar">Tutar (TL)</label><input id="h_tutar" name="tutar" type="number" step="0.01" min="0.01" inputmode="decimal" value="${on.tutar ?? ''}" required></div>
      ${devir ? '' : `<div><label for="h_hesap">${tur === 'VIRMAN' ? 'Çıkan hesap' : tur === 'TAHSILAT' || tur === 'GELIR' ? 'Giren hesap' : 'Çıkan hesap'}</label><select id="h_hesap" name="hesap_id" required>${hesaplar.map(h => `<option value="${h.id}"${on.hesap_id === h.id ? ' selected' : ''}>${esc(h.ad)} (${tl(h.bakiye)})</option>`).join('')}</select></div>`}
      ${tur === 'VIRMAN' ? `<div><label for="h_hedef">Giren hesap</label><select id="h_hedef" name="hedef_hesap_id" required>${hesaplar.map((h, i) => `<option value="${h.id}"${i === 1 ? ' selected' : ''}>${esc(h.ad)}</option>`).join('')}</select></div>` : ''}
      ${['TAHSILAT', 'ODEME'].includes(tur) ? `<div><label for="h_sekil">Ödeme şekli</label><select id="h_sekil" name="odeme_sekli">${ODEME_SEKILLERI.map(o => `<option>${o}</option>`).join('')}</select></div>` : ''}
      ${faturalar.length ? `<div class="tam"><label for="h_fat">İlgili fatura (isteğe bağlı)</label><select id="h_fat" name="fatura_ref"><option value="">—</option>${faturalar.map(x => `<option value="${x.yon}:${x.id}"${on.fatura_ref === x.yon + ':' + x.id ? ' selected' : ''}>${esc(x.fatura_no)} – ${tarihTR(x.tarih)} – ${tl(x.tutar)}</option>`).join('')}</select></div>` : ''}
      ${alan('belge_no', 'Belge / dekont no', on.belge_no || '')}
      ${alan('aciklama', tur === 'MASRAF' || tur === 'GELIR' ? 'Açıklama (ör. kira, elektrik)' : 'Açıklama', on.aciklama || '', tur === 'MASRAF' || tur === 'GELIR' ? 'required' : '')}
    </div>
    ${ekstre ? `<p class="ipucu">Güncel bakiye: ${Math.abs(ekstre.genel_bakiye) < 0.005 ? 'yok' : tl(Math.abs(ekstre.genel_bakiye)) + (ekstre.genel_bakiye > 0 ? ' (size borçlu)' : ' (siz borçlusunuz)')}</p>` : ''}
    <div class="pencere-alt"><div></div><div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Kaydet</button></div></div></form>`);
  $('form', p).onsubmit = e => {
    e.preventDefault();
    const v = formOku(p);
    if (on.cari_id) v.cari_id = on.cari_id;
    calis(e.submitter, async () => { await api('/hareketler', { method: 'POST', body: v }); kapat(); bildir('Kaydedildi.'); sonra && sonra(); });
  };
}

async function cariDetay(id) {
  sayfa(baslik('Cari'));
  const buYil = new Date().getFullYear() + '-01-01';
  const q = new URLSearchParams(location.hash.split('?')[1] || '');
  const bas = q.get('bas') ?? '', bit = q.get('bit') ?? '';
  const [c, e] = await Promise.all([api('/cariler/' + id), api(`/cariler/${id}/ekstre?bas=${bas}&bit=${bit}`)]);
  const b = c.bakiye;
  const s = sayfa(`${baslik(esc(c.unvan), `${CTUR[c.tur] || ''}${c.vkn ? ' – ' + (c.vkn.length === 11 ? 'TCKN ' : 'VKN ') + esc(c.vkn) : ''}${c.telefon ? ' – ' + esc(c.telefon) : ''}${c.vade_gun ? ' – vade ' + c.vade_gun + ' gün' : ''}`,
      `<a class="dugme" href="#/vade?cari=${id}${b < -0.004 ? '&y=borc' : ''}">Açık faturalar</a><button class="dugme" id="duzenle">Bilgileri düzenle</button>`)}
    <div class="bakiye-kart ${b > 0.004 ? 'alacakli' : b < -0.004 ? 'borclu' : ''}">
      <div><div class="etiket">${b > 0.004 ? 'Size borçlu' : b < -0.004 ? 'Siz borçlusunuz' : 'Hesap kapalı'}</div><div class="deger sayi">${tl(Math.abs(b))}</div></div>
      <div class="dugmeler"><button class="dugme ana" data-h="TAHSILAT">Tahsilat al</button><button class="dugme" data-h="ODEME">Ödeme yap</button>
        <button class="dugme" data-h="DEVIR_BORC">Açılış bakiyesi</button>
        ${c.tur !== 'tedarikci' ? `<button class="dugme" id="yeniF">Fatura kes</button>` : ''}</div>
    </div>
    <div class="baslik" style="margin:22px 0 12px"><h2 style="margin:0">Hesap ekstresi</h2>
      <div class="dugmeler tarih-filtre"><input type="date" id="bas" value="${bas}" aria-label="Başlangıç"><input type="date" id="bit" value="${bit}" aria-label="Bitiş">
      <button class="dugme kucuk" id="filtre">Göster</button><button class="dugme kucuk" id="buyil">Bu yıl</button>
      <a class="dugme kucuk" href="/goruntule/ekstre/${id}?bas=${bas}&bit=${bit}" target="_blank" rel="noopener">Yazdır / PDF</a></div></div>
    <div class="tablo-kap"><table class="liste ekstre"><thead><tr><th class="gizle-m">Tarih</th><th>İşlem</th><th class="gizle-m">Belge</th><th class="s gizle-m">Borç</th><th class="s gizle-m">Alacak</th><th class="s yalniz-m-hucre">Tutar</th><th class="s">Bakiye</th><th></th></tr></thead><tbody>
      ${bas ? `<tr class="devir"><td class="gizle-m">${tarihTR(bas)}</td><td>Önceki dönemden devir<div class="ikincil yalniz-m">${tarihTR(bas)}</div></td><td class="gizle-m"></td><td class="gizle-m"></td><td class="gizle-m"></td><td class="yalniz-m-hucre"></td><td class="s sayi">${para(Math.abs(e.devir))} ${e.devir > 0 ? 'B' : e.devir < 0 ? 'A' : ''}</td><td></td></tr>` : ''}
      ${e.satirlar.map(r => `<tr${r.kaynak !== 'hareket' ? ` class="tik" data-git="${r.kaynak === 'fatura' ? '#/fatura/' : '#/alis/'}${r.kaynak_id}"` : ''}>
        <td class="gizle-m">${tarihTR(r.tarih)}</td><td>${esc(r.islem)}<div class="ikincil"><span class="yalniz-m">${tarihTR(r.tarih)} ${esc(r.belge_no || '')} </span>${esc(r.aciklama || '')}</div></td><td class="gizle-m sayi">${esc(r.belge_no || '')}</td>
        <td class="s sayi gizle-m">${r.borc ? para(r.borc) : ''}</td><td class="s sayi gizle-m">${r.alacak ? para(r.alacak) : ''}</td>
        <td class="s sayi yalniz-m-hucre">${r.borc ? para(r.borc) + '<div class="ikincil">borç</div>' : para(r.alacak) + '<div class="ikincil">alacak</div>'}</td>
        <td class="s sayi">${para(Math.abs(r.bakiye))} ${r.bakiye > 0.004 ? 'B' : r.bakiye < -0.004 ? 'A' : ''}</td>
        <td class="s">${r.kaynak === 'hareket' ? `<button class="sil-dugme" data-sil="${r.kaynak_id}" aria-label="Kaydı sil">${ik('sil')}</button>` : ''}</td></tr>`).join('')
        || '<tr><td colspan="8" class="ipucu">Bu dönemde hareket yok.</td></tr>'}
    </tbody><tfoot><tr><td class="gizle-m"></td><td>Toplam</td><td class="gizle-m"></td><td class="s sayi gizle-m">${para(e.toplam_borc)}</td><td class="s sayi gizle-m">${para(e.toplam_alacak)}</td><td class="yalniz-m-hucre"></td><td class="s sayi">${para(Math.abs(e.bakiye))} ${e.bakiye > 0.004 ? 'B' : e.bakiye < -0.004 ? 'A' : ''}</td><td></td></tr></tfoot></table></div>
    <p class="ipucu">B: cari size borçlu, A: siz cariye borçlusunuz. Taslak ve hatalı faturalar bakiyeye katılmaz.</p>`);
  const yenile = () => cariDetay(id);
  $('#duzenle').onclick = () => cariFormu(c, k => k === null ? location.hash = '#/cariler' : yenile());
  if ($('#yeniF')) $('#yeniF').onclick = () => { window.ONSECILI_CARI = id; location.hash = '#/fatura/yeni'; };
  $$('[data-h]', s).forEach(x => x.onclick = () => hareketFormu(x.dataset.h, { cari_id: id, cari_unvan: c.unvan }, yenile));
  $('#filtre').onclick = () => location.hash = `#/cari/${id}?bas=${$('#bas').value}&bit=${$('#bit').value}`;
  $('#buyil').onclick = () => location.hash = `#/cari/${id}?bas=${buYil}&bit=`;
  $$('tr[data-git]', s).forEach(tr => tr.onclick = () => location.hash = tr.dataset.git);
  $$('[data-sil]', s).forEach(x => x.onclick = ev => { ev.stopPropagation(); confirm('Bu tahsilat/ödeme kaydı silinsin mi?') && calis(x, async () => { await api('/hareketler/' + x.dataset.sil, { method: 'DELETE' }); bildir('Kayıt silindi.'); yenile(); }); });
}

// ------------------------------------------------------------------ Kasa ve banka
function hesapFormu(h = {}, sonra) {
  const { p, kapat } = pencere(`<form>${baslik(h.id ? 'Hesabı düzenle' : 'Yeni kasa / banka hesabı')}
    <div class="izgara">
      ${alan('ad', 'Hesap adı', h.ad, 'required tam placeholder="ör. QNB vadesiz, Nakit kasa"')}
      <div><label for="a_tur">Tür</label><select id="a_tur" name="tur"><option value="KASA">Kasa</option><option value="BANKA"${h.tur === 'BANKA' ? ' selected' : ''}>Banka</option></select></div>
      ${alan('acilis_bakiye', 'Açılış bakiyesi (TL)', h.acilis_bakiye ?? '', 'type="number" step="0.01" inputmode="decimal"')}
      ${alan('iban', 'IBAN (banka için)', h.iban, 'tam')}
    </div><p class="ipucu">Açılış bakiyesi: programa başladığınız gün hesapta bulunan para.</p>
    <div class="pencere-alt"><div>${h.id ? `<button type="button" class="dugme tehlike" id="kapatH">Hesabı kapat</button>` : ''}</div>
    <div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Kaydet</button></div></div></form>`);
  $('form', p).onsubmit = e => { e.preventDefault(); calis(e.submitter, async () => { await api(h.id ? '/hesaplar/' + h.id : '/hesaplar', { method: h.id ? 'PUT' : 'POST', body: formOku(p) }); kapat(); bildir('Kaydedildi.'); sonra(); }); };
  if ($('#kapatH', p)) $('#kapatH', p).onclick = e => confirm('Hesap kapatılsın mı?') && calis(e.currentTarget, async () => { await api('/hesaplar/' + h.id, { method: 'DELETE' }); kapat(); bildir('Hesap kapatıldı.'); location.hash = '#/hesaplar'; });
}

async function hesaplarSayfa() {
  sayfa(baslik('Kasa ve banka'));
  const l = await api('/hesaplar');
  const toplam = l.reduce((t, h) => t + h.bakiye, 0);
  const s = sayfa(`${baslik('Kasa ve banka', `Toplam: <strong class="sayi">${tl(toplam)}</strong>`, `<button class="dugme" id="yeniH">${ik('arti')}Yeni hesap</button>`)}
    <div class="dugmeler" style="margin-bottom:16px">
      <button class="dugme ana" data-h="TAHSILAT">Tahsilat al</button><button class="dugme" data-h="ODEME">Ödeme yap</button>
      <button class="dugme" data-h="MASRAF">Masraf gir</button><button class="dugme" data-h="GELIR">Diğer gelir</button>
      ${l.length > 1 ? '<button class="dugme" data-h="VIRMAN">Hesaplar arası transfer</button>' : ''}</div>
    <div class="tablo-kap"><table class="liste"><thead><tr><th>Hesap</th><th class="gizle-m">Tür</th><th class="s">Bakiye</th></tr></thead><tbody>
      ${l.map(h => `<tr class="tik" data-id="${h.id}"><td>${esc(h.ad)}<div class="ikincil">${esc(h.iban || '')}</div></td><td class="gizle-m">${h.tur === 'BANKA' ? 'Banka' : 'Kasa'}</td><td class="s sayi${h.bakiye < 0 ? ' eksi' : ''}">${tl(h.bakiye)}</td></tr>`).join('')}
    </tbody></table></div>`);
  $('#yeniH').onclick = () => hesapFormu({}, hesaplarSayfa);
  $$('[data-h]', s).forEach(b => b.onclick = () => hareketFormu(b.dataset.h, {}, hesaplarSayfa));
  $$('tr[data-id]', s).forEach(tr => tr.onclick = () => location.hash = '#/hesap/' + tr.dataset.id);
}

async function hesapDetay(id) {
  sayfa(baslik('Hesap'));
  const r = await api(`/hesaplar/${id}/hareketler`);
  const h = r.hesap;
  const s = sayfa(`${baslik(esc(h.ad), `${h.tur === 'BANKA' ? 'Banka' : 'Kasa'}${h.iban ? ' – ' + esc(h.iban) : ''}`, `<button class="dugme" id="duzenle">Düzenle</button>`)}
    <div class="bakiye-kart"><div><div class="etiket">Bakiye</div><div class="deger sayi${r.bakiye < 0 ? ' eksi' : ''}">${tl(r.bakiye)}</div></div>
      <div class="dugmeler"><button class="dugme ana" data-h="TAHSILAT">Tahsilat</button><button class="dugme" data-h="ODEME">Ödeme</button><button class="dugme" data-h="MASRAF">Masraf</button><button class="dugme" data-h="VIRMAN">Transfer</button></div></div>
    <div class="tablo-kap" style="margin-top:20px"><table class="liste"><thead><tr><th>Tarih</th><th>İşlem</th><th class="s">Giriş</th><th class="s">Çıkış</th><th class="s gizle-m">Bakiye</th><th></th></tr></thead><tbody>
      ${r.hareketler.map(x => `<tr${x.cari_id ? ` class="tik" data-git="#/cari/${x.cari_id}"` : ''}><td>${tarihTR(x.tarih)}</td><td>${esc(x.tur_ad)}${x.cari_unvan ? ' – ' + esc(x.cari_unvan) : ''}<div class="ikincil">${esc([x.odeme_sekli, x.belge_no, x.aciklama].filter(Boolean).join(' – '))}</div></td>
        <td class="s sayi">${x.giris ? para(x.giris) : ''}</td><td class="s sayi">${x.cikis ? para(x.cikis) : ''}</td><td class="s sayi gizle-m">${para(x.bakiye)}</td>
        <td class="s"><button class="sil-dugme" data-sil="${x.id}" aria-label="Kaydı sil">${ik('sil')}</button></td></tr>`).join('')
        || '<tr><td colspan="6" class="ipucu">Bu hesapta henüz hareket yok.</td></tr>'}
      <tr class="devir"><td></td><td>Açılış bakiyesi</td><td></td><td></td><td class="s sayi gizle-m">${para(h.acilis_bakiye)}</td><td></td></tr>
    </tbody></table></div>`);
  $('#duzenle').onclick = () => hesapFormu(h, () => hesapDetay(id));
  $$('[data-h]', s).forEach(b => b.onclick = () => hareketFormu(b.dataset.h, { hesap_id: id }, () => hesapDetay(id)));
  $$('tr[data-git]', s).forEach(tr => tr.onclick = () => location.hash = tr.dataset.git);
  $$('[data-sil]', s).forEach(x => x.onclick = ev => { ev.stopPropagation(); confirm('Kayıt silinsin mi?') && calis(x, async () => { await api('/hareketler/' + x.dataset.sil, { method: 'DELETE' }); bildir('Kayıt silindi.'); hesapDetay(id); }); });
}

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
baslat();

// ------------------------------------------------------------------ Vade takibi
function vadeFormu(mevcut, faturaTarihi, yol, sonra) {
  const { p, kapat } = pencere(`<form>${baslik('Vadeyi değiştir', 'Yalnızca vade takibini etkiler; gönderilmiş faturanın kendisi değişmez.')}
    <label for="yeniVade">Vade tarihi</label><input id="yeniVade" type="date" min="${faturaTarihi}" value="${mevcut || ''}">
    <p class="ipucu">Boş bırakırsanız fatura peşin sayılır (vade = fatura tarihi).</p>
    <div class="pencere-alt"><div></div><div class="dugmeler"><button type="button" class="dugme" data-kapat>Vazgeç</button><button class="dugme ana">Kaydet</button></div></div></form>`);
  $('form', p).onsubmit = e => {
    e.preventDefault();
    calis(e.submitter, async () => { await api(yol, { method: 'PUT', body: { vade_tarihi: $('#yeniVade', p).value } }); kapat(); bildir('Vade güncellendi.'); sonra(); });
  };
}

async function vadeSayfa() {
  sayfa(baslik('Vade takibi'));
  const q = new URLSearchParams(location.hash.split('?')[1] || '');
  const yon = q.get('y') === 'borc' ? 'borc' : 'alacak', cari = +q.get('cari') || 0, grup = q.get('g') || '';
  const r = await api('/vade' + (cari ? '?cari_id=' + cari : ''));
  const tum = yon === 'borc' ? r.borclar : r.alacaklar, oz = r.ozet[yon];
  const liste = grup ? tum.filter(x => x.grup === grup) : tum;
  const git = (y = yon, g = '') => '#/vade?' + new URLSearchParams({ ...(y === 'borc' ? { y } : {}), ...(cari ? { cari } : {}), ...(g ? { g } : {}) });
  const cariAd = cari && (r.alacaklar[0] || r.borclar[0])?.cari_unvan;
  const s = sayfa(`${baslik('Vade takibi', cari ? `${esc(cariAd || 'Bu cari')} için açık faturalar – <a href="#/vade${yon === 'borc' ? '?y=borc' : ''}">tüm cariler</a>`
      : 'Ödenmemiş faturalar. Tahsilat ve ödemeler önce en eski vadeli faturayı kapatır.')}
    <div class="dugmeler" style="margin-bottom:14px"><div class="sekmeler"><a class="${yon === 'alacak' ? 'aktif' : ''}" href="${git('alacak')}">Alacaklarımız (${tl(r.ozet.alacak.toplam)})</a><a class="${yon === 'borc' ? 'aktif' : ''}" href="${git('borc')}">Borçlarımız (${tl(r.ozet.borc.toplam)})</a></div></div>
    <div class="yaslandirma">${Object.entries(r.gruplar).map(([k, ad]) => `<a href="${git(yon, grup === k ? '' : k)}" class="${grup === k ? 'secili ' : ''}${k !== 'gelmedi' && oz.gruplar[k] ? 'gecmis' : ''}"><span>${ad}</span><strong class="sayi">${tl(oz.gruplar[k])}</strong></a>`).join('')}</div>
    ${!liste.length ? `<div class="panel bos"><p>${grup ? 'Bu grupta' : yon === 'alacak' ? 'Açık alacak' : 'Açık borç'} yok.</p></div>`
      : `<div class="tablo-kap"><table class="liste vade-tablo"><thead><tr><th>Cari</th><th class="gizle-m">Belge</th><th class="gizle-m">Tarih</th><th>Vade</th><th class="s gizle-m">Tutar</th><th class="s">Açık</th></tr></thead><tbody>
      ${liste.map(x => `<tr class="tik" data-git="${x.kaynak === 'fatura' ? '#/fatura/' + x.kaynak_id : x.kaynak === 'alis' ? '#/alis/' + x.kaynak_id : '#/cari/' + x.cari_id}">
        <td>${esc(x.cari_unvan)}<div class="ikincil">${esc(x.islem)} ${esc(x.belge_no || '')}</div></td><td class="gizle-m sayi">${esc(x.belge_no || '')}</td><td class="gizle-m">${tarihTR(x.tarih)}</td>
        <td>${tarihTR(x.vade)}<div>${gecikmeRozet(x.gecikme)}</div></td><td class="s sayi gizle-m">${para(x.tutar)}</td><td class="s sayi"><strong>${para(x.acik)}</strong>${x.acik < x.tutar ? '<div class="ikincil">kısmen ödendi</div>' : ''}</td></tr>`).join('')}
      </tbody><tfoot><tr><td>Toplam</td><td class="gizle-m"></td><td class="gizle-m"></td><td></td><td class="gizle-m"></td><td class="s sayi">${para(liste.reduce((t, x) => t + x.acik, 0))}</td></tr></tfoot></table></div>`}`);
  $$('tr[data-git]', s).forEach(tr => tr.onclick = () => location.hash = tr.dataset.git);
}
