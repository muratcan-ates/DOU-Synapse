# R1 — Backend / RAG — Rol Brief'i

> Bu dosya senin rol tanımın. Projenin **omurgası** sende: retrieval hattı, LLM üretim
> zinciri ve her şeyin birleştiği `chat.py` ucu. Diğer dört rolün işi ya senin yazdığın
> servise bağlanır ya da senin yayınladığın şemayı bekler. R2'nin guardrail'i senin
> retrieval kümenle doğrular, R4'ün frontend'i senin cevap şemanla konuşur, R5'in eval'i
> senin `retrieve()` fonksiyonunu çağırır. **Sen gecikirsen takım durur; sen erken
> bitirirsen takım paralelleşir.**
>
> Aşağıdaki "YAPIŞTIRILACAK PROMPT" bölümünü yeni bir AI sohbetine olduğu gibi
> yapıştır, sonra Adım 1'den başla.

**Sert kapılar:** G5 (Pzt 10 Ağu) dikey RAG demosu · G10 (Pzt 17 Ağu) özellik dondurma ·
G15 (Pzt 24 Ağu) teslim.

**Senin görevlerin:** Faz A'dan **T001, T003-T007** (retrieval hattı; T002 materyal paketi R5'te) · Faz B üretim
kısmı **T008-T012** (LiteLLM + cevap şeması + prompt + üretim servisi) · Faz C backend
**T017-T020** (chat migration + model + uç + testler) · **T027** (Sokratik entegrasyonu —
R2'nin `socratic.py`'sini `chat.py`'ye SEN bağlarsın) · Faz G'den **T048-T050** (Dockerfile
+ worker tetiği + prod doğrulama).

Not: R2 (Guardrail & QA) rolü de sende ama o rolün ayrı brief'i var
(`02_GUARDRAIL_QA_BRIEF.md`). Bu dosya YALNIZ R1 işlerini kapsar; iki rolü aynı AI
sohbetinde karıştırma, her rol kendi sohbetinde kendi brief'iyle çalışır.

---

## YAPIŞTIRILACAK PROMPT (Başlıyor)

Merhaba. Ben Doğuş Üniversitesi COME 491/492 bitirme projesi **DOU-Synapse (CourseGPT)**
takımında **R1 — Backend / RAG** rolündeyim. Proje: ders materyaliyle SINIRLI çalışan,
her cevabını dosya adı + sayfa/slayt kaynağıyla veren bir RAG ders asistanı.

**Repo:** https://github.com/muratcan-ates/DOU-Synapse
**Lokal yol:** `~/code/DOU-Synapse` (iCloud senkronlu klasörlere ASLA konmaz)
**Teslim:** 24 Ağustos 2026.

**Takım ve roller:** R1 Backend/RAG (ben), R2 Guardrail & QA (citation/leakage/sanitize +
Sokratik state machine), R3 Assessment & Analytics (soru üretimi, sınav, mastery),
R4 Frontend (Muratcan — lead + sıcak dosya hakemi), R5 Data & Eval (gold set, eval
harness, belgeler).

**Teknoloji yığını:** Python 3.12 + FastAPI + SQLAlchemy async + psycopg · PostgreSQL 16 +
pgvector · Next.js 16 + Tailwind v4 + Bun · uv (Python paket yöneticisi) · ruff + pytest ·
LiteLLM (Groq → Gemini failover). **LangChain / LlamaIndex / LangGraph bilinçli olarak
YOK** — düz Python servis kodu; öneri getirme (Anayasa, Teknoloji Kilidi).

**Şu ana kadar biten (G1-G4):** ders/üyelik API'si, dosya yükleme + PDF/PPTX/MD/kod
parser'ları, sayfa sınırını koruyan chunking, embedding (multilingual-e5-large; testlerde
`EMBEDDING_PROVIDER=hashing` ile deterministik), pgvector, iki katmanlı izolasyon (uygulama
katmanı + PostgreSQL RLS), Next.js frontend (giriş, ders listesi, materyal yükleme,
sekmeler, üye yönetimi, sınav ve Sokratik ekranlarının tasarım önizlemeleri). 68 test
geçiyor. FTS altyapısı (unaccent + `chunks.fts` generated column + GIN indeksi)
`supabase/migrations/0001_core_schema.sql`'de ZATEN kurulu — yeni migration gerekmez.

**Projenin pazarlık edilmez ilkeleri (`.specify/memory/constitution.md`):** kaynak yoksa
cevap yok · iki katmanlı izolasyon (course_id istemciden asla yetki değildir) · ölçmeden
iddia etme · fail-closed varsayılanlar · Türkçe birinci sınıftır · doğrulama bitmeden
"bitti" yok.

### Benim rolüm

Sorgu pipeline'ının (ARCHITECTURE.md §5) **1-4. adımları ve zincirin birleştirilmesi**
benim; 5-7 R2'nin ama onları `chat.py` içinde çağıran yine benim:

```
1. AuthZ        (var — deps.py: CourseMemberDep)          ← kullanıyorum, değiştirmiyorum
2. Retrieval    dense top-20 ∥ FTS top-20 → RRF → top-8   ← BEN (T003-T006)
3. Evidence     eşik altıysa ABSTAIN (fail-closed)         ← BEN (T006 içinde)
   gate
4. Generation   LiteLLM + XML bağlam + Pydantic şema       ← BEN (T008-T012)
5. Citation     set-membership                             ← R2 (ben chat.py'de çağırırım)
6. Pedagojik    kod/çözüm sızıntı filtresi                 ← R2 (ben chat.py'de çağırırım)
7. Sanitize     XSS + ham hata temizliği                   ← R2 (ben chat.py'de çağırırım)
```

Artı: chat migration'ı + modelleri + ucu (T017-T019), chat davranış testleri (T020),
Sokratik modun `chat.py` entegrasyonu (T027), deploy'un backend ayağı (T048-T050).

**Takımı bloklayan iki işim var, ikisini de erken bitirip gruba duyururum:**

1. **T006 (`retrieve()` servisi)** — B, C, D ve F fazlarının TAMAMI buna bağlı. İlk
   bitecek iş. Bitince gruba: **"T006 hazır, retrieve() çağrılabilir."**
