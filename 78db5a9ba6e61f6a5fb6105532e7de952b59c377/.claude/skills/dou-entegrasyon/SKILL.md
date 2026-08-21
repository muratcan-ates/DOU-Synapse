---
name: "dou-entegrasyon"
description: "DOU-Synapse'te bir dalı birleştirirken, cherry-pick yaparken, başka bir aracın (GPT/codex dahil) yazdığı kodu 002'ye alırken, çakışma çözerken ya da 'bu dal birleşebilir mi', 'şu commit'i al', 'entegre et' sınıfı bir istekle karşılaşınca bu skill'i MUTLAKA kullan. Merge-base ölçümü, çakışma haritası, sözleşme-öncelikli çözüm doktrini ve entegrasyon sonrası zorunlu adımları içerir."
---

# DOU-Synapse entegrasyon doktrini

Entegratör tektir ve `dou-lead` worktree'sinde çalışır; başka hiçbir süreç oraya
yazmaz. Aşağıdaki her kural, ihlalinin ürettiği gerçek bir kazayla gerekçelidir.

## 1. Ölçmeden önce merge-base — en pahalı tuzak

`git diff <entegrasyon-ucu>..<dal>` YANILTIR: dal eski bir tabandan açıldıysa fark,
dalın HİÇ dokunmadığı kalıtsal işi de "dal değiştirmiş" gibi gösterir. Aynı oturumda
iki kez bu tuzağa düşüldü. Her ölçüm dalın kendi tabanına göre yapılır:

```bash
mb=$(git merge-base HEAD <dal>)
git diff --name-only $mb..<dal>          # dalın GERÇEKTEN değiştirdiği
git rev-list --count $mb..<dal>          # gerçek commit sayısı
```

## 2. Birleştirmeden önce harita

- **Kesişim:** `comm -12 <(git diff --name-only $mb1..dal1|sort) <(git diff --name-only $mb2..dal2|sort)`
- **Çakışma önizlemesi (ağaca dokunmadan):** `git merge-tree --write-tree --name-only HEAD <dal>`
- **İçerik zaten alınmış mı:** `git cherry HEAD <dal>` (`-` = içerik SHA farklı olsa da mevcut).
  GitHub'ın "N commit ahead" göstergesi işaretçidir, içerik kanıtı değil.
- **Migration numarası çakışması:** iki dal aynı `supabase/migrations/NNNN_*.sql`
  numarasını almış mı? Aynı işin iki kez yapılmış olabileceğini de kontrol et
  (dosyaların md5'i — bir kez `0012` iki dalda byte-byte aynı çıktı).

## 3. Büyük tek commit'i bölerek almak

`git apply -3` bu iş için YANLIŞ araçtır: atomiktir, tek dosya düşerse tamamı sessizce
geri sarılır. Doğru yol:

```bash
git cherry-pick -n <commit>              # gerçek 3-yollu merge, commit'siz
git checkout HEAD -- docs specs ...      # dışlanacak yolları geri çek
# çakışmaları çöz, sonra yol-bazlı paketler hâlinde commit'le
```

İki ölçülmüş dikkat:

- **Düşen `git add` bile bazı dosyaları stage'lemiş olabilir** (gitignore'lu dosyaya
  takılan zincir). Her commit'ten önce `git status` ile stage'i doğrula — bir kez iki
  paket tek commit'e karıştı.
- Kısmi çözüm bırakma: çağrı yerini bir taraftan, imzayı öbür taraftan almak
  derlenmeyen ara durum üretir. Çözümden sonra ilgili dosyanın bütünlüğünü
  (import'lar, imza, şema alanı) uçtan uca kontrol et.

## 4. Çakışma çözüm doktrini: onaylı sözleşme kazanır

İki taraf aynı işi farklı yazmışsa, bu deponun ONAYLI sözleşmesi kazanır; dışarıdan
gelen kopya uyarlanır:

- Hata zarfı: `{error: {code, message, request_id}}` — `core/errors.py` tek üretici.
- Değerlendirme yanıtı: `score` zorunlu + opsiyonel `rubrik` (T507). Kırılımdan puan
  hesaplanır, modelden okunmaz. Farklı alan adıyla gelen testler sözleşmeye çekilir.
- Kopya yardımcılar tek kurala bağlanır (örn. gelen `_normalized_rubric_weights`
  yerine mevcut `schemas.normalized_rubric`) — "iki şerit aynı kuralı iki kez yazar"
  hastalığını entegrasyonda içeri alma.
- Refactor'ün yarısı alınmaz: taban sınıf/fabrika deseni geldiyse, o desene uymayan
  YENİ kod da (sonradan gelen modeller, testler) desene bağlanır; yoksa depoda iki
  desen kalır.

## 5. Entegrasyon sonrası zorunlu sıra

1. Yol pini yeniden ölç (`create_app().openapi()`) → `tests/test_error_envelope.py`.
2. `openapi.json`'ı uygulamadan yeniden üret (elle düzenlenmez):
   ```bash
   cd apps/api && uv run python -c "
   import json; from app.main import create_app
   json.dump(create_app().openapi(), open('../../specs/001-course-assistant-mvp/contracts/openapi.json','w'), ensure_ascii=False, indent=2)"
   ```
3. `node scripts/docs_check.mjs` → kırmızıysa `--duzelt` (sayılar ölçümden yazılır).
4. Yeni migration'ları paylaşılan `dou_synapse`'a uygula
   (`psql -v ON_ERROR_STOP=1 --single-transaction`), tablo sayısını ölç.
5. Tam kapılar + seri E2E (`dou-kanit` skill'indeki gibi). E2E'nin ürettiği
   `docs/images` değişikliklerini geri al.
6. Push. Ekran görüntüsü/`.next`/`test-results` artıklarıyla push'lama.

## 6. E2E kırılırsa: kararsızlık mı, gerçek mi?

Önce ayır: düşenleri `--workers=1` ile tek tek ve sonra TÜM paketi seri koş.
Seri koşuda da düşüyorsa gerçektir. İki gerçek kırılma sınıfı ölçüldü:

- **Locator belirsizliği:** yeni arayüz ögesi (örn. açılır listede dosya adları)
  `getByText`'i çoğaltır → locator'ı role/kapsayıcıya kapsa.
- **Zarf değişimi:** liste uçları `{items, next_cursor}` sayfalama zarfına geçti;
  düz dizi bekleyen yardımcıları zarfı açacak şekilde güncelle.

API ısınmadan (`embedding: warming`) alınan E2E sonuçları ölçüm değildir — istekler
model yüklemesini bekleyip zaman aşımına düşer; `ok`'u bekle, sonra koş.

## 7. Rezerve dosyalar ve dallar

- `specs/002-*/tasks.md`, `contracts/openapi.json`, `.specify/feature.json`:
  YALNIZ entegratör. Dışarıdan gelen commit'lerdeki bu dosya değişiklikleri
  entegrasyonda dışlanır (entegratör kendisi üretir).
- Belge dosyaları (`ARCHITECTURE.md`, `README.md`, `docs/**`) dış commit'lerden
  alınmaz — `docs_check` güncel ağaçtan yeniden üretir.
- Dal, içeriği alınıp doğrulanmadan silinmez; alındıktan sonra da tutulmaz.
