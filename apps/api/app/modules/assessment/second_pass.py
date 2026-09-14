"""İkinci doğrulayıcı — rubrik puanını göstermeden önce bağımsız teyit (E4).

Bugün bir rubrik puanı **tek** bir model koşusundan çıkıyor
(`grading.grade_with_llm`). O koşu şema ve dayanak kapılarından geçiyor — yani
puanın *biçimi* ve *kaynağa bağlılığı* doğrulanıyor — ama puanın kendisi tek bir
örneklemdir. Aynı cevap, aynı rubrik ve aynı kaynakla ikinci kez puanlandığında
başka bir sayı çıkabilir; öğrenci bunu göremez, çünkü gördüğü sayı görmediği bir
dağılımdan çekilmiş tek bir örnektir. Yakalanan başarısızlık tam olarak budur:
oynak bir puanın kesinmiş gibi gösterilmesi.

Bu modül ikinci, bağımsız bir değerlendirmeyi alır ve iki değerlendirmeyi
**kalem kalem** karşılaştırır. Üç sonuç vardır, ikisi puanı gizler:

| Karar | Anlamı | Puan |
|---|---|---|
| `agreed` | Her kalemde tolerans içinde | gösterilir |
| `escalate` | En az bir kalemde (ya da toplamda) tolerans aşıldı | **gösterilmez**, insana gider |
| `inconclusive` | Kullanılabilir ikinci koşu yok | **gösterilmez** |

`inconclusive`in `agreed`den ayrı tutulması bu modülün varlık nedenidir. İkinci
koşu alınamadığında "uyuştu" demek mekanizmayı sessizce tek koşuya geri
döndürürdü: ekranda iki doğrulayıcıdan geçmiş gibi duran, arkasında tek koşu olan
bir puan kalırdı. Bir doğrulayıcının en kötü arıza biçimi kapalı kalmak değil,
açık görünüp kapalı olmaktır — `grading._rubric_breakdown`in docstring'inde
anlatılan "sessizce değerlendirilemez hâle gelme" kusurunun ikizi.

**Bu modül saftır.** Sağlayıcı çağırmaz, veritabanı okumaz, ağa çıkmaz. İki
değerlendirmeyi hazır alır; ikincinin kim tarafından, hangi sağlayıcıyla, kaç
denemede üretildiği çağıranın işidir. Sebep: bir doğrulayıcının kendisi
doğrulanabilir olmalıdır — karar mantığı ağ olmadan, deterministik olarak
sınanamıyorsa ona güvenmek için bir neden yoktur.

**Kapsam: yalnız LLM ile puanlanan yol** (`essay`, `code_trace`, `bug_hunt`).
`mcq` ve `short_answer` deterministiktir; onlarda "ikinci koşu" aynı fonksiyonu
aynı girdiyle çağırmaktır ve hiçbir şey doğrulamaz. Onları buraya yönlendirmeyin:
dayanakları `evidence_chunk_id` değil `why_wrong_chunk_id` olduğu için hepsi
`inconclusive` döner ve çalışan bir yol sessizce kapanır.

**Grounding sözleşmesi ikinci koşu için de geçerlidir.** `grade_with_llm`
kaynağı doğrulanamayan bir değerlendirmeyi zaten `graded=False` yapar; burada
ayrıca `evidence_chunk_id`in dolu olması aranır. Kaynak kanıtı olmayan bir ikinci
koşu "bağımsız ikinci görüş" değildir ve `agreed` üretemez; `inconclusive` olur.
Aksi hâlde grounding kapısı, kendisini atlayan bir cevabı doğrulayıcı olarak
kabul ederdi.

**Puan ortalanmaz.** `agreed` iken gösterilen puan birincil koşununkidir. İki
sayının ortalaması, hiçbir değerlendiricinin vermediği ve hiçbir rubrik satırının
desteklemediği üçüncü bir sayı üretirdi; öğrenciye gösterilen kırılım tablosunun
toplamı da tutmazdı (Anayasa III). İkinci koşu bir hakemdir, bir ortak yazar değil.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.logging import get_logger
from app.modules.assessment.grading import GradingOutcome
from app.schemas.assessment import RubricCriterionScore, RubricItem, normalized_rubric

logger = get_logger("app.assessment.second_pass")

#: Kalibrasyon yapılmadan önceki muhafazakâr başlangıç: iki değerlendirici bir
#: kalemin kendi ölçeğinin en fazla %10'unda ayrışabilir. Bir ÖLÇÜM DEĞİLDİR,
#: bkz. `criterion_tolerance`.
DEFAULT_TOLERANCE_PERCENT = 10

#: Hem normalize edilmiş rubrik toplamının hem de rubriksiz model puanının ortak
#: ekseni. `normalized_rubric` ağırlıkları tam 100'e tamamlar, `_LlmVerdict.score`
#: da 0–100'dür; bu yüzden toplam ölçeğin genişliği her iki kipte de aynıdır.
_SCORE_SCALE = 100


class ReconcileVerdict(StrEnum):
    """Puanın gösterilip gösterilemeyeceğini belirleyen üç sonuç."""

    AGREED = "agreed"
    ESCALATE = "escalate"
    INCONCLUSIVE = "inconclusive"


class ReconcileReason(StrEnum):
    """Kararın makine-okunur gerekçesi.

    Karar üç değerlidir ama gerekçe değildir: "ikinci koşu hiç alınamadı" ile
    "ikinci koşu geldi ama dayanaksızdı" aynı kararı (puan gizlenir) verir, farklı
    onarımlar gerektirir. Birincisi sağlayıcı/kota sorunudur, ikincisi prompt ya da
    kaynak seçimi sorunudur. Tek bir `inconclusive` etiketiyle yetinilseydi bu iki
    arıza aynı sayaçta toplanır ve hangisinin arttığı görülmezdi.
    """

    AGREEMENT = "agreement"
    CRITERION_GAP = "criterion_gap"
    TOTAL_GAP = "total_gap"
    SECONDARY_MISSING = "secondary_missing"
    PRIMARY_UNGRADED = "primary_ungraded"
    SECONDARY_UNGRADED = "secondary_ungraded"
    PRIMARY_UNGROUNDED = "primary_ungrounded"
    SECONDARY_UNGROUNDED = "secondary_ungrounded"
    NOT_COMPARABLE = "not_comparable"
    INCONSISTENT_TOTAL = "inconsistent_total"


#: Öğrenciye gösterilecek metin. Hiçbirinde RAKAM YOKTUR ve bu bir üslup tercihi
#: değildir: `escalate` ve `inconclusive` durumlarında puan gizlenir, "iki koşu 30
#: puan ayrıştı" demek gizlenen sayının yarısını sızdırmak olurdu. Sayısal gerekçe
#: `Reconciliation` alanlarında durur; o eğitmen ve kayıt içindir.
_STUDENT_MESSAGES: dict[ReconcileVerdict, str] = {
    ReconcileVerdict.AGREED: "Bu cevap birbirinden bağımsız iki değerlendirmeden geçti.",
    ReconcileVerdict.ESCALATE: (
        "Bu cevabın iki bağımsız değerlendirmesi birbirini tutmadı. Puan gösterilmedi; "
        "cevabınız eğitmen incelemesine ayrıldı."
    ),
    ReconcileVerdict.INCONCLUSIVE: (
        "Bu cevap için ikinci bir değerlendirme alınamadı. Puan gösterilmedi; "
        "eğitmeninize bildirebilirsiniz."
    ),
}


def criterion_tolerance(weight: int, *, percent: int = DEFAULT_TOLERANCE_PERCENT) -> int:
    """Bir rubrik kaleminin **kendi ölçek genişliğinden** türetilmiş tolerans.

    Neden mutlak bir sabit değil: kalemin ölçek genişliği `weight`tir, yani o
    kalemden alınabilecek en yüksek puan. Sabit bir tolerans (diyelim 5 puan) iki
    ayrı yönde birden yanlış olur:

    * **Dar kalemde anlamsızdır.** Ağırlığı 5 olan bir kalemde bir değerlendirici
      "tam karşılanmış" (5), diğeri "hiç karşılanmamış" (0) derse fark 5'tir ve
      sabit eşik bunu uyum sayar. Yani birbirinin TAM TERSİ iki puanlama,
      "iki doğrulayıcı da aynı şeyi söyledi" diye geçer.
    * **Geniş kalemde absürt derecede katıdır.** Ağırlığı 60 olan bir kalemde 5
      puan, ölçeğin %8'idir; ikisi de "büyük ölçüde doğru" diyen (85 ve 95) iki
      değerlendirici insana havale edilir. Gereksiz havale de ucuz değildir: puan
      gizlenir, öğrenci bekler, eğitmenin kuyruğu gürültüyle dolar.

    Bu yüzden tolerans kalemin genişliğinin bir ORANIDIR. Oran her iki eksende de
    aynı şeyi söyler: `earned` ekseninde `percent × weight / 100`, kalemin kendi
    0–100 ekseninde ise doğrudan `percent` puan.

    Tam sayı yüzde kullanılır ve aşağı yuvarlanır (tam bölme). İkisi de bilinçli:
    kayan noktalı bir oranda `0.1 * 40` ikili tabanda 4.000000000000001 olur ve
    "tam sınırda" davranış yorumlayıcının yuvarlamasına bağlı hâle gelir — bir
    kapının sınırı yeniden üretilebilir olmalıdır. Aşağı yuvarlama ise şüpheli
    durumda toleransı büyütmemek içindir (fail-closed, Anayasa IV). Bedeli: çok dar
    kalemlerde tolerans 0'a düşer, yani ağırlığı 9 veya altı olan bir kalemde iki
    koşunun birebir aynı puanı vermesi beklenir. Bu da bilinçlidir; o kalemde her
    `earned` puanı ölçeğin en az %11'idir.

    `percent` bir POLİTİKA sayısıdır, ölçüm değildir. Gerçek eşik iki İNSAN
    değerlendiricinin aynı rubrikle aynı cevaplara verdiği puanların yayılımından
    türetilmelidir (`.ai/lane-l8.md`, "E4 eşiği": ölçüm yokken eşik yazılmaz).
    O ölçüm yapılana kadar buradaki sayı muhafazakâr bir başlangıçtır ve bu yüzden
    çağrı yerinden geçilebilir: kalibrasyon bu dosyayı değiştirmeyi gerektirmesin.
    """
    return weight * percent // 100


@dataclass(frozen=True, slots=True)
class CriterionAgreement:
    """Tek bir rubrik kaleminde iki değerlendirmenin karşılaştırması.

    `difference` ve `exceeded` saklanmaz, türetilir: üçü de alan olsaydı birbirini
    tutmayan bir üçlü kurulabilirdi ve "fark 2 ama eşiği aştı" diyen bir gerekçe
    satırı, gerekçenin kendisini okunamaz yapardı.
    """

    point: str
    weight: int
    primary_earned: int
    secondary_earned: int
    tolerance: int

    @property
    def difference(self) -> int:
        """İki koşunun bu kalemden verdiği ağırlıklı puan farkı."""
        return abs(self.primary_earned - self.secondary_earned)

    @property
    def exceeded(self) -> bool:
        """Fark, kalemin kendi toleransını aştı mı? Eşitlik AŞMA SAYILMAZ."""
        return self.difference > self.tolerance


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """Karar + makine-okunur gerekçe.

    Puan yalnız `agreed` iken `displayable_score` alanında taşınır; diğer iki
    kararda alan `None`dır. Karar ile puanın aynı nesnede ve birbirine bağlı
    doğması, "kararı okumayı unutup puanı okuma" hatasını mümkün olduğunca
    imkânsızlaştırır — puan gösterilmemesi gereken durumda ortada gösterilecek bir
    sayı yoktur.
    """

    verdict: ReconcileVerdict
    reason: ReconcileReason
    #: Kalem kalem karşılaştırma. Rubriksiz kipte boştur.
    criteria: tuple[CriterionAgreement, ...] = ()
    total_difference: int | None = None
    total_tolerance: int | None = None
    displayable_score: int | None = None
    #: İki koşu aynı chunk'a mı dayandı? Karara GİRMEZ, bkz. `reconcile`.
    same_evidence: bool | None = None
    #: `not_comparable` ve `inconsistent_total` için hangi kalemin/tarafın sorunlu
    #: olduğunu söyleyen kayıt metni.
    detail: str | None = None

    @property
    def score_is_displayable(self) -> bool:
        """Puan öğrenciye gösterilebilir mi? Yalnız `agreed` iken evet."""
        return self.verdict is ReconcileVerdict.AGREED

    @property
    def exceeded_criteria(self) -> tuple[CriterionAgreement, ...]:
        """Toleransı aşan kalemler — eğitmene "nerede ayrıştılar" sorusunun cevabı."""
        return tuple(item for item in self.criteria if item.exceeded)

    @property
    def student_message(self) -> str:
        """Öğrenciye gösterilecek Türkçe metin; hiçbir kararda puan sızdırmaz."""
        return _STUDENT_MESSAGES[self.verdict]


def _withheld(
    verdict: ReconcileVerdict,
    reason: ReconcileReason,
    *,
    criteria: tuple[CriterionAgreement, ...] = (),
    total_difference: int | None = None,
    total_tolerance: int | None = None,
    same_evidence: bool | None = None,
    detail: str | None = None,
) -> Reconciliation:
    """Puanı gizleyen kararları tek yerden üretir ve kaydeder.

    Tek giriş noktası olması, `displayable_score`un yanlışlıkla doldurulduğu bir
    dalın yazılamaması içindir: gizleyen karar, puanı taşıyamaz.
    """
    logger.info(
        "ikinci doğrulayıcı puanı göstermedi",
        extra={"context": {"verdict": str(verdict), "reason": str(reason), "detail": detail}},
    )
    return Reconciliation(
        verdict=verdict,
        reason=reason,
        criteria=criteria,
        total_difference=total_difference,
        total_tolerance=total_tolerance,
        same_evidence=same_evidence,
        detail=detail,
    )


def _rubric_is_addressable(canonical: list[RubricItem]) -> bool:
    """Ölçüt adları kırılım satırlarını kaleme bağlayabilecek kadar tekil mi?

    Kırılım satırları kaleme ADIYLA bağlanır (`grading._rubric_breakdown` de öyle
    yapar). Rubrikte boş ya da tekrar eden bir ölçüt adı varsa hangi satırın hangi
    kaleme ait olduğu belirsizdir; belirsiz bir eşleşme üzerinden "uyuştular"
    demek, karşılaştırmayı hiç yapmamakla aynı şeydir.
    """
    names = [item.point.strip().casefold() for item in canonical]
    return all(names) and len(set(names)) == len(names)


def _breakdown_problem(
    rows: list[RubricCriterionScore], canonical: list[RubricItem], *, side: str
) -> str | None:
    """Kırılımın rubriği birebir kapsayıp kapsamadığını söyler; temizse None.

    `grading._code_rubric_is_complete` ile aynı katılık, farklı yer: orada modelin
    yanıtı, burada iki koşunun kırılımları hizalanır. Eksik, fazla, tekrarlı ya da
    ağırlığı kaymış bir kırılım karşılaştırılamaz — eksik kalemi 0 sayıp devam
    etmek, ölçülmemiş bir farkı "uyum" diye raporlamak olurdu.
    """
    if len(rows) != len(canonical):
        return f"{side}: kırılım {len(rows)} kalem içeriyor, rubrikte {len(canonical)} kalem var"
    by_point = {row.point: row for row in rows}
    if len(by_point) != len(rows):
        return f"{side}: aynı kalem kırılımda birden çok kez puanlanmış"
    for item in canonical:
        row = by_point.get(item.point)
        if row is None:
            return f"{side}: rubrikteki '{item.point}' kalemi kırılımda yok"
        if row.weight != item.weight:
            return f"{side}: '{item.point}' ağırlığı {row.weight}, normalize rubrikte {item.weight}"
        if row.earned != round(row.weight * row.score / 100):
            return f"{side}: '{item.point}' kaleminde earned, weight × score / 100 ile tutmuyor"
    return None


def _total_problem(outcome: GradingOutcome, *, side: str) -> str | None:
    """Gösterilen puan, kırılım toplamına eşit mi?

    `grading.grade_with_llm` rubrik varken puanı kırılımdan TÜRETİR (FR-117), yani
    sağlam bir sonuçta bu eşitlik zaten vardır. Burada yine de aranır, çünkü bu
    modül `GradingOutcome`u nereden geldiğini bilmeden alır: elle kurulmuş ya da
    kayıttan okunurken bozulmuş bir sonuçta toplam ile satırlar ayrışabilir.
    Ayrıştığında karşılaştırılacak iki ayrı "puan" olur ve hangisinin gösterildiği
    belirsizleşir; belirsiz bir sayıyı doğrulamanın anlamı yoktur.
    """
    if not outcome.rubric_breakdown:
        return None
    earned = sum(row.earned for row in outcome.rubric_breakdown)
    if outcome.score != earned:
        return f"{side}: gösterilen puan {outcome.score}, kalem toplamı {earned}"
    return None


def reconcile(
    primary: GradingOutcome,
    secondary: GradingOutcome | None,
    *,
    rubric: list[RubricItem],
    tolerance_percent: int = DEFAULT_TOLERANCE_PERCENT,
) -> Reconciliation:
    """İki bağımsız rubrik değerlendirmesini karşılaştırır ve puanın gösterilip
    gösterilemeyeceğine karar verir.

    `secondary=None`, "ikinci koşu alınamadı" demektir (sağlayıcı hatası, kota,
    zaman aşımı): `inconclusive`. `agreed` DEĞİL — bu ayrım modülün kendisidir.

    Karşılaştırma kipini rubrik değil, iki sonucun kendisi belirler:

    * **İkisinde de kırılım var** → kalem kalem karşılaştırılır.
    * **İkisinde de kırılım yok** → yalnız toplam karşılaştırılır. Rubrik dolu olsa
      bile bu meşru bir durumdur: talimatı yok sayan bir koşu kırılımsız dönebilir
      ve `grading._rubric_breakdown` o hâlde modelin kendi `score`unu bırakır.
    * **Yalnız birinde kırılım var** → `not_comparable`. İki koşu farklı yollardan
      puanlanmıştır; kırılımsız tarafın hangi kalemden kaç puan verdiği bilinmez ve
      bilinmeyeni "uyum" saymak doğrulayıcıyı boşa çıkarır.

    Toplam farkı da bakılır ama rubrikli kipte KARARI DEĞİŞTİREMEZ ve bu bir
    gözden kaçırma değil, oranlı toleransın bir sonucudur: toplam fark, kalem
    farklarının toplamını aşamaz (üçgen eşitsizliği); kalem toleranslarının toplamı
    da tam bölme yüzünden toplam toleransını aşamaz. Yani her kalem toleransındaysa
    toplam da toleranstadır. Tersi DOĞRU DEĞİLDİR — toplamları eşit olan iki koşu
    kalem dağılımında taban tabana zıt olabilir. Karşılaştırmanın kalem düzeyinde
    yapılmasının tek sebebi budur; toplam üzerinden bakan bir doğrulayıcı o durumu
    hiç görmez. Toplam kontrolü rubriksiz kipte çalışır, orada tek eksen odur.

    İki koşunun FARKLI chunk'lara dayanması tek başına `escalate` değildir: birden
    çok okunabilir kaynak verildiğinde bağımsız iki değerlendiricinin farklı
    cümleye dayanması beklenir ve sayısal olarak aynı sonuca varmaları, aynı
    kaynağa bakıp aynı şeyi söylemelerinden daha güçlü bir teyittir. Gerçek
    ayrışma zaten puanlarda görünür. Yine de kayda geçer (`same_evidence`), çünkü
    bir havaleyi inceleyen eğitmenin ilk soracağı şey budur.

    `tolerance_percent` çağrı yerinden geçilebilir (bkz. `criterion_tolerance`).
    100 ve üstü reddedilir: tolerans kalemin tüm genişliğine eşitlenirse hiçbir
    ayrışma eşiği aşamaz, yani doğrulayıcı kapanır ama `agreed` demeye devam eder.
    Sessizce kapanan bir kapı, hiç olmayan bir kapıdan daha kötüdür.
    """
    if not 0 <= tolerance_percent < 100:
        raise ValueError("tolerance_percent 0 ile 99 arasında olmalı (100 doğrulayıcıyı kapatır).")

    if secondary is None:
        return _withheld(ReconcileVerdict.INCONCLUSIVE, ReconcileReason.SECONDARY_MISSING)

    # Grounding sözleşmesi iki tarafa da uygulanır; hangi tarafın düştüğü gerekçede
    # ayrı durur, çünkü onarımları farklıdır.
    if not primary.graded or primary.score is None:
        return _withheld(ReconcileVerdict.INCONCLUSIVE, ReconcileReason.PRIMARY_UNGRADED)
    if primary.evidence_chunk_id is None:
        return _withheld(ReconcileVerdict.INCONCLUSIVE, ReconcileReason.PRIMARY_UNGROUNDED)
    if not secondary.graded or secondary.score is None:
        return _withheld(ReconcileVerdict.INCONCLUSIVE, ReconcileReason.SECONDARY_UNGRADED)
    if secondary.evidence_chunk_id is None:
        return _withheld(ReconcileVerdict.INCONCLUSIVE, ReconcileReason.SECONDARY_UNGROUNDED)

    primary_score: int = primary.score
    secondary_score: int = secondary.score
    same_evidence = primary.evidence_chunk_id == secondary.evidence_chunk_id

    canonical = normalized_rubric(rubric)
    if canonical and not _rubric_is_addressable(canonical):
        return _withheld(
            ReconcileVerdict.INCONCLUSIVE,
            ReconcileReason.NOT_COMPARABLE,
            same_evidence=same_evidence,
            detail="rubrik ölçüt adları boş ya da tekrarlı; kırılım satırları kaleme bağlanamaz",
        )

    criteria: tuple[CriterionAgreement, ...] = ()
    if primary.rubric_breakdown or secondary.rubric_breakdown:
        problem = _breakdown_problem(primary.rubric_breakdown, canonical, side="birincil") or (
            _breakdown_problem(secondary.rubric_breakdown, canonical, side="ikincil")
        )
        if problem is not None:
            return _withheld(
                ReconcileVerdict.INCONCLUSIVE,
                ReconcileReason.NOT_COMPARABLE,
                same_evidence=same_evidence,
                detail=problem,
            )
        inconsistent = _total_problem(primary, side="birincil") or _total_problem(
            secondary, side="ikincil"
        )
        if inconsistent is not None:
            return _withheld(
                ReconcileVerdict.INCONCLUSIVE,
                ReconcileReason.INCONSISTENT_TOTAL,
                same_evidence=same_evidence,
                detail=inconsistent,
            )
        secondary_rows = {row.point: row for row in secondary.rubric_breakdown}
        criteria = tuple(
            CriterionAgreement(
                point=row.point,
                weight=row.weight,
                primary_earned=row.earned,
                secondary_earned=secondary_rows[row.point].earned,
                tolerance=criterion_tolerance(row.weight, percent=tolerance_percent),
            )
            for row in primary.rubric_breakdown
        )

    total_difference = abs(primary_score - secondary_score)
    total_tolerance = criterion_tolerance(_SCORE_SCALE, percent=tolerance_percent)

    if any(item.exceeded for item in criteria):
        return _withheld(
            ReconcileVerdict.ESCALATE,
            ReconcileReason.CRITERION_GAP,
            criteria=criteria,
            total_difference=total_difference,
            total_tolerance=total_tolerance,
            same_evidence=same_evidence,
        )
    if total_difference > total_tolerance:
        return _withheld(
            ReconcileVerdict.ESCALATE,
            ReconcileReason.TOTAL_GAP,
            criteria=criteria,
            total_difference=total_difference,
            total_tolerance=total_tolerance,
            same_evidence=same_evidence,
        )

    return Reconciliation(
        verdict=ReconcileVerdict.AGREED,
        reason=ReconcileReason.AGREEMENT,
        criteria=criteria,
        total_difference=total_difference,
        total_tolerance=total_tolerance,
        displayable_score=primary_score,
        same_evidence=same_evidence,
    )
