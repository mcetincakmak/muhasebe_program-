# e-Fatura programı

QNB eSolutions üzerinden satış ve iade faturası kesen, alış faturalarını her gün otomatik çeken, telefonla çektiğiniz irsaliye fotoğraflarını okuyup ilgili alış faturasıyla eşleştiren küçük bir program. Ofisteki Windows bilgisayarda çalışır; bilgisayardan ve telefondan tarayıcıyla açılır.

## Kurulum (Windows, tek tık)

1. Zip'i ofis bilgisayarında bir klasöre çıkarın (ör. `C:\eFatura`). Masaüstüne veya "İndirilenler"e değil, kalıcı bir yere.
2. **`KUR.bat`** dosyasına çift tıklayın. Windows izin isterse **Evet** deyin.
3. Betik Python'u, Tesseract'ı ve Türkçe OCR dosyalarını kendisi kurar, masaüstüne **e-Fatura** kısayolunu koyar. İki soru sorar:
   - *Bilgisayar açılınca arka planda başlasın mı?* → **E** (günlük e-fatura taraması için gerekli).
   - *Tailscale kurulsun mu?* → Dışarıdan erişim istiyorsanız **E** (aşağıya bakın).
4. Kurulum bitince tarayıcıda program açılır. İlk ekranda firma ünvanını, kullanıcı adınızı ve şifrenizi (en az 8 karakter) belirleyin, sonra **Ayarlar**'dan firma bilgilerinizi girin.

Program Windows'a **sistem görevi** olarak kaydedilir: bilgisayar açılınca, kimse oturum açmasa bile arka planda başlar ve kapanırsa kendiliğinden yeniden başlatılır. Masaüstündeki kısayol yalnızca tarayıcıda açar.

Kurulumda hata olursa ekranın fotoğrafını gönderin. Elle kurulum gerekirse: python.org'dan Python 3.12 ("Add to PATH" işaretli) ve "Tesseract UB Mannheim" Windows kurulumu, ardından `KUR.bat`'ı tekrar çalıştırın.

Tüm veriler `veri` klasöründe durur (`fatura.db` ve irsaliye fotoğrafları). Program kayıtları `veri\sunucu.log` dosyasındadır.

## Kullanıcılar, firmalar ve lisans

- **Firmalar:** Bir kurulumda birden fazla firma tutulabilir (Yönetim → Firmalar). Her firmanın faturaları, carileri, stoğu, ayarları ve entegratör hesabı tamamen ayrıdır. Firmalar arasında sol üstteki seçiciden geçilir.
- **Kullanıcılar ve roller** (Yönetim → Kullanıcılar): her kullanıcıya firma bazında rol verilir.
  - *Yönetici:* her şey. *Muhasebe:* ayarlar ve yönetim hariç her şey.
  - *Personel:* yalnızca irsaliye yükleme ve stok görme; faturaları ve parayı göremez.
  - *Mali müşavir:* salt okuma ve raporlar/Excel.
  - *Sistem yöneticisi* işaretli kullanıcılar kullanıcı, firma ve lisans yönetebilir; en az bir tane kalmak zorundadır.
- **Lisans** (Yönetim → Lisans): Kurulumdan itibaren 30 gün tam deneme (2 firma, 3 kullanıcı). Süre bitince program salt okumaya geçer; veriler görülebilir ve Excel'e aktarılabilir. Lisans anahtarı girilince sınırlar lisansa göre açılır. Lisans istenirse bilgisayara bağlanabilir; makine kodu aynı sayfada görünür.
- **1.x sürümünden geçiş:** Eski kurulumun üzerine yeni sürümü koyup çalıştırdığınızda veriler otomatik olarak ilk firmaya taşınır; kullanıcı adınız `yonetici`, şifreniz eskisiyle aynıdır. Eski veritabanı `veri/eski_surum_fatura.db` olarak saklanır.

## Telefondan erişim

