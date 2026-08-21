"""Deterministik sahte LLM sağlayıcısı.

Bu bir "stub" değildir ve üç somut işi vardır:

1. **CI.** Test ortamında ağ ve API anahtarı yoktur. Ağa çıkan bir testin kırmızı
   yanması kodla ilgili hiçbir şey söylemez; o yüzden zincirin tamamı sahte
   sağlayıcı üzerinde koşar.
2. **Çevrimdışı demo.** PLAN'ın C planı (internetsiz sunum) buna dayanır.
3. **Kota.** Ücretsiz katman dolduğunda geliştirme durmaz.

Bu işleri yapabilmesi için sahte sağlayıcının GERÇEK payload'ı okuması gerekir:
prompt'taki `<source id="...">` etiketlerini ayrıştırır ve yalnızca gerçekten
verilmiş chunk'lara atıf yapar. Böylece atıf doğrulaması, abstention ve
pedagojik filtre sahte modda da birebir aynı yolu izler — değişen tek şey düzyazı
olur. Cevabı uyduran bir stub kullansaydık, guardrail testleri kendi kurdukları
sahneyi doğrular, üretim yolunu hiç sınamazdı.

`leak_first` / `always_leak` / `malformed_first` bayrakları testler içindir:
regen ve şablona düşme yolları ancak ihlal eden bir cevap üretilebiliyorsa
sınanabilir. Varsayılan davranış (bayraksız) demo ve CI'nın kullandığı temiz
yoldur.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

from app.contracts import AnswerStatus, ChatMode, SocraticStage
from app.modules.generation.llm import LlmCompletion, LlmRequest

FAKE_PROVIDER = "fake"
FAKE_MODEL = "fake/deterministic-v1"

_SOURCE_PATTERN = re.compile(
    r'<source\s+id="(?P<id>[^"]+)"\s+file="(?P<file>[^"]*)"\s+location="(?P<location>[^"]*)"'
    r'(?:\s+section="(?P<section>[^"]*)")?\s*>(?P<text>.*?)</source>',
    re.DOTALL,
)
_QUESTION_PATTERN = re.compile(r"<question>(?P<q>.*?)</question>", re.DOTALL)

#: Atıf yapılacak azami kaynak sayısı. Cevabın tamamı ilk parçalara dayanır;
#: sekiz kaynağın hepsine atıf yapmak "her şeye atıf yaptım" gürültüsü üretir.
_MAX_CITATIONS = 3
_SUMMARY_LENGTH = 180


@dataclass(frozen=True, slots=True)
class ParsedSource:
    """Prompt'tan geri okunan tek kaynak."""

    chunk_id: str
    file_name: str
    location: str
    text: str


def parse_sources(user_prompt: str) -> list[ParsedSource]:
    """Prompt'taki `<source>` etiketlerini geri okur.

    Ayrıştırmanın belirsiz olmaması, `prompts.escape_for_context` sayesindedir:
    materyal metni kaçırıldığı için içeride sahte bir `<source>` etiketi
    duramaz. Yani bu ayrıştırıcı aynı zamanda kaçış mekanizmasının canlı bir
    kontrolüdür — kaçış bozulursa sahte sağlayıcı da bozulur ve testler bunu
    görür.
    """
    sources: list[ParsedSource] = []
    for match in _SOURCE_PATTERN.finditer(user_prompt):
        sources.append(
            ParsedSource(
                chunk_id=match.group("id"),
                file_name=html.unescape(match.group("file")),
                location=html.unescape(match.group("location")),
                text=html.unescape(match.group("text")).strip(),
            )
        )
    return sources


def parse_question(user_prompt: str) -> str:
    match = _QUESTION_PATTERN.search(user_prompt)
    return html.unescape(match.group("q")).strip() if match else ""


def _summarize(text: str, limit: int = _SUMMARY_LENGTH) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    # Cümle sınırında kes: yarım kelime, düzyazıyı okunmaz yapıyor.
    boundary = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    if boundary > limit // 2:
        return cut[: boundary + 1]
    return cut.rsplit(" ", 1)[0] + "…"


