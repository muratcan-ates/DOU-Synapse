# Lider şeridi — devir teslim

> **Güncellendi: 9 Ağustos 2026, ~18:30.** Önce `00_OKU_ONCE.md`, sonra burası.
> Faz 2'nin beş şeridi için `10_OKU_ONCE_FAZ2.md`.
> Şerit: **frontend'in tamamı + entegrasyon + CI + sözleşme dikişleri.**

---

## 1. İlk iş — doğru klasör

```bash
cd ~/code/dou-lead
git branch --show-current      # "main" yazmalı
git pull origin main
```

`~/code/DOU-Synapse` klasörüne **dokunma** — orada başka bir oturum var.

## 2. Sunucular — PORT ÇAKIŞMASI VAR, DİKKAT

Bu makinede **:8000'de başka bir ağacın eski API'si** koşuyor (`~/code/DOU-Synapse`).
O sunucu eski sözleşmeyi konuşuyor (`ChatRequest.message`, ham `{detail:[…]}` 422).
`lib/api.ts`'in varsayılanı `http://localhost:8000` olduğu için, portu açıkça
vermezsen tarayıcı **yanlış sunucuya** gider ve her sohbet isteği 422 döner.

Lider oturumunun portları:

```bash
cd ~/code/dou-lead/apps/api && \
  CORS_ORIGINS='["http://localhost:3000","http://localhost:3100","http://localhost:3010"]' \
  uv run uvicorn app.main:app --port 8010                                  # terminal 1
cd ~/code/dou-lead/apps/api && uv run python -m app.worker                 # terminal 2
cd ~/code/dou-lead/apps/web && NEXT_PUBLIC_API_URL=http://localhost:8010 \
  bun run dev --port 3010                                                  # terminal 3
```

`CORS_ORIGINS`'i vermezsen tarayıcı isteği CORS'a takılır ve ekran "Bağlantı
kurulamadı" der — ürün hatası gibi görünen bir kurulum hatası.

**Test koştururken `bunx playwright` KULLANMA** — ayrı kopya indirip "two
different versions" hatası veriyor. `node_modules/.bin/playwright`.

## 3. Durum — 9 Ağustos 18:30

`main` = `932ce6d`.

