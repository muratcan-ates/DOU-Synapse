# R4 — Cevap kalitesi, guardrail sertleştirme ve açık kusurlar

> **Önce `10_OKU_ONCE_FAZ2.md`.** Bu belge yalnız senin şeridini anlatır.
> Dal: `feat/answer-quality` · Worktree: `~/code/.dou-quality` · Port: **8024**
> Migration numaran: **`0006`** (gerekirse) · Görev: kayda geçmiş açık kusurlar

```bash
cd ~/code/dou-lead && git fetch origin
git worktree add ~/code/.dou-quality -b feat/answer-quality origin/main
cd ~/code/.dou-quality/apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp ../../.env.example .env
uv run pytest -q      # 473 yeşil görmeden başlama
```

---

## Neden bu şerit

Hat çalışıyor ama üç şerit kendi raporunda **açık kusur** bıraktı ve hiçbiri
kendi sınırı içinde çözülemedi. Hepsi cevap kalitesiyle ilgili ve hepsi senin.
Bunlar "iyileştirme" değil, **kayda geçmiş kusurlar** — düzeltilmezse raporda
öyle duracaklar.

## Sahiplendiğin dosyalar

```
apps/api/app/modules/generation/**      TAMAMI senin (prompts, service, llm, fake)
apps/api/app/modules/guardrails/**      TAMAMI senin (chain, citation, leakage, sanitize)
apps/api/app/modules/retrieval/**       TAMAMI senin (dense, fts, fusion, service)
apps/api/app/modules/assessment/socratic.py   senin
apps/api/tests/test_generation.py       senin
apps/api/tests/test_guardrails.py       senin
apps/api/tests/test_retrieval.py        senin
apps/api/tests/test_socratic.py         senin
supabase/migrations/0006_*.sql          YENİ, gerekirse
specs/001-course-assistant-mvp/tasks.md yalnız kendi satırların
```

**Dokunma:** `app/api/chat.py` (lider — uç akışı), `contracts.py` (lider),
`config.py` (lider), `schemas/chat.py` (lider), `apps/web/**` (lider),
`evaluation/**` (R2).

`chat.py`'de değişiklik gerekiyorsa **yamasını raporuna yaz**, lider uygular.
Bu önemli: `chat.py` cevap hattının sırasını tutuyor ve o sıra ARCHITECTURE §5'te
sabit.

---

## Kusur 1 — `out_of_scope` etiketi HİÇ üretilmiyor (en yüksek öncelik)

Şerit 5'in bulgusu: kapsam dışı sorular da `insufficient_context` dönüyor.
Sonuç: ret F1 = 1.00 çıkarken **SC-005 = %0** çıkıyor. İkisi de doğru, farklı
şey ölçüyorlar — ama başarı ölçütlerinden biri yapısal olarak ölçülemez durumda.

