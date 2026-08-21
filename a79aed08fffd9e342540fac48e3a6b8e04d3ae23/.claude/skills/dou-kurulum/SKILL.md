---
name: "dou-kurulum"
description: "DOU-Synapse'te yeni bir worktree/şerit kurarken, API veya web sunucusu açarken, ya da 'sunucu açılmıyor', 'pytest bulunamıyor', 'her istek 422 dönüyor', 'retrieval alakasız sonuç veriyor' sınıfı bir kurulum belirtisiyle karşılaşınca bu skill'i MUTLAKA kullan. Ortam kurulumu, port düzeni, paylaşılan veritabanı kuralları ve bu depoda ölçülerek bulunmuş kurulum tuzaklarını içerir. Kullanıcı 'worktree aç', 'yeni şerit', 'ortamı kur', 'sunucuyu başlat' dediğinde de tetiklenir."
---

# DOU-Synapse ortam kurulumu

Bu depoda her kurulum adımının bir tuzağı ölçülerek bulundu; adımlar keyfî değil.
Sırayla uygula, atlama.

## Yeni worktree

```bash
git -C /Users/muratates/code/dou-lead worktree add -b <dal> /Users/muratates/code/<dizin> <BASE_SHA>
cd /Users/muratates/code/<dizin>
git log --oneline -1    # BASE_SHA olmalı
git status --short      # boş olmalı
```

HEAD base ile aynı değilse veya ağaç kirliyse DUR ve bildir.

## Bağımlılıklar — üç zorunlu adım

```bash
cd apps/api && uv sync --extra dev
cp /Users/muratates/code/dou-lead/apps/api/.env .
cd ../web && bun install
```

Nedenleri (üçü de yaşandı):

1. **`--extra dev` şart.** Düz `uv sync` pytest/ruff/mypy kurmaz; `uv run pytest`
   "Failed to spawn: pytest" der ve bu, ortam hatası yerine testin yokluğu gibi okunur.
2. **`.env` kopyalanmalı.** API onsuz açılmaz (`SUPABASE_JWT_SECRET tanımlı olmalı...`).
   `.gitignore` gereği worktree'ye gelmez.
3. **`.venv` ve `node_modules` ASLA sembolik bağla paylaşılmaz.** venv içindeki
   `_editable_impl_dou_synapse_api.pth` mutlak yol tutar; paylaşılan venv kodu BAŞKA
   ağaçtan çözer ve `uv run` her koşuda bu dosyayı kendi yoluna göre yeniden yazar —
   iki worktree birbirinin üstüne yazar, hangi kodu test ettiğin belirsizleşir.

## Sunucular — adla aç, portla değil

Sunucular `~/.claude/launch.json`'da şerit başına kayıtlıdır (`dou-<şerit>-api` /
`dou-<şerit>-web`). `preview_start` ile adıyla aç. Kayıt yoksa aynı desenle ekle:
API `EMBEDDING_PROVIDER=fastembed` ve doğru `CORS_ORIGINS` (kendi web portu +
Playwright'ın 3100'ü) satır içi almalı; `autoPort: false` olmalı çünkü API'nin CORS'u
web'in portunu, web'in `NEXT_PUBLIC_API_URL`'i API'nin portunu içerir.

**Sunucuya güvenmeden önce ölç** — bir kez, eski bir oturumun sunucusu bayat sözleşme
servis etti ve her istek 422 döndü (25 yol vs güncel 26+):

```bash
curl -s http://localhost:<PORT>/openapi.json | python3 -c "import json,sys;print(len(json.load(sys.stdin)['paths']))"
```

Sayı, koddaki `create_app().openapi()` sayısıyla eşleşmeli.

## Embedding

- Paylaşılan `dou_synapse` korpusu E5 uzayındadır. Korpusa dokunan HER komut
  `EMBEDDING_PROVIDER=fastembed` ile koşmalı — `hashing` ÇÖKMEZ, sessizce alakasız
  sonuç döndürür ve "retrieval kötü" gibi okunur.
- Isıtma süresi ortama bağlıdır: sıcak önbellekte 1,6–3,2 sn, günün ilk koşusunda
  ~15 sn, model hiç indirilmemişse ya da bellek doluysa DAKİKALAR. `/health/ready`
  ısınırken `503 + embedding: warming` döndürür; bu bir arıza değil tasarımdır —
  bekle, `ok` olunca devam et.

## Paylaşılan geliştirme veritabanı

- pytest worktree adına göre ayrı test DB kurar (`dou_synapse_test_<slug>`) —
  paylaşılana dokunmaz. AMA aynı worktree'de iki pytest AYNI test DB'de çakışır ve
  yüzlerce sahte "error" üretir; asla paralel koşturma.
- `COME 331 · İşletim Sistemleri` (`c3b76077-20de-47e5-9fe1-4e770ffa64d2`) GERÇEK
  demo dersidir: onaylı sorular, Ayşe (eğitmen) ve Burak (öğrenci) profilleri.
  Ekran görüntüsü üretimi de buna bağlıdır. Hiçbir temizlik dokunamaz.
- Playwright'ı başka bir sohbetin pytest/API koşusuyla aynı anda çalıştırma; paylaşılan
  DB + `fullyParallel` kararsızlık üretir. Şüphede `--workers=1` ile koş.

## Küçük ama pahalı bilinenler

- `bunx playwright` KULLANMA (ayrı kopya indirir, sürüm çatışması verir):
  `node_modules/.bin/playwright`.
- Next.js 16 aynı dizinden ikinci dev sunucusuna izin vermez.
- İş bitince sunucuları kapat ve `apps/web/.next` + `test-results` sil — bayat sunucu
  bir sonraki sohbeti 422 tuzağına düşürür, artıklar diski doldurur.
