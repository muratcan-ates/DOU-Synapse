# Modülerizasyon v2 — denetim raporu (ölçüm: 16 Ağustos 2026)

Bu rapor `refactor/modularization-v2` dalının başlangıç envanteridir: 5 paralel okuyucu
(backend sınırlar, backend boyut, frontend, sözleşmeler, test kapsamı) + sentez turuyla,
main `dbb8988a` üzerinde ölçüldü. Sayılar o günün ölçümüdür (tarihsel); canlı sayaç değildir.
Plan davranış koruyucudur: her adım mevcut testlerle doğrulanır, main'e doğrudan yazılmaz.

## 1. Mevcut modül haritası (ölçülen)

MONOREPO: apps/api (FastAPI, 38.953 satır Py; app/ 17.717) + apps/web (Next 16.3.0 + Bun, 15.256 satır TS/TSX) + supabase (migrasyonlar + 5 RLS mutasyon betiği) + evaluation + scripts. BACKEND (apps/api/app, 60 dosya, AST ile ölçüldü): main.py (16 router kaydı) / worker.py (ingestion job consumer) / contracts.py (paylaşılan enum+protokoller) — core/ 11 altyapı dosyası (config, db+RLS oturumu, errors, llm_json, logging, pagination imleç codec'i, rate_limit, security/JWT, text_tr, vector_space, warmup) — models/ 5 SQLAlchemy dosyası (temiz alt katman: yalnız base+contracts import eder) — schemas/ 14 Pydantic sözleşme dosyası — api/ 17 router — modules/ 8 alan paketi (ingestion, retrieval, generation, guardrails, assessment, mastery, policy, agent). Ölçülen katmanlama: modules HİÇBİR yerde api'yi import etmiyor (temiz yön); ama api katmanı 'fat router' — 11/14 router modules servislerini çağırırken 29 kenarla doğrudan models+core.db'ye de iniyor, ayrı repository katmanı yok (ARCHITECTURE.md bunu yasaklamıyor). Katman lekesi 4 noktada: core→modules (vector_space:48, warmup:43), schemas→modules (source.py:9), generation↔guardrails, generation.fake↔llm (aşağıda). FRONTEND (apps/web): app/ 20 rota dizini, SIFIR route group; her page.tsx "use client", segment başına ince server layout.tsx yalnız metadata için (şablon lib/metadata.ts'te). lib/ 26 modül / 4.896 satır, ~1:1 co-located test (30 dosya, 352 vaka); components/ 13 dosya / 2.149 satır, render testi yok. Sınır yönü temiz: components/lib app'ten hiçbir şey import etmiyor; tek tersinme type-only (lib/source.ts:11 + lib/questions.ts:17 → components/source-card SourceInfo). fetch+hata zarfı+retry TAM merkezi (lib/api.ts tek fetch çağrı yeri, lib/errors.ts tek mesaj kaynağı); sayfalama use-paged-resource'ta merkezi (bir bağımsız ters-sayfalama kopyası chat sayfasında). TEST AĞI: API 904 pytest (43 dosya, gerçek Postgres+RLS'e entegrasyon seviyesi, çoğu HTTP üzerinden → iç taşımalara dayanıklı), web 352 bun-test (lib), 36 e2e (flows 21 + portal 12 + role-aware-agent 3), 5 RLS SQL mutasyon suiti (Python'dan bağımsız) + 12 mutasyonluk uygulama-katmanı koşucusu. KISIT: AGENTS.md Next 16.3.0 için 'bildiğin Next değil' uyarısı — rota/layout/metadata'ya dokunan her refactor öncesi node_modules/next/dist/docs okunmalı. AI-SDLC policy (.ai/policy.json) sensitive_paths listesi doğrulandı: api/chat.py, api/exams.py, api/blueprints.py, api/policy.py, api/privacy.py, contracts.py, main.py, worker.py, tüm modules/** (retrieval/generation R2, kalanı R3), schemas/{chat,assessment,blueprint,policy}, core/{db,vector_space,text_tr} R3 + {config,llm_json,rate_limit,warmup} R2, api/questions.py R2, migrasyonlar R3, web'de courses/**/chat/**, components/course-assistant/**, lib/course-assistant.ts, lib/chat-availability.ts R3. Testler, api/{courses,documents,sources,deps}.py, core/pagination.py, schemas/source.py, ci.yml ve web'in diğer sayfaları/bileşenleri listede DEĞİL.

## 2. Döngüsel bağımlılıklar

- DOSYA DÜZEYİ (tek statik döngü): app.modules.generation.fake <-> app.modules.generation.llm — fake.py:61 üst-düzey import, llm.py:368 kenarı build_llm_client İÇİNDE function-local; import-zamanı güvenli, kasıtlı ertelenmiş (anahtar yokken fake'e düşme dayanıklılığı). Kırmak zorunlu değil; LlmCompletion/LlmRequest/LlmTask tiplerinin ayrı bir types modülüne alınması yeterli olur.
- PAKET DÜZEYİ: core <-> modules — core/vector_space.py:48 ve core/warmup.py:43 üst-düzeyde app.modules.ingestion.embedding'i import ediyor (FastEmbedProvider, get_embedding_provider); modules/* yaygın biçimde core'u import ediyor. Dosya düzeyinde kapanmıyor ama core saf alt katman değil (katman tersinmesi bu iki dosyada).
- PAKET DÜZEYİ: modules.generation <-> modules.guardrails — guardrails/chain.py:42 'from app.modules.generation.service import USER_TEXT' <-> generation/service.py:43 'from app.modules.guardrails.citation import build_citations'; her iki kenar üst-düzey. USER_TEXT'in contracts.py'ye taşınması paket döngüsünü kırar (okuyucu önerisi).
- PAKET DÜZEYİ: schemas <-> modules — schemas/source.py:9 'from app.modules.retrieval.scope import EvidenceLevel' (schemas içindeki TEK modules importu); ters yönde 7 modules dosyası schemas'ı import ediyor (generation.prompts:33, generation.service:44, guardrails.citation:31, guardrails.leakage:40, assessment.grading:54, assessment.question_gen:60, assessment.blueprint:34).
- FRONTEND (type-only, çalışma zamanı döngüsü YOK): lib/source.ts:11 ve lib/questions.ts:17 → 'import type { SourceInfo } from "@/components/source-card"' — tip lib/types.ts'e ait, ucuz düzeltme.

## 3. Aşırı büyük dosyalar

| Dosya | Satır | Değerlendirme |
|---|---|---|
| `apps/api/app/api/chat.py` | 1622 | Deponun tek gerçek backend god-file'ı; en az 5 katman tek dosyada: DI kaydı set_pipeline/get_* (168-244), önbellek anahtarı+policy/corpus revizyon hash'leri (327-494, 1435-1522), 24 gömülü prompt-SHA256 ile kota ön-şarj matematiği (357-425), DB'siz produce_answer hattı (680-863), ~295 satırlık post_chat + nonlocal closure (871-1343), kalıcılaştırma yardımcıları (1346-1609). AI-SDLC R3 sensitive; test_chat_api set_pipeline/question_hash'i doğrudan import ediyor ve mutasyon koşucusu TAM kaynak baytlarını çiviliyor — bölme en sona. |
| `apps/web/app/courses/[courseId]/chat/page.tsx` | 721 | Web'in tek net god-component'i: ChatScreen 144→EOF tek bileşende 578 satır, 11 useState, 20 hook çağrısı (mod politikası reset'leri, oturum aç/geri yükle+localStorage, elle ters-sayfalama, optimistic pending, gönderim akışı, tüm transcript/composer JSX). Saf karar mantığı zaten lib/chat.ts'te (456 satır, testli). AI-SDLC R3 (courses/**/chat/**). |
| `apps/web/app/courses/[courseId]/questions/page.tsx` | 1030 | En büyük web dosyası ama içten ayrıştırılmış (14 üst-düzey fonksiyon; en büyüğü QuestionPool ~234 satır) — god-component değil, yerel bileşenleri dosya dışına taşıyarak temiz bölünür. |
| `apps/web/app/courses/[courseId]/blueprints/page.tsx` | 964 | 8 bileşen, her biri <=150 satır, 9 resource-hook çağrısı — büyük dosya, ayrıştırılmış; bölme mekanik. (Backend karşılığı api/blueprints.py R3 sensitive ama bu web sayfası policy listesinde değil.) |
| `apps/web/app/courses/[courseId]/exam/page.tsx` | 879 | RunningExam 254-558 (~304 satır) sınırda god-component (sınav cevaplama durum makinesi); dosyanın kalanı ayrışık. |
| `apps/web/app/admin/page.tsx` | 786 | 18 fonksiyon, generic AdminListFrame<T> yeniden kullanılıyor — büyük ama düzenli; düşük öncelik. |
| `apps/api/tests/test_assessment.py` | 1132 | Hem test dosyası hem fiili fixture kütüphanesi: DEADLOCK_TEXTS/FakeCompletion/retrieved/_mcq_response 4 başka test dosyasına export ediliyor; kapsamı da geniş (CRUD+üretim+puanlama+mastery). Bölünmeye en yakın test dosyası. |
| `apps/api/tests/test_exams.py` | 864 | ExamFixture/build_course/start/rewind 4 başka test dosyasının import ettiği fiili fixture hub'ı — bu ortak kurulum factories.py'ye ait; yeniden adlandırma/bölme zinciri kırar. |
| `apps/api/scripts/role_agent_multiworker_load.py` | 1289 | Çok fazlı ama tek amaçlı T408 kanıt betiği; app'ten import edilmiyor — aksiyon GEREKMEZ (kayıt için listede). |

## 4. Tekrar eden mantık

- BACKEND — keyset sayfalama dansı 5 uçta elle kopya (cursor decode → tuple_ WHERE → limit+1 → dilimle → next_cursor encode): courses.py:48-64, documents.py:144-160, questions.py:207-238, chat.py:1258-1272 (oturum listesi), chat.py:1288-1308 (3 parçalı mesaj imleci varyantı); core/pagination.py yalnız imleç codec'ini merkezileştiriyor. En somut çıkarılabilir tekrar.
- BACKEND — 'X is None or X.course_id != context.course_id → NotFoundError' sahiplik-404 kalıbı 15 kez / 7 router: chat.py:1285,1394; exams.py:122,323,402; blueprints.py:89,243; documents.py:102,171,185,213,252; sources.py:87,91; questions.py:294. Tek generic load_owned(session, Model, id, context) yardımcısı hepsini kapatır.
- BACKEND — flush + IntegrityError→409 çevirisi 12 kez (blueprints.py×6, exams.py×2, questions.py×2, documents.py:259, courses.py:81); mesajlar kısıta özgü, tam merkezileştirilemez — blueprints.py:302 ve 368'deki birebir aynı mesaj hariç düşük öncelik.
- BACKEND — modül-global sağlayıcı-kancası deseni 3 bağımsız kopya (chat.set_pipeline:168-244, question_gen.set_providers:119-163, storage.set_storage:168-197) ve None semantiği ayrışık (set_pipeline None'ı yazar/temizler, set_providers atlar) — ortaklaştırılmasa bile semantik hizalanmalı.
- BACKEND dosya-içi küçükler: chat.py'de question_hash çağrı bloğu ×2 (1450-1458, 1498-1505) ve ChatAvailabilityOut aynı 4 kuyruk parametresiyle ×5 (1196-1248); exams.py'de GradingOutcome comprehension ×2 (258-264, 683-689) + 'tamamlanamadi' sihirli dizesi ×3.
- BACKEND — BİLİNÇLİ, DOKUNMA: sınav kilidi kontrolü 3 katman (deps.py:213-221, chat.py:1091-1102 TOCTOU, chat.py:1214-1222) belgeli savunma; kaldırılmamalı.
- API TESTLERİ — fixture-hub bağımlılığı: 8 test dosyası ortak kurulumu factories.py yerine kardeş TEST modüllerinden import ediyor (test_assessment ve test_exams fiili hub); ScriptedLlm ×2 (test_guardrails:464-483, test_generation:330-341), BlockingGenerator ×2 (test_exam_lock:196-210, test_role_aware_agent_application_guards:287-305); ekibin kendi 'üç kullanımda fabrikaya' eşiği (test_chat_api.py:56-57) çoktan aşılmış.
- FRONTEND — EN BÜYÜK tekrar: submit-scaffold (setBusy(true); setError(null); try/catch errorMessage / finally setBusy(false)) ~23 bağımsız kopya / 17 dosya; ortak useSubmit yok; double-submit guard'ı kimi kopyada var (members:223) kimi kopyada yok — sessiz ayrışma riski.
- FRONTEND — eğitmen render-gate JSX'i ×7 (settings:33, quality:22, sources:39, members:69, analytics:67, questions:120, blueprints:81 varyantı); mantık useSession'da merkezi, JSX kopya — tek <InstructorGate> kapatır.
- FRONTEND — ters-sayfalama kopyası: chat/page.tsx historyCursor/olderLoading/historyError üçlüsü (:164-170, :257, :287-301) use-paged-resource'un ikinci kopyası (prepend desteği gerekçesi kısmi haklı); 'ilk 100'ü çek, cursor'ı at' unwrap ×2 (chat:186-192, settings:59-61); hasMore={x.nextCursor !== null} prop ×5.
- FRONTEND — MERKEZİ, TEKRAR DEĞİL (ölçüldü): fetch tek çağrı yeri (api.ts:407), hata zarfı tek unwrap (api.ts:492-510), errorMessage 16 dosyada tek kaynak; QuestionBody ad çakışması (exam:558 vs questions:592) — yalnız ~8 satır ortak, mantık tekrarı değil.
- SÖZLEŞME ÇİFT-TANIMI: 65 frontend arayüzü + ~17 enum backend pydantic şemalarının elle kopyası (codegen yok); üç kez yaşayanlar: QuestionOut=types.Question+blueprint.PoolQuestion (bilinçli, yorumda gerekçeli), AnswerStatus=types.AnswerStatus+admin.RequestStatus (aynı 4 değer iki ad). Backend enum'ları contracts.py'de tek-kaynaklı; frontend eşdeğeri yok.

## 5. API–frontend sözleşmeleri

Sözleşme okuyucusunun ölçümleri: (1) openapi.json GERÇEK ve GÜNCEL — venv ile yeniden export edildi, commit'li dosyayla bayt-bayt özdeş (50 yol / 66 işlem, 240175 bayt). Kod→spec zinciri sağlam; spec→frontend zinciri TAMAMEN elle: codegen aracı yok, 65 arayüz + ~17 string-union enum spec'i elle aynalıyor, frontend spec'in ~%90'ını tüketiyor — drift riski tüm tüketilen yüzey. (2) ÖLÇÜLEN drift: API'de olup frontend tipinde olmayan 8 alan — Question.difficulty/learning_outcome_id/source_stale (types.ts:224), ExamSession.attempt_no/exam_blueprint_id/exam_version_id, AnswerFeedback.rubric_breakdown, UserDataExport.not_included; istek yönünde ExamStartRequest.blueprint_id eksik → blueprint'e bağlı sınav UI'dan HİÇ başlatılamıyor (kapsama boşluğu). Hiç tüketilmeyen uçlar: ai-policy/history, tek-blueprint GET/POST/DELETE, question DELETE. (3) BLOCKER — hata zarfı: çalışma zamanında tutarlı ({error:{code,message,request_id}}, 3 handler main.py:140-144'te 422 dahil kayıtlı; frontend api.ts::errorEnvelope tek noktadan çözüyor) AMA üretilen spec zarfı HİÇ içermiyor; 58 işlem yalnız sunucunun asla döndürmediği HTTPValidationError'ı belgeliyor — spec'ten istemci üreten herkes yanlış hata tipi alır. Router'lara responses={4xx: ErrorEnvelope} (veya openapi post-processing) gerekli. (4) BLOCKER — specs/001-course-assistant-mvp/contracts/README.md iki sürüm geride: '9 yol/13 işlem' diyor, mevcut uçları 'henüz yok' sayıyor, zarfı request_id'siz gösteriyor, çözülmüş 422 sorusunu açık NEEDS CLARIFICATION taşıyor — sözleşme denetçisini aktif yanıltır. (5) Sayfalama üç biçim: PageOut {items,next_cursor} 5 yolda (frontend Page<T> birebir); /admin {items,total,limit,offset} istisnası schemas/admin.py docstring'inde belgeli ve SINIR TUTUYOR (doğrulandı, admin dışına sızmamış, frontend AdminList<T> ile ayrık); belgelenmemiş üçüncü biçim: 9 işlem çıplak dizi dönüyor — büyüyünce PageOut'a geçiş kırıcı olur. (6) Codegen'e giden yolun ölçülmüş engeli: Field(default_factory=list) ~20 alanı spec'te 'optional, defaultsuz' gösteriyor (ChatResponse.citations/hints, ChatMessage.status/feedback, CourseAiPolicyOut'un 8 alanı, Blueprint.published_version_no...) — bugün zararsız, ama openapi-typescript bunları `| undefined` tipler; önce backend'de açık default'a çevrilmeli (schemas/chat.py R3 sensitive → dossier). Önerilen sıra: CI'da export-diff kapısı + TS-tip↔şema alan-diff sözleşme testi (kısa vade), sonra openapi-typescript ile lib/api-types.gen.ts + types.ts re-export (orta vade).

## 6. Test kapsamı boşlukları

- API — doğrudan test dosyası OLMAYAN, yalnız HTTP/dolaylı kapsamlı modüller: modules/policy/service.py, modules/assessment/blueprint.py, modules/assessment/exam_paper.py, core/pagination.py (yalnız limit=101/bozuk-cursor senaryoları), core/warmup.py (yalnız /health/ready monkeypatch'leri), core/db.py (16 dosya import eder, kendi dosyası yok), core/vector_space.py, api/deps.py, api/dashboard.py, api/profile.py (ikisi test_portal içinde), models/base.py, models/policy.py, worker.py (conftest+2 dosya kullanır, kendi dosyası yok), 15 şema dosyasının 13'ü (yalnız schemas/assessment ve schemas/chat doğrudan import ediliyor).
- WEB — components/ için React render/bileşen testi SIFIR (testing-library yok): app-shell, chat-feedback, course-nav, field, page-state, socratic-ladder, source-card, portal/* birim seviyesinde tamamen ağsız, tek güvence 36 e2e; 20 page.tsx'in birim testi yok; lib içinde testsiz: metadata.ts, supabase.ts, types.ts.
- CI'A BAĞLI OLMAYAN mutasyon kanıtları (elle koşulmazsa sessizce çürür): rls_isolation_mutation_check.sh 57'lik tam sürüm (CI tek-mutasyon dumanında), rls_blueprint_mutation_check.sh (23), rls_portal_admin_mutation_check.sh (3), scripts/role_agent_application_mutation_check.py (12) — hiçbir workflow'da geçmiyor (grep ile doğrulandı).
- E2E — screenshots.spec'in 7 testi @ekran arkasında grepInvert'li, gerçek COME 331 dersine bağımlı, yalnız EKRAN=1 ile koşuyor; varsayılan ağın parçası değil.
- TAŞIMADA KIRILACAK sabit-metin bağları (davranış ağı DEĞİL, değişiklik dedektörü — modül taşımalarında güncellenmek zorunda): web'de readFileSync ile kaynak-metin çivileyen testler (lib/members.test.ts→members/page.tsx, lib/question-page-contracts.test.ts→blueprints+questions page, lib/course-assistant*.test.ts→course-assistant.tsx), API'de doğrudan-import testleri (test_chat_api→app.api.chat.set_pipeline/question_hash, test_exam_lock→exam_state), scripts/role_agent_application_mutation_check.py'nin apps/api/app/api/chat.py içindeki TAM KAYNAK BAYT dizileri.
- SÖZLEŞME — frontend'in hiç tüketmediği uçlar (drift'te en önce çürüyecekler): GET /courses/{id}/ai-policy/history, tek-blueprint GET/POST/DELETE, DELETE /courses/{id}/questions/{id}; ExamStartRequest.blueprint_id UI'dan hiç kullanılmıyor.
- Frontend elle tip bakımının ölçülmüş kaçağı: 8 alan (Question×3, ExamSession×3, AnswerFeedback.rubric_breakdown, UserDataExport.not_included) — sözleşme testi/codegen olmadan büyümeye devam eder.

## 7. Önerilen PR sırası (küçük, davranış koruyucu, her adım test edilebilir)

### PR 1: Test fixture konsolidasyonu: kardeş-test importlarını factories.py'ye taşı

- **Kapsam:** Yalnız apps/api/tests/: DEADLOCK_TEXTS, FakeCompletion, retrieved, _mcq_response (test_assessment'ten), ExamFixture/build_course/start/rewind (test_exams'ten), ScriptedLlm (×2 kopya) ve BlockingGenerator (×2 kopya) factories.py'ye; 8 tüketici dosyada (test_exam_lock, test_rate_limit, test_blueprint, test_exams, test_health, test_role_aware_agent_application_guards, test_sources_api, test_user_rights) importlar güncellenir. Ekibin kendi 'üç kullanımda fabrikaya' kuralının uygulanması. Sensitive path YOK (testler policy'de değil) — dossier gerekmez.
- **Risk:** Düşük — üretim kodu değişmiyor; risk yalnız import kırılması, pytest hemen yakalar. Bu PR sonraki tüm backend PR'larının önkoşulu: test dosyaları artık serbestçe bölünebilir/taşınabilir.
- **Doğrulama:** cd apps/api && .venv/bin/python -m pytest --collect-only -q → 904 test toplanmaya devam etmeli; ardından tam pytest yeşil.

### PR 2: CI dışı mutasyon kanıtlarını CI'a bağla

- **Kapsam:** .github/workflows/ci.yml'e (sensitive listede DEĞİL; ai-quality.yml'e dokunulmaz) 4 orphan kapı eklenir: rls_isolation_mutation_check.sh tam 57'lik sürüm (mevcut tek-mutasyon dumanının yerine/yanına), rls_blueprint_mutation_check.sh, rls_portal_admin_mutation_check.sh, scripts/role_agent_application_mutation_check.py. Süre sorun olursa nightly job'a ayrılabilir.
- **Risk:** Düşük-orta — üretim kodu sıfır değişiklik; risk CI süresi ve betiklerin CI ortamında flake'i. Modülerizasyon boyunca ağın çürümesini önlediği için 3+ nolu PR'lardan ÖNCE gelmeli.
- **Doğrulama:** PR dalında CI koşusu yeşil; yerelde: bash supabase/tests/rls_blueprint_mutation_check.sh && bash supabase/tests/rls_portal_admin_mutation_check.sh && python scripts/role_agent_application_mutation_check.py.

### PR 3: Sözleşme hijyeni: contracts/README.md güncelle + CI'da openapi export-diff kapısı

- **Kapsam:** specs/001-course-assistant-mvp/contracts/README.md gerçek duruma çekilir (50 yol/66 işlem, request_id'li zarf, çözülmüş 422 kararı); ci.yml'e 'openapi.json'u yeniden export et, diff boşsa geç' adımı (komut çalışıyor, okuyucu doğruladı). İsteğe bağlı: TS-tip↔şema alan-diff'ini contract testi olarak ekle. Sensitive path yok.
- **Risk:** Düşük — doküman + CI; davranış değişikliği sıfır. İki blocker'dan birini (bayat README) kapatır, diğeri (hata zarfı spec'te yok) PR 10'da.
- **Doğrulama:** cd apps/api && (README'deki export komutu) && git diff --exit-code openapi.json; docs_check.mjs yeşil.

### PR 4: Web: SourceInfo tipini lib/types.ts'e taşı + InstructorGate bileşeni

- **Kapsam:** Type-only tersinme kapanır (lib/source.ts:11, lib/questions.ts:17 → components/source-card yerine lib/types.ts; source-card re-export edebilir). Yeni <InstructorGate> bileşeni 7 kopyayı kapatır: settings, quality, sources, members, analytics, questions sayfaları + blueprints erken-dönüş varyantı. Bu web yolları sensitive listede DEĞİL. DİKKAT: members/page.tsx ve questions/blueprints page'leri readFileSync ile çivileyen kaynak-metin testleri (lib/members.test.ts, lib/question-page-contracts.test.ts) kasıtlı kırılır — güncellenir.
- **Risk:** Orta-düşük — bileşenlerin render testi yok; ağ = lib testleri + e2e rol-ayrımı testleri (flows.spec 'öğrenci eğitmen kontrolü görmez'). AGENTS.md gereği Next 16.3.0 docs (node_modules/next/dist/docs) layout/metadata'ya dokunulmadığı teyit edilerek okunur.
- **Doğrulama:** cd apps/web && bun test lib/ (352 vaka) + üretim derlemesi + Playwright e2e 36 test (özellikle flows rol-ayrımı ve portal blueprint-yetki testleri).

### PR 5: Web: ortak useSubmit hook'u — sensitive olmayan sayfalara uygula

- **Kapsam:** setBusy/setError/try-catch-finally scaffold'unun ~23 kopyasından sensitive OLMAYANLAR ortak hook'a çekilir (blueprints×5, questions×2+varyant, exam×2, members, sources, settings, profile, reset/forgot-password, app/page, courses, [courseId]/page, chat-feedback.tsx, ui.tsx). HARİÇ (R3, sonraki dossier'lı PR'a): chat/page.tsx:314 ve course-assistant.tsx:331. Hook double-submit guard'ını standartlaştırır (bugün members'ta var, diğerlerinde yok — davranışı 'guard'lı' olarak eşitlemek KÜÇÜK davranış değişikliğidir, PR açıklamasında beyan edilir).
- **Risk:** Orta — 17 dosyada dokunuş, bileşen render testi yok; ağ = 352 lib testi + 36 e2e (form akışlarının çoğu e2e'de: giriş, materyal, soru onayı, sınav). Double-submit eşitlemesi tek bilinçli sapma.
- **Doğrulama:** bun test lib/ + tam e2e 36; elle: bir formda çift tıklamanın tek istek ürettiği read_network ile doğrulanır.

### PR 6: Backend: keyset sayfalama + load_owned yardımcıları, sensitive OLMAYAN router'lara

- **Kapsam:** core/pagination.py'ye (sensitive listede DEĞİL) 'limit+1/dilimle/encode' dansını kapsayan paginate() yardımcısı; api/deps.py'ye (listede değil) generic load_owned(session, Model, id, context)→404. Uygulama yalnız courses.py, documents.py, sources.py (üçü de listede değil). questions/blueprints/exams/chat'e DOKUNULMAZ (PR 8).
- **Risk:** Orta-düşük — davranış birebir korunmalı (limit sınırı, bozuk cursor 400'ü, 404 mesajları); ağ = test_courses, test_documents_api, test_sources_api HTTP seviyesinde. core/pagination'ın kendi birim testi yok (kapsama boşluğu) — bu PR'da yardımcıya doğrudan birim testi EKLENİR.
- **Doğrulama:** cd apps/api && .venv/bin/python -m pytest tests/test_courses.py tests/test_documents_api.py tests/test_sources_api.py -q, sonra tam 904'lük suite.

### PR 7: Backend: generation↔guardrails ve schemas↔modules paket döngülerini kır [DOSSIER]

- **Kapsam:** USER_TEXT sabiti generation/service.py:43'ten contracts.py'ye (guardrails/chain.py:42 importu güncellenir); EvidenceLevel retrieval/scope'tan contracts.py'ye (schemas/source.py:9 güncellenir, scope.py geriye-uyum için re-export eder). SENSITIVE: contracts.py R3, guardrails/** R3, generation/** R2, retrieval/** R2 → AI-SDLC dossier gerekir.
- **Risk:** Orta-düşük mekanik risk, ama R3 yüzey — davranış sıfır değişmeli; EvidenceLevel taşıması openapi şema adını DEĞİŞTİRMEMELİ (bayt-özdeş spec, bunun kanıtı).
- **Doğrulama:** pytest tests/test_generation.py tests/test_guardrails.py tests/test_retrieval.py tests/test_sources_api.py + tam suite; openapi yeniden export → git diff --exit-code openapi.json (bayt-özdeş kalmalı).

### PR 8: Backend: sayfalama+load_owned'ı sensitive router'lara uygula [DOSSIER]

- **Kapsam:** PR 6'daki yardımcılar questions.py (R2), blueprints.py (R3), exams.py (R3) ve chat.py'nin iki liste ucuna (R3; 3-parçalı mesaj imleci varyantı yardımcıya parametrik eklenir) uygulanır. exams.py'de _outcomes_of(answers) yardımcısı 3 kopyayı toplar. Dossier gerekir.
- **Risk:** Orta — R3 yüzeyde mekanik değişiklik; chat.py'ye dokunulduğu için mutasyon koşucusunun bayt-çivileri kayabilir — koşucu bu PR'da koşulup gerekiyorsa çiviler güncellenir.
- **Doğrulama:** Tam pytest 904 + python scripts/role_agent_application_mutation_check.py yeşil + rls suit'leri (CI, PR 2 sayesinde otomatik).

### PR 9: Backend: core→modules katman tersinmesini düzelt (vector_space, warmup) [DOSSIER]

- **Kapsam:** core/vector_space.py:48 ve core/warmup.py:43'ün üst-düzey app.modules.ingestion.embedding importları kaldırılır: ya function-local'e ertelenir (minimum değişiklik) ya da contracts.py'deki protokol üzerinden sağlayıcı enjeksiyonu. SENSITIVE: vector_space R3, warmup R2, ingestion/** R3, contracts R3 → dossier.
- **Risk:** Orta — warmup startup davranışı (FR-221) ve embedding uzay kimliği birebir korunmalı; import zamanlaması değişirse soğuk-başlangıç farkı doğabilir.
- **Doğrulama:** pytest tests/test_embedding.py tests/test_embedding_prefix.py tests/test_health.py tests/test_retrieval.py + tam suite; /health/ready akışı e2e'siz smoke ile.

### PR 10: Sözleşme: hata zarfını openapi'ye ekle + default_factory düzeltmeleri [DOSSIER]

- **Kapsam:** ErrorEnvelope/ErrorDetail components'a girer; router'lara ortak responses={4xx: ErrorEnvelope} (veya main.py'de openapi post-processing — main.py R3). ~20 Field(default_factory=list) alanı açık default'a çevrilir (schemas/chat.py R3, policy/blueprint şemaları R3 → dossier). openapi.json BİLEREK değişir ve yeniden commit edilir; PR 3'teki export-diff kapısı bu yeni spec'e göre yeşil kalır. Bu, orta vadeli openapi-typescript codegen'inin önkoşulu.
- **Risk:** Orta — çalışma zamanı davranışı değişmemeli (response_model serileştirmesi aynı); risk spec'in istemcilerce yanlış yorumu, ama bugün spec'ten üretilen istemci yok (frontend elle). İkinci blocker'ı kapatır.
- **Doğrulama:** pytest tests/test_error_envelope.py + tam suite; openapi export → diff yalnız beklenen eklemeler; cd apps/web && bun test lib/api.test.ts (zarf çözümü değişmedi).

### PR 11: Backend: chat.py'yi böl (kota, önbellek, produce_answer, kalıcılaştırma) [DOSSIER, EN RİSKLİ]

- **Kapsam:** 1622 satırlık app/api/chat.py katmanlarına ayrılır: (a) kota ön-şarj matematiği + 24 prompt-hash (357-425) → modules/agent yanına, (b) önbellek anahtarı/revizyon hash'leri + _lookup/_store_cache (327-494, 1435-1522; question_hash tekrarı CacheRevision.hash_for ile kapanır) → ayrı modül, (c) produce_answer (680-863) → modules'a, (d) kalıcılaştırma yardımcıları (1346-1609) → ayrı dosya. set_pipeline/get_*/question_hash app.api.chat'ten RE-EXPORT edilir (test_chat_api doğrudan import ediyor). ZORUNLU eş-güncelleme: scripts/role_agent_application_mutation_check.py'nin chat.py bayt-çivileri yeni dosya düzenine taşınır. R3 → dossier.
- **Risk:** YÜKSEK — deponun en sensitive dosyası (R3), TOCTOU sınav-kilidi ve rezervasyon-üretimden-önce sıralaması gibi belgeli güvenlik sıraları korunmalı; bu yüzden dizinin SONUNA konuldu, tüm ağ (PR 1-2 ile güçlendirilmiş) yerindeyken yapılır.
- **Doğrulama:** Tam pytest 904 (özellikle test_chat_api 36 + test_answer_cache + test_role_aware_agent* + test_exam_lock); python scripts/role_agent_application_mutation_check.py 12/12 (güncellenmiş çivilerle: her mutasyon yalnız kendi testini düşürüyor); e2e chat akışları + role-aware-agent.spec 3.

