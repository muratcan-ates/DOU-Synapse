"""Pedagojik filtre — çözüm sızıntısı dedektörü (T014).

Neden var: CS50 üzerine yapılan çalışma, yapay zekâ destekli asistan
yanıtlarının önemli bir bölümünde öğrenciye doğrudan çalışan kod verildiğini
raporladı. Sokratik mod bir prompt temennisiyle korunamaz; model sıkıştığında
çözümü yazar. Bu yüzden çıktı, üretimden SONRA kural tabanlı olarak taranır.

Dürüstlük notu (Anayasa III): bu filtre iki farklı güce sahiptir ve ikisi
karıştırılmamalıdır.

* **Kalıp temelli sızıntı** — kod çiti, girintili kod bloğu, "cevap: X" kalıbı,
  sözde-kod anahtar sözcükleri — deterministik olarak yakalanır.
* **Kalıpsız sızıntı** — düzyazıyla anlatılmış tam çözüm — yalnızca MİTİGE
  edilir. Sözcük dizisi sonsuzdur; burada "garanti" sözcüğü kullanılamaz.
  Ölçüm test setinde yapılır ve sızıntı oranı raporlanır (SC-007).

Filtre hangi modlarda çalışır: ARCHITECTURE §5 adım 6 uyarınca Sokratik ve sınav
modunda. Soru-cevap modunda ders materyalindeki kodun gösterilmesi meşrudur —
orada öğrencinin ödevini çözmek değil, materyali açıklamak isteniyor.

Sınav modunda filtre yalnız daha sıkı değil, KURTARILAMAZ: ipucu tamamen
kapalıdır, dolayısıyla şablon ipucuna düşme yolu da yoktur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.contracts import (
    AnswerStatus,
    ChatMode,
    Citation,
    GeneratedAnswer,
    GuardrailVerdict,
    RetrievedChunk,
    SocraticStage,
)
from app.core import text_tr
from app.schemas.chat import snippet_of

#: Filtrenin uygulandığı modlar. Tek yerde durur ki "sınavda da geçerli miydi?"
#: sorusu her çağıranda yeniden cevaplanmasın (Anayasa XI).
ENFORCED_MODES = frozenset({ChatMode.SOCRATIC, ChatMode.EXAM})

#: Şablon ipucuna düşmenin mümkün OLMADIĞI modlar: sınavda ipucu yoktur.
NO_FALLBACK_MODES = frozenset({ChatMode.EXAM})

REASON_PREFIX = "leakage"

_TR_UPPER = str.maketrans("iı", "İI")


def _tr_variants(word: str) -> list[str]:
    """Bir sözcüğün küçük/Başlık/BÜYÜK ve AKSANSIZ yazımları.

    `re.IGNORECASE` Türkçede güvenilmez: 'İ'.lower() nokta birleştiricili iki
    kod noktasına çözülür ve 'i' ile eşleşmez. Varyantları açıkça üretmek,
    "Çözüm:" yazan bir sızıntının büyük harfli olduğu için kaçmasını engeller.

    Aksansız yazımlar 9 Ağustos'ta eklendi. Sebep ölçülebilir bir kaçış yoluydu:
    modeller Türkçe çıktıda diyakritikleri düşürebiliyor ve "Cozum: ..." yazan bir
    cevap, "Çözüm:" arayan desenden geçiyordu. Filtre modelin imlasına
    güvenemez — bir sızıntı, doğru yazılmadığı için sızıntı olmaktan çıkmaz.

    Katlama `core.text_tr` ile yapılır (Anayasa XI): kalıp listesi burada,
    Türkçe kuralları orada, tek yerde.
    """
    upper = word.translate(_TR_UPPER).upper()
    title = (word[0].translate(_TR_UPPER).upper() + word[1:]) if word else word
    forms = {word, title, upper}
    folded = text_tr.fold(word)
    if folded != word:
        # Dört ASCII yazım: hepsi gerçek model çıktısında görülebilir. Yalnız
        # `.title()` eklemek "Dogru sik" gibi cümle başı büyütmelerini kaçırırdı —
        # ve kaçan tek bir yazım, dedektörü olmayan bir dedektöre çevirir.
        sentence = folded[0].upper() + folded[1:] if folded else folded
        forms |= {folded, sentence, folded.title(), folded.upper()}
    return sorted(forms)


def _alt(*words: str) -> str:
    variants: list[str] = []
    for word in words:
        variants.extend(_tr_variants(word))
    return "(?:" + "|".join(sorted(set(variants), key=len, reverse=True)) + ")"


# ---------------------------------------------------------------------------
# Dedektörler
# ---------------------------------------------------------------------------

DETECTOR_CODE_FENCE = "code_fence"
DETECTOR_INDENTED_CODE = "indented_code"
DETECTOR_DIRECT_ANSWER = "direct_answer"
DETECTOR_ANSWER_KEY = "answer_key"
DETECTOR_PSEUDOCODE = "pseudocode"
DETECTOR_CODE_SIGNATURE = "code_signature"
DETECTOR_STEP_BY_STEP = "step_by_step_solution"

_FENCE = re.compile(r"(?:```|~~~)|<\s*(?:code|pre)\b", re.IGNORECASE)

_DIRECT_ANSWER = re.compile(
    _alt("cevap", "yanıt", "sonuç", "çözüm") + r"\s*[:=]\s*\S"
    r"|\b(?i:answer|result|solution)\s*[:=]\s*\S"
)

#: Cevap anahtarı kalıpları. `_DIRECT_ANSWER`'dan ayrı bir dedektör çünkü ayrı
#: bir sızıntı türü: "cevap: 42" bir sonuç verir, "doğru şık B" bir sınav
#: sorusunun anahtarını verir. Ölçümde ikisini ayırmak, hangi kalıbın kaç kez
#: tetiklendiğini raporlayabilmek demek (Anayasa III).
#:
#: Desenler bilerek DAR: yalnız iki nokta ya da tek harflik bir seçenek takip
#: ediyorsa tetiklenir. Geniş bir desen ("doğru cevap" geçen her cümle) meşru bir
#: yönlendirmeyi de ("doğru cevaba ulaşmak için önce...") bloklar, her turda
#: yeniden üretim tetikler ve öğrenciyi şablon ipucuna hapseder.
_ANSWER_KEY = re.compile(
    _alt("doğru cevap", "doğru şık", "doğru seçenek", "doğru yanıt")
    + r"\s*(?:[:=]\s*|\b(?:şu|su|şudur|sudur)?\s*)[\"'«]?[A-Ea-e]\b"
    r"|" + _alt("cevap anahtarı", "çözüm anahtarı", "yanıt anahtarı") + r"\b"
    r"|\b(?i:answer\s*key)\b"
    r"|\b(?i:the\s+(?:correct\s+)?answer\s+is)\b"
    r"|\b(?i:correct\s+option\s+is)\b"
)

_PSEUDOCODE_PATTERNS = (
    re.compile(r"(?m)^\s*(?:BEGIN|END|ALGORITHM|PROCEDURE|FUNCTION|INPUT|OUTPUT)\b"),
    re.compile(r"(?m)^\s*" + _alt("algoritma", "girdi", "çıktı", "başla", "bitir") + r"\s*[:.]"),
    re.compile(r"(?i)\b(?:for|foreach|while)\b[^\n]{0,80}\bdo\b"),
    re.compile(r"(?i)\bif\b[^\n]{0,80}\bthen\b"),
    re.compile(r"(?im)^\s*end\s?(?:if|for|while|function|procedure)\b"),
    re.compile(r"←|(?<![-<])<-(?![->])"),
)

#: Kod imzaları. Tek satırlık, çitsiz kod da sızıntıdır: "return n * 2;" yazmak
#: ile bunu üç tırnak arasına almak arasında öğrenci açısından fark yoktur.
_CODE_SIGNATURE_PATTERNS = (
    re.compile(r"\bdef\s+\w+\s*\("),
    re.compile(r"\bclass\s+\w+\s*[:({]"),
    re.compile(r"\b(?:public|private|protected)\s+(?:static\s+)?\w+\s+\w+\s*\("),
    re.compile(r"\bfunction\s+\w+\s*\("),
    re.compile(r"#include\s*[<\"]"),
    re.compile(r"\b(?:printf|scanf|malloc)\s*\("),
    re.compile(r"\bSystem\s*\.\s*out\s*\.\s*print"),
    re.compile(r"\bconsole\s*\.\s*log\s*\("),
    re.compile(r"\bprint\s*\(\s*[\"']"),
    re.compile(r"\breturn\b[^\n;]{0,60};"),
    re.compile(r"\bint\s+main\s*\("),
    re.compile(r"\bfor\s*\([^\n)]*;[^\n)]*;"),
    re.compile(r"(?i)\bSELECT\b[^\n]{0,120}\bFROM\b"),
    re.compile(r"^\s*(?:import|from)\s+\w+", re.MULTILINE),
)

_INDENTED_LINE = re.compile(r"^(?: {4,}|\t+)\S")
#: Girintili satırın gerçekten kod olduğunu gösteren işaretler. Girinti tek
#: başına yetmez: alıntılanmış bir paragraf da girintili olabilir.
_CODE_TOKEN = re.compile(r"[{};=()\[\]]|(?:^|\s)(?:if|for|while|return|else|elif)\b")

_STEP_MARKER = re.compile(
    r"(?m)^\s*(?:\d+\s*[.)]\s+|" + _alt("adım", "aşama") + r"\s*\d+|(?i:step)\s*\d+)"
)
_SEQUENCE_WORDS = re.compile(
    _alt("önce", "sonra", "ardından", "daha sonra", "son olarak", "en son", "ilk olarak")
)
#: Kaç işaret bir "adım adım çözüm" sayılır. İki adım bir liste, üç adım bir
#: prosedürdür; sınırın bir yerde olması gerekiyordu ve gerekçesi budur.
_STEP_THRESHOLD = 3


@dataclass(frozen=True, slots=True)
class LeakageFinding:
    """Tek bulgu: hangi dedektör, metnin neresinde.

    Alıntı taşınıyor çünkü ölçüm için "sızıntı vardı" yetmez; hangi kalıbın kaç
    kez tetiklendiği raporlanabilir olmalı (Anayasa III).
    """

    detector: str
    excerpt: str


def _excerpt(text: str, start: int, end: int, width: int = 60) -> str:
    lo = max(0, start - width // 3)
    hi = min(len(text), end + width)
    return " ".join(text[lo:hi].split())


def _indented_code_finding(text: str) -> LeakageFinding | None:
    """Çitsiz ama girintili kod bloğu: ardışık en az iki girintili kod satırı."""
    run: list[str] = []
    for line in text.splitlines():
        if _INDENTED_LINE.match(line):
            run.append(line)
            if len(run) >= 2 and any(_CODE_TOKEN.search(candidate) for candidate in run):
                return LeakageFinding(
                    detector=DETECTOR_INDENTED_CODE,
                    excerpt=" ".join(" ".join(run).split())[:120],
                )
        else:
            run = []
    return None


def detect(text: str) -> list[LeakageFinding]:
    """Metindeki tüm sızıntı bulgularını döndürür. Saf fonksiyon — LLM çağırmaz."""
    findings: list[LeakageFinding] = []

    if match := _FENCE.search(text):
        findings.append(
            LeakageFinding(DETECTOR_CODE_FENCE, _excerpt(text, match.start(), match.end()))
        )

    if indented := _indented_code_finding(text):
        findings.append(indented)

    if match := _DIRECT_ANSWER.search(text):
        findings.append(
            LeakageFinding(DETECTOR_DIRECT_ANSWER, _excerpt(text, match.start(), match.end()))
        )

    if match := _ANSWER_KEY.search(text):
        findings.append(
            LeakageFinding(DETECTOR_ANSWER_KEY, _excerpt(text, match.start(), match.end()))
        )

    for pattern in _PSEUDOCODE_PATTERNS:
        if match := pattern.search(text):
            findings.append(
                LeakageFinding(DETECTOR_PSEUDOCODE, _excerpt(text, match.start(), match.end()))
            )
            break

    for pattern in _CODE_SIGNATURE_PATTERNS:
        if match := pattern.search(text):
            findings.append(
                LeakageFinding(DETECTOR_CODE_SIGNATURE, _excerpt(text, match.start(), match.end()))
            )
            break

    steps = len(_STEP_MARKER.findall(text))
    if steps < _STEP_THRESHOLD:
        steps = len(_SEQUENCE_WORDS.findall(text))
    if steps >= _STEP_THRESHOLD:
        findings.append(LeakageFinding(DETECTOR_STEP_BY_STEP, f"{steps} adım işareti"))

    return findings


class LeakageGuardrail:
    """`Guardrail` protokolünü uygular. Zincirin ikinci halkası."""

    def __init__(self, *, enforced_modes: frozenset[ChatMode] = ENFORCED_MODES) -> None:
        self._enforced_modes = enforced_modes

    def check(self, answer: GeneratedAnswer, retrieved: list[RetrievedChunk]) -> GuardrailVerdict:
        del retrieved  # bu halka yalnız metne bakar; imza protokol gereği ortaktır
        if answer.mode not in self._enforced_modes:
            return GuardrailVerdict(blocked=False)

        findings = detect(answer.text)
        if not findings:
            return GuardrailVerdict(blocked=False)

        detectors = ",".join(sorted({finding.detector for finding in findings}))
        return GuardrailVerdict(blocked=True, reason=f"{REASON_PREFIX}:{detectors}")


def build_template_hint(
    chunks: list[RetrievedChunk],
    *,
    socratic_stage: SocraticStage | None = None,
) -> GeneratedAnswer | None:
    """Deterministik son durak: model ısrarla sızdırdığında gösterilen ipucu.

    Kaynaksız değildir — en iyi sıradaki chunk'a atıf yapar, çünkü "her yanıtta
    kaynak" kuralı şablon ipuçlarını da kapsar (Anayasa I). Metin sabittir: model
    devrede olmadığı için burada sızıntı riski de yoktur.

    Kaynak yoksa `None` döner; çağıran o durumda cevabı hiç göstermez (Anayasa IV).
    """
    if not chunks:
        return None
    lead = chunks[0]
    text = (
        f"Bu soruyu doğrudan çözmek yerine kaynağa dönelim. "
        f"{lead.file_name} dosyasının {lead.location} bölümündeki tanımı oku ve "
        "kendi cümlelerinle yazmayı dene. Nerede takıldığını yazarsan oradan devam edelim."
    )
    return GeneratedAnswer(
        status=AnswerStatus.ANSWERED,
        mode=ChatMode.SOCRATIC,
        text=text,
        citations=[
            Citation(
                chunk_id=lead.chunk_id,
                file_name=lead.file_name,
                location=lead.location,
                quote=snippet_of(lead),
            )
        ],
        socratic_stage=socratic_stage,
        provider="template",
        model="template/socratic-fallback",
    )
