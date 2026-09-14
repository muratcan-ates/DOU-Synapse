# Jüri demosu

## Gösterim öncesi kontrol

- **Önce örnek profil dosyasını hazırla:** `.env` içinde `# Jüri demosu` başlıklı bölümdeki
  değerleri yalnız bu oturumda etkinleştir; kalıcı dosyayı veya varsayılanını değiştirme.
- **Bayraklar**
  - `QUESTION_AUTHORING_ENABLED=true`
  - `STUDENT_ASSESSMENT_WORKSPACE_ENABLED=true`
  - `DEV_AUTH_ENABLED=true`
  - `EMBEDDING_PROVIDER=fastembed`
  - `LLM_FAKE_PROVIDER=false`
- **Anahtar yoksa bu koşul dursa**: `LLM_FAKE_PROVIDER=false` yalnızca yerel/fake LLM kapanmasını
  istemeyecekse kullan; anahtarsız koşuda hata/ekonomik güvenlik uyarısı bekle.
- **Senaryo öncesi hız kontrolü** için `docs/demo-script.md`'deki ilgili sıralamaya geç.
- **Demo metni** kullanıcıya söylenmemeli: "model bu cevabı üretiyor" gibi ifade yerine
  `docs/demo-script.md`'deki metni takip et.

## Demo profilini uygulama

1. `.env.example`'dan ilgili satırları kopyalayıp ortam değişkeni olarak set et.
2. `docs/demo-script.md` içinde yer alan sunumun ilk 10 dakikasına geç; `source` ve
   "kaynağa dayanmayan cevap" kutusunu sadece `tamamlanamadı` senaryosunda bekle.
3. Prova esnasında birinci öncelik: `feedback-panel`'da `tamamlanamadı` için yalnız metin görünmeli.

