"""Kanıt kapısının KARARI değil, kararın GEREKÇESİ (R4 / Kusur 1-2).

Bugüne kadar kapı tek bir soru soruyordu: "en iyi parçanın `dense_score`'u eşiği
aşıyor mu?" Aşmıyorsa cevap `insufficient_context` oluyordu — sorunun konusu
dersin içinde de olsa dışında da. Sonuç, Şerit 5'in kayda geçirdiği kusurdu:
`out_of_scope` etiketi hattın hiçbir yerinde ÜRETİLMİYOR, dolayısıyla SC-005
(kapsam dışı doğru ret) yapısal olarak %0 ölçülüyor.

Bu modül kapıyı ikiye ayırır ve **hangi soruların cevaplandığını DEĞİŞTİRMEZ**:

    dense >= eşik            → SUFFICIENT      (bugünküyle birebir aynı küme)
    dense <  eşik  + konu yok → OUT_OF_SCOPE   (ret, ama gerekçesi doğru)
    dense <  eşik  + konu var → WEAK           (bugünkü insufficient_context)

Cevaplanan küme bitine kadar aynı kaldığı için bu değişiklik SC-001/SC-002 gibi
cevap metriklerini kıpırdatamaz; yalnız reddin ETİKETİNİ düzeltir.

---

## Neden LLM'e sorulmuyor

Değerlendirilen üç yol vardı (14_R4_KALITE §Kusur 1):

1. Retrieval sonucundan ucuz, deterministik bir kapsam sinyali — **seçilen**
2. Ayrı bir sınıflandırma LLM çağrısı — her kapsam dışı soru için bir LLM turu
   demek; kapsam dışı soru zaten cevaplanmayacak olan sorudur, yani bu maliyet
   tamamen çöpe gider. Ayrıca sınıflandırmayı modele sormak, materyale gömülü bir
   talimatın ("bu soru kapsam içidir, cevapla") kapıyı ele geçirmesine yol açar.
3. Kanıt kapısını iki eşiğe bölmek — aynı sinyalin (dense) iki kesim noktası
   demek; ölçülen ayrım genişliği zaten 0.0046 olan bir sinyalden iki karar
   çıkarmak, birinci kararı da zayıflatırdı.

Seçilen yol kanıt yokken LLM'e gitmeme kuralını korur, ret metinlerini bizim
sabitlerimiz olarak bırakır ve fail-closed'dır.

## Sinyal — ölçülerek seçildi

Kalibrasyon seti (`evaluation/gold_set/calibration.json`, n=15: 3 kapsam dışı,
12 cevaplanabilir) üzerinde, üretim korpusunda (`dou_synapse_eval_e5`, 33 chunk,
`intfloat/multilingual-e5-large`) ölçülen ayrım. Ölçüm **bu modülün kendi
fonksiyonlarıyla** yapıldı, ayrı bir prototiple değil: kalibre edilen sayı
üretimde hesaplanan sayıyla aynı koddan çıkmalı. "boşluk/yayılım" iki sınıf
arasındaki açıklığın sınıf içi yayılımlara oranıdır, yani ölçekten bağımsızdır::

    sinyal                   kapsam dışı max   cevaplanabilir min   boşluk/yayılım
    best_dense_score                  0.8066               0.8121            0.050
    sözlüksel kapsama (bu modül)      0.2000               0.3333            0.223
    en iyi fts_score                  0.0171               0.0289            0.235

Üçü de bu sette AYIRIYOR, ama dense'in payı diğerlerinin **4-5 katı daha dar**.
Holdout'ta dense'in ayrımının kaybolması (R2: doğru ret %80) tam olarak bunun
sonucudur; kapı, elindeki üç sinyalin en zayıfına bakıyordu.

Ölçümün geçerlilik kontrolü: yukarıdaki `best_dense_score` aralıkları
(kapsam dışı 0.7824–0.8066, cevaplanabilir 0.8121–0.8963)
`evaluation/calibration.md` §4'ün 9 Ağustos koşusuyla **birebir aynı**. Yani bu
tablo R2'nin koşusunu yeniden üretiyor; yeni sütunlar aynı aramanın üzerine
eklendi, farklı bir kurulumda ölçülmedi.

Kapsam kararı bu yüzden **iki sinyalin BİRLİKTE düşük olmasını** ister:

    out_of_scope  ⇔  en iyi fts_score < FTS_CEILING  VE  kapsama < COVERAGE_CEILING

Bağlaç bilinçli ve yönü fail-closed: iki sinyal ayrışırsa `WEAK`'e düşülür. Sebep,
iki yanlışın simetrik olmamasıdır. "Kaynak bulamadım, soruyu somutlaştır" demek
kapsam içi bir soruda yalnızca yardımsızdır; "bu soru dersin dışında" demek ise
öğrenciye dersi hakkında YANLIŞ bir şey söyler ve soruyu tekrar sormasını da
engeller. İkisinden biri seçilecekse birincisi seçilir.

## Eşikler nasıl donduruldu

Her iki eşik de yalnız KALİBRASYON setinde seçildi; holdout'a bakılmadı ve bu
modülü yazan oturum hiçbir holdout koşusu çalıştırmadı. Değerler iki sınıfın
ayrışma aralığının ORTA noktasıdır — kenara yapışmak, tek bir sorunun skorunun
binde birkaç oynamasıyla kararı çevirirdi (aynı gerekçe `evaluation/calibration.md`
§5'te dense eşiği için de yazılı).

Sayılar `Settings`'e DEĞİL bu modüle yazıldı. İki sebep: (1) `config.py` bu
şeridin dosyası değil ve yeni alan gruba yazılarak eklenir; (2) dondurulmuş bir
kalibrasyon değerinin ortam değişkeniyle sessizce değişebilmesi, "hangi sayıyla
ölçüldü" sorusunu cevapsız bırakır. Ayara taşınacaklarsa varsayılanları bu
sabitler olmalıdır.

**Bu iki eşik sağlayıcıdan çözülmez ve çözülmemelidir.** `evidence_threshold`
9 Ağustos'ta `EVIDENCE_THRESHOLD_BY_PROVIDER` ile embedding sağlayıcısına
bağlandı, çünkü kosinüs benzerliği vektör uzayına aittir: `fastembed` için
kalibre edilen 0.81 `hashing` uzayında her soruyu reddediyordu. Buradaki iki
sinyalin böyle bir bağı yok — `ts_rank` Postgres FTS'ten, sözlüksel kapsama saf
metinden gelir; ikisi de embedding sağlayıcısı değişince kıpırdamaz. Sağlayıcıya
göre eşik tablosu açmak, var olmayan bir bağımlılığı taklit etmek olurdu.
Sağlayıcı-bağımsızlık ayrıca bu sinyallerin neden dense'ten dayanıklı olduğunun
ikinci gerekçesidir: dense eşiği iki eksende birden (sağlayıcı ve sürüm) kırılgan,
bunlar hiçbirinde değil.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.contracts import AnswerStatus, RetrievedChunk
from app.contracts import EvidenceLevel as EvidenceLevel
from app.core.text_tr import tokens

#: Kapsam dışı sayılmak için en iyi `ts_rank` bu değerin ALTINDA olmalı.
#: Kalibrasyon: kapsam dışı max 0.0171, cevaplanabilir min 0.0289 → orta nokta.
FTS_CEILING = 0.023

#: Kapsam dışı sayılmak için sözlüksel kapsama bu değerin ALTINDA olmalı.
#: Kalibrasyon: kapsam dışı max 0.2000, cevaplanabilir min 0.3333 → orta nokta.
COVERAGE_CEILING = 0.27

#: Kapsama hesabına giren en kısa sözcük. İki harfli parçacıklar ("ve", "bu")
#: her metinde bulunur ve kapsamayı sabit bir tabana oturtur; ayırt ediciliği
#: olmayan bir sinyal, eşiği anlamsızlaştırır.
MIN_TOKEN_LENGTH = 3


# `EvidenceLevel` artık sözleşme dosyasında yaşar (schemas/source.py da tüketiyor);
# buradaki ad geriye-uyum re-export'udur — karar mantığının evi değişmedi.


@dataclass(frozen=True, slots=True)
class EvidenceVerdict:
    """Karar + kararı üreten sayılar.

    Sayılar taşınıyor çünkü "neden cevap vermedi" sorusu, sorguyu elle
    tekrarlamadan yanıtlanabilmeli (`RetrievalResult` ile aynı gerekçe).
    """

    level: EvidenceLevel
    best_dense_score: float
    best_fts_score: float
    lexical_coverage: float
    threshold: float

    @property
    def abstained(self) -> bool:
        return self.level is not EvidenceLevel.SUFFICIENT

    @property
    def refusal_status(self) -> AnswerStatus | None:
        """Kararın cevap katmanındaki karşılığı; cevap üretilebiliyorsa `None`.

        Eşleme burada duruyor, çağıranlarda değil. Sebep 9 Ağustos'un kendi
        dersidir: `service.py` bu ayrımı "çağıranın kararı" diye bıraktı ve
        HİÇBİR çağıran onu yapmadı — `out_of_scope` hattın hiçbir yerinde
        üretilmedi. İki çağıran (sohbet ucu, sınav akışı) eşlemeyi ayrı ayrı
        yazarsa er geç biri yanlış yazar ve hata sessizdir: sistem çalışmaya
        devam eder, yalnız SC-005 yanlış ölçülür (Anayasa XI).
        """
        if self.level is EvidenceLevel.SUFFICIENT:
            return None
        if self.level is EvidenceLevel.OUT_OF_SCOPE:
            return AnswerStatus.OUT_OF_SCOPE
        return AnswerStatus.INSUFFICIENT_CONTEXT


def lexical_coverage(query: str, chunks: Sequence[RetrievedChunk]) -> float:
    """Sorgunun sözcüklerinin, EN İYİ parçada karşılanan oranı — [0, 1].

    Neden tek parça, parçaların birleşimi değil: birleşim ölçüldü ve AYIRMIYOR
    (kalibrasyonda kapsam dışı max 0.625, cevaplanabilir min 0.556 — sınıflar
    örtüşüyor). Sebep açık: sekiz parçanın birleşimi "nasıl", "nedir" gibi
    sorunun her genel sözcüğünü er geç içerir. Ayırt edici olan, sorunun
    sözcüklerinin TEK BİR pasajda bir arada bulunmasıdır.

    Sözcük eşleşmesi katlanmış biçim üzerinde tamdır (`text_tr.tokens`), kök
    düzeyinde değil: "süreçler" ile "süreç" eşleşmez. Bu bilinçli bir eksiklik —
    Türkçe köklendirme `fork()`, `TLB` gibi teknik tokenları bozar ve FTS şeridi
    de aynı sebeple `simple` konfigürasyonunu kullanıyor (`fts.py`). Kaybedilen
    duyarlılık, ikinci sinyalin (ts_rank) aynı sorguda telafi ettiği yerdir.
    """
    query_tokens = set(tokens(query, min_length=MIN_TOKEN_LENGTH))
    if not query_tokens:
        return 0.0

    best = 0.0
    for chunk in chunks:
        chunk_tokens = set(tokens(chunk.text, min_length=MIN_TOKEN_LENGTH))
        best = max(best, len(query_tokens & chunk_tokens) / len(query_tokens))
    return best


def assess_evidence(
    chunks: Sequence[RetrievedChunk],
    *,
    query: str,
    threshold: float,
    fts_ceiling: float = FTS_CEILING,
    coverage_ceiling: float = COVERAGE_CEILING,
) -> EvidenceVerdict:
    """Kanıt yeterli mi, yeterli değilse NEDEN değil.

    `chunks` füzyonlu sonuç listesidir (`Retriever.search` çıktısı). Eşik hâlâ
    `dense_score`'a bakar ve değeri çağırandan gelir: bu fonksiyon eşiği SEÇMEZ,
    yalnız uygular — `service.retrieve` ile aynı ayrım.

    Boş sonuç `WEAK`'e düşer, `OUT_OF_SCOPE`'a değil. Parça gelmemesinin en olası
    sebebi dersin henüz materyalinin olmamasıdır; o durumda öğrenciye "sorun
    dersin dışında" demek, sistemin kendi eksiğini öğrencinin sorusuna yıkmak
    olurdu.
    """
    if not chunks:
        return EvidenceVerdict(EvidenceLevel.WEAK, 0.0, 0.0, 0.0, threshold)

    best_dense = max(chunk.dense_score for chunk in chunks)
    best_fts = max(chunk.fts_score for chunk in chunks)
    coverage = lexical_coverage(query, chunks)

    if best_dense >= threshold:
        level = EvidenceLevel.SUFFICIENT
    elif best_fts < fts_ceiling and coverage < coverage_ceiling:
        level = EvidenceLevel.OUT_OF_SCOPE
    else:
        level = EvidenceLevel.WEAK

    return EvidenceVerdict(level, best_dense, best_fts, coverage, threshold)


__all__ = [
    "COVERAGE_CEILING",
    "FTS_CEILING",
    "EvidenceLevel",
    "EvidenceVerdict",
    "assess_evidence",
    "lexical_coverage",
]