- **Ofisteyken (aynı Wi-Fi):** Ayarlar → *Telefondan erişim* bölümündeki adresi (ör. `http://192.168.1.20:8000`) telefonda açın. Ağ "Ortak" görünüyorsa Windows'ta "Özel" yapın.
- **Her yerden (Tailscale):** Tailscale, telefonunuzla ofis bilgisayarı arasında şifreli özel bir bağlantı kurar; verileriniz buluta yüklenmez, internete açık bir kapı da açılmaz. Kişisel kullanım ücretsizdir.
  1. Kurulumda Tailscale'i seçin (veya tailscale.com/download'dan kurun) ve bilgisayarda giriş yapın.
  2. Tailscale yönetim sayfasında (login.tailscale.com → DNS) **MagicDNS** ve **HTTPS Certificates**'ı açın.
  3. Bilgisayarda yönetici komut isteminde bir kez: `tailscale serve --bg 8000` (kurulum betiği bunu dener).
  4. Telefona Tailscale uygulamasını kurup **aynı hesapla** giriş yapın. Ayarlar'da görünen `https://…ts.net` adresini açın ve tarayıcı menüsünden **Ana ekrana ekle** deyin.
- Program şifreyle korunur; aynı kullanıcı için 5 hatalı denemede 15 dakika kilitlenir. Ofis bilgisayarı açık ve program çalışıyor olmalıdır.

## QNB'ye bağlanma ve test

1. QNB eSolutions'tan **web servis (API) entegrasyonu** için **test ortamı** kullanıcı bilgilerini isteyin.
2. Ayarlar → QNB bağlantısı → modu **Test ortamı** yapın, kullanıcı adı ve şifreyi girip kaydedin.
3. **Bağlantıyı test et** düğmesine basın. Giriş, mükellef sorgusu ve gelen fatura listeleme ayrı ayrı denenir.
4. Hepsi ✓ ise bir test müşterisine e-Fatura ve e-Arşiv birer deneme faturası kesin; QNB test panelinden göründüğünü kontrol edin.
5. ✗ çıkarsa hata mesajını ve QNB'nin teknik dokümanını paylaşın; `app/qnb.py` dosyasını ona göre düzeltelim.
6. Test sorunsuzsa QNB'den canlı bilgileri alıp modu **Canlı** yapın.

## Orion'dan geçiş

- Geçişten önce Orion'daki tüm giden ve gelen faturaları (XML + PDF) indirip saklayın.
- Orion'un kullandığı entegratörden QNB'ye geçiş bir "entegratör değişikliği"dir; QNB bunu sizin adınıza başlatır.
- Aynı yıl içinde numara çakışmaması için Ayarlar'da Orion'dakinden farklı bir fatura serisi seçin. Seri ve numara konusunda mali müşavirinizle teyitleşin.
- Carilerin açılış bakiyelerini, kasa/banka bakiyelerini ve ürünlerin açılış stoklarını geçiş günü itibarıyla girin.

## İrsaliye → fatura eşleştirme nasıl çalışır

1. Mal gelince irsaliyenin fotoğrafını telefondan çekin (**Yeni → İrsaliye fotoğrafı çek**). Birden fazla sayfa varsa hepsini birlikte seçin.
2. Program irsaliye numarasını, tarihi ve tedarikçinin VKN'sini okur. Tedarikçi kayıtlı değilse **cari olarak otomatik eklenir**. Üçü de okunduysa irsaliye doğrudan "Fatura bekleniyor" durumuna geçer; okunamayan varsa "Kontrol gerekli" olur, fotoğrafın yanındaki formdan düzeltip onaylarsınız.
3. Her gün tarama saatinde QNB'den gelen e-faturalar alınır; tedarikçiler cari olarak eklenir ve irsaliyelerle karşılaştırılır:
   - Faturada irsaliye numarası yazıyorsa **otomatik eşleşir**.
   - Yazmıyorsa aynı tedarikçi, yakın tarih ve benzer ürünlere bakılır; uygun fatura "Onay bekliyor" olarak önerilir, **siz onaylarsınız**. Reddettiğiniz fatura bir daha önerilmez.
