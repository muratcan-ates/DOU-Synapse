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

---

## Görev duyarlılığı (9 Ağustos, 14_R4 Kusur 4)

Şerit 4'ün bulgusu: anahtar yokken **soru üretimi** istendiğinde bu sağlayıcı
sohbet cevabı döndürüyordu. Hat fail-closed davranıyordu (uydurma soru havuza
girmiyor), ama çevrimdışı demoda soru üretimi hiç çalışmıyordu.

Sebep yapısaldı: `LlmRequest.mode` bir SOHBET kipidir ve soru üretiminin karşılığı
yoktur; `question_gen` isteği varsayılan `ChatMode.QA` ile gönderiyordu. Çözüm
`LlmRequest.task` (bkz. `llm.py`). Görev iki yoldan belirlenir:

1. **Çağıran söylerse** — `task=LlmTask.QUESTION_GEN`. Doğru yol budur.
2. **Söylemezse** — prompt'un biçiminden çıkarılır. `question_gen._GenerationCompletion`
   bu şeridin dosyası değil ve alanı bugün göndermiyor; çıkarım o düzeltme
   inene kadar çevrimdışı demoyu ayakta tutuyor.

İkinci yol bir kuplaj borcudur ve **sessiz kalmasına izin verilmiyor**:
`tests/test_generation.py` gerçek `question_gen.build_prompt` çıktısını her soru
tipi için bu ayrıştırıcıya verir. Prompt biçimi değişirse test kırmızı yanar —
sahte sağlayıcı sessizce sohbet cevabına dönmez.

Üretilen soru bir ŞEMA İSKELETİDİR, bilgi değildir. Metni materyalden birebir
kopyalanır ve kaynağı prompt'taki gerçek bir `chunk_id`'dir; yani `question_gen`'in
kaynak-uydurma kapısından geçer. İçeriği pedagojik olarak değerli DEĞİLDİR ve
öyleymiş gibi sunulmamalıdır — taslak olarak havuza girer, eğitmen onayı olmadan
hiçbir öğrenciye görünmez (FR-023).
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

from app.contracts import AnswerStatus, ChatMode, SocraticStage
from app.modules.generation.llm import LlmCompletion, LlmRequest, LlmTask

FAKE_PROVIDER = "fake"
FAKE_MODEL = "fake/deterministic-v1"

_SOURCE_PATTERN = re.compile(
    r'<source\s+id="(?P<id>[^"]+)"\s+file="(?P<file>[^"]*)"\s+location="(?P<location>[^"]*)"'
    r'(?:\s+section="(?P<section>[^"]*)")?\s*>(?P<text>.*?)</source>',
    re.DOTALL,
)
_QUESTION_PATTERN = re.compile(r"<question>(?P<q>.*?)</question>", re.DOTALL)
_ATTEMPT_PATTERN = re.compile(r"<student_attempt>(?P<a>.*?)</student_attempt>", re.DOTALL)

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


def parse_attempt(user_prompt: str) -> str:
    """Öğrencinin bu turdaki denemesi; yoksa boş."""
    match = _ATTEMPT_PATTERN.search(user_prompt)
    return html.unescape(match.group("a")).strip() if match else ""


# ---------------------------------------------------------------------------
# Görev çıkarımı — `LlmRequest.task` verilmediğinde
# ---------------------------------------------------------------------------

#: `question_gen.build_prompt`'un ürettiği metinde bulunan, sohbet prompt'unda
#: BULUNMAYAN işaretler. İkisi birden aranıyor: tek işaret, materyalin içinde
#: tesadüfen geçebilir; ikisi birden geçemez (biri kaynak blok başlığı, diğeri
#: çıktı şeması satırı).
_QUESTION_GEN_MARKERS = ('{"questions"', "### KAYNAK")

#: Soru tipini ayırt eden işaretler — `question_gen._TYPE_INSTRUCTIONS`'ın
#: metninden. Sıra ÖNEMLİ: `bug_hunt` de `code` içerir, o yüzden daha ayırt
#: edici olan önce denenir.
_TYPE_MARKERS: tuple[tuple[str, str], ...] = (
    ("bug_type", "bug_hunt"),
    ("izlenecek kod", "code_trace"),
    ("options (4 şık", "mcq"),
    ("key_points", "open"),
)

_CHUNK_ID_PATTERN = re.compile(r"^chunk_id:\s*(?P<id>[0-9a-fA-F-]{36})\s*$", re.MULTILINE)
_COUNT_PATTERN = re.compile(r"kaynaklardan\s+(?P<n>\d+)\s+adet soru")
_SHORT_ANSWER_MARKER = "accepted_answers"


