"""Çoktan seçmeli soru kalite sinyalleri — E4'ün MCQ yarısı.

Bu modül, havuza yazılmış MCQ'ların **ölçülebilir** kusurlarını arar. Var olma
nedeni, soru üretiminin (`question_gen`) bugün yalnız iki şeyi garanti etmesi:
şemaya uyum ve kaynağın uydurulmamış olması. İkisi de sorunun **ölçtüğünü**
söylemez. Şemadan geçen ve kaynağı gerçek olan bir soru şunların hepsini aynı
anda yapabilir ve hiçbir kapı bunu görmez:

* aynı dersin başka bir sorusunun kelimesi kelimesine olmasa da anlamca aynısıdır;
* doğru şıkkı diğerlerinin iki katı uzunluktadır, yani konuyu hiç bilmeyen
  öğrenci de doğru cevabı seçer;
* iki şıkkı normalleştirilince aynı metindir, yani o ikisinden hangisini
  seçtiğinin puanla ilgisi yoktur;
* çeldiricileri gerçek bir öğrenci yanılgısını değil, rastgele yanlış bir cümleyi
  temsil eder — soru ölçmez, eler.

Modül **saftır**: veritabanına, ağa ve LLM'e dokunmaz, yan etkisi yoktur. Girdisi
`questions.payload` jsonb'sinin MCQ biçimidir (`schemas.assessment.McqPayload`),
çıktısı makine-okunur `QualityFinding` listesidir. Bir bulgu **red kararı
değildir**: hiçbir fonksiyon burada soru silmez, statü değiştirmez, eşik
dayatmaz. Hepsi eğitmenin inceleme kuyruğunu sıralamak içindir.

**Neden pydantic değil dataclass.** Bu dizinde (`modules/assessment/`) pydantic
modelleri yalnız *dış dünyadan gelen* veriyi doğrulamak için kullanılıyor
(`grading._LlmVerdict`, `question_gen._McqDraft` — ikisi de LLM çıktısı). Süreç
içinde üretilen rapor nesneleri dataclass: `question_gen.GenerationReport`,
`grading.GradingOutcome`, `socratic.SocraticDecision`. Buradaki her şey ikinci
gruba girer, dolayısıyla `@dataclass(frozen=True, slots=True)`.

**Neden ham dict okuyoruz, `McqPayload` değil.** `McqOption` bugün yalnız `key`
ve `text` alanlarını tanıyor; `misconception` diye bir alan YOK. Payload'ı
`parse_payload` ile okursak pydantic bu etiketi sessizce düşürür ve (e)
sinyalinin ölçecek verisi kalmaz. Etiket bugün jsonb'de yalnız `authoring.py`'nin
"bilinmeyen eski metadata korunur" kanalıyla yaşayabiliyor. Bunun dürüst sonucu
`MISSING_MISCONCEPTION` bulgusunun docstring'inde yazılı.

Eşikler. Buradaki hiçbir varsayılan sayı kalibre EDİLMEDİ. Her biri
"başlangıç değeri" olarak işaretli, parametre olarak dışarı açık ve gerekçesi
kendi sabitinin yanında duruyor. Gerçek bir havuzda ölçülmeden hiçbiri
"doğrulanmış eşik" diye anılmamalı (Anayasa III).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.core import text_tr

# ---------------------------------------------------------------------------
# Ayarlanabilir sayılar — hiçbiri kalibre edilmedi
# ---------------------------------------------------------------------------

#: Yakın-tekrar benzerliğinde kullanılan karakter n-gram uzunluğu.
#:
#: n=3 seçildi çünkü aşağıdaki ÖLÇÜMDE gerçek tekrarı, aynı kalıptan türetilmiş
#: farklı sorudan en geniş farkla ayıran uzunluk oydu (bkz. `similarity`).
DEFAULT_NGRAM = 3

#: Yakın-tekrar eşiği. **KALİBRE EDİLMEDİ — başlangıç değeri.**
#:
#: Tek bir elle yazılmış çift üzerinde ölçülen değerlerin arasına konuldu
#: (gerçek tekrar 0.567, aynı kalıptan farklı soru 0.522). İki ölçümün arası
#: 0.045; bu bir kalibrasyon DEĞİL, tek bir anekdottur. Gerçek bir soru havuzunda
#: eğitmen etiketiyle ölçülmeden "doğrulanmış eşik" diye anılamaz.
DEFAULT_DUPLICATE_THRESHOLD = 0.55

#: Doğru şıkkın uzunluk aykırılığı oranı. **KALİBRE EDİLMEDİ — başlangıç değeri.**
#:
#: 1.5 = "doğru şık en uzun çeldiriciden yarı yarıya uzun". Sınav hazırlama
#: elkitaplarının söylediği şey niteliktir ("doğru şık belirgin biçimde uzun
#: olmasın"), sayı değil; buradaki sayı o niteliği koda çevirebilmek için
#: seçildi, bir çalışmadan alınmadı.
DEFAULT_LENGTH_RATIO = 1.5

#: Bir yanılgının "aşırı tekrar" sayılma oranı. **KALİBRE EDİLMEDİ.**
DEFAULT_OVERUSE_RATIO = 0.4

#: Aşırı tekrar hesabının açılması için gereken en az etiketli çeldirici sayısı.
#:
#: Oran küçük örneklemde gürültüdür: 2 etiketli çeldiricinin 1'i "aşırı tekrar"
#: eşiğini kaçınılmaz aşar. Bu alt sınır, raporun matematiksel olarak kaçınılmaz
#: bir şeyi bulgu diye göstermesini engeller. **KALİBRE EDİLMEDİ.**
DEFAULT_OVERUSE_MIN_SAMPLE = 5

#: Bir şıkkın yanılgı etiketini taşıdığı jsonb anahtarı.
MISCONCEPTION_KEY = "misconception"


class Severity(StrEnum):
    """Bulgunun eğitmen için aciliyeti — otomatik bir karar değil, sıralama ipucu.

    `HIGH` yalnız kodun kanıtlayabildiği kusurlar içindir (iki şık gerçekten
    aynı metin). `MEDIUM` güçlü ama yorumlanabilir sinyaller, `LOW` ise yanlış
    pozitifi bilinerek kabul edilmiş ipuçlarıdır.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingCode(StrEnum):
    """Bulgu türü. Metin değil KOD saklanır; mesaj Türkçedir ve değişebilir."""

    DUPLICATE_OPTION = "duplicate_option"
    CATCH_ALL_OPTION = "catch_all_option"
    ANSWER_LENGTH_OUTLIER = "answer_length_outlier"
    PARALLELISM_BREAK = "parallelism_break"
    MISSING_MISCONCEPTION = "missing_misconception"
    NEAR_DUPLICATE_QUESTION = "near_duplicate_question"
    MISCONCEPTION_UNTESTED = "misconception_untested"
    MISCONCEPTION_OVERUSED = "misconception_overused"


