"""Sokratik merdiven — saf state machine (T026).

Bu modül **veritabanı bilmez ve LLM çağırmaz.** İçinde yalnız "öğrenci ne yaptı,
kademe ilerler mi, ilerlemezse ne denir" kararı vardır. Kalıcılık `app/api/chat.py`'nin
işidir. Ayrım bilinçlidir: merdivenin kuralları prompt'a veya modele bırakılırsa
"öğrenci denemeden ilerlemez" bir temenni olur; burada zorlanınca bir garanti olur
(FR-014, ARCHITECTURE §5).

Merdiven (`contracts.SocraticStage`):

    DIAGNOSE → NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE

## Karar: "öğrenci denemesi" ne sayılır?

Bu bir tasarım kararıdır ve gerekçesiyle birlikte burada duruyor; jüri soracaktır.

Dört sınıf ayırt ediliyor (`AttemptKind`):

* **SUBSTANTIVE** — anlamlı, içerik taşıyan bir metin. Kademe **ilerler.** Doğru olması
  gerekmez: Sokratik yöntemin çalıştığı yer zaten yanlış denemedir.
* **UNSURE** — "bilmiyorum", "fikrim yok", tek harflik bir şey. Kademe **yalnız
  DIAGNOSE'da** ilerler, sonrasında ilerlemez.
* **ANSWER_DEMAND** — "sadece söyle", "cevabı ver". Kademe **ilerlemez**, nazikçe
  reddedilir.
* **EMPTY** — boş mesaj. Kademe ilerlemez.

**UNSURE neden yalnız DIAGNOSE'da ilerletir?** DIAGNOSE'un sorusu "bu konuda ne
biliyorsun"dur; "hiçbir şey" bu sorunun geçerli ve bilgi taşıyan cevabıdır — sistem
öğrencinin nereden başlayacağını öğrenmiş olur. NUDGE'dan sonra ise sistem zaten bir
yön vermiştir; orada "bilmiyorum"u ilerleme saymak merdiveni beş mesajlık bir geri
sayıma çevirir ve öğrenci hiç düşünmeden kaynaklı açıklamaya ulaşır. FR-014'ün
yasakladığı davranış tam olarak budur.

**Yanlış cevap neden ilerletir?** Çünkü alternatifi, sistemin doğruluğu yargılaması ve
yanlış öğrenciyi aynı kademede kilitlemesidir; bu hem yanlış pozitiflerde öğrenciyi
cezalandırır hem de "cevabı zaten biliyorsan ilerle" gibi ters bir teşvik kurar.
Merdiven ilerlemeyi *çabaya* bağlar, *isabete* değil.

## Kalıcılık

`SocraticState` jsonb'a serileşir (`chat_sessions.state`). `from_json` bozuk veya eksik
veriye karşı dayanıklıdır: tanınmayan kademe DIAGNOSE'a düşer. Fail-closed — şüphede
merdivenin başına dönülür, sonuna değil.

## Şablon ipuçları

`template_hint()` deterministik son duraktır (FR-015): üretim filtreden geçemediğinde
kullanıcıya bu metin gider. Şablonlar **chunk metnini asla alıntılamaz**, yalnız dosya
adı + konum işaret eder. Sebep: kaynak parçanın kendisi çözümü içeriyor olabilir;
alıntılayan bir "güvenli son durak" güvenli olmaz. Kaynak yine de taşınır (`chunk_id`),
böylece kaynaksız ipucu yasağı (FR-013, FR-016) şablonlarda da sağlanır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.contracts import Citation, RetrievedChunk, SocraticStage
from app.core import text_tr

# Merdivenin sırası. `contracts.SocraticStage` tanımlıdır ama Python enum'ında sıra
# anlamlı bir API değildir; ilerleme mantığı bu listeye dayanır.
STAGE_ORDER: tuple[SocraticStage, ...] = (
    SocraticStage.DIAGNOSE,
    SocraticStage.NUDGE,
    SocraticStage.CONCEPT_HINT,
    SocraticStage.SIMILAR_EXAMPLE,
    SocraticStage.EXPLAIN_WITH_SOURCE,
)

#: En yüksek kademe indeksi. `config.socratic_max_stage` ile aynı olmalıdır (4);
#: mastery ipucu çarpanları o indekse göre hesaplanır. Bu modül config'e bağımlı
#: değildir — bağımlı olsaydı saf state machine testleri ayar yüklemek zorunda kalırdı.
MAX_STAGE_INDEX = len(STAGE_ORDER) - 1

#: Deneme sayılması için, dolgu ifadeler ayıklandıktan sonra kalması gereken en az
#: karakter. "deadlock" (tek kelime) geçer; "hı", "?", "..." geçmez.
MIN_ATTEMPT_CHARS = 3

#: `chat_sessions.state` sınırsız büyümesin diye saklanan son geçiş sayısı. Denetim
#: için son N geçiş yeterlidir; tam geçmiş `chat_messages.socratic_stage`'de zaten var.
MAX_TRANSITIONS_KEPT = 50


class AttemptKind(StrEnum):
    """Öğrenci mesajının pedagojik sınıfı."""

    SUBSTANTIVE = "substantive"
    UNSURE = "unsure"
    ANSWER_DEMAND = "answer_demand"
    EMPTY = "empty"


# ---------------------------------------------------------------------------
# Metin normalizasyonu
# ---------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Eşleştirme için metni tek biçime indirger (kullanıcıya dönen metinde KULLANILMAZ).

    Gövde 9 Ağustos'ta `app/core/text_tr.py`'ye taşındı: aynı Türkçe katlama üçüncü
    kez yazılmak üzereydi (burası, `question_gen.normalize_tr`, ve yeni kapsam
    sinyali) — Anayasa XI. Ad burada kalıyor çünkü bu modülün kalıpları ASCII'ye
    indirgenmiş metne göre yazılmış ve okurun kalıpları anlamak için başka dosyaya
    gitmesi gerekmiyor.
    """
    return text_tr.fold(text)