| Katman | Durum |
|---|---|
| Backend testleri | **479 geçiyor** |
| mypy | temiz, 59 dosya |
| ruff | temiz (check + format) |
| Frontend birim | **184 geçiyor** (sabah 25'ti) |
| Frontend uçtan uca | **19 vaka** — 16 geçiyor, 3 gerekçeli atlanıyor |
| `next build` | temiz |
| Kontrast kapısı | temiz, CI'da koşuyor |
| OpenAPI | kodla birebir, 24 yol |
| Şema | `0001` `0003` `0004` `0005` — 15 tablo |

**Dört ekranın dördü de gerçek uçlara bağlı** ve tarayıcıda doğrulandı:
sohbet (T022), sınav provası (T034), soru havuzu (T035), ilerleme (T040).
Hiçbirinde `PreviewBanner` kalmadı; uydurma veri kalmadı.

Faz 2'nin beş şeridi `10_OKU_ONCE_FAZ2.md` ile başlatıldı.

**Atlanan üç uçtan uca vakası** koşulmadı çünkü soru üretimi API anahtarı
olmadan sahte sağlayıcıya düşüyor ve hiç soru döndürmüyor. Atlama koşullu ve
kendi kendini açar: üretim çalıştığı gün üç vaka da kendiliğinden koşar.

## 4. Bugün kapatılan üç sessiz kusur

Üçü de "sistem çalışıyor gibi görünürken çalışmıyordu" sınıfından. Bu sınıf bu
projede özellikle tehlikeli, çünkü **abstention ürünün başarısı sayılıyor** —
yani bozuk bir sistem, kibarca reddederek sağlıklı görünebiliyor.

**1. Uç ile istemci farklı sözleşmeler konuşuyordu.** T021 frontend tiplerini
`app/schemas/chat.py`'ye göre yazmıştı; canlı uç ise kendi geçici kopyasını
kullanıyordu (`message` vs `question`, `quote` vs `snippet`, `hints[]` yok,
`student_attempt` hiç geçirilmiyor). Her sohbet isteği 422 alacaktı ve hiçbir
test bunu göremezdi: backend testleri uçtaki kopyaya karşı yazılmıştı, yani iki
taraf da kendi içinde tutarlı ve birbiriyle kullanılamazdı. Zarf artık tek
dosyada.

**2. İşlem, yanıt istemciye gittikten SONRA commit ediliyordu.** FastAPI'nin
`yield` bağımlılıkları varsayılan olarak yanıt yazıldıktan sonra kapanıyor.
`SessionDep` artık `scope="function"`. Yan etki: yükleme ucunun arka plan
worker tetiği **artık gerçekten iş buluyor** — önceden boş kuyruk görüp sessizce
sıfır dönüyordu, yani yalnız API çalıştırılan bir kurulumda hiçbir belge
işlenmezdi.

**3. Kanıt eşiği vektör uzayına bağlıydı ve bu bağ zorlanmıyordu.** 0.81
`fastembed` (E5) uzayında kalibre edildi; dev veritabanı `hashing` ile ingest
edilmişti ve o uzayda skorlar 0.07–0.37 arasında. Sonuç: eşik **her soruyu**
reddediyordu, kapsam içindekiler dahil — ve ekranda bu, düzgün çalışan bir
abstention gibi görünüyordu. Eşik artık sağlayıcı başına çözülüyor ve yeni bir
sağlayıcı eşiksiz eklenirse test kırmızı yanıyor.

## 5. Arayüz bulguları — 44/47 kapandı

Altı mercekli incelemenin 47 bulgusundan 44'ü kapatıldı (`BULGULAR_ARAYUZ.json`).
Dört major: silme hatasını yutan kopya buton, AA altındaki `--fg-subtle`,
rota başlıkları, tek geçici hatanın bütün sayfayı silmesi.

`--fg-subtle` artık **ölçülüyor, iddia edilmiyor**: `apps/web/scripts/contrast.mjs`
her token çiftini iki temada raporluyor ve değerle birlikte commit'li.

Betik bize katılmadığı yerde de konuştu: `--border-strong` girdi/ikincil buton
kenarlığında **1.33:1** (açık) ve **1.62:1** (koyu) çıktı — WCAG 1.4.11'in
istediği 3:1'in altında. Düzeltildi: şimdi 3.16/3.13 (açık), 3.12/3.15 (koyu).

Betik artık **CI'da kapı**: eşiği geçmeyen bir çift varsa `web` job'u kırılır.
Kapının gerçekten kırdığı da doğrulandı — `--fg-subtle` bilerek zayıflatıldığında
çıkış kodu 1 ve iki çifti birden adlandırıyor, geri alınınca 0. Metin dışı bölüm
bir süre "ölçülür ama kapı değil" diye koştu ve `--border-strong` tam o boşlukta
kalmıştı; **ölçülüp kapıya bağlanmayan sayı, ölçülmemiş sayıdır.**

## 6. Frontend'in tamamı liderde

Faz 2'de **hiçbir şerit `apps/web`'e dokunmuyor.** Sebep: dokuz ekran aynı beş
ortak bileşeni (`ui.tsx`, `page-state.tsx`, `use-resource.ts`, `session.ts`,
`labels.ts`) paylaşıyor ve bunlar paralel düzenlemeye dayanmıyor.

Şeritler arayüzde bir şeye ihtiyaç duyarsa raporlarına yazıyor; lider yapıyor.
Gelmesi beklenenler: R1'den giriş ekranı çağrı imzası, R5'ten KVKK sayfası metni.

## 7. Sıradaki iş

1. **Sınav oturum listesi ucu** — karar senin (bkz. §8). Öğrenci oturum
   kimliğini kaybederse devam eden sınavına dönemiyor.
2. R1'in giriş sözleşmesi gelince gerçek Supabase Auth'a bağlama (T023 frontend ayağı)
3. R5'in KVKK metni gelince sayfa
4. Şerit 4/5'ten gelen `0005` üç kalemi için migration numarası ata
5. Dört ekranın erişilebilirlik ikinci turu (odak tuzakları, klavye akışı)
6. Anahtar geldiğinde: soru üretimini gerçek LLM'le koştur, atlanan üç uçtan
   uca vakasının açıldığını gör

## 8. Şeritlerden gelen ve karar bekleyen kalemler

Şerit 4 ve 5 raporlarından, kapatılmamış olanlar:

- **Sınav oturum listesi ucu yok.** Öğrenci oturum kimliğini kaybederse devam
  eden sınavına dönemiyor; aynı açık, oturumu bırakıp yeni süre almasına da
  izin veriyor. Brief `GET .../{session_id}` diyor; Şerit 4 kendi başına
  genişletmedi. **Karar liderin.**
- **`0005`'te üç kalem:** eğitmen soru silme politikası, `exam_sessions` kolon
  GRANT'i, opsiyonel yeniden puanlama fonksiyonu. Yamaları
  `KARARLAR_SERIT4.md`'de yazılı.
- ~~**Belge silme 500'ü**~~ — **KAPANDI (9 Ağu).** Havuzda sorusu olan belgeyi
  silmek artık 409 ve anlaşılır Türkçe mesaj döndürüyor; kısıt (`source_chunk_id
  ON DELETE RESTRICT`) bilinçli olarak yerinde bırakıldı. Reddedilen silmenin
  ne satırı ne dosyayı bozmadığı da testli.
- **`out_of_scope` etiketi hiç üretilmiyor** → SC-005 %0 çıkıyor. **R4'e verildi.**
- **`EVAL_LLM_API_KEY`** artık `Settings`'te (bugün eklendi).
- **Analitikte "en çok yanlış yapılan sorular"** hiç yanlış yapılmamış soruları
  da listeliyordu — **kapandı (9 Ağu)**, artık yalnız gerçekten yanlış yapılmış
  sorular giriyor ve boş liste anlamlı bir cevap.
- **AÇIK RİSK: embedding SÜRÜM uyuşmazlığı.** fastembed bu modeli artık mean
  pooling ile koşuyor (eskiden CLS) ve bunu yalnız bir uyarıyla söylüyor.
  Vektör uzayı değişikliğidir; farklı sürümle embed edilmiş korpus sessizce
  yanlış komşu döndürür. Kalıcı çözüm chunk başına sağlayıcı+sürüm kaydı ister
  (migration) — **R4'e verildi**, R2 ve R3'ün belgelerine de yazıldı.

## 9. Çalışma kuralları

- **Anayasa XI**: aynı davranış üçüncü kez yazılıyorsa ortak modüle çıkar;
  etkin görünüp iş yapmayan buton kusurdur; ölü kod temizlenir.
- **Anayasa VIII**: davranış gerçek ortamda gözlenmeden "bitti" denmez.
  Bu şeritte "gerçek ortam" = tarayıcı + bu ağacın API'si (:8010), curl değil.
- Commit gövdesi "ne"yi değil **"neden"i** anlatır; `Co-Authored-By` asla.
- **Commit ve push için tam yetki sende**, izin sorma.