@dataclass(frozen=True, slots=True)
class QualityFinding:
    """Tek bir kalite bulgusu.

    `message` eğitmene gösterilebilir Türkçe metindir ama **sözleşme değildir**;
    makine tarafı her zaman `code` ile dallanmalıdır. İkisini ayırmanın nedeni,
    mesaj metnini iyileştirmenin bir arayüz kırılmasına yol açmamasıdır.
    """

    code: FindingCode
    severity: Severity
    message: str
    question_id: str = ""
    #: Bulgunun ilgili olduğu şıkkın anahtarı; soru düzeyindeki bulgularda None.
    option_key: str | None = None
    #: Çift üreten bulgularda (aynı iki şık, aynı iki soru) diğer uç.
    related_key: str | None = None


@dataclass(frozen=True, slots=True)
class OptionView:
    """Kalite analizine giren tek şık.

    `misconception` ayrı bir alan: "etiket yok" ile "etiket boş dize" arasındaki
    farkı kaybetmemek için `None` ve `""` ayrı tutulur, ama `review_options`
    ikisini de eksik sayar — boş bir etiket beyan değildir.
    """

    key: str
    text: str
    misconception: str | None = None


@dataclass(frozen=True, slots=True)
class McqView:
    """Bir MCQ'nun kalite analizine giren hâli.

    `Question` ORM nesnesi DEĞİLDİR ve olmamalı: bu modülün veritabanı bilmemesi,
    testlerinin veritabanı istememesini sağlıyor. Çağıran `mcq_view` ile
    payload'dan kurar.
    """

    question_id: str
    stem: str
    options: tuple[OptionView, ...]
    answer_key: str

    @property
    def correct(self) -> OptionView | None:
        """Doğru şık; `answer_key` hiçbir şıkla eşleşmiyorsa None.

        Şema bunu zaten doğruluyor (`McqPayload._check_keys`), ama bu modül
        şemadan geçmemiş eski satırlara da bakabilmeli; eşleşme yoksa doğru şıkka
        bağlı sinyaller sessizce atlanır, `KeyError` ile analiz düşmez.
        """
        for option in self.options:
            if option.key == self.answer_key:
                return option
        return None

    @property
    def distractors(self) -> tuple[OptionView, ...]:
        return tuple(option for option in self.options if option.key != self.answer_key)


def mcq_view(payload: Mapping[str, Any], *, question_id: str = "") -> McqView:
    """`questions.payload` jsonb'sini analiz görünümüne çevirir.

    Yapısal olarak okunamayan payload'da **ValueError fırlatır, boş görünüm
    döndürmez.** Gerekçe: sıfır şıklı bir görünüm üzerinden "kusur bulunamadı"
    raporlamak, incelenmemiş bir soruyu incelenmiş göstermek olurdu. Çağıran
    hatayı yakalayıp o soruyu "okunamadı" diye ayrıca sayabilir.

    Bilinmeyen anahtarlar (ör. `misconception`) KORUNUR — bu fonksiyonun
    `parse_payload` yerine ham dict okumasının tek sebebi budur.
    """
    raw_options = payload.get("options")
    if not isinstance(raw_options, list) or not raw_options:
        raise ValueError("MCQ payload'ında okunabilir 'options' listesi yok.")

    options: list[OptionView] = []
    for raw in raw_options:
        if not isinstance(raw, dict):
            raise ValueError("MCQ şıkkı bir nesne değil.")
        label = raw.get(MISCONCEPTION_KEY)
        options.append(
            OptionView(
                key=str(raw.get("key", "")),
                text=str(raw.get("text", "")),
                misconception=label if isinstance(label, str) else None,
            )
        )

    return McqView(
        question_id=question_id,
        stem=str(payload.get("stem", "")),
        options=tuple(options),
        answer_key=str(payload.get("answer_key", "")),
    )


