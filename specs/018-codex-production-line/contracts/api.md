# 018 — Ürün ve gizlilik sözleşmesi

## Kod ölçütleri ve kaynaklı geri bildirim

`code_trace` ve `bug_hunt` payload'ları `rubric: [{point, weight}]` alanını taşır. Önceden onaylanmış rubriksiz kayıtlar okunabilir ve eski puanlama davranışı korunur. Yeni üretim ve taslak yazımında en az bir, boş olmayan, büyük/küçük harf ve çevre boşluğu göz önüne alınarak benzersiz ölçüt gerekir; ağırlık toplamı 100 olmalıdır. Boş veya atlanmış rubrikle yeni yazım 422 `validation_error` döner ve mevcut taslağı değiştirmez.

Rubrikli kod sorusunda model her tanımlı ölçütü tam bir kez puanlamalıdır. Eksik, tekrarlı veya bilinmeyen ölçüt sonucu kabul edilmez; toplam iki denemede doğrulanamazsa puan üretilmez. Önceki açık uçlu ve rubriksiz kod sözleşmeleri ayrı korunur. Kod yürütülmez.

`AnswerFeedbackOut.grounded_missing_criterion` isteğe bağlıdır:

```json
{
  "criterion": "Eğitmenin tanımladığı ölçüt",
  "source": {
    "chunk_id": "kaynak-kimliği",
    "file_name": "ders-notu.pdf",
    "location": "Sayfa 4",
    "snippet": "Kaynakta birebir bulunan kesit"
  }
}
```

İçerik, gerçek öğretmen ölçütüne ve açıkça puanlanan eksikliğe bağlanır; alıntı boş olamaz, en çok 320 karakterdir ve okunabilir parçada birebir bulunur. Dosya/konum modelden alınmaz. Kaydedilmiş geri bildirim tekrar açılırken güncel kaynak ve soru ölçütleri yeniden doğrulanır. Bu doğrulama kaynak ilişkisini kanıtlar; modelin pedagojik yorumunu veya anlamsal çelişkiyi bağımsız olarak kanıtlamaz. Alan MCQ `why_wrong` alanından ayrıdır; arayüz etiketi “Eksik ölçütün dayanağı”dır.

Aktif sınav yanıtında puan/çözüm/ölçüt kırılımı ve bu yeni alan açıklanmaz. Çalışma oturumunda izin verilen geri bildirim açılabilir. Tamamlanmış sınav için `/results` kullanılır; `/answers/{question_id}` çalışma geri okuma yoludur ve sınav modunda 403 döner. Başka öğrencinin oturumu ve başka ders bilgisi açılmaz.

## Sohbet silme ve geç yanıtlar

Kişinin kendi oturumunu, dersteki kendi geçmişini veya bütün kişisel geçmişini silmesi sunucu tarafında yetkilendirilir. Silme sırasında üretilmekte olan yanıt, son kayıt adımında silme sürümünü ve güncel üyelik/rolü yeniden kontrol eder. Eski konuşmayı diriltecek durum 409 `chat_history_changed` ile sonlanır; sonraki açık kullanıcı isteği yeni konuşma başlatabilir.

0024 göçündeki hesap/ders kapsamlı sürüm sayacı soru veya cevap içermez; kullanıcıyla ilişkili teknik veridir. Kişisel dışa aktarımın `not_included` alanı bu sayacı açıklar. Hesap anonimleştirme işlemi geçmiş verilerin tüm kopyalarını silmiş veya auth hesabını kapatmış sayılmaz; mevcut kapsam `docs/kvkk.md` içinde açıklanır.

Tarayıcı silme bildirimi içerik taşımaz. Aynı hesapta ilgili konuşma temizlenir; geç ve eski kimliğe ait başarı/hata yanıtları yeni ekrana uygulanmaz. Bildirimi kaçıran sekme yeniden görünür olduğunda gerçek sunucu yetkisini ve geçmişi tekrar okur. Aktif sınav kendi geçmişini silmeye engel değildir; yardım kaynaklarına erişim sınav kilidine tabidir.

## Eğitmen arayüzleri

Öğrenme çıktısı oluştururken konu seçilebilir. Soru havuzunda durum/konu sunucuya filtre olarak gönderilir; filtre değişiminde imleç sıfırlanır. Politika geçmişi salt okunur ve sayfalıdır; actor kimliğinden isim uydurulmaz. Geçici rol doğrulaması sırasında özel görünüm kapanır, aynı yetkili kullanıcının kaydedilmemiş politika taslağı yalnız bellekte korunur; kesin yetki kaybı veya hesap/ders değişimi taslağı temizler.