def infer_task(request: LlmRequest) -> LlmTask:
    """İsteğin görevi. Çağıran söylediyse o, söylemediyse prompt biçiminden.

    Çıkarım yalnız `CHAT` varsayılanıyla gelen istekler için çalışır: çağıran
    açıkça `QUESTION_GEN` dediyse tahmin yürütmenin anlamı yok, dediyse `CHAT`
    diye ısrar edemeyiz — ama varsayılanı ayırt edemediğimiz için `CHAT` gelen
    isteğe bakmak zorundayız. Ayrım netleştiğinde (bkz. modül docstring'i, madde 2)
    bu fonksiyonun gövdesi tek satıra iner.
    """
    if request.task is not LlmTask.CHAT:
        return request.task
    if all(marker in request.user for marker in _QUESTION_GEN_MARKERS):
        return LlmTask.QUESTION_GEN
    return LlmTask.CHAT


def _question_type_of(user_prompt: str) -> str:
    for marker, question_type in _TYPE_MARKERS:
        if marker in user_prompt:
            return question_type
    # Tanınmayan tip: en dar şema seçilir. Geniş bir şema uydurmak, doğrulamadan
    # geçen ama anlamsız bir soru üretmek olurdu (Anayasa IV).
    return "open"


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


def _socratic_text(
    stage: SocraticStage | None, source: ParsedSource, *, attempt: str = ""
) -> str:
    """Kademeye uygun, çözüm İÇERMEYEN tek ipucu.

    Metinler bilerek soruyla biter: Sokratik modun ölçütü öğrencinin bir sonraki
    adımı kendi atmasıdır. Kademe seçimi burada yapılmaz, verilen kademeye
    uyulur — merdiven state machine'in işidir.

    **Deneme yalnız ALINTILANIR, anlaşılmaz.** Öğrencinin yazdığı metin ipucunun
    başına tırnak içinde eklenir; içeriği yorumlanmaz, hiçbir kavram ondan
    çıkarılmaz. Sebep DIAGNOSE kademesindeki somut tutarsızlıktı: öğrenci ne
    denediğini yazdıktan sonra sahte sağlayıcı yine "bu konuda ne denedin?" diye
    soruyordu ve çevrimdışı demo kendi kendisiyle çelişiyordu.

    Bu ekleme "ipucu denemeye göre şekilleniyor"un KANITI DEĞİLDİR ve öyle
    sunulmamalıdır — mekanik bir yankıdır. Gerçek şekillenme yalnız gerçek modelle
    ölçülebilir; sahte sağlayıcının ürettiği hiçbir metin o iddiayı taşıyamaz
    (14_R4 Kusur 3, ölçüm notu).
    """
    if not attempt:
        return _stage_question(stage, source)
    prefix = f"«{_summarize(attempt, 90)}» demişsin. "
    if stage is None or stage is SocraticStage.DIAGNOSE:
        # DIAGNOSE'un sabit sorusu "ne denedin?"dir ve deneme ELDEYKEN o soruyu
        # sormak demoyu kendi kendisiyle çelişkiye düşürüyordu. Deneme varken
        # kademenin amacı (nerede takıldığını görmek) korunuyor, sorusu değişiyor.
        where = f"{source.file_name}, {source.location}"
        return (
            f"{prefix}{where} bölümünü açıp bu cümleni oradaki tanımla karşılaştır. "
            "Hangi noktada ayrıldıklarını yazar mısın?"
        )
    return prefix + _stage_question(stage, source)


def _stage_question(stage: SocraticStage | None, source: ParsedSource) -> str:
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