# ---------------------------------------------------------------------------
# 1. Yakın-tekrar tespiti
# ---------------------------------------------------------------------------


def _char_ngrams(text: str, size: int) -> frozenset[str]:
    """Normalleştirilmiş metnin karakter n-gram kümesi.

    `text_tr.normalize` kullanılır, `fold` değil: normalize noktalamayı atar ve
    boşlukları teke indirir, dolayısıyla "deadlock'a girer?" ile "deadlock a
    girer" aynı n-gram'ları üretir. Boşluk n-gram'ın İÇİNDE kalır, bu bilinçli —
    kelime sınırını aşan n-gram'lar zayıf bir sıra bilgisi taşır ve saf kelime
    torbasının "aynı kelimeler, başka cümle" körlüğünü bir miktar kapatır.

    `size < 1` reddedilir. Sessizce kabul edilseydi `range(len - size + 1)` her
    konumdan boş dilim üretir, iki metnin n-gram kümesi de `{""}` olur ve
    `similarity` HER çift için 1.0 döner: yani yanlış bir parametre, yakın-tekrar
    kapısını "her soru her sorunun tekrarıdır" diyecek biçimde açar. Bu bir
    fail-open'dır; kapının kendisi gibi, çağıran hatası da gürültülü olmalı.
    """
    if size < 1:
        raise ValueError("n-gram uzunluğu en az 1 olmalı; 0 ve altı her çifti benzer gösterir.")
    normalized = text_tr.normalize(text)
    if not normalized:
        return frozenset()
    if len(normalized) <= size:
        return frozenset({normalized})
    return frozenset(
        normalized[index : index + size] for index in range(len(normalized) - size + 1)
    )


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def similarity(left: str, right: str, *, ngram: int = DEFAULT_NGRAM) -> float:
    """İki soru kökünün 0–1 arası yüzeysel benzerliği.

    **Neden karakter n-gram, neden kelime kümesi (Jaccard) değil.** Türkçe
    eklemeli bir dildir: aynı kök farklı ekle farklı bir *token* üretir
    ("sistemi" / "sisteminde" / "sistemlerde"). Kelime kümesi Jaccard'ı bu üçünü
    tamamen ayrı sayar ve gerçek tekrarı olduğundan uzak gösterir. Karakter
    n-gram'ları ise kökün n-gram'larını paylaşır; ek, bir tokenin tamamına değil
    birkaç n-gram'a mal olur.

    Bu bir tercih değil, bu depoda ÖLÇÜLDÜ. `text_tr` ile normalleştirilmiş iki
    çift üzerinde (soldaki gerçek tekrar, sağdaki aynı kalıptan türetilmiş
    *farklı* soru):

        gerçek tekrar     — n=3: 0.567   n=4: 0.508   n=5: 0.452   kelime: 0.444
        aynı kalıp/farklı — n=3: 0.522   n=4: 0.493   n=5: 0.485   kelime: 0.500

    Kelime kümesi Jaccard'ı SIRAYI ters çeviriyor: farklı soruya (0.500) gerçek
    tekrardan (0.444) daha yüksek puan veriyor. Yani bu çiftte kelime kümesi
    yalnız zayıf değil, yanlış yönde. n=5 de tersine dönüyor (0.452 < 0.485).
    Doğru sırayı veren ve aradaki farkı en geniş bırakan n=3 seçildi.

    **Dürüst sınır.** Aradaki fark 0.045'tir. Bu ölçü yakın-tekrarı farklı
    sorudan GÜVENİLİR biçimde AYIRAMAZ; yalnız bir inceleme kuyruğunu sıralar.
    Aynı kalıptan üretilen ("... hangisi X'tir?" / "... hangisi Y'dir?") gerçek
    ve meşru soru çiftleri bu ölçüde yüksek puan alır ve yanlış pozitif üretir.
    Anlamsal tekrarı gerçekten yakalamak gömme (embedding) benzerliği ister;
    bu modül saf ve bağımlılıksız olduğu için oraya gitmez.

    Ölçüm iki metnin de aynı dilde ve aynı uzunluk mertebesinde olduğunu varsayar;
    çok kısa bir kök (n'den kısa) tek n-gram'a indirgenir ve skoru anlamsızlaşır.
    """
    return _jaccard(_char_ngrams(left, ngram), _char_ngrams(right, ngram))


