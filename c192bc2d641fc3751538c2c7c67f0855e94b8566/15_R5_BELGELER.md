# R5 — Belgeler, kılavuzlar ve teslim paketi

> **Önce `10_OKU_ONCE_FAZ2.md`.** Bu belge yalnız senin şeridini anlatır.
> Dal: `feat/docs` · Worktree: `~/code/.dou-docs` · Port: **8025**
> Görevler: **T056 (kısmen), T057, T058, T059, T060**

```bash
cd ~/code/dou-lead && git fetch origin
git worktree add ~/code/.dou-docs -b feat/docs origin/main
cd ~/code/.dou-docs/apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp ../../.env.example .env
cd ../web && bun install
```

---

## Neden bu şerit

Bu bir bitirme projesi. Jüri kodu satır satır okumayacak; **belgeleri okuyacak ve
demoyu izleyecek.** Bugün elde çok iyi bir sistem var ve onu anlatan hiçbir şey
yok: kurulum README'de eksik, eğitmen ne yapacağını bilmiyor, demo günü planı
kimsenin kafasında.

Ayrıca bir dürüstlük işi: `ARCHITECTURE.md`, `PLAN.md` ve `DESIGN.md` 9
Ağustos'tan önce yazıldı ve sistem o gün epey değişti. **Belgeler ürünü artık
tam tarif etmiyor.** Bunu kapatmak senin işin.

## Sahiplendiğin dosyalar

```
README.md                        senin
docs/runbook.md                  YENİ
docs/instructor-guide.md         YENİ
docs/student-guide.md            YENİ
docs/kvkk.md                     YENİ (metin; SAYFAYI lider yapar)
docs/demo-script.md              YENİ
ARCHITECTURE.md                  senin (gerçekle hizala)
PLAN.md                          senin (gerçekle hizala)
specs/001-course-assistant-mvp/quickstart.md   senin
specs/001-course-assistant-mvp/tasks.md        yalnız T057-T060 satırların
```

