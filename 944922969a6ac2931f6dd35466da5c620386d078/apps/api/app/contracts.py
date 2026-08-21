"""Modüller arası sözleşmeler — paralel geliştirmenin taşıyıcı kirişi.

Bu dosya niye var: retrieval, generation, guardrail ve ölçme modülleri ayrı
oturumlarda paralel yazılıyor. Her biri diğerinin *imzasına* karşı kod yazabilsin
diye tipler burada, gövdelerden ÖNCE sabitlendi. Bir modül henüz yazılmamışken
bile onu çağıran kod derlenebilir ve test edilebilir.

Kural: **bu dosyayı yalnız takım lideri değiştirir.** Bir alan eklemek gerekiyorsa
gruba yazılır; tek taraflı değişiklik, ona karşı yazılmış üç modülü aynı anda kırar.

Tasarım notu: burada iş mantığı YOKTUR. Yalnız veri şekli ve protokol. Böylece
bu dosya hiçbir modüle bağımlı değildir ve döngüsel import doğuramaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

# ---------------------------------------------------------------------------
# Retrieval (Faz A)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Aramadan dönen tek parça.

    `page_number`/`slide_number` atıfın HAM MADDESİDİR: cevaptaki kaynak
    referansı model metninden değil buradan üretilir (Anayasa I). Bu yüzden
    alanlar opsiyonel olsa da ikisinin birden boş olması bir veri hatasıdır.
    """

    chunk_id: UUID
    document_id: UUID
    file_name: str
    page_number: int | None
    slide_number: int | None
    section_title: str | None
    text: str
    # Skorlar açıklanabilirlik için ayrı taşınır: bir parçanın neden geldiğini
    # (anlamsal mı, kelime eşleşmesi mi) söyleyemezsek eşik kalibrasyonu körleşir.
    #
    # KANIT EŞİĞİ `dense_score`'a UYGULANIR — `fused_score`'a değil.
    # RRF skoru sıralamadan üretilir ve üst sınırı ~0.033'tür; alakadan bağımsız
    # olarak küçüktür, yani 0.35 gibi bir eşikle KARŞILAŞTIRILAMAZ ve her soru
    # reddedilir. `ts_rank` de mutlak ölçekli değildir. Hattaki tek mutlak ölçekli
    # sayı `dense_score`'dur. Şerit 1 ve Şerit 3 bu tuzağa ayrı ayrı düştü;
    # kural buraya yazıldı ki üçüncü kez düşülmesin.
    dense_score: float = 0.0
    fts_score: float = 0.0
    fused_score: float = 0.0

    @property
    def location(self) -> str:
        """Kullanıcıya gösterilecek konum: 'Sayfa 7' | 'Slayt 3' | bölüm adı."""
        if self.page_number is not None:
            return f"Sayfa {self.page_number}"
        if self.slide_number is not None:
            return f"Slayt {self.slide_number}"
        return self.section_title or "Konum yok"


class Retriever(Protocol):
    """Faz A'nın dışarı verdiği tek yüzey.

    `course_id` bir yetki belgesi DEĞİLDİR; çağıran taraf üyeliği zaten
    doğrulamıştır (deps.py). Buradaki görevi yalnız arama alanını daraltmaktır —
    ama RLS de aynı oturumda devrededir, yani iki katman birden çalışır.
    """

    async def search(
        self, *, course_id: UUID, query: str, limit: int = 8
    ) -> list[RetrievedChunk]: ...


# ---------------------------------------------------------------------------
# Generation (Faz B)
# ---------------------------------------------------------------------------


class AnswerStatus(StrEnum):
    """Cevabın dört meşru sonucu. Üçü 'cevap yok' ama SEBEPLERİ farklı.

    Karıştırılmamalı: `insufficient_context` "materyalde var olabilir ama kanıt
    zayıf", `out_of_scope` "bu ders bu konuyu hiç kapsamıyor". Kullanıcıya
    verilen metin de ölçüm kategorisi de farklıdır (SC-005 yalnız ikincisini ölçer).
    """

    ANSWERED = "answered"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    OUT_OF_SCOPE = "out_of_scope"
    BUDGET_EXHAUSTED = "budget_exhausted"


class ChatMode(StrEnum):
    QA = "qa"
    SOCRATIC = "socratic"
    EXAM = "exam"


class SocraticStage(StrEnum):
    """Sokratik merdiven. Sıra ANLAMLIDIR ve atlanamaz (spec FR-014).

    Öğrenci kendi denemesini yapmadan bir sonraki kademeye geçilmez; bu kural
    state machine'de zorlanır, prompt'a bırakılmaz.
    """

    DIAGNOSE = "diagnose"
    NUDGE = "nudge"
    CONCEPT_HINT = "concept_hint"
    SIMILAR_EXAMPLE = "similar_example"
    EXPLAIN_WITH_SOURCE = "explain_with_source"


