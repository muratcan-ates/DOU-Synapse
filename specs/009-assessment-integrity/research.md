# Araştırma Kararları

## R1 — Eski sorular neden `practice` backfill edilir?

Eski havuzun hangi sorusunun resmî sınav için gizli üretildiği bilinmiyor. Hepsini
`assessment` yapmak öğrenci provasını boşaltır; `both` değeri ise yeniden aynı havuz
sızıntısını yaratır. Bilinmeyen veri için en dürüst varsayım `practice`'tır. Mevcut
published sürümler kimlikle çalışmaya devam eder; yalnız yeni kâğıt assessment amacı ister.

## R2 — Student `/questions` neden tamamen kapanır?

Ürün UI'ı soru havuzunu yalnız eğitmene gösteriyor. Öğrenci çalışma yüzeyi `/exams`
practice akışıdır. Toplu banka ucu öğrencinin ihtiyacı olmayan extraction yüzeyidir;
practice sorularını dahi toplu vermek tekrar kullanım değerini düşürür. RLS practice
okumasını exam oluşturma/answer için korurken router instructor-only olur.

## R3 — Sonuç neden `closes_at + duration` sonrası açılır?

`closes_at`, yeni başlangıç kapısıdır; son öğrencinin bitişi değildir. `closes_at`
anında açıklamak, bir dakika önce başlayan öğrenci sürerken cevap anahtarını açar.
Duration eklemek bütün geçerli başlangıçların sona erdiği en erken güvenli üst sınırdır.
Zaman oturuma snapshot'lanır; sonradan blueprint değişikliği geçmiş kararı oynatmaz.

Alternatifler reddedildi:

- finish anında açıklama: kohort sızıntısı;
- yalnız `closes_at`: geç başlayan öğrenci sızıntısı;
- öğretmen manuel düğmesi: iyi gelecek dilim, fakat bu tur yeni admin yaşam döngüsünü büyütür;
- istemci sayacı: güven kaynağı olamaz.

## R4 — Weighted score eşlemesi

Formül yalnız değerlendirilmiş cevaplar için:

`sum(answer_score[q] * points[q]) / sum(points[q])`

Buradaki score 0–100'dür; sonuç yine 0–100 olur. Eşleme liste sırasıyla değil
`question_id` ile yapılır. Blueprint dışı akışta `weights=None` mevcut eşit ortalamayı korur.

## R5 — Grading fail-closed koşulları

Rubrikli sorunun güvenilir sonucu için modelin döndürdüğü kriter kümesi beklenen
normalize kriter kümesiyle birebir olmalıdır: eksik/fazla/duplicate yok. Kanıt kimliği
de yalnız sağlanan source setinden gelmelidir. Bu koşullardan biri bozulursa cevap
yanlış sayılmaz; `graded=false` olur.

Dinamik prompt metinleri chat'in `escape_for_context` primitive'ini yeniden kullanır.
Student answer, reference ve source ayrı etiketlerde DATA olarak tanımlanır; system
prompt açıkça bu blokların talimat olmadığını söyler.

## R6 — Feature flag sınırı

Kill switch yeni blueprint start'ı kapatır. Submit/finish/results'u kapatmak rollback
değil veri/süre kaybıdır. Deterministik practice akışı da bu değişikliğin blast radius'una
dahil değildir.