**Dokunma:** `apps/**` (kod), `evaluation/**` (R2), `docs/test-report.md` (R2),
`docs/security.md` (R1), `docs/deployment.md` (R3),
`docs/team/parallel/**` (lider), `DESIGN.md` (lider — frontend'in belgesi).

Koda dokunmuyorsun ama **kodu okumak zorundasın.** Yazdığın her cümlenin kodda
karşılığı olmalı.

---

## İş 0 — sistemi kendin çalıştır (yazmadan önce)

Ekran görüntüsü ve doğru anlatım için gerekli. Kendi portlarında:

```bash
# terminal 1
cd ~/code/.dou-docs/apps/api && uv run uvicorn app.main:app --port 8025
# terminal 2
cd ~/code/.dou-docs/apps/api && uv run python -m app.worker
# terminal 3
cd ~/code/.dou-docs/apps/web && NEXT_PUBLIC_API_URL=http://localhost:8025 bun run dev --port 3025
```

**Tuzak:** bu makinede `NEXT_PUBLIC_API_URL` ortamda `:9100`'e kayabiliyor;
yukarıdaki gibi açıkça ver. Playwright koştururken `bunx playwright` KULLANMA
(ayrı kopya indirir, "two different versions" hatası); `node_modules/.bin/playwright`.

Giriş: demo kimlikleri `supabase/seed_demo.sql`'de —
Ayşe Hoca (eğitmen) `11111111-…`, Burak (öğrenci) `22222222-…`.
Materyali olan bir ders: `COME 331`.

**Frontend lider tarafından aktif olarak değiştiriliyor.** Ekran görüntüsü
almadan önce `git pull origin main` yap; ekranlar bugün epey değişti.

## İş 1 — `docs/runbook.md` (T057) — en yüksek değerli belge

Demo günü tek başvuru kaynağı. Üç planlı:

- **Plan A — canlı bulut.** minReplicas=1, sabah warm-up, oturumlar önceden
  açık. Hangi URL, hangi hesap, hangi sırayla.
- **Plan B — telefon hotspot.** Ne zaman geçilir (hangi belirti), nasıl geçilir,
  ne kadar sürer.
- **Plan C — tam çevrimdışı.** `docker compose` fallback profili + dev-auth +
  önceden doldurulmuş `answer_cache`. R3 bunu kuruyor ve **gerçekten ağsız
  koşturuyor**; ölçümlerini ve kısıtlarını ondan al.

Her plan için: **geçiş kararı kimin, hangi belirtiyle, kaç saniyede.**
"İnternet yavaşsa" yetmez; "ilk soruya 15 sn'de cevap gelmezse B'ye geç" yeter.

Ayrıca:
- Sabah kontrol listesi (T-60 dk, T-15 dk, T-0)
- Bilinen kırılgan noktalar ve her birinin kaçış yolu
- Cold start süresi (R3 ölçüyor) — jüri beklerken ne söylenecek
- **Ne gösterilmeyecek:** yarım kalan ekranlar, ölçülmemiş sayılar

## İş 2 — `docs/demo-script.md` — sahne sahne anlatım

Runbook "bozulursa ne yapılır"; bu belge "her şey yolundayken ne anlatılır".

Ürünün tezi şu sırayla gösterilmeli:
1. Eğitmen materyal yükler, işlenme ilerlemesi görünür
2. Öğrenci soru sorar → **kaynaklı cevap, dosya adı + sayfa numarasıyla**
3. Öğrenci ödev sorusu sorar → **cevap yerine Sokratik merdiven**
4. Öğrenci "sadece söyle" der → **merdiven ilerlemez, nazikçe reddedilir**
5. Öğrenci ders dışı soru sorar → **nazik ret; bu bir hata değil, ÖZELLİK**
6. Sınav provası + "neden yanlış" + ilerleme

5. madde bu ürünün en özgün anı: **"bilmiyorum diyebilen asistan".** Bunu bir
kusur gibi değil, tasarım kararı olarak anlat. Her sahne için: ne söylenecek,
ne tıklanacak, ne görünecek, kaç saniye.

Her sahnenin sorusunu **önceden `answer_cache`'e doldurulacak** sorularla
eşleştir (R3'ün `fill_answer_cache.py` betiği) ve listeyi R3'e ver.

## İş 3 — `docs/instructor-guide.md` ve `docs/student-guide.md` (T058, T059)

Ekran görüntülü, adım adım. Eğitmen: ders açma, materyal yükleme + n/m
ilerleme, soru üretimi ve **onay** (onaylanmadan öğrenciye görünmez — bunu
vurgula), sınav yayınlama, analitik. Öğrenci: derse katılım, kaynaklı sohbet,
Sokratik mod, sınav provası, "neden yanlış?", mastery görünümü.

Ekran görüntülerini `docs/images/` altına koy. **Gerçek ekran görüntüsü al**,
çizim yapma. Kişisel veri görünmesin (demo hesapları kullan).

İkisinde de bir **"asistan ne yapmaz"** bölümü olsun: internetten bilgi
getirmez, eğitmenin yüklemediği kaynaktan cevap vermez, ödevi çözmez,
kaynaksız cevap göstermez. Beklentiyi doğru kurmak, sonradan "çalışmıyor"
denmesini engeller.

## İş 4 — `docs/kvkk.md` (T060'ın bir parçası)

Aydınlatma metni. **Hukuki metin uydurma** — yalnız kodda gerçekten olan veri
akışını anlat:
- Hangi kişisel veri işleniyor (e-posta, ad, ders üyeliği, sohbet mesajları,
  sınav cevapları, mastery skorları)
- Nerede saklanıyor, ne kadar süre
- **Soru metinlerinin `request_logs`'a yazılmadığı** (şemada serbest metin
  sütunu yok — yapısal önlem, kod referansıyla)
- Üçüncü taraf: LLM sağlayıcısına ne gidiyor (soru + retrieve edilen parçalar),
  ne gitmiyor (kimlik)
- Kullanıcının hakları ve başvuru yolu

Sayfayı **lider** yapacak (`apps/web` senin değil) — metni markdown olarak ver,
raporunda "sayfa gerekiyor" diye belirt.

## İş 5 — `ARCHITECTURE.md` ve `PLAN.md`'yi gerçekle hizala

Belgeler 9 Ağustos'tan önce yazıldı. Kodu oku, farkları bul, **tek yönde hizala**
ve neyi neden değiştirdiğini yaz. Bilinen ayrışmalar:

- ARCHITECTURE §5 atıf şemasındaki `claim` alanı: `contracts.Citation`'da
  bilinçli olarak YOK, zarf katmanında (`schemas/chat.py`) taşınıyor.
  Bunun gerekçesi `contracts.py`'de yazılı — belgeye taşı.
- `hints[]` dizisi: zarfta VAR ve Sokratik turda doluyor.
- Kanıt eşiği artık **0.81** ve kalibre edildi; holdout doğrulamadı.
- `SessionDep` `scope="function"` — işlem yanıttan önce commit ediliyor.
- Worker tetiği: süreç içi + (R3'ten sonra) HTTP.

**Uygulanmamış bir kararı "yapılacak" diye bırakacaksan belgede AÇIKÇA
"uygulanmadı" yaz.** Sessizce duran bir iddia yalandır.

## İş 6 — `README.md` ve `quickstart.md` (T060)

README: proje ne, canlı URL, `docker compose up` ile kurulum, teslim paketi
haritası (hangi belge nerede), ekip. Jüri buradan başlayacak.

`quickstart.md`: sıfırdan kurulumu **gerçekten baştan koştur** ve her adımın
çalıştığını doğrula. Bugün bilinen bir tuzak var: dev veritabanı `dou_synapse`
`0003`'ü eksik koşuyordu ve sohbet 500 veriyordu. Quickstart bütün
migration'ları sırayla koşturuyor mu, gerçekten kontrol et.

## Lidere iletmen gerekenler

- KVKK sayfası (metin hazır, sayfa lazım)
- Arayüzde yanlış/eksik gördüğün her şey (ekran görüntüsü alırken çok
  göreceksin — bunlar değerli, hepsini yaz)
- DESIGN.md ile kod arasında fark görürsen (DESIGN.md lider'in)

## Bitti sayılma ölçütün

- [ ] Sistemi kendin çalıştırdın, ekran görüntüleri gerçek
- [ ] `runbook.md`: üç plan, geçiş kararı belirtiyle tanımlı
- [ ] `demo-script.md`: altı sahne, her biri süreli ve replikli
- [ ] İki kılavuz ekran görüntülü, "asistan ne yapmaz" bölümlü
- [ ] `kvkk.md` yalnız kodda gerçekten olanı anlatıyor
- [ ] `ARCHITECTURE.md` + `PLAN.md` ürünle uyumlu; uygulanmayanlar "uygulanmadı"
- [ ] `README.md` + `quickstart.md` sıfırdan koşuldu ve çalıştı