4. Kağıt gelen faturaları **Alış faturası gir** ile ekleyebilir, fotoğrafından otomatik doldurabilirsiniz. Her şeyi elle de girebilirsiniz.

**OCR hakkında:** Basılı irsaliye numarası, tarih ve VKN'yi iyi okur. Nokta vuruşlu yazıcı, karbon kopya ve el yazısında zorlanır; ürün satırları eksik çıkabilir. Fotoğrafı düz, gölgesiz ve belge ekranı dolduracak şekilde çekmek sonucu çok iyileştirir. İsterseniz Ayarlar'dan yapay zekâ ile okumaya (Claude API, ücretli) geçebilirsiniz; varsayılan OCR'dır.

## Cari hesap, tahsilat ve ödeme

- **Bakiye kendiliğinden oluşur:** Kestiğiniz satış faturası müşteriyi borçlandırır, gelen alış faturası tedarikçiyi alacaklandırır. Taslak ve hatalı faturalar bakiyeye katılmaz.
- **Orion'dan geçerken önce açılış bakiyelerini girin:** Her carinin geçiş günündeki bakiyesini **Cariler → cari → Açılış bakiyesi** ile girin. Kasa ve banka hesaplarını da **Kasa ve banka → Yeni hesap** ile, o günkü bakiyeleriyle açın. Eski faturaları tekrar girmenize gerek yok.
- **Tahsilat / ödeme:** Cari sayfasından veya doğrudan fatura sayfasından ("Tahsilat al", "Ödeme yap"). Para hangi kasaya/bankaya girdi veya çıktıysa onu seçin.
- **Masraf ve diğer gelir:** Cariye bağlı olmayan kira, elektrik, banka masrafı gibi kalemler **Kasa ve banka → Masraf gir**.
- **Hesaplar arası transfer:** Kasadaki parayı bankaya yatırmak gibi.
- **Ekstre:** Cari sayfasında tarih aralığı seçip **Yazdır / PDF** ile mutabakat için karşı tarafa gönderebilirsiniz.

## Stok

- Ürün kartında **Türü**: stoklu ürün veya hizmet (hizmette stok tutulmaz). İsteğe bağlı **kritik stok seviyesi** girin; altına düşünce özet ekranında uyarı çıkar.
- **Stok girişi:** İrsaliyeyi kaydettiğinizde satırlar stoka girer. Her satırın hangi ürün olduğunu “Stok ürünü” sütununda seçin (veya “Yeni ürün olarak ekle”). Bu seçim o tedarikçi için hatırlanır; sonraki irsaliyelerde otomatik gelir. İrsaliyesi olmayan alışlar için alış faturasında **Stoka al**.
- **Stok çıkışı:** Satış faturası gönderildiğinde düşer. Faturaya ürünü "Kayıtlı üründen ekle" ile ekleyin; elle yazılan satır, adı veya stok kodu ürünle aynıysa yine tanınır.
- **Geçişte:** Her ürün için **Açılış stoku gir** (miktar ve alış fiyatı). Dönem sonunda **Sayım yap** ile sayılan miktarı girin, fark otomatik düzeltilir.
- **Maliyet:** İrsaliye faturayla eşleşince faturadaki birim fiyat stok girişine işlenir; brüt kâr bu ortalama maliyetle hesaplanır.

## Raporlar ve Excel

**Raporlar** sayfasında seçtiğiniz dönem için net satış/alış, aylık grafik, brüt kâr, tahmini KDV (hesaplanan − indirilecek), nakit hareketi ve en çok çalışılan cari/ürünler görünür. **Excel'e aktar** ile mali müşavire gönderebileceğiniz 8 sayfalık bir dosya iner: özet, satış ve alış faturaları, cari bakiyeler ve hareketler, stok, kasa-banka, aylık.

## Tevkifat ve döviz