@dataclass(frozen=True, slots=True)
class DuplicatePair:
    """Eşik üstü benzerlikte bir soru çifti. Sıra `left`/`right` girdideki sıradır."""

    left_id: str
    right_id: str
    score: float


def find_near_duplicates(
    questions: Sequence[McqView],
    *,
    threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
    ngram: int = DEFAULT_NGRAM,
) -> list[DuplicatePair]:
    """Aynı havuzda anlamca aynı olma ihtimali yüksek soru çiftlerini döndürür.

    Neden gerekiyor: aynı sınavda anlamca aynı soruyu iki kez sormak, o konuyu
    bilen öğrenciye iki puan, bilmeyene iki sıfır yazar — sınavın o konuya
    verdiği ağırlığı sessizce ikiye katlar ve blueprint'in hücre dağılımını
    yalanlar. Dize eşitliği bunu yakalamaz, çünkü ikinci soru ilkinin birebir
    kopyası değil yeniden yazımıdır.

    **Yalnız soru kökü karşılaştırılır, şıklar değil.** İki gerekçe: (1) şıkları
    karıştırılmış bir kopya hâlâ kopyadır, (2) şık metinlerini karışıma katmak,
    dört farklı çeldiricinin birebir aynı kökü seyreltip eşiğin altına
    itmesine izin verirdi.

    Karşılaştırma O(n²) çifttir; bir dersin havuzu (yüzler mertebesi) için bu
    sorun değil. n-gram kümeleri çift başına değil SORU başına bir kez
    hesaplanır — çift başına hesaplansaydı 200 soruluk bir havuzda aynı metin
    ~200 kez normalleştirilirdi.

    Sonuç skora göre AZALAN sıralanır: kuyruk zaten bir inceleme sırasıdır,
    en şüpheli çift başta olmalı. Eşit skorlarda girdi sırası korunur.
    """
    grams = [_char_ngrams(question.stem, ngram) for question in questions]
    pairs: list[DuplicatePair] = []
    for left in range(len(questions)):
        for right in range(left + 1, len(questions)):
            score = _jaccard(grams[left], grams[right])
            if score >= threshold:
                pairs.append(
                    DuplicatePair(
                        left_id=questions[left].question_id,
                        right_id=questions[right].question_id,
                        score=score,
                    )
                )
    pairs.sort(key=lambda pair: pair.score, reverse=True)
    return pairs


def duplicate_findings(pairs: Sequence[DuplicatePair]) -> list[QualityFinding]:
    """Çiftleri, diğer sinyallerle aynı kuyruğa girebilecek bulgulara çevirir."""
    return [
        QualityFinding(
            code=FindingCode.NEAR_DUPLICATE_QUESTION,
            severity=Severity.MEDIUM,
            message=(
                f"Bu soru, {pair.right_id or 'başka bir soru'} ile yüzeysel olarak "
                f"%{pair.score * 100:.0f} örtüşüyor; ikisi aynı şeyi ölçüyor olabilir."
            ),
            question_id=pair.left_id,
            related_key=pair.right_id,
        )
        for pair in pairs
    ]


# ---------------------------------------------------------------------------
# 2. Çeldirici kalitesi
# ---------------------------------------------------------------------------

#: Kapsayıcı ("hepsi/hiçbiri") şıklarını işaret eden katlanmış belirteçler.
#:
#: Katlanmış hâliyle yazılır çünkü karşılaştırılan taraf `text_tr.tokens`
#: çıktısıdır ve o taraf katlanmıştır: "hiçbiri" → "hicbiri", "tümü" → "tumu".
#: Elle katlamak yerine `fold` çağrılıyor ki liste okunur kalsın (aynı karar
#: `question_gen._STOPWORDS`'te de verildi).
_CATCH_ALL_MARKERS = frozenset(
    text_tr.fold(word) for word in ("hepsi", "hiçbiri", "tümü", "tamamı")
)

#: Türkçe çekimli fiil sonlarının katlanmış hâli (ASCII).
#:
#: Bu bir morfolojik çözümleyici DEĞİLDİR ve öyle olduğu iddia edilmiyor —
#: yeni bağımlılık yasak, elde yalnız yazım var. Liste yalnız "bu şık bir fiille
#: mi bitiyor?" sorusuna kaba bir yanıt üretir.
_VERB_ENDINGS = (
    "iyor",
    "uyor",
    "acak",
    "ecek",
    "mez",
    "maz",
    "mis",
    "mus",
    "dir",
    "tir",
    "ir",
    "ur",
    "er",
    "ar",
    "di",
    "du",
    "ti",
    "tu",
)

#: Fiil sınıflandırmasının uygulandığı en kısa sözcük uzunluğu.
#:
#: "bir", "kir", "sir" gibi üç harfli adlar `_VERB_ENDINGS`'teki "ir" ile
#: eşleşir. Alt sınır bu sınıfı toptan eler; bedeli, üç harfli gerçek fiillerin
#: ("der", "sor") ad sayılmasıdır. İki hatadan görülmesi zor olanı seçildi.
_MIN_VERB_WORD_LENGTH = 4