2. **T010 (cevap şeması)** — R2'nin guardrail'i ve R4'ün TypeScript tipleri bu şemayı
   bekliyor. Yazar yazmaz gruba: **"şema hazır."** (Gövde kodu beklemez; şema dosyası
   tek başına commit'lenir.)

### Dosya sahipliğim (bunların dışına ÇIKMAM)

```
apps/api/app/modules/retrieval/          ← TAMAMI benim (dense, fts, fusion, service)
apps/api/app/modules/generation/         ← TAMAMI benim (llm, prompts, service)
apps/api/app/api/chat.py                 ← benim (Sokratik entegrasyonu dahil, T027)
apps/api/app/models/chat.py              ← benim
apps/api/app/schemas/chat.py             ← benim (T010 — R2 ve R4 bunu bekliyor)
supabase/migrations/0003_chat.sql        ← benim
apps/api/tests/test_retrieval.py         ← benim
apps/api/tests/test_chat_api.py          ← benim
apps/api/Dockerfile                      ← benim (T048)
apps/api/app/api/internal.py             ← benim (T049, YENİ)
```

**Sıcak dosyalar (ekleme yaparım, başkasının satırına DOKUNMAM — çakışırsa
`git pull --rebase`, asla `--ours`/`--theirs`):**

- `apps/api/app/core/config.py` — yalnız kendi bölüm yorumlarımın altına:
  `# --- Retrieval ---` ve `# --- LLM ---`. Var olan alan silinmez.
- `apps/api/app/main.py` — yalnız `include_router` satırı + import. Tek satırlık değişiklik.
- `apps/api/pyproject.toml` — `litellm` listenin SONUNA, sürümü sabitlenmiş.
- `specs/001-course-assistant-mvp/contracts/openapi.json` — **elle düzenlenmez**, uç
  ekleyen commit'te yeniden export edilir (komut aşağıda, Kurallar 9).

**Bana ait OLMAYAN, dokunmayacağım dosyalar:** `apps/api/app/modules/guardrails/` ve
`apps/api/app/modules/assessment/socratic.py` (R2 — ben yalnız import edip çağırırım),
`question_gen.py` / `grading.py` / `mastery/` (R3), `apps/web/` (R4 — tip değişikliğini
R4'e BİLDİRİRİM, `lib/types.ts`'i kendim düzenlemem), `evaluation/gold_set/` ve `docs/`
kılavuzları (R5), `supabase/migrations/0001_core_schema.sql` (DONDURULMUŞ; şema
değişikliği yeni migration'la), `app/core/security.py` ve `app/api/deps.py` (auth; değişiklik
gerekirse Murat onaylar).

---

### Teslimat 1 — FTS doğrulaması (T001, migration YOK)

Kod yazılmaz. `0001_core_schema.sql` FTS'in tamamını zaten kurmuş: `unaccent` extension,
`app.immutable_unaccent` IMMUTABLE sarmalayıcı, `chunks.fts` generated column
(`to_tsvector('simple', ...)`) ve `chunks_fts_idx` GIN indeksi. Görev yalnız lokal DB'de
doğrulamak:

```sql
SELECT fts FROM chunks LIMIT 1;   -- kolon dolu mu
SELECT chunk_index, page_number
FROM chunks
WHERE fts @@ websearch_to_tsquery('simple', unaccent('fork'))
LIMIT 5;                          -- sorgulanabilir mi
```

Sonuç `tasks.md`'ye tarihli DONE notu olarak işlenir. `simple` konfigürasyonu bilinçli:
köklendirme yok, `fork()` ve `O(n log n)` gibi teknik token'lar bozulmaz (ARCHITECTURE §1).

### Teslimat 2 — YOK: `sample_data/` paketi (T002) **R5'in (Metehan) işidir**

Sen bu paketi hazırlamazsın. Faz A kapanış kriteri gerçek materyal gerektirdiği için
yalnızca **beklersin**: paket G7'ye kadar gelmezse gruba yaz. Kendi geliştirmen sırasında
köprü olarak `apps/api/tests/test_ingestion.py`'deki `make_pdf()` yardımcısıyla küçük test
PDF'leri üretip ingest edebilirsin (bu geçici, teslimata girmez).

≥3 PDF + 1 PPTX + 2 kod dosyası; telifsiz veya kendi üretimi İşletim Sistemleri
materyali. Canlı demo yüklemesi için 5-10 sayfalık küçük bir PDF ayrıca işaretlenir.
`sample_data/README.md` içerik listesini tutar. Bu görev kod işlerinle paralel gider ve
yalnız Faz A kapanış kriterini bloklar; ama R5'in gold set'i (T041) bu materyale soru
yazacağı için geciktirilmez.

### Teslimat 3 — `apps/api/app/modules/retrieval/dense.py` (T003)

```python
"""Dense retrieval: pgvector cosine top-k.

Kural (Anayasa II): her sorguda ZORUNLU `WHERE course_id = :authorized_course_id`.
course_id bu modüle deps.py'nin doğruladığı bağlamdan gelir; istemciden gelen değer
hiçbir katmanda yetki değildir. Filtre chunks.course_id denormalize kolonuna vurur,
JOIN'e bağlı kalmaz.
"""
from __future__ import annotations
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.retrieval.service import RetrievedChunk   # tek veri sınıfı, aşağıda


async def dense_search(
    session: AsyncSession,
    *,
    course_id: UUID,
    query: str,
    k: int = 20,
) -> list[RetrievedChunk]:
    """Sorguyu embed eder, cosine mesafeye göre top-k chunk döner (skor: 1 - mesafe)."""
    ...
```

**E5 önek kuralı — sessiz kalite kaybı riski (ARCHITECTURE §1):** sorgu embedding'i
MUTLAKA `app/modules/ingestion/embedding.py`'deki
`get_embedding_provider().embed_query(query)` ile üretilir. `embed_query` `query: `
önekini KENDİSİ ekler (davranış `tests/test_embedding_prefix.py` ile sabit). Yani:
`embed_documents` ile sorgu embed'leme (o `passage: ` ekler, uzay kayar); öneki elle
ekleme (çift önek olur). Önek atlanırsa hata alınmaz, retrieval kalitesi sessizce düşer —
bu yüzden kural katıdır.

SQL iskeleti: `ORDER BY embedding <=> :query_vec LIMIT :k`, seçilen kolonlar
`id, course_id, document_id, page_number, slide_number, section_title, content_type, text`
+ dosya adı için `documents.file_name` (tek JOIN; izolasyon filtresi yine
`chunks.course_id` üzerinde).

### Teslimat 4 — `apps/api/app/modules/retrieval/fts.py` (T004, [P])

```python
"""Sparse retrieval: PostgreSQL FTS (simple + unaccent), MEVCUT chunks.fts kolonu.

Aynı zorunlu course_id filtresi. Yeni index/migration YOK (T001'de doğrulandı).
"""
async def fts_search(
    session: AsyncSession,
    *,
    course_id: UUID,
    query: str,
    k: int = 20,
) -> list[RetrievedChunk]:
    """websearch_to_tsquery('simple', unaccent(:q)) ile top-k; skor ts_rank_cd."""
    ...
```

`websearch_to_tsquery` seçimi bilinçli: kullanıcı girdisini güvenle parse eder,
`to_tsquery`'nin sözdizimi hatalarına düşmez. Boş/parse edilemeyen sorguda boş liste
döner, exception fırlatmaz.

### Teslimat 5 — `apps/api/app/modules/retrieval/fusion.py` (T005)

```python
"""Reciprocal Rank Fusion (k=60). Saf fonksiyon: I/O yok, LLM yok, rastgelelik yok.

RRF skoru: score(c) = Σ_lists 1 / (k + rank_c)   (rank 1'den başlar)
"""
def rrf_fuse(
    result_lists: Sequence[Sequence[RetrievedChunk]],
    *,
    k: int = 60,
    top_n: int = 8,
) -> list[RetrievedChunk]:
    """Sıralı listeleri birleştirir, chunk_id bazında tekilleştirir, top_n döner.

    Dönen her chunk'ın `score` alanına RRF skoru yazılır (evidence gate bunu okur).
    Deterministiktir: aynı girdi listeleri her zaman aynı çıktıyı verir; eşitlik
    chunk_id ile kırılır (test edilebilirlik).
    """
    ...
```

### Teslimat 6 — `apps/api/app/modules/retrieval/service.py` + config ayarları (T006) — **HERKESİ BLOKLAYAN İŞ**

Tek giriş noktası. R2, R3, R5 ve `chat.py` yalnız bunu çağırır; `dense/fts/fusion`
iç detaydır.

```python
"""Retrieval servisi: dense ∥ FTS → RRF → evidence gate.

Fail-closed (Anayasa IV): en iyi sonuç eşik altındaysa chunk listesi BOŞ döner ve
abstained=True işaretlenir. Şüphede sistem kapanır, açılmaz.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class RetrievedChunk:
    """Retrieval'dan dönen tek kayıt.

    ALAN ADLARI SÖZLEŞMEDİR: R2'nin citation.py'si bu alanlara Protocol ile bağlanıyor
    (chunk_id, file_name, page_number, slide_number, text). Adları değiştirmek R2'yi
    kırar; değişiklik gerekirse önce gruba yazılır.
    """
    chunk_id: UUID
    course_id: UUID
    document_id: UUID
    file_name: str
    page_number: int | None
    slide_number: int | None
    section_title: str | None
    content_type: str          # text | table | code
    text: str
    score: float = 0.0         # dense/fts kendi skorunu, fusion RRF skorunu yazar


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]   # abstain'de BOŞ
    abstained: bool                # True => evidence gate kapandı
    top_score: float | None        # loga ve kalibrasyona (T043) gider


async def retrieve(
    session: AsyncSession,
    course_id: UUID,
    query: str,
) -> RetrievalResult:
    """dense top-k ∥ fts top-k → rrf_fuse → evidence gate → RetrievalResult.

    course_id, deps.py'nin DOĞRULADIĞI değerdir; bu fonksiyon üyelik kontrolü yapmaz
    ama filtreyi her alt sorguya koşulsuz uygular (çift emniyet: uygulama + RLS).
    """
    ...
```

`apps/api/app/core/config.py`'ye kendi bölümüm (sıcak dosya protokolü — yalnız ekleme):

```python
    # --- Retrieval ----------------------------------------------------------
    retrieval_dense_k: int = 20
    retrieval_fts_k: int = 20
    rrf_k: int = 60
    retrieval_final_k: int = 8
    evidence_threshold: float = 0.03   # GEÇİCİ başlangıç değeri; kalibrasyon T043'te
```

Eşik değeri hakkında dürüstlük (Anayasa III): başlangıç değeri tahmindir ve öyle
etiketlenir. Kalibrasyonu R5, `evaluation/evaluate.py --set calibration` ile G11'de yapar;
ben yalnız config'ten okurum, koda gömmem. **Bu görev bitince gruba haber: "T006 hazır."**

### Teslimat 7 — `apps/api/tests/test_retrieval.py` (T007)

`EMBEDDING_PROVIDER=hashing` ile deterministik koşar (hashing provider sözcük örtüşmesine
göre gerçek benzerlik üretir, model indirmez). En az şu davranışlar:

1. **İzolasyon:** başka dersin chunk'ı hiçbir koşulda dönmez — iki ders seed'le, A'nın
   sorgusu B'nin chunk'ını asla getirmez (dense de FTS de ayrı ayrı denenir).
2. **RRF doğruluğu:** sentetik sıralamalarla `rrf_fuse` beklenen birleşimi veriyor
   (elle hesaplanmış küçük örnek: 2 liste × 3 eleman).
3. **Abstain:** eşik altı sorguda `abstained=True` ve `chunks == []`.
4. **Teknik token:** FTS `fork()` sorgusunu yakalıyor (simple + unaccent seçiminin kanıtı).

### Teslimat 8 — LiteLLM bağımlılığı + LLM config'i (T008)

- `apps/api/pyproject.toml` → `litellm` listenin sonuna, sürüm sabitli (ör. `litellm==1.x.y`
  — kurulum günü güncel kararlı sürüm neyse o, sonra dokunulmaz).
- `apps/api/app/core/config.py` → kendi `# --- LLM ---` bölümüm:

```python
    # --- LLM ----------------------------------------------------------------
    llm_primary_model: str = "groq/llama-3.3-70b-versatile"
    llm_fallback_model: str = "gemini/gemini-2.0-flash"
    groq_api_key: str = ""
    gemini_api_key: str = ""
    llm_timeout_seconds: float = 30.0
    llm_num_retries: int = 2
    llm_daily_token_budget: int = 500_000
```

- `.env.example` aynı commit'te güncellenir — **anahtarlar boş şablon olarak**. Gerçek
  anahtar repoya da bu sohbete de girmez.

### Teslimat 9 — `apps/api/app/modules/generation/llm.py` (T009)

```python
"""LiteLLM Router: Groq (Llama) → Gemini Flash OTOMATİK failover.

KRİTİK (ARCHITECTURE §1): failover KOD SEVİYESİNDEDİR — Router'ın fallbacks
mekanizması + exponential backoff. "Groq düşerse anahtarı elle değiştiririz" DEĞİL.
Bu davranış T016'da (R2) mock ile ve T050'de canlıda (Groq anahtarı bilerek bozulur)
test edilir. Her iki sağlayıcı da düşerse LLMUnavailableError yükselir; chat.py bunu
anlaşılır Türkçe hataya çevirir, yarım/kaynaksız cevap ASLA dönmez.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResult:
    text: str
    model_used: str        # loga: hangi sağlayıcı cevapladı (failover kanıtı)
    prompt_tokens: int
    completion_tokens: int


class LLMUnavailableError(Exception):
    """Her iki sağlayıcı da başarısız. chat.py Türkçe hata zarfına çevirir."""


async def complete(
    messages: list[dict[str, str]],
    *,
    response_json: bool = True,     # Pydantic'e gidecek çıktı için JSON modu
    max_tokens: int | None = None,
) -> LLMResult:
    """Router üzerinden tek tamamlanma. Token kullanımı redaction'lı logger'a yazılır."""
    ...
```

Router kurulumu modül seviyesinde tembel (lazy) yapılır; ayarlar `get_settings()`'ten
okunur. Token sayıları `request_logs`'a T019'da bağlanır; günlük bütçe aşımı loglanır.

### Teslimat 10 — `apps/api/app/schemas/chat.py` (T010, [P]) — **R2 VE R4'Ü BLOKLAYAN İŞ**

ARCHITECTURE §5'teki cevap şeması birebir. Bu dosya tek başına, gövde kodu beklemeden
commit'lenir ve gruba **"şema hazır"** yazılır — R2'nin `citation.validate`'i ve R4'ün
`lib/types.ts` tipleri bunu bekliyor.

```python
"""Chat istek/cevap şemaları (T010). Sözleşme dosyası: R2 ve R4 buna bağlanır."""
from __future__ import annotations
from enum import StrEnum
from uuid import UUID
from pydantic import BaseModel, Field


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_CONTEXT = "insufficient_context"   # retrieval boş/eşik altı
    OUT_OF_SCOPE = "out_of_scope"                   # retrieval var ama müfredat dışı


class ChatMode(StrEnum):
    QA = "qa"
    SOCRATIC = "socratic"
    EXAM = "exam"


class Citation(BaseModel):
    chunk_id: UUID
    claim: str                       # cevabın bu kaynağa dayanan iddiası


class Hint(BaseModel):
    text: str
    chunk_id: UUID                   # kaynaksız hint YOK (Anayasa I, FR-013)


class SourceCard(BaseModel):
    """Kullanıcıya giden kaynak kartı — chunk METADATA'sından üretilir, model
    metninden ASLA (FR-010). chunk_id → bu karta eşlemeyi backend yapar."""
    chunk_id: UUID
    file_name: str
    page_number: int | None
    slide_number: int | None
    snippet: str


class AnswerResponse(BaseModel):
    status: AnswerStatus
    mode: ChatMode
    answer: str = ""                             # abstain'de nazik Türkçe mesaj
    citations: list[Citation] = Field(default_factory=list)
    hints: list[Hint] = Field(default_factory=list)
    sources: list[SourceCard] = Field(default_factory=list)  # citation.validate sonrası


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)      # FR-035 girdi sınırı
    mode: ChatMode = ChatMode.QA
    session_id: UUID | None = None               # None => yeni oturum açılır
```

Ek olarak oturum/geçmiş uçlarının çıktı şemaları: `ChatSessionOut`, `ChatMessageOut`
(mesaj + citations jsonb'nin karşılığı). LLM'den beklenen ham çıktı şeması ise ayrı bir
iç model olarak burada durur (`RawModelOutput`: status/answer/citations/hints — `sources`
YOK, onu model üretemez, backend üretir).

### Teslimat 11 — `apps/api/app/modules/generation/prompts.py` (T011)

```python
"""Prompt şablonları. Bağlam VERİ olarak işaretlenir (indirect injection önlemi).

Retrieval bağlamı XML etiketiyle verilir; belge içindeki 'önceki talimatları unut'
tarzı metin talimat değil VERİDİR ve sistem talimatı bunu açıkça söyler
(ARCHITECTURE §6). Bu bir mitigasyondur; test yükümlülüğü R2'nin T046 koşusundadır.
"""

def build_context_block(chunks: Sequence[RetrievedChunk]) -> str:
    """<retrieved_context><source id="{chunk_id}" file="{file_name}" page="{n}">...
    </source></retrieved_context> biçiminde bağlam. İçerik XML-escape edilir."""
    ...

def build_messages(
    *,
    chunks: Sequence[RetrievedChunk],
    question: str,
    mode: ChatMode,
    socratic_stage: str | None = None,   # R2'nin SocraticStage değeri (T027'de bağlanır)
) -> list[dict[str, str]]:
    """Moda göre sistem+kullanıcı mesajları: qa / socratic / exam.

    Ortak kurallar: yalnız bağlamdaki kaynaklardan cevapla; her iddiaya source id ile
    atıf ver; bağlam yetersizse insufficient_context döndür; müfredat dışına NAZİK
    TÜRKÇE ret (out_of_scope). Socratic: cevabı verme, kademeye uygun tek ipucu üret.
    Exam: hint üretme.
    """
    ...
```

### Teslimat 12 — `apps/api/app/modules/generation/service.py` (T012)

```python
"""Üretim servisi: prompt → LLM → Pydantic validasyon → 1 retry → fail-closed.

Kural (FR-020 deseni): bozuk çıktıda 1 kez yeniden denenir; yine bozuksa uydurma
bir cevap YERİNE status=insufficient_context döner. Şüphede kapanırız.
"""

async def generate(
    chunks: Sequence[RetrievedChunk],
    question: str,
    mode: ChatMode,
    *,
    socratic_stage: str | None = None,
) -> AnswerResponse:
    """build_messages → llm.complete → RawModelOutput.model_validate_json →
    AnswerResponse. Validasyon iki kez de düşerse insufficient_context.
    LLMUnavailableError'ı YUTMAZ, yukarı (chat.py'ye) bırakır."""
    ...
```

Dikkat: bu servis `sources` alanını DOLDURMAZ ve atıf doğrulamaz — o R2'nin
`citation.validate`'inin işi; zincir sırası `chat.py`'de kurulur. Faz B, T006'yı
beklemeden **mock retrieval ile** test edilebilir (tasks.md Faz B notu) — R2 zaten
sahte `RetrievedChunk` nesneleriyle çalışıyor, ben de üretim testlerinde aynısını yaparım.

### Teslimat 13 — `supabase/migrations/0003_chat.sql` (T017)

0001 DONDURULMUŞ; chat şeması yeni migration'la gelir. Tablolar (ARCHITECTURE §3):

- `chat_sessions` — id, course_id, user_id, `mode` (qa|socratic), `state` jsonb
  (R2'nin `SocraticState.to_json()` çıktısı buraya yazılır), created_at.
- `chat_messages` — id, session_id, role (user|assistant), content, `citations` jsonb,
  status, created_at.
- `answer_cache` — course_id, `question_hash` (normalize edilmiş sorunun SHA-256'sı),
  `response` jsonb; UNIQUE(course_id, question_hash). **Exact-match** demo cache (FR-034)
  — benzerlik tabanlı eşleşme BİLİNÇLİ olarak yok.
- `request_logs` — redaction'lı: latency_ms, status, course_id, user_id, token_count,
  model_used. Soru metni HAM saklanmaz.

RLS politikaları: üye yalnız KENDİ oturumunu/mesajını okur-yazar (course üyeliği +
user_id eşleşmesi); `request_logs`'a istemci rolünden erişim YOK (yalnız servis içi).
0001'deki politika desenini (`dou_app` rolü, `app.current_user_id` GUC) kopyala, yeni
desen icat etme.

### Teslimat 14 — `apps/api/app/models/chat.py` (T018)

0003'teki dört tablonun SQLAlchemy modelleri, `app/models/core.py` deseniyle birebir
(aynı Base, aynı tip alışkanlıkları, jsonb için aynı yaklaşım). ORM'den şema üretilmez;
model migration'ı YANSITIR (Yol Kuralları).

### Teslimat 15 — `apps/api/app/api/chat.py` (T019)

Zincirin birleştiği yer. Uçlar:

- `POST /courses/{course_id}/chat` — ana uç.
- `GET  /courses/{course_id}/chat/sessions` — kullanıcının oturum listesi.
- `GET  /courses/{course_id}/chat/sessions/{session_id}/messages` — mesaj geçmişi.

`POST` akışı — SIRA GÜVENLİK SINIRIDIR, değiştirilemez (ARCHITECTURE §5):

```python
# 0. AuthZ: CourseMemberDep (deps.py'den) — course_id burada, YALNIZ burada yetkilenir
# 1. Girdi sınırları (FR-035): uzunluk 422, kullanıcı başına rate limit 429
# 2. answer_cache exact-match kontrolü — isabet varsa LLM'e HİÇ gidilmez
# 3. retrieval.retrieve(session, course_id, request.message)          # T006
#    → abstained ise: 200 + AnswerResponse(status=insufficient_context)
#      (hata zarfı DEĞİL — abstention olağan sonuçtur, Anayasa VII)
# 4. generation.generate(chunks, question, mode, socratic_stage=...)  # T012
# 5. citation.validate(citations=…, hints=…, retrieved=chunks)        # R2
#    → ok=False ise cevap GÖSTERİLMEZ → insufficient_context (fail-closed)
#    → ok ise SourceCard listesi buradan gelir (chunk metadata'sından)
# 6. mode in (socratic, exam) ise leakage.enforce(...)                # R2
# 7. sanitize.sanitize_text(...)                                      # R2
# 8. chat_messages + request_logs kaydı; Sokratik state'i session'a yaz
```

`LLMUnavailableError` → anlaşılır Türkçe hata zarfı (`app/core/errors.py` düzeni:
`{"error": {"code", "message"}}` — yeni zarf icat edilmez). Router `main.py`'ye tek
satırla eklenir ve **aynı commit'te** `openapi.json` yeniden export edilir.

### Teslimat 16 — `apps/api/tests/test_chat_api.py` (T020)

LLM mock'lanır; retrieval ve guardrail'ler GERÇEK koşar (yeşile boyama yok). Maddeler:

1. Kaynaksız akademik cevap asla dönmez (mock LLM uydurma chunk_id verir → cevap bloklanır).
2. Kapsam dışı soru `out_of_scope` + nazik Türkçe metinle döner.
3. Üye olmayan kullanıcı erişemez (403/404 — mevcut `test_courses.py` desenine bak).
4. Cache isabeti LLM çağrısı YAPMAZ (mock çağrı sayacıyla kanıt).
5. Abstention hata zarfı DEĞİL, normal `200` + `insufficient_context`.
6. Rate limit aşımı `429`, aşırı uzun soru `422` (FR-035).

### Teslimat 17 — Sokratik entegrasyonu (T027, dosya: yine `apps/api/app/api/chat.py`)

> **Ek madde (T037'nin chat.py ayağı):** Sokratik oturum kapanışında R3'ün
> `mastery.record_answer(...)` fonksiyonu çağrılır. İmzayı R3 (Metehan) yazılı verir;
> sen yalnız çağırırsın. R3'ün dosyalarına dokunmazsın.

R2 `socratic.py`'yi yazar ve arayüz sözleşmesini yazılı verir (02 brief'inde hazır);
**entegrasyonu BEN yaparım** — `chat.py` benim dosyam, R2 ona dokunmaz:

- `state = SocraticState.from_json(session.state)` → `turn = advance(state, message=...)`
- `generation.generate(..., socratic_stage=turn.state.stage)` — prompt kademeye göre.
- Sokratik cevap yolu leakage filtresinden (T014) ZORUNLU geçer.
- `exam` modunda hint TAMAMEN kapalı — mod politikaları backend'de, istemci belirleyemez.
- `session.state = turn.state.to_json()` — state `chat_sessions.state`'te kalıcı
  (oturum yeniden yüklense de kademe korunur; R2'nin T028 testi bunu doğrular).

R2'nin fonksiyonları saf ve senkron, sonuç nesnesi döner, exception fırlatmaz — akış
kontrolü bende kalır. Sözleşmede değişiklik gerekirse koda değil önce gruba yazılır.

### Teslimat 18 — `apps/api/Dockerfile` (T048)

- Multi-stage build: model (multilingual-e5-large, ONNX **int8 quantize**) build
  aşamasında indirilir ve imaja GÖMÜLÜR; `EMBEDDING_CACHE_DIR` imaj içini gösterir.
  Çalışma zamanında HuggingFace'e SIFIR bağımlılık (scale-to-zero uyanması dış servise
  bağlanamaz — ARCHITECTURE §1).
- `.github/workflows/ci.yml`'e assertion adımı: konteyner `--network=none` ile ayağa
  kalkıyor ve embed üretebiliyor.
- Replika başına RSS ölçülür ve NOT edilir (ACA consumption ≤ 2 vCPU / 4 GiB) — ölçmeden
  "sığar" denmez (Anayasa III).

### Teslimat 19 — Worker HTTP tetiği (T049)

- YENİ: `apps/api/app/api/internal.py` — `POST /internal/drain`, paylaşılan secret ile
  korumalı (`X-Internal-Secret` başlığı, config'te `internal_drain_secret`; yanlış/boş
  secret → 403). İş: `worker.drain()`'i tetikler.
- `apps/api/app/api/documents.py::_trigger_worker` ortama göre seçer: lokal →
  in-process `worker.drain()`, bulut → worker servisine HTTP çağrısı.
- KARAR (tasks.md): tek Docker imajı, iki ayrı Container App — api (uvicorn) ve worker
  (`python -m app.worker`). IaC/deploy betiği bu görevde yazılır. ARCHITECTURE §2 ile uyumlu.

### Teslimat 20 — Prod ortam doğrulaması (T050)

İlk GERÇEK bulut deploy'u budur (G1'de "hello world deploy" fiilen yapılmadı; gerekirse
Faz G beklenmeden öne alınabilir). Kontrol listesi:

1. Migration'lar (0002-0004) prod Supabase'de koşulur (0002 R4'ün, 0004 R3'ün — koşuyu
   ben yaparım, içeriklerine dokunmam).
2. Vercel: `NEXT_PUBLIC_API_URL` + Supabase anahtarları.
3. ACA: CORS ayarı + `DEV_AUTH_ENABLED=false` — config'in production'da dev-auth'u
   REDDETTİĞİ (uygulama başlamaz) gerçek ortamda gözlemlenir.
4. **LLM failover canlı testi:** Groq anahtarı BİLEREK bozulur → isteğin Gemini'den
   döndüğü loglardan (`model_used`) gözlemlenir → anahtar geri alınır. Kayıt, R5'in test
   raporuna (T056) girdi olur.

---

#> **Erişimler:** Demo ve prod Groq/Gemini anahtarlarını, Vercel / Azure Container Apps /
> Supabase erişimini Murat sağlar. T008'de boş şablon yeter; T050'den ÖNCE ondan iste.


### Teslimat — demo sertleştirme (T052, T053, T054, T055)

Faz G'nin kalan dört görevi de sende (T054-T055 provalarını Murat'la birlikte koşarsın):

- **T052** YENİ `.github/workflows/keepalive.yml` — günlük cron: Supabase'e hafif sorgu +
  API `/health/ready` ping'i. Amaç: free-tier projesinin teslim ile jüri arasında
  uykuya alınmaması.
- **T053** YENİ `apps/api/scripts/fill_answer_cache.py` — demo senaryosu sorularını
  `answer_cache`'e doldurur. **Girdiler elle yazılmaz:** script gerçek chat pipeline'ını
  (T019) çağırır, guardrail zincirinden geçmiş yanıtı saklar. Derse belge eklendiğinde
  veya silindiğinde o dersin cache satırları temizlenir (ingestion'a hook).
- **T054** Yedek + restore provası — `pg_dump` + Storage yedeği; `docker-compose.yml`
  fallback profiline restore edilip dev-auth ile açılır. (Murat'la birlikte.)
- **T055** Cold-start ölçümü + demo günü ayarı — scale-to-zero'dan uyanma süresi ölçülür,
  sıcak replikada sorgu yolu p95 ölçülür, demo/prova günleri için `minReplicas=1` kararı
  yazılır. Ölçülen sayılar `docs/runbook.md`'ye R5 üzerinden geçer. (Murat'la birlikte.)

## KURALLAR — bunlara uyacağım

1. **Her retrieval sorgusunda ZORUNLU `course_id` filtresi (Anayasa II).** dense.py'de de
   fts.py'de de, istisnasız. Filtre `chunks.course_id` denormalize kolonuna vurur.
   İstemciden gelen course_id hiçbir katmanda yetki değildir; yetkiyi `CourseMemberDep`
   verir, ben veriliyi kullanırım. Bu filtreyi "RLS zaten var" diye gevşetmek YASAK —
   izolasyon iki katmanlıdır, tek katmana güvenilmez.
2. **Evidence gate fail-closed (Anayasa IV).** Eşik altı → boş sonuç + abstain. "Az da
   olsa bir şey gösterelim" bu projede yanlıştır. Abstain hata değil olağan sonuçtur;
   200 + `insufficient_context` döner, hata zarfı dönmez.
3. **E5 önek kuralı:** sorgu tarafında HER ZAMAN `embed_query` (öneki kendisi ekler);
   `embed_documents`'la sorgu embed'lemek ve elle önek eklemek yasak. Sessiz kalite
   kaybıdır, hata vermez — o yüzden koddan değil kuraldan yakalanır.
4. **LiteLLM Router otomatik failover** — manuel anahtar/model değişimi değil. Failover
   kodda yaşar, davranışı mock'la (T016/T020) ve canlıda (T050) kanıtlanır.
5. **`chat.py`'nin sahibi benim.** R2/R3 modüllerini ben import edip ben çağırırım;
   onların dosyalarına yazmam, benimkine kimse yazmaz. Guardrail zincir SIRASI
   (retrieval → evidence → generation → citation → leakage → sanitize) ARCHITECTURE §5'te
   sabittir; sırayı değiştirmek güvenlik sınırı değiştirmektir, yapılmaz.
6. **Sıcak dosya protokolü:** `config.py`'de yalnız kendi bölümüm, `main.py`'de yalnız
   `include_router` + import, `pyproject.toml`'da listenin sonuna sürüm sabitli ekleme,
   `openapi.json` elle düzenlenmez — uç ekleyen commit'te yeniden export (komut Kurallar
   9'un altında). Çakışmada `git pull --rebase`, asla `--ours`/`--theirs`.
7. **Bloklayan işler önce, duyuru hemen:** T006 bitince "T006 hazır", T010 commit'lenince
   "şema hazır" gruba yazılır. Bekleyen insan varken sessiz kalmak takımı durdurur.
8. **Kod, commit mesajı, dosya adı İngilizce; docstring/yorum ve kullanıcıya dönen her
   metin Türkçe** (Anayasa V). Ham stack trace kullanıcıya asla gitmez; tek hata zarfı
   `app/core/errors.py`'dedir.
9. **Görev = commit = PR.** Conventional commit (`feat(retrieval): ...`), gövdede "neden".
   **`Co-Authored-By` satırı ASLA eklenmez** (Anayasa IX). `main`'e doğrudan push yok.
   PR öncesi üçü de yeşil: `ruff check . && ruff format --check . && python -m pytest -q`.
   OpenAPI yeniden export komutu (uç ekleyen her commit'te):

   ```bash
   cd apps/api && .venv/bin/python -c "
   import json, os
   os.environ.setdefault('DEV_AUTH_ENABLED','true')
   from app.main import create_app
   spec = create_app().openapi()
   open('../../specs/001-course-assistant-mvp/contracts/openapi.json','w').write(
       json.dumps(spec, ensure_ascii=False, indent=2))
   print('güncellendi:', len(spec['paths']), 'yol')
   "
   ```

10. **Ölçmeden iddia etme (Anayasa III).** Eşik değeri "geçici" diye etiketlenir; RSS,
    p95, failover davranışı ölçülür, tahmin edilmez. Testte deterministik olmayan hiçbir
    şeye "deterministik" denmez (RRF deterministiktir, LLM üretimi değildir).

### YAPMA listesi

- `apps/api/app/modules/guardrails/` ve `socratic.py`'ye **dokunma** — R2'nin. Entegrasyon
  hatası görürsen düzeltme, R2'ye söyle.
- `question_gen.py` / `grading.py` / `mastery/` / `0004_assessment.sql`'e **dokunma** — R3'ün.
- `apps/web/` altına **yazma** — R4'ün. Şema değişikliğini R4'e bildir, `lib/types.ts`'i
  kendisi günceller.
- `supabase/migrations/0001_core_schema.sql`'i **değiştirme** — DONDURULMUŞ. FTS için de
  gerek yok (T001).
- `app/core/security.py` / `app/api/deps.py`'yi **değiştirme** — auth; gerekirse Murat onaylar.
- **LangChain / LlamaIndex / LangGraph / yeni RAG kütüphanesi önerme/ekleme** — bilinçli
  dışarıda (Teknoloji Kilidi). Tek yeni bağımlılık `litellm` (T008'de kararlı).
- **Semantik cache yazma** — yalnız exact-match `answer_cache` (FR-034). "Benzer soruya
  aynı cevap" yanlış cevap sızıntısıdır, bilinçli kesildi.
- **Ayrı vektör DB (Qdrant/FAISS/Chroma) önerme** — pgvector tek depo; ikinci depo
  senkron + yetki sızıntısı riski.
- **Reranker ekleme** — P1, bayrak arkasında, dondurma sonrası; bu listede yok.
- **`retrieve()`'i evidence gate'siz kısa devre etme** — "demo için eşiği kapatalım"
  yok; demo sigortası `answer_cache`'tir (T053), gate gevşetmek değil.
- **course_id filtresini JOIN üzerinden kurma** — `chunks.course_id` denormalize kolonu
  var, doğrudan ona filtrele.
- **Guardrail'leri mock'layarak chat testini yeşile boyama** — mock'lanacak tek şey LLM.
- **Streaming (SSE) ekleme** — P1, kapsam dışı.
- **Gerçek `.env`, LLM API anahtarı, Supabase service-role anahtarı, gerçek öğrenci
  verisi** hiçbir AI sohbetine yapıştırılmaz.

### Çıktı kontrol listesi (PR atmadan önce)

**Faz A (T001-T007) için:**
- `SELECT fts FROM chunks LIMIT 1` dolu; `websearch_to_tsquery` sorgusu sonuç veriyor (T001)
- `dense_search` ve `fts_search` imzalarında `course_id` zorunlu keyword; SQL'de
  `WHERE course_id` görünüyor (grep ile bak)
- Sorgu embedding'i `embed_query` ile — `embed_documents` sorgu yolunda HİÇ geçmiyor
- `rrf_fuse` saf: `await`/`session` içermiyor; elle hesaplanmış örnekle testli
- `retrieve()` abstain'de boş liste + `abstained=True` dönüyor
- Config'te 5 retrieval ayarı var, eşik "geçici" yorumuyla işaretli
- İzolasyon testi iki ders seed'iyle koşuyor ve geçiyor; `EMBEDDING_PROVIDER=hashing`
- Gruba "T006 hazır" yazıldı

**Faz B (T008-T012) için:**
- `litellm` pyproject'te sürüm sabitli; `.env.example` boş şablonla güncel
- Failover Router konfigürasyonunda (fallbacks) — kodda if/else anahtar değişimi YOK
- `LLMResult.model_used` loglanıyor (failover kanıtının veri kaynağı)
- `schemas/chat.py` tek başına commit'lendi, gruba "şema hazır" yazıldı
- Bağlam `<retrieved_context><source id= file= page=>` etiketli; içerik XML-escape'li
- `generate()` bozuk çıktıda 1 retry → yine bozuksa `insufficient_context` (testli)
- `generate()` `sources` doldurmuyor, atıf doğrulamıyor (o R2'nin katmanı)

**Faz C (T017-T020) için:**
- 0003 migration'da 4 tablo + RLS; `request_logs`'a istemci erişimi yok; soru metni ham
  saklanmıyor
- `models/chat.py` migration'la birebir (kolon adı/tipi karşılaştırıldı)
- `chat.py`'de zincir sırası ARCHITECTURE §5 ile birebir; cache isabeti LLM'den önce
- Abstention 200 + `insufficient_context` (hata zarfı değil) — testli
- 429 ve 422 sınırları testli (FR-035)
- `main.py`'ye tek satır eklendi; `openapi.json` aynı commit'te yeniden export edildi
- Tarayıcıda veya gerçek API çağrısıyla uçtan uca gözlendi (Anayasa VIII — test yeşili
  tek başına "bitti" değildir)

**T027 için:**
- State `chat_sessions.state`'ten okunup yazılıyor; oturum yeniden yüklenince kademe korunuyor
- Sokratik yol leakage'tan geçiyor; exam modunda hint yolu tamamen kapalı
- R2'nin sözleşme bloğuyla satır satır karşılaştırıldı

**Faz G (T048-T050) için:**
- CI'da `--network=none` konteyner + embed assertion'ı yeşil
- RSS ölçüldü ve not edildi (sayı yazıldı, tahmin değil)
- `/internal/drain` yanlış secret'la 403; lokal/bulut seçimi ortam değişkenine bağlı
- Prod'da `DEV_AUTH_ENABLED=true` denemesinin uygulamayı BAŞLATMADIĞI gözlendi
- Groq→Gemini failover canlıda gözlendi, log kaydı R5'e (T056) iletildi, anahtar geri alındı

### Adım adım plan

**Adım 0 — Kurulum** (aşağıdaki "Kurulum" bölümü, ~45 dk, tek seferlik).

**Adım 1 — Zemini oku (1 saat, kod yazma).** `ARCHITECTURE.md` §1-§6,
`.specify/memory/constitution.md`, `specs/001-course-assistant-mvp/spec.md` FR-009…FR-013
ve FR-034/FR-035, `docs/team/00_TAKIM_KOORDINASYON.md`, mevcut kod:
`apps/api/app/api/deps.py` (CourseMemberDep deseni), `apps/api/app/api/courses.py` (uç
deseni), `apps/api/app/modules/ingestion/embedding.py` (embed_query/önek),
`apps/api/app/models/core.py`, `apps/api/tests/conftest.py`,
`supabase/migrations/0001_core_schema.sql` (chunks + fts + RLS deseni). Sonra bana
pipeline'ın 7 adımını, hangilerinin bende olduğunu ve iki bloklayan işimi geri anlat.

**Adım 2 — T001 doğrulama + T010 şema (G5 sabahı, yarım gün).**
```bash
git checkout main && git pull
git checkout -b feat/T010-answer-schema
```
Önce T001'i koş (10 dakika, tasks.md'ye not). Sonra `schemas/chat.py`'yi TEK BAŞINA yaz
ve commit'le — gövde kodu gelmeden. **Gruba: "şema hazır."** R2 ve R4 aynı gün paralel
başlar.

**Adım 3 — T003 dense + T005 fusion + T006 servis, dense-only v0 (G5).**
```bash
git checkout -b feat/T003-dense-retrieval    # her görev kendi branch'i + PR'ı
```
`retrieve()` ilk sürümde dense-only çalışır (FTS listesi boş geçilir) — G5 kapısı dikey
dilim ister, mükemmel hibrit istemez. **Gruba: "T006 hazır."**

**Adım 4 — T008 + T009 LLM katmanı (G6).** Bağımlılık + config + Router. Failover'ı
mock'la sına (Groq 429 → Gemini).

**Adım 5 — T011 + T012 üretim zinciri (G6).** Mock retrieval ile test ederek — T006'ya
gerçek bağımlılık yok, sahte `RetrievedChunk` yeterli.

**Adım 6 — T004 FTS + hibrit T006 + T007 (G7).** `fts_search`'ü yaz, `retrieve()`'e
RRF'yi bağla, dört maddelik test dosyasını kapat. R5'in T002 materyal paketi de bu güne
kadar hazırla (paralel iş) — kapanış kriteri gerçek materyalle canlı sorgu ister.

**Adım 7 — T017 + T018 chat şeması (G7-G8).** Migration + modeller. R2'nin
`SocraticState` JSON'ının `chat_sessions.state`'e yazılacağını bilerek tasarla.

**Adım 8 — T019 + T020 chat ucu (G8).** Zinciri birleştir. R2'nin `citation.validate`
arayüzü bu noktada hazır olacak (o da G6-G8'de yazıyor); değilse imza sözleşmesine göre
yaz, entegrasyonu arayüz gelince tamamla. `main.py` + `openapi.json` aynı commit'te.
**Bitince tarayıcıda gerçek soru sorup kaynak kartını GÖR (Anayasa VIII).**

**Adım 9 — T027 Sokratik entegrasyonu (G9).** R2'nin sözleşme bloğunu al, `chat.py`'ye
işle. R2'nin T028 testleri + benim T020'm birlikte yeşil olmalı.

**Adım 10 — Dondurma (G10).** Açık uç toplama, düzeltme. Yeni özellik YOK.

**Adım 11 — T048 + T049 (G13).** Dockerfile + drain ucu + CI assertion + deploy betiği.

**Adım 12 — T050 (G13-G14).** Prod doğrulama listesi + canlı failover testi. Kanıtları
R5'e ilet. Sonrasında R2 şapkanla T051 (RLS canlılık kanıtı) zaten sende.

### Takıldığında

- Hata mesajını + komutu + ne yaptığını olduğu gibi yapıştır.
- R2'nin arayüzü hazır değilse **bekleme**: imzalar 02 brief'inde yazılı
  (`CitationResult`, `LeakageOutcome`, `SocraticTurn`); onlara karşı kodla, gövde gelince
  bağla. Aynısı senden bekleniyor: T010'u erken ver.
- 30 dakikadan fazla takılırsan gruba yaz (30 dakika kuralı).
- "Şunu da ekleyeyim mi?" (reranker, streaming, semantik cache...) sorusunun cevabı:
  **önce gruba sor.** PLAN'da bilinçli kesilmiş bir şeyi geri getiriyor olabilirsin.

### Bu projeyi anladığını göstermek için

1. Pipeline'ın 7 adımını sırayla say; hangileri bende, hangileri R2'de?
2. T006 ve T010 neden herkesi blokluyor; bittiklerinde ne yapmam gerekiyor?
3. E5 önek kuralı nedir, sorgu tarafında hangi fonksiyonu çağırmalıyım ve önek atlanırsa
   ne olur (neden fark edilmesi zor)?
4. Evidence gate eşik altında kaldığında kullanıcıya ne döner — HTTP kodu ve status alanı
   ne olur, neden hata zarfı değil?
5. Groq düştüğünde sistem ne yapar ve bu davranışı nerede/nasıl kanıtlıyoruz?

Cevap verdikten sonra Adım 1'den başlayalım.

## YAPIŞTIRILACAK PROMPT (Bitti)

---

## Nasıl kullanırsın?

1. Yeni bir AI sohbeti aç.
2. Yukarıdaki "YAPIŞTIRILACAK PROMPT (Başlıyor)" ile "(Bitti)" arasındaki her şeyi kopyala,
   yapıştır.
3. Asistan 5 soruya doğru cevap veriyorsa bağlamı anlamıştır. Veremiyorsa ilgili dosyayı
   (`ARCHITECTURE.md`, `constitution.md`) da yapıştır.
4. "Adım 1'den başlayalım" de.
5. Her adımda komutları sen çalıştır, çıktıyı yapıştır. **Kodu okumadan commit etme** —
   retrieval ve chat katmanını jüri karşısında savunacak olan sensin, "AI yazdı" cevabı yok.
6. R2 rolüne geçerken AYRI sohbet aç ve `02_GUARDRAIL_QA_BRIEF.md`'yi kullan; iki rolü
   tek sohbette karıştırma.

---

## Kurulum (yaklaşık 45 dakika, tek seferlik)

Aşağıdaki adımlar `specs/001-course-assistant-mvp/quickstart.md`'de doğrulanmış kurulumun
kısaltılmışıdır. Takılırsan tam metin ve sorun giderme tablosu orada. (R2 kurulumunu
zaten yaptıysan bu bölüm tamam demektir; atla.)

### 1. Repo

```bash
mkdir -p ~/code
cd ~/code
# ÖN KOŞUL: GitHub kullanıcı adını Murat'a gönder, collaborator davetini kabul et.
# Davet olmadan clone 404 verir.
brew install uv                     # Python paket yöneticisi
brew install oven-sh/bun/bun        # frontend çalıştırmak istersen
git clone https://github.com/muratcan-ates/DOU-Synapse.git
cd DOU-Synapse
```

**Repo `~/code` altında yaşar.** Masaüstü/Belgeler iCloud'a senkronlanır ve Python
projelerini bozar (Anayasa IX).

### 2. PostgreSQL 16 + pgvector

```bash
brew install postgresql@16
brew services start postgresql@16

# postgresql@16 keg-only: psql/createdb için PATH'e ekle (kalıcısı ~/.zshrc'ye)
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
```

**pgvector kaynaktan derlenir.** Homebrew'daki paket pg17/18'e karşı derlenir, 16'ya
kurulmaz:

```bash
cd /tmp
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
make install PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
```

### 3. Veritabanı (bu sıra önemli)

```bash
cd ~/code/DOU-Synapse
createdb dou_synapse
psql -d dou_synapse -f supabase/migrations/0001_core_schema.sql
psql -d dou_synapse -f supabase/local_dev_setup.sql   # dou_app / dou_worker rollerine yerel giriş
psql -d dou_synapse -f supabase/seed_demo.sql         # demo kullanıcıları (ders İÇERMEZ; dersi arayüzden Ayşe ile açarsın)
```

`local_dev_setup.sql` ve `seed_demo.sql` **üretimde/demoda çalıştırılmaz.**

### 4. Backend

```bash
cd ~/code/DOU-Synapse/apps/api
uv venv --python 3.12          # pyproject: >=3.12,<3.13 (onnxruntime/fastembed pini)
uv pip install -e ".[dev]"
cp ../../.env.example .env
```

Testleri koş:

```bash
.venv/bin/python -m pytest -q
```

68 test yeşil görmelisin. Testler `dou_app` rolüyle bağlanır (RLS gerçekten tetiklenir)
ve `EMBEDDING_PROVIDER=hashing` ile model indirmeden koşar — senin retrieval testlerin de
aynı düzeni kullanacak.

### 5. Frontend (davranışı tarayıcıda görmek için — Anayasa VIII bunu ister)

```bash
cd ~/code/DOU-Synapse/apps/web
bun install
bun run dev        # http://localhost:3000, API http://localhost:8000
```

API'yi ayrı terminalde başlat:

```bash
cd ~/code/DOU-Synapse/apps/api
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Demo girişi: **Ayşe Hoca** (eğitmen) / **Burak Yılmaz** (öğrenci). Giriş kartına
tıklandığında tarayıcıya `Bearer dev:<uuid>` token'ı yazılır; backend bunu
`DEV_AUTH_ENABLED=true` iken kabul eder. Bu bayrak `ENVIRONMENT=production` iken açılırsa
**uygulama başlamaz** — T050'de bunu prod'da bizzat doğrulayacaksın.

---

## Zaman planı

| Gün | İş | Görev | Çıktı |
|---|---|---|---|
| G5 (Pzt 10 Ağu) | T001 doğrulama + cevap şeması + dense-only `retrieve()` | T001, T010, T003, T005, T006 | **İki duyuru: "şema hazır", "T006 hazır"** — G5 kapısı |
| G6 (Sal 11 Ağu) | LLM katmanı + üretim zinciri (mock retrieval'la) | T008, T009, T011, T012 | Üretim zinciri birim testli |
| G7 (Çar 12 Ağu) | FTS + hibrit + retrieval testleri | T004, T006(hibrit), T007 | Faz A kapanış kriteri (R5'in T002 paketi bu güne kadar hazır olmalı — bağımlılık) |
| G8 (Per 13 Ağu) | Chat migration + model + uç + testler | T017, T018, T019, T020 | Tarayıcıda kaynaklı cevap |
| G9 (Cum 14 Ağu) | Sokratik entegrasyonu (R2 sözleşmesiyle) | T027 | Kademeli mod uçtan uca |
| G10 (Pzt 17 Ağu) | Açık uç toplama, düzeltmeler | — | **Özellik dondurma** |
| G11-G12 (18-19 Ağu) | R5'in kalibrasyonuna (T043) destek; eşik config'ten güncellenir | — | Kalibre eşik |
| G13 (Per 20 Ağu) | Dockerfile + worker tetiği + deploy | T048, T049 | CI'da network'süz assertion |
| G14 (Cum 21 Ağu) | Prod doğrulama + canlı failover testi | T050 | Kanıtlar R5'e (T056) |
| G15 (Pzt 24 Ağu) | Demo provası, teslim | — | Teslim |

Toplam efor tahmini: **Faz A ~2 gün · Faz B ~1.5 gün · Faz C ~1.5 gün · T027 ~yarım
gün · T048-T050 ~2 gün.** R2 işlerin (ayrı brief) bu takvimin arasına giriyor — iki rolün
kesişme günlerinde (G6-G8) önceliği HER ZAMAN bloklayan işe ver: T006 ve T010 hazır
değilse R2 işine başlama.

---

## Önemli uyarılar

**T006 ve T010, iki ayrı hız sınırıdır — ikisini de öne al.** T010 bir öğleden sonra işi:
şemayı yazmak için tek satır gövde kodu gerekmez. G5 günü ilk iş olarak commit'le. T006
ise "mükemmel hibrit" beklemez: dense-only v0 servis, arayüzü sabitler ve herkesi serbest
bırakır; hibriti G7'de içine koyarsın, arayüz değişmez.

**course_id filtresi tartışılmaz.** Bu projede jüri karşısındaki en sert iddialardan biri
"dersler arası sızıntı: 0 vaka" (SC-001). RLS ikinci kattır, ilk kat senin `WHERE`
cümlendir. Kod incelemesinde ilk bakılacak şey bu satırdır; her PR'da kendin de grep'le.

**Evidence gate'i kimse için gevşetme.** Demo öncesi "eşik yüzünden cevap gelmiyor"
baskısı olacak. Doğru cevap eşiği düşürmek değil: (1) kalibrasyonu beklemek (T043),
(2) demo sorularını `answer_cache`'e koymak (T053). Gate'i kapatmak, projenin ana
iddiasını demo günü çöpe atmaktır.

**Failover "anahtar değiştiririz" değildir.** Jüriye gösterilecek davranış: Groq 429/500
verirken isteğin kod müdahalesi olmadan Gemini'den dönmesi ve logda `model_used` alanının
bunu söylemesi. T050'de bunu canlıda bilerek kıracaksın; log o günün kanıtıdır.

**`chat.py` senin, ama zincirin sırası senin değil.** Sıra ARCHITECTURE §5'te güvenlik
sınırı olarak sabitlenmiş: citation'dan önce leakage çağırmak, sanitize'ı atlamak,
cache'i retrieval'dan sonraya koymak — hepsi sırayı bozar ve testle yakalanır. Zinciri
kısaltma, adım ekleme; değişiklik ihtiyacı görürsen önce gruba yaz.

**Şema değişikliği bir duyuru işidir.** `AnswerResponse`'a alan eklemek/çıkarmak R2'nin
validator'ını ve R4'ün tiplerini kırar. T010 commit'lendikten sonra her şema değişikliği
önce gruba yazılır, sonra yapılır ve `openapi.json` aynı commit'te yeniden export edilir.

**Tarayıcıda görmeden "bitti" deme (Anayasa VIII).** T019 kapanmadan önce gerçek
tarayıcıda: giriş → ders → materyalde olan soru → kaynak kartında dosya adı + sayfa →
kapsam dışı soru → nazik ret. Test yeşili gerekli ama yeterli değil.

---

## Son söz

Bu projede herkesin işi bir yerde senin koduna dokunuyor: R2 senin retrieval kümenle
doğruluyor, R3 senin LLM servisinle soru üretiyor, R4 senin şemanı çiziyor, R5 senin
`retrieve()`'ini ölçüyor. Bu bir yük değil, kaldıraç: **iki dosyayı erken bitirdiğin an
dört kişi paralel çalışmaya başlıyor.**

Jüri "cevaplar gerçekten materyalden mi geliyor?" diye sorduğunda cevap; zorunlu
`course_id` filtresi, eşik altında kapanan bir gate ve sırası değişmeyen bir zincir
olacak. O üçünü sen yazıyorsun.

**Önce bloklayan iş. Filtre her sorguda. Şüphede kapan.**

Bittiğinde gruba yaz: "chat ucu canlıda, kaynak kartları gerçek metadata'dan geliyor,
failover kanıtı logda."

İyi çalışmalar.