# "Sadece söyle" ailesi. Öğrenci ısrar ettiğinde kademe ilerlemez; bu kalıplar o
# ısrarı tanır. Liste tam değildir ve olamaz — tanınmayan bir ısrar SUBSTANTIVE'e
# düşer, yani merdiven bir kademe ilerler ama cevap yine de doğrudan verilmez
# (kademe metnini guardrail zinciri denetler). Fail-open değil, kademeli.
_ANSWER_DEMAND_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"\bsadece\s+(soyle|yaz|ver|cevap)",
        r"\bcevab\w*\s+(ver|soyle|yaz)\b",
        r"\bcevap\s+(ver|yaz)\b",
        r"\bcozum\w*\s+(ver|yaz|soyle|goster)\b",
        r"\bdirek(t)?\s+(cevap|soyle|ver|yaz)",
        r"\bbana\s+(cevab|cozum|sonuc)",
        r"\bipucu\s+(istemiyorum|gerek\w*\s+yok)",
        r"\bugrasmak\s+istemiyorum\b",
        r"\bsoyle\s+gitsin\b",
        r"\bjust\s+tell\s+me\b",
        r"\bgive\s+me\s+the\s+answer\b",
    )
)

# "Bilmiyorum" ailesi. Mesajdan çıkarıldığında geriye anlamlı metin kalmıyorsa mesaj
# UNSURE'dur; kalıyorsa ("bilmiyorum ama sanırım dört koşul var") SUBSTANTIVE'dir —
# öğrenci tereddüdünü belirtip yine de denemiştir.
_UNSURE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"\bhic\s*bir\s+fikrim\s+yok\b",
        r"\bfikrim\s+yok\b",
        r"\bbilmiyorum\b",
        r"\bbilmiyom\b",
        r"\bbilmem\b",
        r"\bemin\s+degilim\b",
        r"\bno\s+idea\b",
        r"\bi\s+don'?t\s+know\b",
        r"\bpas\b",
    )
)

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def classify_attempt(message: str) -> AttemptKind:
    """Öğrenci mesajını pedagojik olarak sınıflar. Modül docstring'indeki karar."""
    if not message.strip():
        return AttemptKind.EMPTY

    normalized = normalize(message)
    if any(pattern.search(normalized) for pattern in _ANSWER_DEMAND_PATTERNS):
        return AttemptKind.ANSWER_DEMAND

    residual = normalized
    for pattern in _UNSURE_PATTERNS:
        residual = pattern.sub(" ", residual)
    residual = _PUNCTUATION.sub(" ", residual)
    residual = " ".join(residual.split())

    if len(residual) < MIN_ATTEMPT_CHARS:
        return AttemptKind.UNSURE
    return AttemptKind.SUBSTANTIVE