def _ends_like_verb(text: str) -> bool:
    """Metnin son sözcüğü çekimli bir fiil gibi mi bitiyor (yalnız yazımdan)."""
    words = text_tr.tokens(text)
    if not words:
        return False
    last = words[-1]
    if len(last) < _MIN_VERB_WORD_LENGTH:
        return False
    return last.endswith(_VERB_ENDINGS)


def _duplicate_option_findings(question: McqView) -> list[QualityFinding]:
    """(c) Normalleştirilince aynı olan şık çiftleri.

    **Beş sinyalin en güçlüsü budur ve tek `HIGH` olanı odur.** Burada yorum
    yok: iki şık gerçekten aynı metinse, öğrencinin hangisini işaretlediğinin
    puanla ilgisi yoktur; ikisinden biri doğru şıksa soru şıkkı iki kez doğru
    kabul etmediği için doğrudan bozuktur.

    Karşılaştırma `text_tr.normalize` üzerinden yapılır, `==` üzerinden değil:
    "Döngüsel bekleme." ile "döngüsel bekleme" dize olarak farklıdır ama şık
    olarak aynıdır. Türkçe tuzağı da burada kapanır — `str.lower()` "İşlem"i
    birleşik noktalı "i̇şlem"e indirir ve "işlem" ile EŞLEŞMEZ; `text_tr` i/İ ve
    ı/I'yı önce elle eşlediği için ikisi de "islem" olur.

    Kabul edilen bedel: `normalize` aksanı söker, dolayısıyla yalnız aksanla
    ayrışan iki meşru şık ("acı"/"açı") burada yanlışlıkla aynı sayılır. Bu
    ödünç `text_tr.normalize`'ın ürün kararıdır ve orada gerekçelendirilmiştir;
    bu modül kendi "aynılık" tanımını yazarak o kararı ikiye bölmez.
    """
    findings: list[QualityFinding] = []
    seen: dict[str, str] = {}
    for option in question.options:
        normalized = text_tr.normalize(option.text)
        if not normalized:
            continue
        first = seen.get(normalized)
        if first is None:
            seen[normalized] = option.key
            continue
        findings.append(
            QualityFinding(
                code=FindingCode.DUPLICATE_OPTION,
                severity=Severity.HIGH,
                message=(
                    f"{option.key} şıkkı {first} şıkkıyla normalleştirilince aynı metin; "
                    "ikisinden hangisinin işaretlendiği puanı değiştirmiyor."
                ),
                question_id=question.question_id,
                option_key=option.key,
                related_key=first,
            )
        )
    return findings


def _catch_all_findings(question: McqView) -> list[QualityFinding]:
    """(b) "hepsi" / "hiçbiri" / "yukarıdakilerin tümü" gibi kapsayıcı şıklar.

    Neden kusur: kapsayıcı şık konuyu değil sınav tekniğini ölçer. Öğrenci iki
    şıkkın doğru olduğunu görürse "hepsi"nin doğru olduğunu konuyu bilmeden
    çıkarır; tersine tek bir şıkkı kesin yanlış bilirse "hepsi"yi konuyu
    bilmeden eler. Doğru şıkkın kendisi kapsayıcıysa durum daha ağırdır, mesaj
    bunu ayrıca söyler.

    **Bu sinyal ZAYIFTIR.** Belirteç sözcük olarak aranır, dolayısıyla cümlenin
    ortasında geçen meşru bir "hepsi" ("Süreçlerin hepsi aynı kaynağı bekler")
    de yakalanır. Kısa şıklarla sınırlamak (ör. "en çok üç sözcük") yanlış
    pozitifi azaltırdı ama kapsayıcı şık uzun da yazılabiliyor
    ("Yukarıda verilen seçeneklerin hepsi doğrudur"), yani o filtre yanlış
    negatif üretirdi. Görülebilir hatayı seçtik: fazla bulgu, eksik bulguya
    yeğdir — bulgu bir red değil, bir bakma isteğidir.

    Şık birleşimleri ("A ve B", "Yalnız I ve III") YAKALANMAZ; onların kalıbı
    ders ve şık numaralandırma biçimine göre değişiyor ve tek bir listeyle
    ölçülemedi.
    """
    findings: list[QualityFinding] = []
    for option in question.options:
        marker = next(
            (word for word in text_tr.tokens(option.text) if word in _CATCH_ALL_MARKERS), None
        )
        if marker is None:
            continue
        is_key = option.key == question.answer_key
        suffix = (
            " Üstelik doğru şık bu; öğrenci konuyu bilmeden eleme ile bulabilir."
            if is_key
            else " Kapsayıcı şıklar konuyu değil sınav tekniğini ölçer."
        )
        findings.append(
            QualityFinding(
                code=FindingCode.CATCH_ALL_OPTION,
                severity=Severity.MEDIUM,
                message=f"{option.key} şıkkı kapsayıcı bir ifade içeriyor.{suffix}",
                question_id=question.question_id,
                option_key=option.key,
            )
        )
    return findings