def _question_drafts(user_prompt: str) -> str:
    """Soru üretimi isteğine ŞEMA İSKELETİ döndürür.

    Üç kural, üçü de `question_gen`'in kapılarından geçmek için:

    1. `source_chunk_id` prompt'ta GERÇEKTEN listelenmiş bir kimliktir. Uydurma
       bir UUID yazsaydık `question_gen` soruyu haklı olarak atardı ve çevrimdışı
       demo yine boş dönerdi — sahte sağlayıcının işi kapıyı delmek değil,
       kapıdan geçebilen geçerli bir taslak üretmek.
    2. Soru metni materyalden BİREBİR kopyalanır. Uydurulmuş bir soru kökü,
       "materyalde geçmeyen bilgi kullanma" kuralının sahte tarafta ihlali olurdu.
    3. Şıklar/cevap anahtarı yapısal doldurmadır ve doğru cevabı temsil ETMEZ.
       Bu bir taslaktır; eğitmen onayı olmadan öğrenciye görünmez (FR-023).
    """
    chunk_ids = _CHUNK_ID_PATTERN.findall(user_prompt)
    if not chunk_ids:
        return json.dumps({"questions": []}, ensure_ascii=False)

    count_match = _COUNT_PATTERN.search(user_prompt)
    count = int(count_match.group("n")) if count_match else 1
    question_type = _question_type_of(user_prompt)
    # Materyal metni: `### KAYNAK n` bloklarının gövdesi. Kaynak sayısı sorudan
    # az olabilir, o yüzden sırayla dolanılır.
    bodies = _source_bodies(user_prompt)

    questions = []
    for index in range(count):
        chunk_id = chunk_ids[index % len(chunk_ids)]
        body = bodies[index % len(bodies)] if bodies else ""
        questions.append(_draft_for(question_type, chunk_id, body, user_prompt))
    return json.dumps({"questions": questions}, ensure_ascii=False)


_SOURCE_BLOCK = re.compile(
    r"### KAYNAK \d+\nchunk_id: [^\n]+\ndosya: [^\n]+\n(?P<body>.*?)(?=\n\n### KAYNAK |\Z)",
    re.DOTALL,
)


def _source_bodies(user_prompt: str) -> list[str]:
    return [match.group("body").strip() for match in _SOURCE_BLOCK.finditer(user_prompt)]


def _draft_for(question_type: str, chunk_id: str, body: str, user_prompt: str) -> dict[str, object]:
    excerpt = _summarize(body, 200) or "ders materyalindeki ilgili bölüm"
    short = _summarize(body, 60) or "materyaldeki tanım"

    if question_type == "mcq":
        return {
            "source_chunk_id": chunk_id,
            "stem": f"Ders materyaline göre aşağıdakilerden hangisi doğrudur? ({short})",
            "options": [
                {"key": "A", "text": excerpt},
                {"key": "B", "text": "Materyalde bu şekilde anlatılmıyor."},
                {"key": "C", "text": "Bu bölümde tanımlanmayan bir davranış."},
                {"key": "D", "text": "Materyaldeki tanımın tersi."},
            ],
            "answer_key": "A",
            "explanation": "Doğru şık, kaynak bölümün metninden birebir alınmıştır.",
        }

    if question_type == "code_trace":
        return {
            "source_chunk_id": chunk_id,
            "language": "python",
            "code": "for i in range(3):\n    print(i)",
            "prompt": f"Bu kodun çıktısı nedir? Kaynak bölüm: {short}",
            "answer_key": "0\n1\n2",
            "explanation": "Döngü 0'dan 2'ye kadar sayar ve her adımda değeri basar.",
        }

    if question_type == "bug_hunt":
        return {
            "source_chunk_id": chunk_id,
            "language": "python",
            "code": "def ortalama(sayilar):\n    return sum(sayilar) / len(sayilar) + 1",
            "prompt": f"Bu kodda tek bir hata var; hangi satırda? Kaynak bölüm: {short}",
            "answer_key": {
                "line": 2,
                "bug_type": "yanlış aritmetik",
                "fix_summary": "Fazladan eklenen 1 kaldırılmalı.",
            },
            "explanation": "Ortalama hesabına sabit eklenmiş.",
        }

    # open — kısa cevap istendiyse `accepted_answers`, aksi hâlde `key_points`
    # zorunlu (`OpenPayload._check_format`). İkisini birden doldurmak şemayı
    # geçirirdi ama istenmeyen alanı da taşırdı.
    draft: dict[str, object] = {
        "source_chunk_id": chunk_id,
        "prompt": f"Kaynak bölüme dayanarak açıklayınız: {short}",
        "answer_key": excerpt,
    }
    if _SHORT_ANSWER_MARKER in user_prompt:
        draft["accepted_answers"] = [short]
    else:
        draft["key_points"] = [short]
        draft["rubric"] = [{"point": short, "weight": 100}]
    return draft


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

        if infer_task(request) is LlmTask.QUESTION_GEN:
            # Soru üretimi sohbet zarfını KULLANMAZ. Ayrım burada, tek yerde:
            # aşağıdaki gövde `<source>` etiketlerine göre kurulmuş ve soru
            # üretimi prompt'unda öyle bir etiket yok — ayrım yapılmasaydı
            # `sources` boş çıkar ve istek "kaynak yok" cevabı alırdı.
            return _question_drafts(request.user)

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
            answer = _socratic_text(
                request.socratic_stage, lead, attempt=parse_attempt(request.user)
            )
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
