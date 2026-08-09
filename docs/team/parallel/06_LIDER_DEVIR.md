# Lider şeridi — devir teslim

> **9 Ağustos 2026, saat ~14:00.** Bu belge, lider oturumunun bittiği yerden devam
> edecek yeni oturum içindir. Önce `00_OKU_ONCE.md` oku, sonra burayı.
>
> Şerit: **frontend + CI + belgeler + entegrasyon.** Backend'e dokunmuyorsun;
> beş paralel oturum orada çalışıyor.

---

## 1. İlk iş — doğru klasörde çalış

Lider için ayrı bir çalışma ağacı açıldı. **`~/code/DOU-Synapse` klasörüne
dokunma**, orada başka bir oturum kendi dalında çalışıyor.

```bash
cd ~/code/dou-lead
git branch --show-current      # "main" yazmalı
git pull origin main
```

`~/code/dou-lead` yoksa:

```bash
git -C ~/code/DOU-Synapse worktree add ~/code/dou-lead main
cd ~/code/dou-lead/apps/web && bun install
cd ../api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp ../../.env.example .env
```

**Neden ayrı ağaç:** beş oturum aynı makinede çalışıyor ve `git checkout` dalı
klasörü kullanan herkes için değiştiriyor. Bu 9 Ağustos'ta yaşandı — lider
farkında olmadan Şerit 3'ün dalında çalışıyordu, commit'siz iş onların dalının
üstünde birikmişti. İş kaybolmadı ama kurtarmak vakit aldı.

## 2. Sunucuları ayağa kaldır

```bash
# API (ayrı terminal)
cd ~/code/dou-lead/apps/api && uv run uvicorn app.main:app --port 8000
# Worker (ayrı terminal, materyal işlenmesi için)
cd ~/code/dou-lead/apps/api && uv run python -m app.worker
# Web (ayrı terminal)
cd ~/code/dou-lead/apps/web && bun run dev
```

**Tuzak:** bu makinede `NEXT_PUBLIC_API_URL` ortamda `:9100`'e (önizleme proxy'si)
işaret edebiliyor. Tarayıcı API'ye ulaşamıyorsa önce bunu kontrol et:

```bash
cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8000 bun run dev
```

Uçtan uca testler bu sorundan etkilenmez — kendi sunucusunu açıkça
yapılandırılmış adresle başlatıyorlar (`playwright.config.ts`).

## 3. Şu anki durum

`main` = `7fd38bd` (bu belge işlendiğinde daha ileride olabilir).

| Katman | Durum |
|---|---|
| Backend testleri | **159 geçiyor** (92'ydi; Şerit 3'ün chat + Sokratik testleri geldi) |
| Frontend birim | **25 geçiyor** — `cd apps/web && bun test lib/` |
| Frontend uçtan uca | **9 geçiyor** — `cd apps/web && node_modules/.bin/playwright test` |
| Lint / tip / derleme | temiz, 9 rota |
| CI | üç job: `api`, `web`, `e2e` |

**Test koştururken:** `bunx playwright` KULLANMA — ayrı bir kopya indirip
"two different versions" hatası veriyor. `node_modules/.bin/playwright` ya da
`bun run test:e2e` kullan.

## 4. Bekleyen iş: 47 doğrulanmış arayüz bulgusu

Altı mercekli bir inceleme (62 ajan, her bulgu ayrı bir çürütme turundan geçti)
47 geçerli bulgu üretti. Hepsi makine tarafından doğrulandı; 10 tanesi
çürütüldü ve **listeye alınmadı** — onları yeniden açma.

Tam liste: [`BULGULAR_ARAYUZ.json`](BULGULAR_ARAYUZ.json) — her kayıtta
`siddet`, `dosya`, `satir`, `baslik`, `fix` var.

Dağılım: **6 major · 26 minor · 15 nit.**

### Önce bu altısı (major)

