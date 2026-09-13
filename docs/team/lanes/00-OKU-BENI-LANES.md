# Şerit paketi — 13 Eylül 2026

Bu dizin, 13 Eylül'de kurulan **paralel şerit** çalışma düzeninin kayıtlı hâlidir. Her dosya bir GPT/Codex
sohbetine olduğu gibi yapıştırılan tam iş talimatıdır: ortak kurallar, o şeridin işleri, kabul komutları.

**Neden depoda:** Bu dosyalar 13 Eylül 16:09'da yalnız yerel diskte üretildi. Aynı gün 16:40'ta makine
çöktü ve tek kopya oldukları görüldü. Süreç belgeleri de kod kadar kayıp riski taşır; bu yüzden sürümleniyorlar.

| Dosya | Şerit | Dal | Dossier | Göç |
|---|---|---|---|---|
| `L1-gates.md` | Kapılar, CI, eval kablosu | `018-l1-gates` | 040–049 | — |
| `L2-product.md` | Ürün: blueprint, neden-yanlış, learning_events | `018-l2-product` | 050–059 | **0029** (eski 0027) |
| `L3-deploy.md` | Deploy, göç runner, imaj, rollback | `018-l3-deploy` | 060–069 | — |
| `L4-retrieval-ops.md` | Retrieval, kota, worker, ölçüm | `018-l4-retrieval-ops` | 070–079 | **0030** (eski 0028) |
| `L5-auth-storage.md` | Kimlik, private Storage | `018-l5-auth` | 080–089 | **0031** (eski 0029) |
| `L6-frontend-docs.md` | Frontend kararlılığı, belgeler, jüri | `018-l6-frontend-docs` | 090–099 | — |
| `L7-ux-audit.md` | UX denetimi ve küçük düzeltmeler | `018-l7-ux` | 100–109 | — |
| `_ORTAK.md` | Her şeridin başına giren ortak kurallar | — | — | — |
| `CODEX-MEVCUT-SOHBET-MESAJI.md` | Süren Codex oturumunu L4'e geçiren mesaj | — | — | — |
| `50-LIDER-GOREVLERI.md` | Lider (Murat) için hesap/anahtar/onay sırası | — | — | — |

**Göç numarası düzeltmesi (13 Eylül 16:50):** Yedek daldan kurtarılan iki tamamlanmış iş `0027` ve `0028`
numaralarını aldı. Şerit dosyalarının gövdesinde hâlâ eski numaralar yazıyor; geçerli olan yukarıdaki tablodur.
Numaraları 0030'un ötesine taşımak `ci.yml`'deki `--allow-gap` bayraklarını değiştirmeyi gerektirirdi ve orası L1'in yüzeyi.

**Entegrasyon kuralı:** Şeritler `refresh_aggregate_dossier.py` koşturmaz; toplayıcı yönetişim kaydını
birleştirmeyi yapan yazar. Şerit PR'larında "Govern reviewed AI diff" kırmızı görünebilir, bu beklenen durumdur.
