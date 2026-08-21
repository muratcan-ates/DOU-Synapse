# Lider şeridi — devir teslim

> **Güncellendi: 9 Ağustos 2026, ~14:15.** Önce `00_OKU_ONCE.md`, sonra burası.
> Şerit: **frontend + entegrasyon + CI + belgeler.** Backend'e yalnız
> entegrasyon dikişleri için dokunulur.

---

## 1. İlk iş — doğru klasör

```bash
cd ~/code/dou-lead
git branch --show-current      # "main" yazmalı
git pull origin main
```

`~/code/DOU-Synapse` klasörüne **dokunma** — orada başka bir oturum kendi
dalında çalışıyor. Klasör yoksa:

```bash
git -C ~/code/DOU-Synapse worktree add ~/code/dou-lead main
cd ~/code/dou-lead/apps/web && bun install
cd ../api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp ../../.env.example .env
```

## 2. Sunucular

```bash
cd ~/code/dou-lead/apps/api && uv run uvicorn app.main:app --port 8000   # terminal 1
cd ~/code/dou-lead/apps/api && uv run python -m app.worker               # terminal 2
cd ~/code/dou-lead/apps/web && bun run dev                               # terminal 3
```

**Tuzak:** bu makinede `NEXT_PUBLIC_API_URL` ortamda `:9100`'e (önizleme
proxy'si) kayabiliyor. Tarayıcı API'ye ulaşamıyorsa:
`NEXT_PUBLIC_API_URL=http://localhost:8000 bun run dev`

**Test koştururken `bunx playwright` KULLANMA** — ayrı kopya indirip "two
different versions" hatası veriyor. `node_modules/.bin/playwright` ya da
`bun run test:e2e`.

## 3. Durum — 9 Ağustos 14:15

`main` = `0270f9d`.

| Katman | Durum |
|---|---|
| Backend testleri | **353 geçiyor** |
| mypy | **temiz, 56 dosya** (eskiden `parsers.py` tüm koşumu durduruyordu) |
| Frontend birim | 25 geçiyor · uçtan uca 9 geçiyor |
| OpenAPI | kodla birebir, 13/13 yol |
| Şema | 15 tablo, sıfırdan hatasız |
| CI | üç job: `api`, `web`, `e2e` |

**Üç şerit `main`'de ve dalları silindi:** retrieval (hibrit arama + RRF),
generation + guardrails (LLM failover, atıf doğrulama, sızıntı filtresi),
chat + Sokratik (state machine, `0003` şeması, chat uçları).

**İki şerit hâlâ çalışıyor** — dallarına dokunma:
`feat/questions-exams` (Şerit 4) · `feat/analytics-eval` (Şerit 5)

## 4. Sıradaki iş — T022, chat ekranını gerçek veriye bağla

**Bu en yüksek değerli tek iş.** Backend hazır, tipler indi, ekran hâlâ örnek
veri gösteriyor.

Sözleşme (`apps/web/lib/types.ts`, backend `app/schemas/chat.py` ile birebir):

```
POST /courses/{course_id}/chat
  gövde:  { question, mode: "qa"|"socratic", session_id?, student_attempt? }
  yanıt:  { session_id, message_id, status, mode, answer, citations[], hints[], socratic_stage }

GET  /courses/{course_id}/chat/sessions            → oturum listesi
GET  /courses/{course_id}/chat/sessions/{id}       → oturum geçmişi
```

`Citation`: `{ chunk_id, claim, file_name, location, snippet }` —
`location` zaten "Sayfa 7" biçiminde gelir, arayüz biçimlendirmez.