# ---------------------------------------------------------------------------
# Durum
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StageTransition:
    """Tek kademe geçişi — denetim kaydı.

    "Sistem gerçekten yönlendirdi mi, yoksa cevabı mı verdi?" sorusuna sonradan cevap
    verebilmek için her geçiş kayda alınır (FR-014: "her kademe kayıt altına alınır").
    """

    from_stage: SocraticStage
    to_stage: SocraticStage
    attempt_kind: AttemptKind
    occurred_at: datetime | None = None

    def to_json(self) -> dict[str, str]:
        payload = {
            "from": self.from_stage.value,
            "to": self.to_stage.value,
            "attempt": self.attempt_kind.value,
        }
        if self.occurred_at is not None:
            payload["at"] = self.occurred_at.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class SocraticState:
    """Bir sohbet oturumunun Sokratik durumu. `chat_sessions.state` içinde yaşar."""

    stage: SocraticStage = SocraticStage.DIAGNOSE
    #: Kabul edilmiş deneme sayısı (UNSURE dahil değil).
    attempts: int = 0
    #: "Sadece söyle" ısrarı sayısı. Israrcı öğrenci senaryosunun ölçüsü.
    refusals: int = 0
    transitions: tuple[StageTransition, ...] = ()

    @property
    def stage_index(self) -> int:
        return STAGE_ORDER.index(self.stage)

    @property
    def is_final_stage(self) -> bool:
        return self.stage is SocraticStage.EXPLAIN_WITH_SOURCE

    def to_json(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "attempts": self.attempts,
            "refusals": self.refusals,
            "transitions": [t.to_json() for t in self.transitions],
        }

    @classmethod
    def from_json(cls, raw: Any) -> SocraticState:
        """Kalıcı durumu geri okur. Bozuk veriye karşı fail-closed: merdivenin başı.

        Kademe tanınmıyorsa DIAGNOSE'a düşülür — sona değil. Bozuk bir jsonb yüzünden
        öğrencinin doğrudan kaynaklı açıklamaya atlaması, bozuk veri yüzünden bir kademe
        geri gitmesinden çok daha kötüdür.
        """
        if not isinstance(raw, dict):
            return cls()

        try:
            stage = SocraticStage(raw.get("stage", ""))
        except ValueError:
            stage = SocraticStage.DIAGNOSE

        return cls(
            stage=stage,
            attempts=_non_negative_int(raw.get("attempts")),
            refusals=_non_negative_int(raw.get("refusals")),
            transitions=tuple(_transitions_from_json(raw.get("transitions"))),
        )


def _non_negative_int(value: Any) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _transitions_from_json(raw: Any) -> list[StageTransition]:
    if not isinstance(raw, list):
        return []
    parsed: list[StageTransition] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            transition = StageTransition(
                from_stage=SocraticStage(item["from"]),
                to_stage=SocraticStage(item["to"]),
                attempt_kind=AttemptKind(item["attempt"]),
                occurred_at=_datetime_from_json(item.get("at")),
            )
        except (KeyError, ValueError, TypeError):
            continue  # Tek bozuk kayıt tüm geçmişi düşürmez.
        parsed.append(transition)
    return parsed


