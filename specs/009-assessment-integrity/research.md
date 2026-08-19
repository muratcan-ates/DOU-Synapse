# Araştırma Kararları

## R1 — Eski sorular neden `practice` backfill edilir?

Eski havuzun hangi kâğıtsız sorusunun resmî sınav için gizli üretildiği bilinmiyor.
Hepsini `assessment` yapmak öğrenci provasını boşaltır; `both` değeri ise yeniden aynı
havuz sızıntısını yaratır. Bilinmeyen, kâğıtsız veri için en dürüst varsayım
`practice`'tır. Buna karşılık herhangi bir `exam_item` tarafından referanslanan eski
soruyu practice bırakmak, mevcut resmî kâğıdı doğrudan prova havuzuna açar; onlar
migration sırasında `assessment` olur. Yayınlanmış/superseded kâğıtta approved olmayan
bir soru görülürse migration sessizce düzeltmek yerine fail-closed durur.

Bir eski soru hem `exam_items` hem de migration öncesi, kâğıtsız bir oturumun
`question_ids`/`answers` kaydı tarafından kullanılıyorsa özgün satır yine `assessment`
olur. Practice kopyası üretmek reddedildi: onaylı kopya yeni practice seçim havuzuna
girerek resmî içeriği gelecekteki öğrencilere açabilirdi. Bunun yerine
`has_own_exam_question` yalnız aynı soruyu zaten içeren kendi legacy oturumuna dar bir
devam dalı verir; oturum dizisi ve cevap referansı değişmez. Yeni practice seçimi
`purpose=practice` filtresini korur. Upgrade kanıtı hem legacy sahibin devamını hem
aynı dersteki fakat böyle bir oturumu olmayan öğrencinin reddini ölçer.

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

Migration öncesi oturumda kapanış varsa aynı formül uygulanır. Kapanış yoksa NULL'ı
korumak seçilmedi: PostgreSQL `NOT VALID` CHECK bile o tarihsel satırın daha sonraki
`finished_at` güncellemesini reddederdi. Bunun yerine migration DB saatinden bir tam
blueprint süresi sonrası yazılır. Bu, aktif oturumu bitirilebilir bırakırken deploy
anında eski çözümü açmayan sonlu ve fail-closed bir geçiştir.

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

## R7 — Resmî blueprint puanı neden `mastery`'ye yazılmaz?

Mevcut `mastery` tablosu formative practice/legacy self-servis cevaplarının EWMA
göstergesidir; hangi sınavın katkı verdiğini taşımaz. Blueprint puanını erken finish'te
yazmak öğrenci dashboard'u ve eğitmen analitiğinden sonuç yayın saatini dolanırdı.
Sonuç okumasında sonradan yazmak ise idempotent GET'i gizli, yarışabilir bir mutation'a
çevirirdi. Bu yüzden resmî/summative blueprint sonucu bu tur yalnız dondurulmuş sınav
sonuç zarfında kalır; practice ve legacy davranışı korunur. Ayrı summative gradebook,
kendi event/kimlik modeliyle sonraki bir ürün dilimidir.

## R8 — Neden `dou_app` LOGIN değil, ayrı `dou_api_runtime` kimliği?

RLS kullanıcıyı `app.current_user_id` transaction-local GUC'sinden çözer. API
işlemi için doğru olan bu mekanizma, veritabanına doğrudan bağlanabilen bir
credential'a karşı kimlik doğrulama değildir: böyle bir oturum GUC'yi başka UUID
ile yazabilir. Hassas assessment cevap/puan/sürüm yüzeyinin yalnız “GUC dolu”
olmasına güvenmesi bu yüzden yeterli değildir.

`dou_app` genel RLS izinlerini taşıyan NOLOGIN roldür. Gerçek API bağlantısı dar
özellikli `dou_api_runtime` LOGIN'idir; hassas doğrudan ACL'ler yalnız ona verilir
ve restrictive policy `session_user`ı tam adla doğrular. `current_user`, GUC veya
`SET ROLE` aynı kanıt değildir. Runtime secret yine trusted-backend yetkisidir:
ele geçirilirse kullanıcı bağlamı taklit edilebilir; bu nedenle frontend/PostgREST'e
verilmez ve backend ağı/gizli-değer kasası sınırında tutulur.

Mevcut ortam kesimi migration'dan önce rol/secret/üyeliği hazırlar ve pooler'ın
`session_user`ı koruduğunu ölçer. Trafik durduktan sonra `dou_app NOLOGIN PASSWORD
NULL` ayrı bir admin transaction'ında commit edilir; eski login'in reddi ve aktif
oturum sayısının sıfır olduğu ölçülür. Migration bu kesimi ilk kez yapmak yerine
assert eder ve özellikleri normalize eder: aynı transaction içinde NOLOGIN vermek,
preflight ile commit arasındaki yeni bağlantı yarışını açık bırakırdı. Sonradan
uygulama geri alınsa bile DSN runtime olarak kalır; carrier LOGIN açmak rollback
değil güvenlik kontrolünü kaldırmaktır.

Rol grafiği de dar tutulur: `dou_api_runtime` yalnız `dou_app`ın `INHERIT TRUE`,
`SET FALSE`, `ADMIN FALSE` üyesidir; runtime'ın üyesi yoktur ve `dou_app` başka bir
rolden yetki miras alamaz. Aksi bir parent/member kenarı hassas ACL analizini anlamsız
kılacağından migration normalleştirmek yerine preflight'ta fail-closed durur.

## R9 — Neden default ACL yalnız migration sahibinde temizlenmez?

PostgreSQL default privilege kayıtları nesne sahibine özeldir. Yalnız migration'ı
çalıştıran owner için `ALTER DEFAULT PRIVILEGES` yapmak, başka bir owner'ın daha önce
`dou_app`, `dou_worker` veya `PUBLIC` lehine bıraktığı kaydı korur; o owner'ın gelecekte
oluşturacağı tablo/fonksiyon tekrar yetki sızıntısı yaratır. Tablo grant'leri bu yüzden
unsafe `pg_default_acl` kayıtlarının owner'ı bazında kaldırılır.

Fonksiyonlarda ek bir ayrım vardır: PostgreSQL'in hard-wired PUBLIC EXECUTE
varsayılanını `IN SCHEMA app` biçimli bir REVOKE kapatmaz. `0016`, `app` schema sahibi,
mevcut `app` fonksiyon owner'ları ve current migration owner için şemasız/global
REVOKE uygular; açık schema-local grant'i de kaldırır. `acldefault` ile etkin global
varsayılanı doğrular ve migration sonrası başka owner'ın oluşturduğu probe fonksiyonun
PUBLIC'e açık olmadığını upgrade kanıtında ölçer. Operatörün ilgili owner'lar adına
default privilege değiştirme yetkisi yoksa doğru çözüm uygun admin kimliğiyle yeniden
çalıştırmaktır; kontrolü atlamak değildir.