@dataclass(frozen=True, slots=True)
class Citation:
    """Tek atıf. `chunk_id` doğrulanabilir olmak zorundadır.

    Guardrail bu kimliği retrieve edilen kümeye karşı sınar; kümede yoksa atıf
    düşer. Model uydursa bile geçemez — kontrol deterministiktir, modele sorulmaz.
    """

    chunk_id: UUID
    file_name: str
    location: str
    quote: str

    # KARAR (9 Ağu): ARCHITECTURE §5'teki `claim` alanı buraya EKLENMEDİ.
    # Bu dosya guardrail zincirinin sözleşmesidir; `claim` ise sunum verisidir ve
    # hiçbir guardrail kararı ona bakmaz. Zarf katmanında (`schemas/chat.py`)
    # taşınır. Buraya konsaydı, hiçbir kontrolün okumadığı bir alanı üç modül
    # birden doldurmak zorunda kalırdı. Tartışma yeniden açılmasın.


@dataclass(slots=True)
class GeneratedAnswer:
    """Üretim katmanının çıktısı — guardrail zincirine GİRMEDEN önceki hâli.

    Bu nesne kullanıcıya doğrudan gitmez. Zincir sırası ARCHITECTURE §5'te
    sabittir: generation → citation → leakage → sanitize.
    """

    status: AnswerStatus
    mode: ChatMode
    text: str
    citations: list[Citation] = field(default_factory=list)
    socratic_stage: SocraticStage | None = None
    #: Sağlayıcı adı ve model — hangi cevabın neyle üretildiği raporlanabilmeli.
    provider: str | None = None
    model: str | None = None
    #: Sağlayıcının ölçtüğü kullanım. Retry ve guardrail yeniden üretimleri toplanır.
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Generator(Protocol):
    """Faz B'nin dışarı verdiği tek yüzey."""

    async def generate(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        mode: ChatMode,
        socratic_stage: SocraticStage | None = None,
        #: Öğrencinin bu turdaki denemesi (Sokratik mod). İpucu buna göre şekillenir:
        #: neyi yanlış anladığını görmeden verilen ipucu yönlendirme değil, tahmindir.
        #: Sözleşmeye 9 Ağustos'ta eklendi — Şerit 2'nin gerçek servisinde zaten
        #: vardı, Şerit 3 ise yokluğunda ipucunu kişiselleştiremiyordu.
        student_attempt: str | None = None,
    ) -> GeneratedAnswer: ...


class ClaimedAnswer(Protocol):
    """`ClaimingGenerator`'ın döndürdüğü şekil: cevap + chunk başına iddia metni.

    Yapısal tiptir, taşıyıcı sınıf değil: üretim servisi kendi `GenerationResult`
    dataclass'ını döndürmeye devam eder, buraya bir bağımlılık eklemez.
    """

    answer: GeneratedAnswer
    claims: dict[UUID, str]


@runtime_checkable
class ClaimingGenerator(Protocol):
    """`Generator`'ın isteğe bağlı uzantısı: atıfın hangi iddiayı desteklediği.

    Ayrı bir protokol olmasının sebebi, `Generator`'ı bozmamak. `claim` sunum
    verisidir ve hiçbir guardrail kararı ona bakmaz (bkz. `Citation` notu), yani
    onu üretmek zorunlu bir yükümlülük olmamalı — sahte üreteçler ve test
    ikizleri `Generator`'ı uygulamaya devam eder.

    Buna karşılık üreten bir uygulama varsa çağıran bunu KULLANMALIDIR: aksi
    hâlde istemci zarfında hiçbir zaman dolmayan bir alan kalır ve arayüz onu
    boş yere çizer (Anayasa XI — iş yapmayan yüzey kusurdur).
    """

    async def generate_with_claims(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        mode: ChatMode,
        socratic_stage: SocraticStage | None = None,
        student_attempt: str | None = None,
    ) -> ClaimedAnswer: ...


# ---------------------------------------------------------------------------
# Guardrails (Faz B)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GuardrailVerdict:
    """Zincirin kararı. `blocked` ise cevap KULLANICIYA GİTMEZ.

    `dropped_citations` boş bırakılmaz: hangi atıfın neden düştüğü ölçülebilir
    olmalı, yoksa "model atıf uydurmuyor" iddiası kanıtsız kalır (Anayasa III).
    """

    blocked: bool
    reason: str | None = None
    dropped_citations: list[UUID] = field(default_factory=list)
    #: Filtre metni değiştirdiyse temizlenmiş hâli; değiştirmediyse None.
    sanitized_text: str | None = None


class Guardrail(Protocol):
    """Zincirdeki her halka bu yüzeyi uygular; sıra çağıranda sabittir."""

    def check(
        self, answer: GeneratedAnswer, retrieved: list[RetrievedChunk]
    ) -> GuardrailVerdict: ...


# ---------------------------------------------------------------------------
# Ölçme (Faz D)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GradedAnswer:
    """Bir cevabın değerlendirme sonucu.

    `score` 0-100'dür ve mastery servisi onu 0-1'e normalize eder — iki ayrı
    ölçek bilinçlidir: puan kullanıcıya yüzde olarak, mastery içeride oran olarak
    anlamlıdır.
    """

    score: int
    is_correct: bool | None
    missing_points: list[str] = field(default_factory=list)
    #: "Neden yanlış": çeldiricinin çeliştiği kaynak parça.
    evidence_chunk_id: UUID | None = None