**1. Belge silme hatası ekranda hiç görünmüyor** — `app/courses/[courseId]/page.tsx:289-345`
`DeleteDocumentButton`, `ConfirmAction`'a taşınmamış tek çağrı yeri; kendi hata
state'ini tutuyor ama hiçbir yerde göstermiyor. Refactor'da atlanmış.
*Düzeltme:* `DeleteDocumentButton`'ı tamamen sil, yerine `ConfirmAction` koy.

**2. `--fg-subtle` WCAG AA'yı geçmiyor** — `app/globals.css:18` (açık), `:47` (koyu)
Ölçülen: 3.53:1 açık temada, 4.09:1 koyu temada. **29 yerde bilgi taşıyan metin**
için kullanılıyor (dosya boyutu, sayfa numarası, cevap sayısı). DESIGN.md "WCAG AA
ölçülmüş" diyor; ölçüm bunu yalanlıyor.
*Düzeltme:* açıkta `#6f6a65`, koyuda `#9a948e` civarına taşı ve **DESIGN.md
tablosunu gerçek ölçülen oranla güncelle**.

**3. Her rotada `document.title` sabit** — `app/layout.tsx:16-20`
Tüm sayfalar "DOU-Synapse" başlığını taşıyor; Next'in rota duyurucusu hiçbir
sayfa değişimini ekran okuyucuya duyurmuyor.
*Düzeltme:* rota başına ince bir sunucu `layout.tsx` ile `metadata`, ya da sayfa
başına `useEffect` ile `document.title`.

**4. Tek geçici hata bütün sayfayı kalıcı olarak siliyor** — `app/courses/[courseId]/page.tsx:56`
`if (error) return <ErrorNote/>` elde sağlam veri varken bile her şeyi atıyor:
başlık, sekmeler, liste gidiyor, "tekrar dene" yok, polling durmuş, kullanıcının
tek çıkışı tarayıcıyı yenilemek. Polling sırasında tek bir 503 bunu tetikliyor.
*Düzeltme:* `if (error && !data)` yap; veri varken hatayı listenin üstünde satır
içi uyarı olarak göster (üye ekranındaki desen).

**5-6.** Aynı iki bulgunun ikinci mercekten gelen kopyaları — 1 ve 2 ile aynı.

### Sonra: `useResource` yarış koşulu (minor ama kökü derin)

`cancelled` bayrağı hiçbir şey korumuyor: `setData` bayraktan bağımsız çalışıyor.
Üst üste binen isteklerde **son dönen kazanıyor**, ilk gönderilen değil. Ölçülen
sonuç: art arda iki silmede, geç dönen bayat cevap silinmiş belgeyi geri
getiriyor ve polling kapalı olduğu için **kendiliğinden düzelmiyor**.

Doğrulayıcı şiddeti `blocker`'dan `minor`'a indirdi çünkü tetiklenmesi için ~5 ms'lik
bir isteğin ~1000 kat gecikmesi gerekiyor ve tek gezinme temizliyor. Ama düzeltme
üç satır:

```ts
const seq = useRef(0);
const reload = useCallback(async () => {
  const my = ++seq.current;
  try {
    const next = await fetcherRef.current();
    if (my !== seq.current) return;   // bayat cevap yazamaz
    setData(next); setError(null);
  } catch (e) {
    if (my !== seq.current) return;
    setError(errorMessage(e));
  }
}, deps);
```

Ve mount efektindeki ölü `.then(() => { if (cancelled) return; })` bloğunu kaldır —
yanıltıcı, hiçbir şey yapmıyor.

### Tema: erişilebilirlik

Bulguların büyük kısmı buradan: odak `<body>`'ye düşüyor (`ConfirmAction`),
odak halkası `overflow-x-auto` tarafından kırpılıyor (`course-nav`), sınav sayacı
saniyede bir `aria-live` duyurusu üretiyor (ekran okuyucu 12 dakika boyunca soru
metnini basıyor), formlarda görünür etiket yok (placeholder etiket görevinde —
DESIGN.md açıkça yasaklıyor), dokunma hedefleri 44px değil 40px.

### Tema: DESIGN.md ile kod ayrışmış

