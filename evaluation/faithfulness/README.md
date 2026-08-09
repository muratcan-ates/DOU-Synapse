# T047 — human faithfulness değerlendirmesi

Bu klasör, 20-30 gerçek LLM cevabının iki insan tarafından **birbirinden bağımsız**
etiketlenip ham uyum ve Cohen's kappa ile raporlanmasını sağlar. Araçlar insan yerine
etiket vermez; yalnız örneklem/etiket bağını doğrular ve hesabı yeniden üretilebilir
hâle getirir.

## Şu anki dürüst durum

`sample_2026-08-09.json` fake provider ile çekildiği için kanıt değildir. Boş
`labels_etiketleyici_1.md` ve `labels_etiketleyici_2.md` dosyaları yalnız iş akışının
hazır olduğunu gösterir. `score_labels.py` bu örneklemi özellikle reddeder; bu
dosyalardan yanlışlıkla başarı metriği üretilemez.

## Gerçek anahtar geldiğinde

1. API'yi `LLM_FAKE_PROVIDER=false` ve gerçek Groq/Gemini anahtarıyla başlatın.
2. `pull_sample.py` ile aynı seed kullanarak 20-30 cevabı yeniden çekin.
3. İki etiketleyici ayrı Markdown dosyalarını, birbirinin kararını görmeden doldursun.
4. Etiketleme tamamen bittikten sonra aşağıdaki komutu çalıştırın:

```bash
cd apps/api
uv run python ../../evaluation/faithfulness/score_labels.py \
  --sample ../../evaluation/faithfulness/sample_<tarih>.json \
  --first ../../evaluation/faithfulness/labels_etiketleyici_1.md \
  --second ../../evaluation/faithfulness/labels_etiketleyici_2.md \
  --labeler-1 "<ad soyad>" --labeler-2 "<ad soyad>" \
  --attest-independent \
  --json-out ../../evaluation/results/faithfulness_<tarih>.json \
  --adjudication-out ../../evaluation/results/faithfulness_<tarih>_adjudication.md
```

`--attest-independent`, iki dosyanın tartışma öncesi bağımsız doldurulduğuna dair
operatör beyanıdır; aracın bunu teknik olarak gözlemlediği anlamına gelmez.

## Üretilen kanıt

- JSON sonucu örneklemin ve iki etiket dosyasının SHA-256 özetlerini taşır.
- Ham uyum ve Cohen's kappa **tartışma öncesi** etiketlerden hesaplanır.
- Uyuşmazlıklar ayrı hakem formuna çıkar; nihai karar ham uyumun üzerine yazılmaz.
- Fake provider, 20-30 dışı örneklem, `answered` olmayan/boş cevap,
  eksik/geçersiz etiket, farklı item sırası, aynı kişi veya bağımsızlık beyanı
  eksikliği fail-closed reddedilir.

T047 ancak gerçek sağlayıcı örneklemi, iki gerçek etiketleyicinin tamamlanmış
dosyaları ve üretilen sonuç artefaktları bulunduğunda `DONE` sayılabilir.