def _datetime_from_json(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Karar
# ---------------------------------------------------------------------------

# Kullanıcıya dönen metinler Türkçedir ve backend'de üretilir (Anayasa V): frontend
# kendi metnini uydurmaz, model de bu metinleri yazmaz — reddin sözü bize aittir.
_REFUSAL_ANSWER_DEMAND = (
    "Cevabı doğrudan veremem; bu modun amacı çözümü birlikte kurmak. "
    "Aklına gelen ilk adımı ya da bir tahminini yazar mısın? "
    "En küçük deneme bile bir sonraki ipucunu açar."
)
_REFUSAL_EMPTY = (
    "Devam edebilmem için senden bir şey duymam gerekiyor. "
    "Soruyla ilgili aklına gelen ilk cümleyi yazman yeter."
)
_REFUSAL_UNSURE = (
    "İlk adımda «bilmiyorum» yeterliydi, şimdi bir tahmin istiyorum. "
    "Yanlış olması sorun değil; nereden başlayacağını görmem için gerekli."
)


@dataclass(frozen=True, slots=True)
class SocraticDecision:
    """`advance()` çıktısı: bu turda ne servis edilecek ve yeni durum ne."""

    state: SocraticState
    #: Bu turda üretilecek ipucunun kademesi.
    stage: SocraticStage
    attempt_kind: AttemptKind
    advanced: bool
    #: Deneme kabul edilmediyse kullanıcıya gösterilecek nazik Türkçe uyarı.
    refusal_notice: str | None = None
    transition: StageTransition | None = None


def advance(
    state: SocraticState | None,
    message: str,
    *,
    occurred_at: datetime | None = None,
) -> SocraticDecision:
    """Öğrenci mesajını değerlendirip kademeyi ilerletir ya da yerinde tutar.

    `state is None` ilk turu ifade eder: o mesaj sorunun kendisidir, bir deneme değil.
    Bu yüzden ilk tur DIAGNOSE'da başlar ve ilerlemez — "ilk turda cevap verilmez"
    kuralı buradan gelir.
    """
    if state is None:
        return SocraticDecision(
            state=SocraticState(),
            stage=SocraticStage.DIAGNOSE,
            attempt_kind=AttemptKind.EMPTY,
            advanced=False,
        )

    kind = classify_attempt(message)

    if kind is AttemptKind.EMPTY:
        return _stay(state, kind, _REFUSAL_EMPTY)
    if kind is AttemptKind.ANSWER_DEMAND:
        return _stay(replace(state, refusals=state.refusals + 1), kind, _REFUSAL_ANSWER_DEMAND)
    if kind is AttemptKind.UNSURE and state.stage is not SocraticStage.DIAGNOSE:
        return _stay(state, kind, _REFUSAL_UNSURE)

    # Buraya gelen her mesaj bir denemedir: SUBSTANTIVE, ya da DIAGNOSE'daki UNSURE.
    attempts = state.attempts + 1
    if state.is_final_stage:
        # Son kademede kalınır; merdiven bitmiştir, deneme sayacı işlemeye devam eder.
        return SocraticDecision(
            state=replace(state, attempts=attempts),
            stage=state.stage,
            attempt_kind=kind,
            advanced=False,
        )

    next_stage = STAGE_ORDER[state.stage_index + 1]
    transition = StageTransition(
        from_stage=state.stage,
        to_stage=next_stage,
        attempt_kind=kind,
        occurred_at=occurred_at,
    )
    new_state = replace(
        state,
        stage=next_stage,
        attempts=attempts,
        transitions=(*state.transitions, transition)[-MAX_TRANSITIONS_KEPT:],
    )
    return SocraticDecision(
        state=new_state,
        stage=next_stage,
        attempt_kind=kind,
        advanced=True,
        transition=transition,
    )


def _stay(state: SocraticState, kind: AttemptKind, notice: str) -> SocraticDecision:
    return SocraticDecision(
        state=state,
        stage=state.stage,
        attempt_kind=kind,
        advanced=False,
        refusal_notice=notice,
    )


# ---------------------------------------------------------------------------
# Şablon ipuçları — deterministik son durak
# ---------------------------------------------------------------------------

# Kademeye göre sabit metin. `{kaynak}` dosya adı + konum, `{konu}` bölüm başlığıdır;
# ikisi de chunk METADATA'sından gelir, model metninden değil (Anayasa I). Chunk'ın
# kendi metni bilinçli olarak ALINTILANMAZ — kaynak parça çözümü içerebilir.
_TEMPLATES: dict[SocraticStage, str] = {
    SocraticStage.DIAGNOSE: (
        "Başlamadan önce nerede olduğunu görelim. Kaynak: {kaynak}. "
        "Sorunun hangi kavramı sorduğunu kendi cümlelerinle yazar mısın?"
    ),
    SocraticStage.NUDGE: (
        "Doğru yöndesin. {kaynak} bölümünü aç ve oradaki koşulları soruyla karşılaştır. "
        "Hangisinin sağlanmadığını düşünüyorsun? Bir cümlelik tahminin yeter."
    ),
    SocraticStage.CONCEPT_HINT: (
        "Bu soru {konu} kavramına dayanıyor; kaynağı {kaynak}. "
        "Tanımı oradan okuyup sorudaki duruma nasıl uyduğunu anlatır mısın?"
    ),
    SocraticStage.SIMILAR_EXAMPLE: (
        "{kaynak} bölümünde aynı yapıda çözülmüş bir örnek var. "
        "Önce o örneğin adımlarını izle, sonra aynı adımları kendi sorunda dene ve "
        "hangi adımda takıldığını yaz."
    ),
    SocraticStage.EXPLAIN_WITH_SOURCE: (
        "Bu aşamada kaynağa doğrudan bakmanın sırası: {kaynak}. "
        "Oradaki açıklamayı okuduktan sonra çözümünü kendi cümlelerinle yaz; "
        "takıldığın adımı birlikte gözden geçirelim."
    ),
}


def template_hint(stage: SocraticStage, chunk: RetrievedChunk) -> tuple[str, Citation]:
    """Kademeye uygun, kaynaklı ve deterministik ipucu.

    Üretim pedagojik filtreden geçemediğinde (FR-015) kullanıcıya bu gider. Metin
    chunk'tan alıntı YAPMAZ; yalnız dosya adı ve konum işaret eder, bu yüzden
    kod/çözüm sızdırması yapısal olarak imkânsızdır.
    """
    kaynak = f"{chunk.file_name} — {chunk.location}"
    text = _TEMPLATES[stage].format(kaynak=kaynak, konu=chunk.section_title or "ilgili")
    return text, hint_citation(chunk)


def hint_citation(chunk: RetrievedChunk) -> Citation:
    """İpucu için atıf.

    `quote` alanına chunk METNİ konmaz, bölüm başlığı veya konum konur. Sokratik modda
    kaynak bir "oku" işaretidir, gösterilecek içerik değil; parçanın kendisi çözümü
    içeriyorsa atıf kutusundan sızardı.
    """
    return Citation(
        chunk_id=chunk.chunk_id,
        file_name=chunk.file_name,
        location=chunk.location,
        quote=chunk.section_title or chunk.location,
    )