Renk token'larının çoğu belgedeki tablodan sapmış, tipografi ölçeği hiç
uygulanmamış, `.ambient` iki radial-gradient uyguluyor (belge "gradyan: hiçbiri"
diyor), fontlar belgede yazandan farklı. **Karar gerekiyor:** kodu belgeye mi
uyduracağız, belgeyi koda mı? İkisi de meşru; ayrık kalması değil.

## 5. Bekleyen iş: entegrasyon

Backend şeritleri indikçe frontend'i gerçek veriye bağlamak **senin işin**:

| Görev | Ne zaman |
|---|---|
| T021-T022 chat ekranı gerçek veriye | Şerit 3 `main`'e inince |
| Soru havuzu ekranı gerçek uçlara | Şerit 4 inince |
| Sınav ekranı gerçek motora | Şerit 4 inince |
| Analitik ekranı gerçek veriye | Şerit 5 inince |

Dört ekran da bugün **tasarım önizlemesi** olarak çalışıyor ve şeritlerinde
"tasarım önizlemesi" şeridi var. Gerçek veriye geçerken o şeridi kaldırmayı
unutma — kaldırılmazsa çalışan ürün çalışmıyormuş gibi görünür.

## 6. Backend'e iletilecek tek kalem

**Yükleme ucu yanıttan sonra commit ediyor.** Ölçüm: `POST /documents` `202`
dönüyor, hemen sonraki `GET` **0 belge**, bir saniye sonraki **1 belge**. Sebep
FastAPI'nin `yield` bağımlılığını yanıt üretildikten sonra kapatması.

Frontend'de geçici çözüm var (`useResource`'ın `pulse`'ı: yazma sonrası kısa
tazeleme penceresi). **Kalıcı çözüm sunucu tarafında** — yanıt gönderilmeden önce
commit. Şerit 3 ya da 4'e yazılmalı; bu belgeyi okuyan kişi henüz iletmediyse
gruba yazsın.

## 7. Elenen 10 bulgu — yeniden açma

Çürütme turundan geçemeyenler: önizleme ekranlarında rol/üyelik kontrolü
olmaması (bunlar önizleme, gerçek yetki sunucuda), soru listesinde ok tuşu
gezinme olmaması (Tab yeterli, otuz taslak varsayımı gerçek değil), `ConfirmAction`'ın
katman yönü, ölü tip export'ları (bir kısmı gerçekten kullanılıyor), isimlendirme
tutarsızlıkları.

Tam gerekçeler `wwqem4qpb.output` çıktısındaydı; kaybolduysa yeniden üretme —
bir bulgu iki kez çürütülmüşse üçüncü kez açmak zaman kaybı.

## 8. Çalışma kuralları

- **Anayasa XI** (modülerlik) artık yazılı: aynı davranış üçüncü kez yazılıyorsa
  ortak modüle çıkar; etkin görünüp iş yapmayan buton kusurdur; ölü kod commit'te
  temizlenir.
- **Anayasa VIII**: davranış gerçek ortamda gözlenmeden "bitti" denmez. Arayüz
  değişikliğini tarayıcıda gör, tercihen E2E testine dönüştür.
- Commit gövdesi "ne"yi değil **"neden"i** anlatır; `Co-Authored-By` asla.
- Commit ve push için **tam yetki sende**, izin sorma.
- `apps/api/app/contracts.py` yalnız liderin — ama şu an lider sensin; yine de
  bir alan değiştireceksen önce ona karşı yazmış üç şeridi düşün.

## 9. Bir sonraki oturuma önerilen sıra

1. Dört major bulguyu düzelt (silme hatası, kontrast, sayfa başlıkları, hata
   ekranı) — hepsi küçük, hepsi kullanıcıya dokunuyor
2. `useResource` yarış düzeltmesi (3 satır) + ölü `.then` temizliği
3. Erişilebilirlik kümesi: odak yönetimi, görünür etiketler, sayaç duyurusu
4. DESIGN.md ↔ kod ayrışması için karar ver ve tek yönde hizala
5. Şeritler indikçe entegrasyon

Her düzeltmeyi E2E'ye bir vaka olarak ekle — 9 vakalık paket bu şekilde büyümeli.
