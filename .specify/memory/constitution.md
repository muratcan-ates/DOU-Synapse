<!--
SYNC IMPACT REPORT
==================
Version change: (initial) → 1.0.0
Bump rationale: DOU-Synapse anayasasının ilk onayı.

Added principles (I–X, tümü yeni):
  I.    Kaynak Yoksa Cevap Yok
  II.   İki Katmanlı İzolasyon
  III.  Ölçmeden İddia Etme
  IV.   Fail-Closed Varsayılanlar
  V.    Türkçe Birinci Sınıftır
  VI.   Kapsam Kapıları
  VII.  Tasarım Sistemi Disiplini
  VIII. Doğrulama Bitmeden "Bitti" Yok
  IX.   Git Disiplini
  X.    Demo Hazırlığı
-->

# DOU-Synapse Anayasası

Bu belge projenin pazarlık edilmez ilkelerini tanımlar. `spec.md`, `plan.md` ve
`tasks.md` bu ilkelerle çelişemez; çelişki bulunursa önce anayasa güncellenir
(gerekçesiyle), sonra iş yapılır.

## İlkeler

### I. Kaynak Yoksa Cevap Yok
Öğrenciye gösterilen her akademik cevap, retrieval'dan gelmiş gerçek bir chunk'a
atıfla doğrulanır. Atıf `chunk_id` set-membership kontrolünden geçer; model
retrieve edilmemiş bir kaynağa atıf yapamaz. Geçerli atıf kalmadıysa cevap
GÖSTERİLMEZ. Dosya adı ve sayfa numarası model metninden değil chunk
metadata'sından üretilir. Sokratik ipuçları da bu kurala tabidir.

### II. İki Katmanlı İzolasyon
Ders verisi hem uygulama katmanında (sunucu tarafı üyelik doğrulaması; istemciden
gelen course_id asla yetki değildir) hem PostgreSQL RLS'te izole edilir. API,
tablo sahibi olmayan ve BYPASSRLS taşımayan `dou_app` rolüyle bağlanır; testler de
aynı rolle koşar. RLS'in gerçekten tetiklendiği, politika bilerek bozularak
kanıtlanır (CI bunu her koşuda doğrular).

### III. Ölçmeden İddia Etme
Kontrast oranı, retrieval kalitesi, sızıntı oranı, gecikme: raporlanacak her sayı
ölçülür, tahmin edilmez. Eşikler kalibrasyon setiyle ayarlanır, metrikler holdout
sette raporlanır; ikisi asla karışmaz. Çalıştırılmayan deney için sonuç yazılmaz.
"Deterministik" ve "garanti" sözcükleri yalnız gerçekten deterministik mekanizmalar
için kullanılır.

### IV. Fail-Closed Varsayılanlar
Belirsizlikte sistem kapanır, açılmaz: oturum bağlamı yoksa RLS hiçbir satır
göstermez; kanıt eşiği aşılamazsa abstention döner; pedagojik filtre ihlali
regen'le çözülmezse şablon ipucuna düşülür; embedding üretilemezse belge
"completed" işaretlenmez. DEV_AUTH üretim ortamında açılamaz (config bunu reddeder).

### V. Türkçe Birinci Sınıftır
Kullanıcıya dönen her metin (hata mesajları dahil) anlaşılır Türkçedir ve backend
tek hata zarfı üretir; frontend kendi hata metnini uydurmaz. `text-transform:
uppercase` yasaktır (i/İ bozulur). UI metninde em dash kullanılmaz. Embedding ve
FTS seçimleri TR/EN karışık materyale göre yapılır ve testle sabitlenir.

### VI. Kapsam Kapıları
Dikey dilim kapısı geçilmeden üstüne özellik inşa edilmez; özellik dondurma
tarihinden sonra yalnız bayrak arkasında P1 işi ve düzeltme yapılır. Kapsam dışı
bırakılanlar (fine-tuning, GraphRAG, multi-agent, kod çalıştırma sandbox'ı,
mikroservis, K8s) gerekçesiyle PLAN.md'de listelidir; geri alınmaları anayasa
değişikliği değil plan revizyonu gerektirir ama yazılı gerekçe şarttır.

### VII. Tasarım Sistemi Disiplini
Renk, tipografi ve boşluk kararlarının tek kaynağı DESIGN.md'dir; bileşen içinde
ham hex yazılmaz, token yoksa önce DESIGN.md'ye eklenir. Kırmızı yalnız üç yerde
kullanılır (birincil eylem, aktif navigasyon, kurumsal başlık) ve asla hata rengi
değildir. Abstention hata gibi gösterilmez. Durum, renk + metin (+ikon) üçlüsüyle
işaretlenir; renk tek başına bilgi taşımaz. Koyu tema zorunludur ve marka rengi
koyu zeminde ölçülmüş açık tona geçer.

### VIII. Doğrulama Bitmeden "Bitti" Yok
Bir görev; testleri yeşil, lint temiz ve davranışı gerçek ortamda (tarayıcı veya
API çağrısı) gözlenmiş olmadan tamamlanmış sayılmaz. UI değişikliği tarayıcıda
görülmeden, API değişikliği gerçek istekle sınanmadan commit mesajına "works"
yazılamaz. Test edilemeyen iş, görev tanımına geri döner.

### IX. Git Disiplini
Her görev kendi conventional commit'iyle biter (Done = committed). Commit gövdesi
"ne"yi değil "neden"i anlatır. Co-Authored-By / "Generated with" izleri ASLA
eklenmez; contributors listesinde yalnız takım üyeleri görünür. Repo `~/code`
altında yaşar (iCloud senkron dizinlerinde asla). `.env` ve gerçek anahtarlar
repoya girmez; commit öncesi sızıntı taraması yapılır. `main` korunur; iş
branch + PR + en az bir insan incelemesiyle girer (takım çalışmaya başladığında).

### X. Demo Hazırlığı
Sistem her akşam gösterilebilir durumda bırakılır. Seed verisi ve demo senaryosu
repoda yaşar; demo günü planı (A: canlı bulut, B: hotspot, C: çevrimdışı
cache'li Compose) prova edilmiş olmalıdır. Kullanıcıya asla ham stack trace
gösterilmez.

## Teknoloji Kilidi

Sürümler kök `README.md` ve `apps/*/package.json` / `pyproject.toml`'da sabittir.
Çekirdek: Next.js (App Router) + Tailwind v4 · FastAPI + Python 3.12 (pin:
onnxruntime uyumu) · PostgreSQL 16 + pgvector · fastembed/multilingual-e5-large
(1024) · LiteLLM (Groq→Gemini failover). Yeni çatı/kütüphane eklemek plan
revizyonu ve yazılı gerekçe ister; LangChain/LlamaIndex/LangGraph bilinçli
olarak dışarıdadır.

## Geliştirme İş Akışı

specs/001-course-assistant-mvp/tasks.md tek iş listesi kaynağıdır. Görevler tam
dosya yoluyla yazılır, [P] işareti paralelleştirilebilirliği gösterir, her görev
kendi commit'iyle kapanır ve tamamlanınca tarihli DONE notu düşülür.

## Yönetişim

Anayasa değişikliği: SemVer (MAJOR ilke kaldırma/anlam değişimi, MINOR yeni ilke,
PATCH metin düzeltmesi) + SYNC IMPACT RAPORU + takım onayı. Bu belge, çelişen tüm
alışkanlıklardan üstündür.

**Version**: 1.0.0 | **Ratified**: 2026-08-05 | **Last Amended**: 2026-08-05