def _length_outlier_findings(question: McqView, *, length_ratio: float) -> list[QualityFinding]:
    """(a) Doğru şıkkın belirgin biçimde en uzun ya da en kısa olması.

    Neden kusur: soru yazarı doğru şıkkı tam ve koşullu yazma eğilimindedir
    ("...ancak yalnız dört koşul aynı anda sağlandığında"), çeldiricileri ise
    kısa keser. Öğrenci bunu öğrenir ve konuyu bilmeden en ayrıntılı şıkkı
    seçer — sorunun ölçtüğü şey bilgi değil, yazarın alışkanlığı olur.

    **Bu sinyal ZAYIFTIR ve zayıflığı sayılabilir:** dört şıkkın biri zaten her
    zaman en uzundur, yani "en uzun olmak" tek başına %25 taban orana sahiptir.
    Bu yüzden kural "en uzun" değil, "en uzun çeldiriciden `length_ratio` kat
    uzun". Oranın kendisi kalibre edilmedi (bkz. `DEFAULT_LENGTH_RATIO`).

    Uzunluk, `strip()` sonrası HAM karakter sayısıdır; katlanmış metin değil.
    Öğrencinin gördüğü şey ham metindir ve ipucu da ondan çıkar; katlama
    noktalamayı atarak gerçek görsel farkı küçültürdü.
    """
    correct = question.correct
    distractors = question.distractors
    if correct is None or len(distractors) < 2:
        # Tek çeldirici varsa "aykırılık" diye bir şey yok: karşılaştırılacak
        # dağılım yok, iki değerden biri kaçınılmaz olarak uzun olandır.
        return []

    correct_length = len(correct.text.strip())
    lengths = [len(option.text.strip()) for option in distractors]
    longest, shortest = max(lengths), min(lengths)

    if correct_length > longest * length_ratio:
        return [
            QualityFinding(
                code=FindingCode.ANSWER_LENGTH_OUTLIER,
                severity=Severity.MEDIUM,
                message=(
                    f"Doğru şık ({correct.key}) {correct_length} karakter; en uzun çeldirici "
                    f"{longest}. Uzunluk tek başına doğru cevabı ele veriyor olabilir."
                ),
                question_id=question.question_id,
                option_key=correct.key,
            )
        ]
    if correct_length * length_ratio < shortest:
        return [
            QualityFinding(
                code=FindingCode.ANSWER_LENGTH_OUTLIER,
                severity=Severity.MEDIUM,
                message=(
                    f"Doğru şık ({correct.key}) {correct_length} karakter; en kısa çeldirici "
                    f"{shortest}. Tek kısa şık olmak da bir ipucudur."
                ),
                question_id=question.question_id,
                option_key=correct.key,
            )
        ]
    return []


def _parallelism_findings(question: McqView) -> list[QualityFinding]:
    """(d) Şıkların dilbilgisel paralelliğini tek başına bozan şık.

    Neden kusur: diğerlerinden farklı bir dilbilgisel biçimde yazılmış tek şık
    gözle ayrışır. Öğrenci "öteki üçü aynı kalıpta, bu farklı" diye onu ya seçer
    ya eler; her iki durumda da karar konuya değil biçime dayanır.

    **Bu, beş sinyalin EN ZAYIFI'dır.** Elde morfolojik çözümleyici yok (yeni
    bağımlılık yasak), dolayısıyla bakılan şey dilbilgisi değil YAZIM: son
    sözcüğün çekimli fiil eklerinden biriyle bitip bitmediği. "kenar", "damar",
    "tekrar" gibi adlar "-ar" ile biter ve fiil sayılır; tersine "ada", "kapı"
    gibi sonla biten gerçek fiil biçimleri kaçırılır.

    Yanlış pozitifi sınırlamak için kural kasten dar tutuldu: bulgu yalnız
    (1) en az üç şık varsa ve (2) şıklardan TAM BİRİ diğerlerinin ortak
    biçiminden ayrılıyorsa üretilir. İki şık ayrışıyorsa hiçbir şey
    raporlanmaz — o durumda "hangisi aykırı" sorusunun cevabı yok. Önem `LOW`:
    bu bir gözle bakma isteğidir, kusur iddiası değil.
    """
    if len(question.options) < 3:
        return []

    verb_like = {option.key: _ends_like_verb(option.text) for option in question.options}
    odd = [key for key, is_verb in verb_like.items() if is_verb != (sum(verb_like.values()) > 1)]
    # `sum(...) > 1`: çoğunluğun biçimi. Tam bir şık çoğunluktan ayrılıyorsa o
    # tektir; ikisi ayrılıyorsa aykırı diye bir şey yoktur.
    if len(odd) != 1:
        return []

    key = odd[0]
    kind = "fiille biten tek şık" if verb_like[key] else "fiille bitmeyen tek şık"
    return [
        QualityFinding(
            code=FindingCode.PARALLELISM_BREAK,
            severity=Severity.LOW,
            message=(
                f"{key} şıkkı diğerlerinden farklı bir biçimde bitiyor ({kind}); "
                "biçim farkı konuyu bilmeyen öğrenciye ipucu verebilir."
            ),
            question_id=question.question_id,
            option_key=key,
        )
    ]


