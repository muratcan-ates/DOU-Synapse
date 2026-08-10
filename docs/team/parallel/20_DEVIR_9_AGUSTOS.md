# Devir teslim — 9 Ağustos 2026, gün sonu

> **10 Ağustos düzeltme notu:** Bu belge tarihsel bir anı kaydeder. Aşağıdaki
> "sahte sağlayıcı sıfır soru döndürüyor" iddiası `67ee442` ile bayatladı;
> `test_uretilen_taslak_havuza_kadar_gider` deterministik sağlayıcının geçerli
> taslak üretip havuza yazdığını kanıtlıyor. Gerçek anahtarın beklediği şey akış
> değil, pedagojik kalite ve faithfulness değerlendirmesidir.

> **Bu belge yeni bir oturumun tek başlangıç noktasıdır.** Önce bunu bitir, sonra
> gerekirse `00_OKU_ONCE.md` ve `10_OKU_ONCE_FAZ2.md`'ye bak (ikisi de artık
> tarihsel kayıt — şeritleri anlatıyorlar, hepsi kapandı).
>
> Teslim **24 Ağustos**. Bugün elde çalışan, ölçülmüş ve belgelenmiş bir sistem var.

---

## 1. İlk iş — doğru klasör ve doğru portlar

```bash
cd ~/code/dou-lead
git branch --show-current      # "main" yazmalı
git pull origin main
```

`~/code/DOU-Synapse` klasörüne **dokunma** (orada eski bir oturum ağacı var).

### PORT ÇAKIŞMASI — bu makinede gerçek bir tuzak

`:8000`'de **başka bir ağacın eski API'si** koşuyor olabilir ve o sunucu eski
sözleşmeyi konuşuyor. `apps/web/lib/api.ts`'in varsayılanı `http://localhost:8000`
olduğu için portu açıkça vermezsen tarayıcı yanlış sunucuya gider ve her sohbet
isteği 422 döner — ürün hatası gibi görünen bir kurulum hatası.

Bu oturumun portları ve **çalışan tam komut**:

```bash
# terminal 1 — API
cd ~/code/dou-lead/apps/api && \
  EMBEDDING_PROVIDER=fastembed \
  CORS_ORIGINS='["http://localhost:3000","http://localhost:3010","http://localhost:3100"]' \
  uv run uvicorn app.main:app --port 8010

# terminal 2 — worker
cd ~/code/dou-lead/apps/api && uv run python -m app.worker

# terminal 3 — web
cd ~/code/dou-lead/apps/web && \
  NEXT_PUBLIC_API_URL=http://localhost:8010 bun run dev --port 3010
```

Üç şey birden gerekli ve üçü de bir kez unutuldu:

* **`EMBEDDING_PROVIDER=fastembed`** — paylaşılan `dou_synapse` korpusu E5
  uzayında gömülü. `hashing` ile sorgularsan çökmez, **sessizce alakasız sonuç**
  döner ve "retrieval kötü" gibi okunur.
* **`CORS_ORIGINS`'e 3100** — Playwright kendi sunucusunu orada açıyor. Yoksa
  uçtan uca ve ekran görüntüsü koşuları "Bağlantı kurulamadı" gösterir.
* **`bunx playwright` KULLANMA** — ayrı kopya indirir, "two different versions"
  hatası verir. `node_modules/.bin/playwright`.

## 2. Durum

`main` = `5a567fe`. **Bugün 141 commit.**

| Katman | Durum |
|---|---|
| Backend testleri | **664 geçiyor** |
| Frontend birim | **211 geçiyor** |
| Uçtan uca | 19 vaka — 16 geçiyor, 3 gerekçeli atlanıyor |
| mypy | temiz, 62 dosya |
| ruff | temiz (check + format) |
| `next build` | temiz |
| Kontrast kapısı | temiz, CI'da koşuyor |
| OpenAPI | kodla birebir, **25 yol** |
| Şema | `0001`–`0007`, **15 tablo** |
| Görev listesi | **56/60 — %93** |

**On şerit de kapandı ve `main`'de:** retrieval, generation, chat+Sokratik,
soru/sınav, analitik+eval (Faz 1) · kimlik, ölçüm, dağıtım, cevap kalitesi,
belgeler (Faz 2). Beş Faz-2 dalı uzaktan **silinmedi**, duruyor.

Dört ekranın dördü de gerçek uçlarda ve tarayıcıda sürülerek doğrulandı:
sohbet, sınav provası, soru havuzu, ilerleme. Hiçbirinde önizleme şeridi ya da
uydurma veri kalmadı.

