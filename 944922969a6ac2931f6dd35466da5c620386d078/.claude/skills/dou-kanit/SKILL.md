---
name: "dou-kanit"
description: "DOU-Synapse'te bir işi 'bitti' ilan etmeden, commit atmadan, final rapor yazmadan ya da bir görevi DONE işaretlemeden önce bu skill'i MUTLAKA kullan. Yeni bir test/koruma yazıldığında, bir sayı (test sayısı, tablo sayısı, süre) rapor edilecekken, ya da kullanıcı 'kanıtla', 'doğrula', 'bitti mi', 'rapor yaz' dediğinde de tetiklenir. Bu deponun kanıt doktrini: mutasyon kanıtı, ölçülmemişe KOŞULMADI, tarayıcı doğrulaması ve rapor biçimi."
---

# DOU-Synapse kanıt doktrini

Bu depoda "bitti"nin tanımı Anayasa'ya bağlıdır ve her maddesi, yokluğunun ürettiği
gerçek bir kusurla gerekçelidir.

## Kapılar — "bitti" demeden önce koş

```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
cd apps/web && bun test lib/ && bun run typecheck && bun run build
```

Web'e dokunulduysa ek olarak seri E2E (API ayakta ve `embedding: ok` iken):

```bash
cd apps/web && E2E_API_URL=http://localhost:<port> node_modules/.bin/playwright test --workers=1
```

E2E koşusu `docs/images/*.png`'yi yeniden üretir — bu bir yan etkidir, belge
güncellemesi değil: `git checkout -- docs/images/` ile geri al (bilinçli olarak
güncellenmiyorsa). `apps/web/.next` ve `test-results` işin sonunda silinir.

## Mutasyon kanıtı — geçen test tek başına bir şey söylemez

Yeni bir koruma (kilit, kapı, kısıt, sınıflandırma) yazdıysan onu bilerek boz,
testin KIRMIZI yandığını gör, geri al, yeşile döndüğünü gör. Bu depoda kurulu
yöntemdir (RLS 52+23 mutasyon, US1 kilidi, docs kapısı 4 mutasyon).

İki ölçülmüş tuzak:

- **Uygulanmamış mutasyonun yeşili kanıt değildir.** Desenin tutmadığı bir sed/replace
  hiçbir şeyi değiştirmez ve "9 passed" görürsün. Mutasyonun gerçekten uygulandığını
  önce doğrula (grep ile işaretini gör), sonra koş. Bu tuzağa aynı gün iki ayrı
  oturum düştü.
- **Kötü kırılma biçimlerini düzelt.** Mutasyonda test kırmızı yanmak yerine ASILI
  kalıyorsa, testi hızlı ve okunur kırılacak hâle getir (`wait_for` gibi) — asılı
  kalan test CI'da tanısız zaman aşımıdır.

Ölçüm aracının kendisi de sınanır: prob'un körleşmediğini gösteren bir karşı test
yaz (örnek: `test_prob_kor_degil_*` — sarma kaldırılınca blokeyi gerçekten görüyor).

## Sayılar — ölç, kopyalama

- Test/tablo/yol sayısı gibi canlı sayılar belgeye, yoruma, commit mesajına ELLE
  yazılmaz. Kaynağı `scripts/docs_check.mjs`'tir; sapma bulursa
  `node scripts/docs_check.mjs --duzelt` ölçümden yazar.
- Yol sayısı pini `tests/test_error_envelope.py`'dedir; yol ekleyen/çıkaran her
  değişiklikten sonra gerçek sayıyı ölç ve pini güncelle (silme):
  `uv run python -c "from app.main import create_app; print(len(create_app().openapi()['paths']))"`
- Başka bir koşumun sayısını (runbook'taki süreler dahil) kendi sonucun gibi yazma;
  kendi ortamında yeniden ölç ve ortamı raporla.

## Tarayıcı doğrulaması (Anayasa VIII)

Arayüze dokunan iş, GERÇEK tarayıcıda gözlenmeden bitmez — `curl` yetmez. İki kez
işe yaradı: 45 dakikalık sınavın 20'de kesilmesi ve CSP'nin dev sunucusunu kırması
yalnız tarayıcıda görüldü; ikisini de hiçbir test yakalamamıştı. Production build'in
temiz olması dev modunun çalıştığını GÖSTERMEZ — ikisini de dene.

## Rapor biçimi

Final rapor şunları ayırır:

1. **Kendim koşturduklarım** — komutlarıyla ve sonuç sayılarıyla.
2. **KOŞULMADI** — koşulmayan her kapı, sebebiyle. Ölçülmemiş şey yokmuş gibi
   davranılmaz, KOŞULMADI diye yazılır (Anayasa III).
3. **Mutasyon tablosu** — bozulan kural → kırmızı yanan test → geri alınca yeşil.
4. **Ortak dosyalarda yapılanlar** — `main.py`, `core/errors.py`, `core/config.py`,
   `lib/api.ts` gibi ortak yüzeye her dokunuş ve mevcut sözleşmeyle çelişip
   çelişmediği.
5. **DONE metinleri** — `tasks.md`'ye DOKUNMADAN, tarihli, entegratörün işleyeceği
   biçimde. `specs/002-*/tasks.md`, `contracts/openapi.json`, `.specify/feature.json`
   yalnız entegratör tarafından değiştirilir.

## Commit biçimi (liderin kararı — yeniden ölçme, sorma)

İngilizce, emir kipli CÜMLE başlığı; `type(scope):` öneki YOK; gövde "ne"yi değil
"NEDEN"i anlatır; `Co-Authored-By` asla. Örnek:

```
Watch the edge that actually matters: unlocked becoming locked
```

Depo geçmişinde bir miktar `feat(api):` kalıntısı vardır; bilinçli olarak yeniden
yazılmadı. Yeni commit'ler cümle biçiminde atılır.