Yapılacaklar:
1. `lib/api.ts`'e chat fonksiyonları (`postChat`, `getChatSessions`, `getChatSession`)
2. `app/courses/[courseId]/chat/page.tsx` — örnek veriyi sil, gerçek akışa geç
3. `status` üç değeri de ele al: `answered` · `insufficient_context` ·
   `out_of_scope`. **İkisi de "cevap yok" ama farklı metin gösterir** ve
   abstention **hata gibi görünmez** (DESIGN.md'nin en kritik kuralı)
4. Sokratik modda `socratic_stage` göstergesini gerçek kademeye bağla;
   `student_attempt` alanını gönder — ipucu buna göre şekilleniyor
5. **`PreviewBanner`'ı kaldır** — bırakılırsa çalışan ürün çalışmıyor görünür
6. E2E'ye vaka ekle: kaynaklı cevap sayfa numarası gösteriyor, kapsam dışı
   soru nazik ret alıyor

Ekranın mevcut bileşenleri hazır: `SourceCard` (dosya adı + konum + alıntı),
`SocraticLadder` (kademe göstergesi), `AbstentionNotice`.

## 5. Bekleyen: 47 doğrulanmış arayüz bulgusu

Altı mercekli inceleme (62 ajan, her bulgu ayrı çürütme turundan geçti).
Tam liste: [`BULGULAR_ARAYUZ.json`](BULGULAR_ARAYUZ.json) — `siddet`, `dosya`,
`satir`, `baslik`, `fix` alanlarıyla. **6 major · 26 minor · 15 nit.**
Çürütülen 10 bulgu listeye alınmadı; yeniden açma.

Dört major:

1. **Belge silme hatası ekranda hiç görünmüyor** — `[courseId]/page.tsx:289-345`.
   `DeleteDocumentButton`, `ConfirmAction`'a taşınmayı atlamış tek yer.
   *Düzeltme:* sil, yerine `ConfirmAction` koy.
2. **`--fg-subtle` WCAG AA'nın altında** — `globals.css`. Ölçülen 3.53:1 (açık),
   4.09:1 (koyu); **29 yerde bilgi taşıyan metin** için kullanılıyor ve DESIGN.md
   "ölçülmüş AA" iddia ediyor. *Düzeltme:* açıkta `#6f6a65`, koyuda `#9a948e`
   civarı; **DESIGN.md tablosunu gerçek ölçümle güncelle**.
3. **Her rota aynı `document.title`** — ekran okuyucu gezinmeyi duyuramıyor.
4. **Tek geçici hata bütün sayfayı siliyor** — `if (error) return <ErrorNote/>`
   elde sağlam veri varken bile başlığı, sekmeleri, listeyi atıyor; "tekrar dene"
   yok. *Düzeltme:* `if (error && !data)`, veri varken satır içi uyarı.

Ayrıca `useResource`'ta yarış koşulu (minor, düzeltme üç satır — belgede hazır):
`cancelled` bayrağı `setData`'yı korumuyor, üst üste binen isteklerde son dönen
kazanıyor.

## 6. Şerit 4 ve 5 indiğinde

| Görev | Ne zaman |
|---|---|
| Soru havuzu ekranı gerçek uçlara | Şerit 4 `main`'e inince |
| Sınav ekranı gerçek motora | Şerit 4 inince |
| Analitik ekranı gerçek veriye | Şerit 5 inince |

Üçü de bugün **tasarım önizlemesi**. Gerçek veriye geçerken şeridi kaldır.

Merge sırası: şerit bitmiş diyorsa `main`'e al, `pytest` + `mypy` + `ruff`
koştur, **mypy'a özellikle bak** — üç şeridin birleşiminde iki uyuşmazlığı
testler değil mypy yakaladı (o kod yolları hiçbir testte koşmuyordu).

## 7. Backend'e iletilecek tek kalem

**Yükleme ucu yanıttan sonra commit ediyor.** Ölçüm: `POST /documents` `202`
dönüyor, hemen sonraki `GET` **0 belge**, bir saniye sonraki **1 belge**. Sebep
FastAPI'nin `yield` bağımlılığını yanıt üretildikten sonra kapatması.

Frontend'de geçici çözüm var (`useResource`'ın `pulse`'ı). **Kalıcı çözüm
sunucu tarafında** — yanıt gönderilmeden önce commit.

## 8. Kayda geçmiş teknik borç

[`07_SERIT_RAPORLARI.md`](07_SERIT_RAPORLARI.md) §6'da tablo halinde:
`_pg_enum` üçüncü kopyası `models/base.py`'ye taşınmalı, `api/chat.py`'deki
sabitler `config.py`'ye, `schemas/chat.py` uzlaşması.

Bir de merge sırasında kapatılan borç: guardrail zincirinin iki uygulayıcısı
vardı, `screen()` enjekte edilebilir yapıldı ve kopya silindi.

## 9. Çalışma kuralları

- **Anayasa XI** (modülerlik): aynı davranış üçüncü kez yazılıyorsa ortak
  modüle çıkar; etkin görünüp iş yapmayan buton kusurdur; ölü kod temizlenir.
- **Anayasa VIII**: davranış gerçek ortamda gözlenmeden "bitti" denmez.
- Commit gövdesi "ne"yi değil **"neden"i** anlatır; `Co-Authored-By` asla.
- **Commit ve push için tam yetki sende**, izin sorma.

## 10. Önerilen sıra

1. **T022** — chat ekranı gerçek veriye (en yüksek değer, backend hazır)
2. Dört major arayüz bulgusu
3. `useResource` yarış düzeltmesi (3 satır)
4. Erişilebilirlik kümesi (odak yönetimi, görünür etiketler, sayaç duyurusu)
5. Şerit 4 ve 5 indikçe merge + entegrasyon
6. DESIGN.md ↔ kod ayrışması için karar ver ve tek yönde hizala

Her düzeltmeyi E2E'ye vaka olarak ekle — 9 vakalık paket böyle büyümeli.