def _misconception_findings(question: McqView) -> list[QualityFinding]:
    """(e) Beyan edilmiş yanılgı etiketi taşımayan çeldirici.

    Neden kusur: bir çeldirici, öğrencinin gerçekten yaptığı bir hatayı temsil
    etmiyorsa soru ölçmez, eler. "Hangi yanılgıyı test ediyor?" sorusunun
    yazılı bir cevabı yoksa o çeldiricinin neden orada olduğunu kimse
    bilmiyordur; yanlış cevabı "neden yanlış?" diye açıklamak da
    (`distractor_sources` kaynağı bulsa bile) bir yanılgıya bağlanamaz.

    **Bu sinyal bugün HER çeldiricide yanar ve bu bir kusur değil, ölçüm.**
    `McqOption` şemasında `misconception` alanı YOK; `question_gen` üretirken
    böyle bir alan yazmıyor ve `authoring.validate_draft_payload` yeni ve
    bilinmeyen bir alanın eklenmesini reddediyor ("Soru içeriğinde tanınmayan
    alan değiştirilemez"). Yani etiket bugün yalnız doğrudan veritabanına
    yazılmış eski satırlarda bulunabilir. Sinyalin önemi bu yüzden `LOW`:
    kapıya çevrilirse tüm havuzu kırmızı yakar. Etiketi gerçekten beyan
    edilebilir kılmak `McqOption`'a alan eklemeyi gerektirir ve o başka şeridin
    dosyasıdır.
    """
    return [
        QualityFinding(
            code=FindingCode.MISSING_MISCONCEPTION,
            severity=Severity.LOW,
            message=(
                f"{option.key} çeldiricisi hangi yanılgıyı ölçtüğünü beyan etmiyor; "
                "yanlış ama rastgele bir şık soruyu ölçmez hâle getirir."
            ),
            question_id=question.question_id,
            option_key=option.key,
        )
        for option in question.distractors
        if option.misconception is None or not option.misconception.strip()
    ]


def review_options(
    question: McqView, *, length_ratio: float = DEFAULT_LENGTH_RATIO
) -> list[QualityFinding]:
    """Tek bir sorunun şık düzeyindeki tüm sinyallerini koşar.

    Sonuç önem sırasına (HIGH → MEDIUM → LOW) göre sıralanır; eşit önemde
    sinyallerin kendi içindeki sırası korunur, böylece aynı girdi her zaman aynı
    çıktıyı verir (test edilebilirlik için sıralama kararlı olmalı).
    """
    findings = [
        *_duplicate_option_findings(question),
        *_catch_all_findings(question),
        *_length_outlier_findings(question, length_ratio=length_ratio),
        *_parallelism_findings(question),
        *_misconception_findings(question),
    ]
    order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
    findings.sort(key=lambda finding: order[finding.severity])
    return findings


# ---------------------------------------------------------------------------
# 3. Yanılgı kapsaması
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MisconceptionCoverage:
    """Bir soru kümesinin yanılgı dağılımı.

    `counts` anahtarı etiketin İLK GÖRÜLEN yazımıdır, normalleştirilmiş hâli
    değil: rapor eğitmene gösterilecek ve "kaynak tutma yanilgisi" diye
    katlanmış bir metin göstermek bilgi kaybettirir. Gruplama yine
    normalleştirilmiş anahtar üzerinden yapılır, yani "Kaynak tutma yanılgısı."
    ile "kaynak tutma yanılgısı" tek satırda toplanır.
    """

    counts: Mapping[str, int]
    #: `expected` içinde verilip hiçbir çeldirici tarafından test edilmeyen etiketler.
    untested: tuple[str, ...]
    #: Etiketli çeldiricilerin `overuse_ratio`'sundan fazlasını tek başına kaplayanlar.
    overused: tuple[str, ...]
    labelled_distractors: int
    unlabelled_distractors: int
    findings: tuple[QualityFinding, ...] = field(default_factory=tuple)