def _socratic_text(stage: SocraticStage | None, source: ParsedSource) -> str:
    """Kademeye uygun, çözüm İÇERMEYEN tek ipucu.

    Metinler bilerek soruyla biter: Sokratik modun ölçütü öğrencinin bir sonraki
    adımı kendi atmasıdır. Kademe seçimi burada yapılmaz, verilen kademeye
    uyulur — merdiven state machine'in işidir.
    """
    where = f"{source.file_name}, {source.location}"
    match stage:
        case SocraticStage.NUDGE:
            return (
                f"{where} bölümündeki tanımı bir kez daha oku. "
                "Sence orada senin sorunun hangi parçası tarif ediliyor?"
            )
        case SocraticStage.CONCEPT_HINT:
            return (
                f"Aradığın kavram {where} bölümünde anlatılıyor. "
                "Bu kavramı kendi cümlelerinle nasıl tanımlarsın?"
            )
        case SocraticStage.SIMILAR_EXAMPLE:
            return (
                f"{where} bölümündeki örnek seninkine benziyor ama aynısı değil. "
                "O örnekte sonucu belirleyen adım hangisi?"
            )
        case SocraticStage.EXPLAIN_WITH_SOURCE:
            return (
                f"{where} bölümüne göre: {_summarize(source.text)} "
                "Buradan yola çıkarak kendi sorunda ilk adımı nasıl atarsın?"
            )
        case _:
            return (
                f"Bu konuda şimdiye kadar ne denedin? {where} bölümündeki "
                "hangi adımda takıldığını yazar mısın?"
            )


def _qa_text(question: str, sources: list[ParsedSource]) -> str:
    lead = sources[0]
    body = _summarize(lead.text)
    if len(sources) > 1:
        extra = f" Konunun devamı {sources[1].file_name}, {sources[1].location} bölümünde."
    else:
        extra = ""
    return f"Ders materyaline göre: {body}{extra}"


def _exam_text() -> str:
    return (
        "Sınav sürerken ipucu veya çözüm paylaşılmaz. "
        "Sorunun kaynağını sınav bittikten sonra geri bildirimle birlikte görebilirsin."
    )


#: Pedagojik filtrenin yakalaması GEREKEN, bilerek ihlal eden cevap. Testler
#: regen ve şablona düşme yollarını ancak böyle bir çıktı üretilebiliyorsa
#: sınayabilir.
_LEAKING_TEXT = "Çözüm şöyle:\n\n```python\ndef cevap(n):\n    return n * 2\n```\n\ncevap: 42"


class FakeLlmClient:
    """`LlmClient` protokolünü uygulayan deterministik sağlayıcı."""

    def __init__(
        self,
        *,
        leak_first: bool = False,
        always_leak: bool = False,
        malformed_first: bool = False,
    ) -> None:
        self._leak_first = leak_first
        self._always_leak = always_leak
        self._malformed_first = malformed_first
        #: Kaç kez çağrıldığı: testler "cache isabetinde LLM çağrılmadı" ve
        #: "yalnız bir kez retry edildi" iddialarını buna bakarak kanıtlar.
        self.calls = 0

    async def complete(self, request: LlmRequest) -> LlmCompletion:
        self.calls += 1
        text = self._payload_for(request)
        return LlmCompletion(
            text=text,
            provider=FAKE_PROVIDER,
            model=FAKE_MODEL,
            prompt_tokens=len(request.system) // 4 + len(request.user) // 4,
            completion_tokens=len(text) // 4,
        )

    def _payload_for(self, request: LlmRequest) -> str:
        if self._malformed_first and self.calls == 1:
            return "Tabii, işte cevabınız: bu bir JSON değil."

        sources = parse_sources(request.user)
        if not sources:
            # Kaynaksız cevap üretmek yerine kapan (Anayasa IV).
            return json.dumps(
                {
                    "status": AnswerStatus.INSUFFICIENT_CONTEXT.value,
                    "answer": (
                        "Bu soruyu ders materyalinde bulabildiğim kaynaklarla cevaplayamıyorum."
                    ),
                    "citations": [],
                    "hints": [],
                },
                ensure_ascii=False,
            )

        cited = sources[:_MAX_CITATIONS]
        lead = cited[0]

        leaking = self._always_leak or (self._leak_first and not request.strict_retry)
        if leaking:
            answer = _LEAKING_TEXT
        elif request.mode is ChatMode.SOCRATIC:
            answer = _socratic_text(request.socratic_stage, lead)
        elif request.mode is ChatMode.EXAM:
            answer = _exam_text()
        else:
            answer = _qa_text(parse_question(request.user), cited)

        hints = []
        if request.mode is ChatMode.SOCRATIC:
            hints = [{"text": answer, "chunk_id": lead.chunk_id}]

        return json.dumps(
            {
                "status": AnswerStatus.ANSWERED.value,
                "answer": answer,
                "citations": [
                    {
                        "chunk_id": source.chunk_id,
                        "claim": _summarize(source.text, 90),
                    }
                    for source in cited
                ],
                "hints": hints,
            },
            ensure_ascii=False,
        )