Neden oluyor: `chat.py`'nin akışında kanıt eşiği **üretimden ÖNCE** çalışıyor
(doğru sıra — kanıt yoksa LLM'e gitmenin anlamı yok). Kapsam dışı bir soru
zaten kanıt bulamıyor, dolayısıyla `insufficient_context`'e düşüyor ve model
"bu kapsam dışı" deme fırsatı bulamıyor.

**Bu bir tasarım gerilimi, basit bir hata değil.** Çözerken şunları koru:
- Kanıt yokken LLM'e gidilmemeli (maliyet + uydurma riski)
- Ret metinleri **bizim sabitlerimiz** kalmalı (injection savunması)
- Fail-closed

Değerlendirebileceğin yollar (kendin karar ver, gerekçesini yaz):
- Retrieval sonucundan **ucuz ve deterministik** bir kapsam sinyali türet
  (ör. en iyi skor eşiğin çok altında + sorgu terimlerinin korpusla örtüşmemesi)
- Ayrı, çok kısa bir sınıflandırma çağrısı (maliyet: bir LLM turu — ölç)
- `out_of_scope`'u yalnız modelin döndürdüğü durumda koru ama kanıt kapısını
  iki eşiğe böl: "hiç alakasız" vs "alakalı ama zayıf"

Hangisini seçersen seç: **kararı ölçerek ver.** R2'nin gold set'inde kapsam dışı
sorular etiketli; bir yol seçip o set üzerinde doğruluk ölç, sonra yaz.
Ölçmediysen değiştirme.

`chat.py` senin değil — çözüm oraya dokunmayı gerektiriyorsa **tam yamayı**
raporuna yaz.

## Kusur 2 — kanıt eşiği holdout'ta hedefi tutmuyor

`evidence_threshold` 0.81'e kalibre edildi (lider uyguladı). Holdout'ta doğru ret
oranı **%80**, hedef **%90**. Tarama 0.820'nin 10/10 yakaladığını gösteriyor ama
oraya geçmek holdout'u ikinci bir kalibrasyon setine çevirirdi — bu yüzden
geçilmedi.

Doğru çözüm eşiği kurcalamak değil, **sinyali iyileştirmek**. Bak:
- Füzyon skoru sıralama için, eşik için değil (RRF ~0.016 çıkar) — bu yüzden
  eşik `dense_score`'a bakıyor. Daha iyi bir güven sinyali türetilebilir mi?
  (ör. en iyi ile ikinci arasındaki fark, skor dağılımının şekli, FTS örtüşmesi)
- `retrieval/fusion.py`'deki RRF `k` sabiti (60) kalibre edilmedi.
- `retrieval_top_k` (8) küçük bir korpusta korpusun dörtte birini döndürüyor.

Bir iyileştirme önerirsen **R2'nin kalibrasyon setinde** kalibre et,
**holdout'a bakmadan** dondur, sonra R2'ye "yeniden koş" diye haber ver.
Yöntemi `evaluation/calibration.md` anlatıyor — o disiplini bozma.

## Kusur 3 — Sokratik ipucu öğrencinin denemesini kullanıyor mu, gerçekten?

9 Ağustos'ta `student_attempt` uçtan üretime geçirildi (lider yaptı) ve
`prompts.build_request` onu alıyor. Ama **ipucunun gerçekten denemeye göre
şekillendiği ölçülmedi.**

Yap:
- Aynı soru + aynı kademe + **farklı denemeler** ile üretim koştur.
- İpuçlarının gerçekten farklılaştığını göster (ya da farklılaşmadığını).
- Farklılaşmıyorsa prompt'u düzelt: model denemedeki yanlış anlamayı
  görmeli ve ipucunu ona göre kurmalı.
- Bunu bir teste bağla — sahte sağlayıcıyla değil, prompt içeriğine bakan bir
  testle (denemenin prompt'a girdiği doğrulanabilir; çıktının kalitesi
  sahte sağlayıcıyla doğrulanamaz, bunu karıştırma).

## Kusur 4 — sahte sağlayıcı "cevap gibi" metin üretiyor

Şerit 4'ün bulgusu: API anahtarı yokken soru üretimi istendiğinde sahte
sağlayıcı **sohbet cevabı** üretiyor, soru değil. Fail-closed davranıyor
(uydurma soru havuza girmiyor) ama sahte sağlayıcı moda duyarlı değil.

Sahte sağlayıcı sadece bir test aracı değil — **çevrimdışı demo yedeği**
(`LLM_FAKE_PROVIDER`). Modu tanımalı: QA'da kaynaklı cevap taslağı, Sokratik'te
kademeye uygun ipucu, soru üretiminde geçerli şemada soru.

Dikkat: sahte sağlayıcı **deterministik** kalmalı (testler ona bağlı) ve
ürettiği hiçbir şey gerçek bilgi gibi sunulmamalı.

## Kusur 5 — guardrail zincirinin kendi testleri yeterli mi?

`modules/guardrails/` üç halka: citation (set-membership), leakage, sanitize.
Sıra `chain.py`'de sabit ve `screen()` tek uygulayıcı (9 Ağustos'ta kopya
silindi). Sertleştir:

- **Mutasyon düşüncesiyle bak:** her halkayı teker teker etkisizleştir ve
  hangi testin kırmızı yandığını göster. Hiçbiri yanmıyorsa o halkanın testi
  yok demektir. (Şerit 5 RLS'te bu deseni kurdu; aynısını burada kur.)
- Sızıntı filtresi: kod bloğu, tam çözüm, cevap anahtarı kalıpları — Türkçe ve
  İngilizce. Türkçe kalıplar için `socratic.py`'deki normalizasyon desenine bak
  (i/İ ve ı/I dönüşümü kayıplıdır, `lower()` yetmez).
- Sanitize: ne değiştiriyor, değiştirdiğinde atıflar hâlâ geçerli mi?

## Kusur 6 — `answer_cache` ve mod güvenliği

`question_hash` mod'u anahtara katıyor (QA cevabı Sokratik moda servis
edilirse merdiven baypas edilir) ve harf büyüklüğünü koruyor. Bunu **teste
bağla** — bugün bu davranışın regresyon koruması zayıf. Ayrıca:
bozuk önbellek satırı yok sayılıyor mu, ders bazlı izolasyon tutuyor mu.

## Lidere iletmen gerekenler

- `chat.py` için tam yamalar (dosya senin değil)
- `contracts.py`/`config.py`'de gereken alanlar
- R2'ye: hangi ölçümün yeniden koşulması gerektiği
- Eşiği değiştirdiysen: hangi sette kalibre edildi, ne zaman donduruldu

## Bitti sayılma ölçütün

- [ ] `out_of_scope` üretiliyor **ve** doğruluğu bir sette ölçüldü
- [ ] Eşik/sinyal iyileştirmesi ya yapıldı (kalibrasyon setinde, holdout'a
      bakmadan) ya da "denendi, işe yaramadı" diye ölçümle yazıldı
- [ ] Sokratik ipucunun denemeye göre şekillendiği gösterildi (ya da gösterilemedi
      ve düzeltildi)
- [ ] Sahte sağlayıcı mod duyarlı, deterministik kalıyor
- [ ] Her guardrail halkası için mutasyon kanıtı var
- [ ] `answer_cache` mod/izolasyon davranışı testli
- [ ] 473+ test yeşil, mypy temiz, ruff temiz