- **Tevkifat:** Fatura ekranında **Tevkifatlı** kutusunu işaretleyin; her satır için tevkifat kodunu seçin (ör. 612 temizlik 9/10, 604 yemek 5/10). Fatura "TEVKIFAT" tipinde kesilir; ödenecek tutardan tevkif edilen KDV düşülür. Kod ve oranları mali müşavirinizle teyit edin.
- **Döviz:** Para birimi USD, EUR veya GBP seçin, kuru girin ya da **TCMB** düğmesiyle fatura tarihindeki döviz alış kurunu getirin. Fatura dövizli kesilir; cari bakiye, raporlar ve Excel TL karşılığıyla çalışır. Kur farkı hesabı bu sürümde yok.

## Yedek

**Ayarlar → Yedek → Yedeği indir**: veritabanı ve irsaliye fotoğrafları tek zip. Program çalışırken de tutarlı yedek alınır.

## İade faturası

- Tedarikçiye mal iade ederken: **Alış faturaları →** ilgili fatura **→ İade faturası kes**. Satırlar faturadan gelir; iade ettiğiniz ürün ve miktarları bırakıp gönderin. Fatura, alış faturasına referansla "İADE" tipinde kesilir.
- Referans faturayı elle girmek için: **Yeni → İade faturası**.

## Programın yapabildikleri

- Cariler: müşteri ve tedarikçi; tedarikçiler irsaliye ve e-faturalardan otomatik tanımlanır; e-Fatura mükellefiyet sorgusu
- Satış ve iade faturası: mükellefe **e-Fatura**, diğerlerine **e-Arşiv** otomatik; iskonto, %20/%10/%1/%0 KDV; taslak, gönderme, durum sorgulama, XML, yazdırma
- Alış faturaları: günlük otomatik e-fatura çekme, elle/fotoğraftan giriş
- İrsaliyeler: fotoğraftan okuma (OCR), elle giriş, otomatik ve onaylı eşleştirme
- Cari hesap: bakiye, ekstre (yazdırılabilir), açılış bakiyesi, tahsilat ve ödeme
- Kasa ve banka: birden çok hesap, masraf/gelir, hesaplar arası transfer
- Stok: irsaliyeden otomatik giriş, satıştan otomatik çıkış, kritik seviye, sayım, ortalama maliyet
- Raporlar: aylık grafik, brüt kâr, KDV, nakit; 8 sayfalık Excel çıktısı
- Tevkifatlı ve dövizli (USD/EUR/GBP, TCMB kuru) fatura
- Tek tıkla yedek, tek tıkla kurulum, telefondan her yerden güvenli erişim (Tailscale)

**Henüz olmayanlar:** çek/senet takibi, vade takibi, kur farkı faturası, özel matrah, e-İrsaliye kesme. %0 KDV'de varsayılan istisna kodu 351'dir; farklı bir istisna uyguluyorsanız mali müşavirinize danışın.

## Güvenlik

- Program şifreyle korunur; oturumlar 30 günde düşer, şifre değişince diğer cihazlardaki oturumlar kapanır. 5 hatalı denemede giriş 15 dakika kilitlenir.
- Başka sitelerden oturumunuzla istek gönderilmesi (CSRF), sayfanın başka sitede gizlice açılması ve dışarıdan gelen faturalardaki zararlı içerik (XML bombası, betik, Excel formülü) engellenir.
- Ofis Wi-Fi'ında `http://` adresiyle bağlanırken trafik şifrelenmez. Şifresi herkeste olan veya misafirlere açık bir ağda, ofisteyken de Tailscale'in `https://` adresini kullanın.
- Entegratör şifresi ve (varsa) Claude API anahtarı bu bilgisayardaki veritabanında durur ve **yedek zip dosyasına da girer**. Yedekleri şifreli bir klasörde veya güvendiğiniz bir yerde saklayın; kimseyle paylaşmayın.
- Bilgisayarın Windows kullanıcı hesabına şifre koyun; `veri` klasörüne erişen herkes verilere de erişebilir.

## Geliştirici notları

- Mimari ve geliştirme kuralları: `MIMARI.md`.
- Testler: `.venv\Scripts\python -m pytest tests` (deneme modunda çalışır, entegratöre bağlanmaz).
- QNB servis adları ve adresleri `app/qnb.py` içinde; test ortamında doğrulanmalıdır.