### PR 12: Web: ChatScreen'i böl + useSubmit'i chat yüzeyine uygula [DOSSIER]

- **Kapsam:** chat/page.tsx'teki 578 satırlık ChatScreen hook'lara/alt-bileşenlere ayrılır: useChatSession (aç/geri yükle/localStorage), useReverseHistory (prepend destekli sayfalama — use-paged-resource'un ters varyantı, settings'teki ilk-sayfa-unwrap'i de kapsayabilir), gönderim akışı useSubmit'e bağlanır (PR 5'te hariç tutulan chat:314 + course-assistant:331 dahil). SENSITIVE: apps/web/app/courses/**/chat/** R3, components/course-assistant/** R3 → dossier. ZORUNLU: lib/course-assistant*.test.ts kaynak-metin çivileri güncellenir; Next 16.3.0 için node_modules/next/dist/docs önce okunur.
- **Risk:** YÜKSEK (web tarafının en risklisi) — tek bileşende 11 useState'in etkileşimi (optimistic pending, mod reset'leri) render testi olmadan bölünüyor; ağ = lib/chat.ts'in 44 testi (saf mantık zaten dışarıda, bu riski ciddi azaltır) + e2e sohbet akışları. Sona konuldu.
- **Doğrulama:** bun test lib/ (chat 44 + course-assistant testleri güncellenmiş halde) + tam e2e: flows.spec sohbet bölümü (kaynaklı cevap, nazik ret, Sokratik merdiven, geçmiş yenilemede kalır) + role-aware-agent.spec 3 + portal.spec mobil/koyu tema.

---

Kurallar: `[DOSSIER]` işaretli adımlar AI-SDLC sensitive path'lere dokunur ve dossier+kanıt ister.
`chat.py` bölünmesi (PR 11) ve ChatScreen bölünmesi (PR 12) en riskli adımlardır ve sona bırakılmıştır;
ilk adımlar test ağını güçlendirir (fixture konsolidasyonu, CI'a mutasyon kanıtları, sözleşme kapısı).