## 3. Kalan dört görev — hepsi dış erişim bekliyor

Kod tarafında yapılabilecek iş **kalmadı**. Dördü de senin sağlaman gereken bir
erişime bağlı:

| Görev | Neyi bekliyor | Hazır olan |
|---|---|---|
| **T023** Supabase Auth canlı koşusu | Gerçek Supabase projesi + anahtarları | `0002` köprüsü, JWT sertleştirmesi, 7 vakalık test — sahte `auth.users` üstünde sınandı |
| **T047** Faithfulness örneklemi | Gerçek LLM anahtarı | Şablon, örnekleyici, süreç |
| **T050** Prod ortam doğrulaması | Bulut erişimi (ACA/Vercel/Supabase) | `docs/deployment.md`, Dockerfile, compose profili |
| **T051** RLS kanıtının prod'da koşması | Aynı erişim | Yerelde 98 iddia / 52 mutasyon geçiyor |

**Anahtar geldiği gün ilk koşulacaklar** (sırayla):

1. Soru üretimini gerçek sağlayıcıyla koştur — bugün sıfır soru dönüyor
2. Atlanan üç uçtan uca vakasının kendiliğinden açıldığını gör
3. T047 örneklemini çek, iki tur etiketle
4. Kapsam ayrımı (`retrieval/scope.py`) yerindeyken **eşiği yeniden ölç**

## 4. Bilinen üç açık — hepsi kayda geçmiş

**a) Soru üretimi bu ortamda sıfır soru döndürüyor.** Gerçek anahtar yokken
sahte sağlayıcı devreye giriyor ve soru şemasını üretemiyor
(`rejection_reasons: ["yanıtta 'questions' dizisi yok"]`). Sistem fail-closed
davranıyor — uydurma soru havuza **girmiyor**, ki doğrusu bu. Ama sınav demosu
elle tohumlanmış havuza bağlı ve üç uçtan uca vakası bu yüzden atlanıyor.
Atlama koşullu ve kendini açar: üretim çalıştığı gün üçü de kendiliğinden koşar.

**b) Kanıt eşiği holdout'ta hedefi tutturmuyor.** 0.81 kalibre edildi, doğru ret
**%80** (hedef %90). Üç şerit üç farklı sayı önerdi:

* R2 (n=40, en dengeli set): 0.815
* R3 (n=16): "0.81 GEÇERLİ soruları kesiyor" — doğru belgesi en üstte gelen iki
  soru 0.7973 ve 0.8051 ile reddedildi, en yüksek kapsam dışı 0.7867
* R4 (n=15): "sorun eşiğin değeri değil, baktığı sinyalin darlığı"

**Değiştirilmedi** ve gerekçesi `config.py`'de yazılı: üçü de kapsam ayrımı
inmeden önce ölçüldü, o modül eşiğin işini değiştirdi. Şimdi 0.815'e çekmek,
ölçülmemiş bir dünyada ölçülmüş bir sayı kullanmak olurdu. **Doğru sıra: yeniden
ölç, sonra karar ver.**

**c) Embedding sürüm uyuşmazlığı.** `fastembed` 0.8.0, e5-large'ı mean pooling'e
geçirdiğini yalnız bir uyarıyla söylüyor. Sürüm `0.8.x`'e sabitlendi ve her parça
hangi uzayda gömüldüğünü kaydediyor (`0006`), uyuşmazlık fail-closed reddediliyor.
Ama `0006` öncesi gömülmüş bir korpusun damgası **NULL** ve NULL damga kontrolü
geçer — yani eski korpuslar hâlâ korunmuyor. Bilinçli: "damgasız satırı da reddet"
demek, göçün uygulandığı anda her kurulumu tuğlaya çevirirdi.

## 5. Bugünün en önemli dersi — sessiz kusur sınıfı

Bugün bulunan ciddi kusurların **tamamı** gürültülü değil sessizdi. Sistem
çökmedi, hata vermedi; **çalışıyor gibi göründü**:

| Kusur | Nasıl gizlendi |
|---|---|
| İstemci ve sunucu farklı sözleşme konuşuyordu | Her iki tarafın testleri kendi kopyasına karşı yazılmıştı, ikisi de yeşildi |
| İşlem yanıttan **sonra** commit ediliyordu | Yükleme worker tetiği ömrü boyunca boş kuyruk gördü ve sessizce sıfır döndü |
| Kanıt eşiği yanlış vektör uzayından | **Her soruyu** kibarca reddetti — tam da ürünün doğru davranışı gibi |
| "En çok yanlış yapılan sorular" | Kimsenin yanlış yapmadığı sorularla kendini dolduruyordu |
| Guardrail zinciri dört yolu atlıyordu | Atıf kartı, önbellek, şablon ipucu ve `claim` denetimden geçmiyordu |
| Kendi yazdığım FTS nöbetçisi | İlk **iki** denemesi, kod bilerek bozulduğunda da yeşil kaldı |

**Bunun sebebi ürünün tezi:** "bilmiyorum diyebilen asistan". Abstention bir
başarı sayıldığında, **bozuk bir sistemle çalışan bir sistem aynı ekranı çizer.**

Pratik kural: *"kibarca reddetti" doğrulanacak bir şeydir, güvenilecek bir şey
değil.* Ve bir testin geçmesi, ancak **kırılabildiği gösterildiğinde** bir şey
söyler — mutasyonla dene.

## 6. Dosya sahipliği — artık tek oturum

Faz 2 bitti, kilit yok. Ama iki alışkanlık korunmalı:

* `specs/.../contracts/openapi.json` — **elle düzenlenmez.** Yeni uç eklediysen
  oturum sonunda bir kez yeniden export et. Çakışırsa `git checkout --theirs`,
  sonra komutu tekrar koştur.
* `specs/.../tasks.md` — merge sırasında `--theirs` alırsan **kendi işaretlerini
  silersin.** Bugün bir kez oldu ve altı görev yanlışlıkla açık göründü.

## 7. Yeni bir paralel tur açacaksan

Desen çalıştı ve iki turda 10 şerit taşıdı. Kritik üç kural:

1. **Her oturum kendi `git worktree`'sinde.** `git checkout -b` klasör genelinde
   etki eder; ilk turda iki şeridin commit'i başka dalın üstüne düştü.
2. **Ortak dosyalar önden düzenlenir.** İki şeridin dokunacağı her şeyi tur
   başlamadan lider bir kez düzenler (`config.py`, `main.py`, `contracts.py`,
   tipler). Faz 2'de bu yapıldı ve tek bir gerçek çakışma çıktı.
3. **Ölçmeden sayı yazma.** Faz 2 brifinginde "19 tablo görmelisin" yazdım;
   doğrusu 15'ti ve iki şerit sağlam bir veritabanını bozuk sanıp zaman harcadı.

## 8. Belgeler — hangisi ne anlatıyor

| Belge | İçerik |
|---|---|
| [`README.md`](../../../README.md) | Jürinin başlayacağı yer: ne, kime, farkı ne, kanıtı ne, ekran görüntüleriyle |
| [`docs/runbook.md`](../../runbook.md) | Demo günü — üç plan, geçiş kararı belirtiyle tanımlı |
| [`docs/demo-script.md`](../../demo-script.md) | Sahne sahne anlatım, süreli ve replikli |
| [`docs/test-report.md`](../../test-report.md) | Ölçüm raporu — her satır ya sayı ya `KOŞULMADI` |
| [`docs/security.md`](../../security.md) | Kimlik, izolasyon, injection savunması; iddiaların kod karşılığı satır numaralı |
| [`docs/deployment.md`](../../deployment.md) | Kurulum, ortam değişkenleri, rollback |
| [`docs/kvkk.md`](../../kvkk.md) | Aydınlatma metni — sayfası `/kvkk`, metni buradan okur |
| [`docs/instructor-guide.md`](../../instructor-guide.md) · [`student-guide.md`](../../student-guide.md) | Ekran görüntülü kullanım kılavuzları |
| [`evaluation/calibration.md`](../../../evaluation/calibration.md) | Eşiğin nasıl donduğu — **yöntem dersi**, okunması önerilir |
| `14_R4_KALITE.md` · `12_R2_OLCUM.md` · vb. | Şerit raporları; her sayının yanında onu üreten komut |

## 9. Çalışma kuralları

* **Anayasa VIII**: davranış gerçek ortamda gözlenmeden "bitti" denmez. Bu
  şeritte gerçek ortam = tarayıcı + bu ağacın API'si, `curl` değil.
* **Anayasa XI**: etkin görünüp iş yapmayan yüzey kusurdur; ölü kod temizlenir.
* Commit gövdesi "ne"yi değil **"neden"i** anlatır; `Co-Authored-By` asla.
* **Commit ve push için tam yetki**, izin sorulmaz.