def misconception_coverage(
    questions: Sequence[McqView],
    *,
    expected: Sequence[str] = (),
    overuse_ratio: float = DEFAULT_OVERUSE_RATIO,
    min_sample: int = DEFAULT_OVERUSE_MIN_SAMPLE,
) -> MisconceptionCoverage:
    """Hangi yanılgı hiç test edilmemiş, hangisi aşırı tekrar ediyor.

    Neden gerekiyor: tek tek her sorusu kusursuz olan bir havuz, KÜME olarak
    yine de kötü olabilir. Aynı yanılgıyı yirmi çeldiricide tekrarlayan bir
    havuz o tek hatayı yirmi kez ölçer, geri kalan yanılgıları hiç ölçmez;
    öğrencinin puanı bilgi profilini değil, o tek yanılgıya düşüp düşmediğini
    gösterir. Bu soru bazında görünmez, ancak toplamda görünür.

    `expected` eğitmenin ders için beyan ettiği yanılgı listesidir. Verilmezse
    `untested` boş döner — **bu bilinçli bir sessizliktir:** beklenen liste
    olmadan "hiç test edilmeyen yanılgı" diye bir küme hesaplanamaz, sadece
    "gözlenmeyen" hesaplanabilir ve ikisini karıştırmak, ölçülmemiş bir şeyi
    ölçülmüş göstermek olurdu.

    Aşırı tekrar hesabı `min_sample` altındaki örneklemde HİÇ yapılmaz; iki
    etiketli çeldiricide "biri toplamın %50'si" demek matematiksel bir
    zorunluluğu bulgu diye sunmak olurdu.

    Etiketsiz çeldiriciler `unlabelled_distractors` olarak ayrıca sayılır ve
    oranların paydasına GİRMEZ: payda "beyan edilmiş yanılgılar"dır. Bugün bu
    sayı tipik olarak çeldiricilerin tamamıdır (bkz. `_misconception_findings`),
    yani rapor çoğu havuzda "hiç etiket yok" der — ve doğru söyler.
    """
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    unlabelled = 0

    for question in questions:
        for option in question.distractors:
            raw = (option.misconception or "").strip()
            if not raw:
                unlabelled += 1
                continue
            key = text_tr.normalize(raw)
            if not key:
                unlabelled += 1
                continue
            labels.setdefault(key, raw)
            counts[key] = counts.get(key, 0) + 1

    labelled = sum(counts.values())
    findings: list[QualityFinding] = []

    untested: list[str] = []
    for label in expected:
        key = text_tr.normalize(label)
        if key and key not in counts:
            untested.append(label)
            findings.append(
                QualityFinding(
                    code=FindingCode.MISCONCEPTION_UNTESTED,
                    severity=Severity.MEDIUM,
                    message=(
                        f"'{label}' yanılgısını hiçbir çeldirici test etmiyor; "
                        "bu yanılgıya sahip öğrenci sınavda görünmez."
                    ),
                )
            )

    overused: list[str] = []
    if labelled >= min_sample:
        for key, count in counts.items():
            if count / labelled > overuse_ratio:
                overused.append(labels[key])
                findings.append(
                    QualityFinding(
                        code=FindingCode.MISCONCEPTION_OVERUSED,
                        severity=Severity.MEDIUM,
                        message=(
                            f"'{labels[key]}' yanılgısı etiketli çeldiricilerin "
                            f"{count}/{labelled}'ini kaplıyor; havuz tek bir hatayı "
                            "tekrar tekrar ölçüyor."
                        ),
                    )
                )

    return MisconceptionCoverage(
        counts={labels[key]: count for key, count in counts.items()},
        untested=tuple(untested),
        overused=tuple(overused),
        labelled_distractors=labelled,
        unlabelled_distractors=unlabelled,
        findings=tuple(findings),
    )


# ---------------------------------------------------------------------------
# Havuz raporu
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PoolReview:
    """Üç mekanizmanın tek raporu. `findings` hepsini birleşik sırada taşır."""

    findings: tuple[QualityFinding, ...]
    duplicates: tuple[DuplicatePair, ...]
    coverage: MisconceptionCoverage


def review_pool(
    questions: Sequence[McqView],
    *,
    expected_misconceptions: Sequence[str] = (),
    threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
    ngram: int = DEFAULT_NGRAM,
    length_ratio: float = DEFAULT_LENGTH_RATIO,
    overuse_ratio: float = DEFAULT_OVERUSE_RATIO,
    min_sample: int = DEFAULT_OVERUSE_MIN_SAMPLE,
) -> PoolReview:
    """Üç mekanizmayı bir havuzun tamamında koşar.

    Bir kolaylık sarmalayıcısıdır; kendi kuralı yoktur. Ayrı ayrı çağırmak da
    geçerlidir ve kapının eşiğini değiştirmek isteyen çağıran zaten öyle yapar.
    """
    duplicates = find_near_duplicates(questions, threshold=threshold, ngram=ngram)
    coverage = misconception_coverage(
        questions,
        expected=expected_misconceptions,
        overuse_ratio=overuse_ratio,
        min_sample=min_sample,
    )
    findings: list[QualityFinding] = list(duplicate_findings(duplicates))
    for question in questions:
        findings.extend(review_options(question, length_ratio=length_ratio))
    findings.extend(coverage.findings)
    return PoolReview(findings=tuple(findings), duplicates=tuple(duplicates), coverage=coverage)


__all__ = [
    "DEFAULT_DUPLICATE_THRESHOLD",
    "DEFAULT_LENGTH_RATIO",
    "DEFAULT_NGRAM",
    "DEFAULT_OVERUSE_MIN_SAMPLE",
    "DEFAULT_OVERUSE_RATIO",
    "MISCONCEPTION_KEY",
    "DuplicatePair",
    "FindingCode",
    "McqView",
    "MisconceptionCoverage",
    "OptionView",
    "PoolReview",
    "QualityFinding",
    "Severity",
    "duplicate_findings",
    "find_near_duplicates",
    "mcq_view",
    "misconception_coverage",
    "review_options",
    "review_pool",
    "similarity",
]
