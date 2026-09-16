# P5 şerit kapanış kaydı — jüri demo provası (AŞILDI)

> **Bu, projenin nihai raporu DEĞİLDİR.** P5 şeridinin tek bir oturumdaki kapanış
> tutanağıdır ve aşağıdaki "KOŞULMADI" satırları **o oturumun** ortam engelini
> anlatır (`docker` binary'si yoktu), projenin durumunu değil. Hepsi sonradan
> aşıldı: demo yığını docker'sız çalışır hâle getirildi (`scripts/demo/run_api.sh`),
> gerçek Groq ile koşuldu, ekran görüntüleri yenilendi <!-- docs-check: tarihsel 16 · 2026-09-15 --> (16 görüntü, 14-15 Eylül).
>
> Projenin güncel durumu için: [`README.md`](../../README.md) "Güncel durum" tablosu ·
> ölçümler için [`docs/test-report.md`](../test-report.md) · gece koşusu için
> [`docs/team/GECE-RAPORU-14-EYLUL.md`](GECE-RAPORU-14-EYLUL.md).

## Amaç
P5 kapsamında jüri demo provası ve iki kayıtlı arayüz kusurunun kapanış raporu.

## Mimari
`app-shell.tsx` ve `course-nav.tsx` üzerinde mobil üst çubukta profil/aksiyon alanı ile materyal asistan yerleşimini dar ekranlarda çakışmayacak şekilde güncelledik.

## Hocanın maddeleri ↔ kanıt

| Madde | Ölçülen sayı | Durum |
|---|---:|---|
| Jüri senaryosu tamamlanan adım sayısı | 0 | **KOŞULMADI** (çalıştırma ortamında `docker` yok) |
| Demo senaryosu ölçüm süresi (saniye) | KOŞULMADI | Demo stack başlatılamadı |
| Kayıtlı UI kusur düzeltmesi | 2 commit | Tamamlandı |
| Önce/sonra ekran görüntüsü üretimi | 0 dosya | **KOŞULMADI** |

## “Gerçek model” bölümü
- Gerçek model koşusu: **KOŞULMADI** (anahtar yok / ortam koşusuz).

## Sınırlar
- Veri seti: canlı/demo doğrulaması yapılamadı.
- Dış servisler: bu oturumda `docker` binary'si bulunmadığı için PostgreSQL + API servisleri ayağa kaldırılamadı.
- Ekran görüntüsü: bu oturumda otomatik/manuel görüntü alınamadı.

## Ekip/İş bölümü
- Commit 1: 375px koyu profil çakışmasının mobilde kapanması (`b96bc1e`).
- Commit 2: Materyal asistan çakışmasının mobilde kapanması (`40ee2c4`).
- Commit 3: Jüri demo deneme notu ve UX/audit günlüklerinin eklenmesi (`62a5d74`).

## Not-rastgele
- Dosyalar: `docs/jury-demo.md`, `docs/ux-audit-2026-09.md`, `docs/team/P5-KAPANIS-KAYDI-14-EYLUL.md` (eski adı `docs/final-report.md`), `docs/images/jury-2026-09/`.
- Dossier aralığı: **160–169**.
