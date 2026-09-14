"""MCQ kalite sinyalleri — `app/modules/assessment/quality.py`.

Modül saftır (veritabanı, ağ ve LLM yok), dolayısıyla bu dosya da öyledir: tek
girdi elle kurulmuş `McqView`'lar ve ham jsonb sözlükleridir.

Dosyanın asıl işi üç şeyi kilitlemek:

1. **Her `FindingCode` yanlış pozitif kontrolüyle birlikte ölçülür.** Her kod
   için hem yakalayan hem yakalamayan bir örnek var (`TestFindingCodeKapsami`);
   kod eklendiğinde o test enum'la birlikte kırmızı yanar.
2. **Türkçe katlama gerçekten çalışıyor.** `str.lower()` iki harfte yanılır
   (i/İ ve ı/I); `TestTurkceTuzagi` tam o iki tuzağı kurar ve `lower()` temelli
   bir karşılaştırmanın kaçıracağı çiftleri modülün yakaladığını gösterir.
3. **Modülün docstring'lerindeki iddialar ölçülür.** Örneğin `mcq_view`'ın
   `parse_payload` yerine ham dict okuma gerekçesi: pydantic `misconception`
   etiketini sessizce düşürüyor. `TestMcqView` ikisini yan yana koyar.

Eşiklerin hiçbiri kalibre EDİLMEDİ; buradaki testler de onları kalibre etmez.
Sayı doğrulayan testler varsayılan eşiği değil, eşiğin **uygulanışını** ölçer
(eşik altı çift dönmez, `min_sample` altında oran hesabı açılmaz gibi).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from app.core import text_tr
from app.modules.assessment import quality
from app.modules.assessment.quality import FindingCode, Severity
from app.schemas.assessment import McqPayload

_STEM = "Kilitlenmenin dört koşulundan hangisi kaldırılırsa kilitlenme oluşmaz?"

#: Yakın-tekrar testlerinde kullanılan ikinci kök: aynı soruyu yeniden yazar.
_STEM_REWRITTEN = "Kilitlenmenin dört koşulundan hangisinin kaldırılması kilitlenmeyi önler?"

#: Aynı havuzda duran, konusu tamamen başka bir kök.
_STEM_OTHER = "Sayfalama tablosunda TLB isabetsizliği hangi ek maliyeti doğurur?"


def _option(
    key: str, text: str, misconception: str | None = "kaynak sırası yanılgısı"
) -> quality.OptionView:
    """Varsayılanı ETİKETLİ şıktır; aksi belirtilmedikçe (e) sinyali susar."""
    return quality.OptionView(key=key, text=text, misconception=misconception)


def _view(
    options: list[quality.OptionView],
    *,
    answer_key: str = "A",
    stem: str = _STEM,
    question_id: str = "q1",
) -> quality.McqView:
    return quality.McqView(
        question_id=question_id, stem=stem, options=tuple(options), answer_key=answer_key
    )


def _option_codes(question: quality.McqView, **kwargs: Any) -> list[FindingCode]:
    return [finding.code for finding in quality.review_options(question, **kwargs)]


def _pool_codes(questions: list[quality.McqView], **kwargs: Any) -> list[FindingCode]:
    return [finding.code for finding in quality.review_pool(questions, **kwargs).findings]


def _neutral(key: str, text: str) -> quality.OptionView:
    """Hiçbir sinyali tetiklemeyen dolgu şıkkı: etiketli, ad öbeği, orta uzunlukta."""
    return _option(key, text)


# ---------------------------------------------------------------------------
# Her kod için yakalayan/yakalamayan örnek
# ---------------------------------------------------------------------------


def _duplicate_option_case(*, broken: bool) -> list[FindingCode]:
    ikinci = "işlem tablosu." if broken else "Sayfa tablosu"
    return _option_codes(
        _view(
            [
                _neutral("A", "İŞLEM Tablosu"),
                _neutral("B", ikinci),
                _neutral("C", "Kesme vektörü"),
                _neutral("D", "Yığın çerçevesi"),
            ],
            answer_key="C",
        )
    )


def _catch_all_case(*, broken: bool) -> list[FindingCode]:
    dorduncu = "Yukarıdakilerin hepsi" if broken else "Yukarıdaki ilk koşul"
    return _option_codes(
        _view(
            [
                _neutral("A", "Karşılıklı dışlama"),
                _neutral("B", "Döngüsel bekleme"),
                _neutral("C", "Elde tutma ve bekleme"),
                _neutral("D", dorduncu),
            ],
            answer_key="A",
        )
    )


def _length_outlier_case(*, broken: bool) -> list[FindingCode]:
    dogru = (
        "Kaynak grafiğinde bir çevrim bulunması ve dört koşulun aynı anda sağlanması gerekir"
        if broken
        else "Kaynak grafiğinde çevrim bulunması"
    )
    return _option_codes(
        _view(
            [
                _neutral("A", dogru),
                _neutral("B", "Kaynak grafiğinde çevrim olmaması"),
                _neutral("C", "Kaynak sayısının süreçten azlığı"),
                _neutral("D", "Süreç sayısının kaynaktan çokluğu"),
            ],
            answer_key="A",
        )
    )


def _parallelism_case(*, broken: bool) -> list[FindingCode]:
    birinci = "Süreç kaynağı bekler" if broken else "Karşılıklı dışlama"
    return _option_codes(
        _view(
            [
                _neutral("A", birinci),
                _neutral("B", "Döngüsel bekleme"),
                _neutral("C", "Elde tutma"),
                _neutral("D", "Kesintisizlik"),
            ],
            answer_key="B",
        )
    )


def _missing_misconception_case(*, broken: bool) -> list[FindingCode]:
    etiket = None if broken else "çevrim yanılgısı"
    return _option_codes(
        _view(
            [
                _neutral("A", "Karşılıklı dışlama"),
                _option("B", "Döngüsel bekleme", etiket),
                _neutral("C", "Elde tutma"),
                _neutral("D", "Kesintisizlik"),
            ],
            answer_key="A",
        )
    )


def _near_duplicate_case(*, broken: bool) -> list[FindingCode]:
    ikinci_kok = _STEM_REWRITTEN if broken else _STEM_OTHER
    pair = [
        _view([_neutral("A", "Döngüsel bekleme"), _neutral("B", "Elde tutma")], question_id="q1"),
        _view(
            [_neutral("A", "Döngüsel bekleme"), _neutral("B", "Elde tutma")],
            stem=ikinci_kok,
            question_id="q2",
        ),
    ]
    return _pool_codes(pair)


def _untested_case(*, broken: bool) -> list[FindingCode]:
    beklenen = "açlık yanılgısı" if broken else "çevrim yanılgısı"
    havuz = [
        _view(
            [
                _neutral("A", "Karşılıklı dışlama"),
                _option("B", "Döngüsel bekleme", "çevrim yanılgısı"),
            ],
            answer_key="A",
        )
    ]
    return _pool_codes(havuz, expected_misconceptions=[beklenen])


def _overused_case(*, broken: bool) -> list[FindingCode]:
    etiketler = (
        ["çevrim yanılgısı", "çevrim yanılgısı", "çevrim yanılgısı", "açlık yanılgısı"]
        if broken
        else ["çevrim yanılgısı", "açlık yanılgısı", "tutma yanılgısı", "kesinti yanılgısı"]
    )
    havuz = [
        _view(
            [
                _neutral("A", "Karşılıklı dışlama"),
                _option("B", "Döngüsel bekleme", etiketler[0]),
                _option("C", "Elde tutma", etiketler[1]),
            ],
            answer_key="A",
            question_id="q1",
        ),
        _view(
            [
                _neutral("A", "Kesintisizlik"),
                _option("B", "Kaynak paylaşımı", etiketler[2]),
                _option("C", "Öncelik tersinmesi", etiketler[3]),
            ],
            answer_key="A",
            stem=_STEM_OTHER,
            question_id="q2",
        ),
    ]
    return _pool_codes(havuz, min_sample=4)


_CODE_CASES: dict[FindingCode, Callable[..., list[FindingCode]]] = {
    FindingCode.DUPLICATE_OPTION: _duplicate_option_case,
    FindingCode.CATCH_ALL_OPTION: _catch_all_case,
    FindingCode.ANSWER_LENGTH_OUTLIER: _length_outlier_case,
    FindingCode.PARALLELISM_BREAK: _parallelism_case,
    FindingCode.MISSING_MISCONCEPTION: _missing_misconception_case,
    FindingCode.NEAR_DUPLICATE_QUESTION: _near_duplicate_case,
    FindingCode.MISCONCEPTION_UNTESTED: _untested_case,
    FindingCode.MISCONCEPTION_OVERUSED: _overused_case,
}


class TestFindingCodeKapsami:
    def test_her_kod_icin_hem_yakalayan_hem_yakalamayan_ornek_var(self) -> None:
        """Sekiz kodun sekizi de ölçülür ve hiçbiri temiz girdide yanmaz.

        İkinci yarısı (yakalamayan örnek) asıl değerli olan: bir sinyal her
        girdide yanıyorsa kuyruğu sıralamaz, yalnız uzatır.
        """
        assert set(_CODE_CASES) == set(FindingCode)
        for code, case in _CODE_CASES.items():
            assert code in case(broken=True), f"{code} bozuk örnekte yakalanmadı"
            assert code not in case(broken=False), f"{code} temiz örnekte yanlış yandı"


# ---------------------------------------------------------------------------
# mcq_view
# ---------------------------------------------------------------------------


class TestMcqView:
    def test_yanilgi_etiketi_ham_dictten_okunur_pydantic_onu_dusurur(self) -> None:
        """Modül docstring'inin "neden ham dict" gerekçesi burada kilitlenir.

        `McqOption` `misconception` alanını TANIMIYOR; pydantic bilinmeyen alanı
        sessizce atar. `mcq_view` `parse_payload` kullansaydı (e) sinyalinin
        ölçecek verisi kalmazdı. Bu test ikisini yan yana koyar: aynı payload,
        iki farklı okuma.
        """
        payload: dict[str, Any] = {
            "stem": _STEM,
            "options": [
                {
                    "key": "A",
                    "text": "Döngüsel bekleme",
                    "misconception": "kaynak sırası yanılgısı",
                },
                {"key": "B", "text": "Karşılıklı dışlama", "misconception": "paylaşım yanılgısı"},
            ],
            "answer_key": "A",
            "distractor_sources": {"B": "11111111-1111-4111-8111-111111111111"},
        }

        parsed = McqPayload.model_validate(payload)
        assert "misconception" not in parsed.options[1].model_dump()

        view = quality.mcq_view(payload, question_id="q9")
        assert view.options[1].misconception == "paylaşım yanılgısı"
        assert view.question_id == "q9"
        assert view.stem == _STEM
        assert view.answer_key == "A"

    def test_okunamayan_payload_bos_gorunum_yerine_hata_verir(self) -> None:
        """Sıfır şıklı görünüm "kusur bulunamadı" yalanı üretirdi."""
        for bozuk in ({}, {"options": []}, {"options": "A, B, C"}, {"options": [None]}):
            with pytest.raises(ValueError):
                quality.mcq_view(bozuk)

    def test_eksik_alanlar_bos_dizeye_duser_metin_olmayan_etiket_yok_sayilir(self) -> None:
        view = quality.mcq_view({"options": [{"key": "A"}, {"text": "x", "misconception": 42}]})
        assert view.stem == ""
        assert view.answer_key == ""
        assert view.options[0].text == ""
        assert view.options[1].key == ""
        assert view.options[1].misconception is None

    def test_dogru_sik_bulunamayinca_analiz_dusmez(self) -> None:
        """Şemadan geçmemiş eski satır `KeyError` değil, sessiz atlama üretmeli."""
        view = _view([_neutral("A", "Bir"), _neutral("B", "İki")], answer_key="Z")
        assert view.correct is None
        assert [option.key for option in view.distractors] == ["A", "B"]
        assert _option_codes(view) == []

    def test_dogru_sik_ve_celdiriciler_ayrilir(self) -> None:
        view = _view([_neutral("A", "Bir"), _neutral("B", "İki"), _neutral("C", "Üç")])
        assert view.correct is not None
        assert view.correct.key == "A"
        assert [option.key for option in view.distractors] == ["B", "C"]


# ---------------------------------------------------------------------------
# similarity
# ---------------------------------------------------------------------------


class TestSimilarity:
    def test_ayni_metin_tam_benzerlik_verir(self) -> None:
        assert quality.similarity(_STEM, _STEM) == 1.0

    def test_tamamen_farkli_metinler_dusuk_benzerlik_verir(self) -> None:
        skor = quality.similarity(_STEM, _STEM_OTHER)
        assert 0.0 < skor < 0.2

    def test_bos_metin_cokmez_ve_sifira_bolme_uretmez(self) -> None:
        """Boş/noktalamadan ibaret kök normalleştirilince hiç n-gram bırakmaz.

        Bölen sıfır olur; fonksiyon `ZeroDivisionError` değil 0.0 döndürmeli.
        """
        assert quality.similarity("", "") == 0.0
        assert quality.similarity("", _STEM) == 0.0
        assert quality.similarity(_STEM, "") == 0.0
        assert quality.similarity("...", "!!!") == 0.0
        assert quality.similarity("   ", "   ") == 0.0

    def test_ngramdan_kisa_metin_tek_ngrama_iner(self) -> None:
        """n'den kısa kök tek parçaya indirgenir: eşitse 1.0, değilse 0.0.

        Ara değer YOKTUR — `similarity`'nin docstring'indeki "çok kısa kökün
        skoru anlamsızlaşır" uyarısı tam olarak bu davranıştır.
        """
        assert quality.similarity("ab", "ab", ngram=3) == 1.0
        assert quality.similarity("ab", "cd", ngram=3) == 0.0
        assert quality.similarity("ab", "abc", ngram=3) == 0.0

    def test_ngram_uzunlugu_skoru_degistirir(self) -> None:
        """n bir parametredir ve gerçekten kullanılır (sabite kaçmıyor)."""
        assert quality.similarity(_STEM, _STEM_REWRITTEN, ngram=3) != quality.similarity(
            _STEM, _STEM_REWRITTEN, ngram=6
        )


# ---------------------------------------------------------------------------
# Türkçe tuzağı
# ---------------------------------------------------------------------------


class TestTurkceTuzagi:
    def test_lower_iki_harfte_yaniliyor_olmasa_bu_dosya_gereksizdi(self) -> None:
        """Tuzağın var olduğunu önce kanıtla, sonra kapandığını göster."""
        assert "İŞLEM".lower() != "işlem"  # i + U+0307 birleşik nokta
        assert "ISI".lower() != "ısı".lower()  # I → i, Türkçede ı olmalı

    def test_lower_in_kacirdigi_sik_cifti_duplicate_olarak_yakalanir(self) -> None:
        """ "İŞLEM Tablosu" ile "işlem tablosu." şık olarak AYNIDIR.

        `str.lower()` temelli bir karşılaştırma ikisini ayrı sayardı; `text_tr`
        i/İ'yi elle eşlediği için ikisi de "islem tablosu" olur.
        """
        sol, sag = "İŞLEM Tablosu", "işlem tablosu."
        assert sol.lower() != sag.lower()
        assert text_tr.normalize(sol) == text_tr.normalize(sag)

        findings = quality.review_options(
            _view(
                [
                    _neutral("A", sol),
                    _neutral("B", sag),
                    _neutral("C", "Kesme vektörü"),
                    _neutral("D", "Yığın çerçevesi"),
                ],
                answer_key="C",
            )
        )
        duplicates = [f for f in findings if f.code is FindingCode.DUPLICATE_OPTION]
        assert len(duplicates) == 1
        assert duplicates[0].option_key == "B"
        assert duplicates[0].related_key == "A"
        assert duplicates[0].severity is Severity.HIGH

    def test_isi_ve_ISI_ayni_sik_sayilir(self) -> None:
        """ı/I tuzağı: "ISI" ile "ısı" aynı sözcüktür, `lower()` ayırırdı."""
        codes = _option_codes(
            _view(
                [
                    _neutral("A", "ISI"),
                    _neutral("B", "ısı"),
                    _neutral("C", "Basınç"),
                    _neutral("D", "Hacim"),
                ],
                answer_key="C",
            )
        )
        assert FindingCode.DUPLICATE_OPTION in codes

    def test_benzerlik_buyuk_kucuk_harf_farkindan_etkilenmez(self) -> None:
        """Aynı kök, biri tamamen büyük harfle yazılmış: skor 1.0 olmalı.

        `lower()` temelli saf bir karakter n-gram'ı aynı çiftte 1.0'ın çok
        altında kalır; farkı burada sayıyla gösteriyoruz.
        """
        buyuk = "İŞLETİM SİSTEMİ ÇEKİRDEĞİ NEDİR?"
        kucuk = "işletim sistemi çekirdeği nedir?"
        assert quality.similarity(buyuk, kucuk) == 1.0

        naive_sol = {buyuk.lower()[i : i + 3] for i in range(len(buyuk) - 2)}
        naive_sag = {kucuk.lower()[i : i + 3] for i in range(len(kucuk) - 2)}
        naive = len(naive_sol & naive_sag) / len(naive_sol | naive_sag)
        assert naive < 0.5

    def test_yanilgi_etiketleri_yazim_farkina_ragmen_tek_satirda_toplanir(self) -> None:
        """ "Kaynak tutma yanılgısı." ile "kaynak tutma yanilgisi" tek etikettir.

        Gösterilen ad İLK GÖRÜLEN yazımdır; katlanmış hâli eğitmene gösterilmez.
        """
        havuz = [
            _view(
                [
                    _neutral("A", "Doğru şık"),
                    _option("B", "Bir", "Kaynak tutma yanılgısı."),
                    _option("C", "İki", "kaynak tutma yanilgisi"),
                ],
                answer_key="A",
            )
        ]
        coverage = quality.misconception_coverage(havuz)
        assert coverage.counts == {"Kaynak tutma yanılgısı.": 2}
        assert coverage.labelled_distractors == 2


# ---------------------------------------------------------------------------
# find_near_duplicates / duplicate_findings
# ---------------------------------------------------------------------------


class TestFindNearDuplicates:
    def test_esik_alti_cift_dondurulmez(self) -> None:
        havuz = [
            _view([_neutral("A", "Bir")], question_id="q1"),
            _view([_neutral("A", "Bir")], stem=_STEM_REWRITTEN, question_id="q2"),
        ]
        skor = quality.similarity(_STEM, _STEM_REWRITTEN)
        assert quality.find_near_duplicates(havuz, threshold=skor - 0.01) != []
        assert quality.find_near_duplicates(havuz, threshold=skor + 0.01) == []

    def test_ayni_soru_kendisiyle_eslesmez(self) -> None:
        """Tek soruluk havuzda çift yoktur; eşik 0 olsa bile."""
        tek = [_view([_neutral("A", "Bir")], question_id="q1")]
        assert quality.find_near_duplicates(tek, threshold=0.0) == []

    def test_n_soru_icin_cift_sayisi_dogru(self) -> None:
        """Eşik 0 iken sonuç n(n-1)/2 çift olmalı; köşegen ve tekrar yok."""
        havuz = [
            _view([_neutral("A", "Bir")], stem=f"{_STEM} {index}", question_id=f"q{index}")
            for index in range(4)
        ]
        pairs = quality.find_near_duplicates(havuz, threshold=0.0)
        assert len(pairs) == 6
        assert {(pair.left_id, pair.right_id) for pair in pairs} == {
            ("q0", "q1"),
            ("q0", "q2"),
            ("q0", "q3"),
            ("q1", "q2"),
            ("q1", "q3"),
            ("q2", "q3"),
        }

    def test_sonuc_skora_gore_azalan_siralanir(self) -> None:
        havuz = [
            _view([_neutral("A", "Bir")], question_id="q1"),
            _view([_neutral("A", "Bir")], stem=_STEM_OTHER, question_id="q2"),
            _view([_neutral("A", "Bir")], stem=_STEM_REWRITTEN, question_id="q3"),
        ]
        pairs = quality.find_near_duplicates(havuz, threshold=0.0)
        skorlar = [pair.score for pair in pairs]
        assert skorlar == sorted(skorlar, reverse=True)
        assert (pairs[0].left_id, pairs[0].right_id) == ("q1", "q3")

    def test_yalniz_kok_karsilastirilir_siklar_degil(self) -> None:
        """Şıkları tamamen farklı ama kökü aynı iki soru yine de kopyadır."""
        havuz = [
            _view(
                [_neutral("A", "Döngüsel bekleme"), _neutral("B", "Elde tutma")], question_id="q1"
            ),
            _view(
                [_neutral("A", "Sayfa hatası"), _neutral("B", "Yığın taşması")], question_id="q2"
            ),
        ]
        pairs = quality.find_near_duplicates(havuz)
        assert len(pairs) == 1
        assert pairs[0].score == 1.0

    def test_bos_havuz_cift_uretmez(self) -> None:
        assert quality.find_near_duplicates([], threshold=0.0) == []


class TestDuplicateFindings:
    def test_cift_bulguya_cevrilir_ve_karsi_uc_saklanir(self) -> None:
        pair = quality.DuplicatePair(left_id="q1", right_id="q2", score=0.6)
        (finding,) = quality.duplicate_findings([pair])
        assert finding.code is FindingCode.NEAR_DUPLICATE_QUESTION
        assert finding.severity is Severity.MEDIUM
        assert finding.question_id == "q1"
        assert finding.related_key == "q2"
        assert "q2" in finding.message
        assert "%60" in finding.message

    def test_kimliksiz_cift_mesaji_bos_kimlik_gostermez(self) -> None:
        pair = quality.DuplicatePair(left_id="", right_id="", score=1.0)
        (finding,) = quality.duplicate_findings([pair])
        assert "başka bir soru" in finding.message

    def test_bos_cift_listesi_bos_bulgu_verir(self) -> None:
        assert quality.duplicate_findings([]) == []


# ---------------------------------------------------------------------------
# Şık düzeyi sinyalleri
# ---------------------------------------------------------------------------


class TestDuplicateOption:
    def test_ucuncu_ayni_sik_de_ilk_sikka_baglanir(self) -> None:
        findings = [
            finding
            for finding in quality.review_options(
                _view(
                    [
                        _neutral("A", "Döngüsel bekleme"),
                        _neutral("B", "döngüsel bekleme."),
                        _neutral("C", "DÖNGÜSEL BEKLEME"),
                        _neutral("D", "Elde tutma"),
                    ],
                    answer_key="D",
                )
            )
            if finding.code is FindingCode.DUPLICATE_OPTION
        ]
        assert [(f.option_key, f.related_key) for f in findings] == [("B", "A"), ("C", "A")]

    def test_bos_siklar_birbirinin_kopyasi_sayilmaz(self) -> None:
        """Normalleştirilince boşalan iki şık "aynı metin" diye raporlanmaz."""
        codes = _option_codes(
            _view(
                [
                    _neutral("A", "Döngüsel bekleme"),
                    _neutral("B", "..."),
                    _neutral("C", "!!!"),
                    _neutral("D", "Elde tutma"),
                ],
                answer_key="A",
            )
        )
        assert FindingCode.DUPLICATE_OPTION not in codes


class TestCatchAllOption:
    def test_dogru_sik_kapsayiciysa_mesaj_bunu_ayrica_soyler(self) -> None:
        findings = quality.review_options(
            _view(
                [
                    _neutral("A", "Karşılıklı dışlama"),
                    _neutral("B", "Döngüsel bekleme"),
                    _neutral("C", "Elde tutma"),
                    _neutral("D", "Yukarıdakilerin hepsi"),
                ],
                answer_key="D",
            )
        )
        (catch,) = [f for f in findings if f.code is FindingCode.CATCH_ALL_OPTION]
        assert catch.option_key == "D"
        assert catch.severity is Severity.MEDIUM
        assert "eleme ile bulabilir" in catch.message

    def test_celdirici_kapsayiciysa_mesaj_daha_yumusak(self) -> None:
        findings = quality.review_options(
            _view(
                [
                    _neutral("A", "Karşılıklı dışlama"),
                    _neutral("B", "Döngüsel bekleme"),
                    _neutral("C", "Elde tutma"),
                    _neutral("D", "Hiçbiri"),
                ],
                answer_key="A",
            )
        )
        (catch,) = [f for f in findings if f.code is FindingCode.CATCH_ALL_OPTION]
        assert catch.option_key == "D"
        assert "sınav tekniğini ölçer" in catch.message

    def test_belirtecler_katlanmis_yazimla_da_eslesir(self) -> None:
        """ "Tümü"/"Tamamı" aksanlı yazılır, karşılaştırma tarafı ASCII'dir."""
        for metin in ("Yukarıdakilerin tümü", "Seçeneklerin tamamı", "HİÇBİRİ"):
            codes = _option_codes(
                _view(
                    [
                        _neutral("A", "Karşılıklı dışlama"),
                        _neutral("B", "Döngüsel bekleme"),
                        _neutral("C", "Elde tutma"),
                        _neutral("D", metin),
                    ],
                    answer_key="A",
                )
            )
            assert FindingCode.CATCH_ALL_OPTION in codes, metin


class TestAnswerLengthOutlier:
    def test_asiri_uzun_dogru_sik_yakalanir(self) -> None:
        findings = quality.review_options(
            _view(
                [
                    _neutral(
                        "A",
                        "Kaynak grafiğinde bir çevrim bulunması ve dört koşulun aynı anda "
                        "sağlanması gerekir",
                    ),
                    _neutral("B", "Kaynak grafiğinde çevrim olmaması"),
                    _neutral("C", "Kaynak sayısının süreçten azlığı"),
                    _neutral("D", "Süreç sayısının kaynaktan çokluğu"),
                ],
                answer_key="A",
            )
        )
        (outlier,) = [f for f in findings if f.code is FindingCode.ANSWER_LENGTH_OUTLIER]
        assert outlier.option_key == "A"
        assert "en uzun çeldirici" in outlier.message

    def test_asiri_kisa_dogru_sik_da_yakalanir(self) -> None:
        findings = quality.review_options(
            _view(
                [
                    _neutral("A", "Çevrim"),
                    _neutral("B", "Kaynak grafiğinde çevrim bulunması gerekir"),
                    _neutral("C", "Kaynak grafiğinde çevrim olmaması gerekir"),
                    _neutral("D", "Kaynak grafiğinde iki çevrim olması gerekir"),
                ],
                answer_key="A",
            )
        )
        (outlier,) = [f for f in findings if f.code is FindingCode.ANSWER_LENGTH_OUTLIER]
        assert outlier.option_key == "A"
        assert "en kısa çeldirici" in outlier.message

    def test_oran_esigi_gercekten_uygulanir(self) -> None:
        """Aynı soru, yalnız `length_ratio` değişiyor: sinyal açılıp kapanmalı."""
        question = _view(
            [
                _neutral("A", "Kaynak grafiğinde bir çevrim bulunması gerekir"),
                _neutral("B", "Çevrim yoktur"),
                _neutral("C", "Kaynak azdır"),
                _neutral("D", "Süreç azdır"),
            ],
            answer_key="A",
        )
        assert FindingCode.ANSWER_LENGTH_OUTLIER in _option_codes(question, length_ratio=1.5)
        assert FindingCode.ANSWER_LENGTH_OUTLIER not in _option_codes(question, length_ratio=9.0)

    def test_tek_celdiricide_aykirilik_hesaplanmaz(self) -> None:
        """İki şıktan biri kaçınılmaz olarak uzundur; bu bir bulgu değildir."""
        codes = _option_codes(
            _view(
                [
                    _neutral("A", "Kaynak grafiğinde bir çevrim bulunması gerektiği için oluşur"),
                    _neutral("B", "Yok"),
                ],
                answer_key="A",
            )
        )
        assert FindingCode.ANSWER_LENGTH_OUTLIER not in codes


class TestParallelismBreak:
    def test_fiille_biten_tek_sik_yakalanir(self) -> None:
        findings = quality.review_options(
            _view(
                [
                    _neutral("A", "Süreç kaynağı bekler"),
                    _neutral("B", "Döngüsel bekleme"),
                    _neutral("C", "Elde tutma"),
                    _neutral("D", "Kesintisizlik"),
                ],
                answer_key="B",
            )
        )
        (odd,) = [f for f in findings if f.code is FindingCode.PARALLELISM_BREAK]
        assert odd.option_key == "A"
        assert odd.severity is Severity.LOW
        assert "fiille biten tek şık" in odd.message

    def test_fiille_bitmeyen_tek_sik_da_yakalanir(self) -> None:
        findings = quality.review_options(
            _view(
                [
                    _neutral("A", "Süreç kaynağı bekler"),
                    _neutral("B", "Süreç kaynağı bırakır"),
                    _neutral("C", "Süreç kaynağı ister"),
                    _neutral("D", "Karşılıklı dışlama"),
                ],
                answer_key="A",
            )
        )
        (odd,) = [f for f in findings if f.code is FindingCode.PARALLELISM_BREAK]
        assert odd.option_key == "D"
        assert "fiille bitmeyen tek şık" in odd.message

    def test_iki_sik_ayrisinca_aykiri_diye_bir_sey_yoktur(self) -> None:
        codes = _option_codes(
            _view(
                [
                    _neutral("A", "Süreç kaynağı bekler"),
                    _neutral("B", "Kaynak sayısı azalır"),
                    _neutral("C", "Karşılıklı dışlama"),
                    _neutral("D", "Döngüsel bekleme"),
                ],
                answer_key="C",
            )
        )
        assert FindingCode.PARALLELISM_BREAK not in codes

    def test_uc_siktan_azinda_hic_bakilmaz(self) -> None:
        codes = _option_codes(
            _view(
                [_neutral("A", "Süreç kaynağı bekler"), _neutral("B", "Döngüsel bekleme")],
                answer_key="B",
            )
        )
        assert FindingCode.PARALLELISM_BREAK not in codes


class TestMissingMisconception:
    def test_etiketsiz_ve_bos_etiketli_celdiriciler_yakalanir(self) -> None:
        """`None` ile `"   "` ayrı saklanır ama ikisi de eksik sayılır."""
        findings = quality.review_options(
            _view(
                [
                    _neutral("A", "Karşılıklı dışlama"),
                    _option("B", "Döngüsel bekleme", None),
                    _option("C", "Elde tutma", "   "),
                    _option("D", "Kesintisizlik", "kesinti yanılgısı"),
                ],
                answer_key="A",
            )
        )
        eksik = [f for f in findings if f.code is FindingCode.MISSING_MISCONCEPTION]
        assert [f.option_key for f in eksik] == ["B", "C"]
        assert all(f.severity is Severity.LOW for f in eksik)

    def test_dogru_sikkin_etiketsizligi_bulgu_degil(self) -> None:
        """Yanılgı etiketi çeldiricinin işidir; doğru şıkkın yanılgısı yoktur."""
        codes = _option_codes(
            _view(
                [
                    _option("A", "Karşılıklı dışlama", None),
                    _option("B", "Döngüsel bekleme", "çevrim yanılgısı"),
                    _option("C", "Elde tutma", "tutma yanılgısı"),
                ],
                answer_key="A",
            )
        )
        assert FindingCode.MISSING_MISCONCEPTION not in codes


class TestReviewOptions:
    def test_bulgular_onem_sirasina_gore_gelir(self) -> None:
        """HIGH → MEDIUM → LOW; eşit önemde girdi sırası korunur."""
        findings = quality.review_options(
            _view(
                [
                    _neutral("A", "İŞLEM Tablosu"),
                    _neutral("B", "işlem tablosu."),
                    _neutral("C", "Yukarıdakilerin hepsi"),
                    _option("D", "Sayfa hatası oluşur", None),
                ],
                answer_key="A",
            )
        )
        siralar = [
            {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}[f.severity] for f in findings
        ]
        assert siralar == sorted(siralar)
        assert {f.severity for f in findings} == {Severity.HIGH, Severity.MEDIUM, Severity.LOW}

    def test_temiz_soru_hic_bulgu_uretmez(self) -> None:
        """Beş sinyalin beşi de susabiliyor olmalı, yoksa kuyruk anlamsızlaşır."""
        assert (
            _option_codes(
                _view(
                    [
                        _neutral("A", "Döngüsel bekleme"),
                        _neutral("B", "Karşılıklı dışlama"),
                        _neutral("C", "Elde tutma ve bekleme"),
                        _neutral("D", "Kesintisizlik ilkesi"),
                    ],
                    answer_key="A",
                )
            )
            == []
        )

    def test_bulgular_soru_kimligini_tasir(self) -> None:
        findings = quality.review_options(
            _view(
                [
                    _neutral("A", "İŞLEM Tablosu"),
                    _neutral("B", "işlem tablosu."),
                    _neutral("C", "Kesme vektörü"),
                ],
                answer_key="C",
                question_id="q42",
            )
        )
        assert findings
        assert all(finding.question_id == "q42" for finding in findings)


# ---------------------------------------------------------------------------
# misconception_coverage
# ---------------------------------------------------------------------------


def _labelled_pool(etiketler: list[str]) -> list[quality.McqView]:
    """Her etiket için bir çeldirici taşıyan tek soruluk havuz."""
    options = [_neutral("A", "Doğru şık")]
    options += [
        _option(chr(ord("B") + index), f"Çeldirici {index}", etiket)
        for index, etiket in enumerate(etiketler)
    ]
    return [_view(options, answer_key="A")]


class TestMisconceptionCoverage:
    def test_min_sample_altinda_asiri_kullanim_iddia_edilmez(self) -> None:
        """4 etiketli çeldiricide 3/4 = %75; yine de `overused` boş kalmalı.

        Küçük örneklemde oran gürültüdür: iddia matematiksel olarak kaçınılmaz
        olur ve rapor ölçmediği bir şeyi ölçmüş gibi gösterirdi.
        """
        havuz = _labelled_pool(["çevrim", "çevrim", "çevrim", "açlık"])
        coverage = quality.misconception_coverage(havuz, min_sample=5)
        assert coverage.labelled_distractors == 4
        assert coverage.overused == ()
        assert coverage.findings == ()

    def test_min_sample_ustunde_asiri_kullanim_raporlanir(self) -> None:
        havuz = _labelled_pool(["çevrim", "çevrim", "çevrim", "açlık"])
        coverage = quality.misconception_coverage(havuz, min_sample=4)
        assert coverage.overused == ("çevrim",)
        (finding,) = coverage.findings
        assert finding.code is FindingCode.MISCONCEPTION_OVERUSED
        assert finding.severity is Severity.MEDIUM
        assert "3/4" in finding.message

    def test_oran_esigi_gercekten_uygulanir(self) -> None:
        havuz = _labelled_pool(["çevrim", "çevrim", "açlık", "tutma"])
        assert quality.misconception_coverage(havuz, min_sample=4, overuse_ratio=0.4).overused == (
            "çevrim",
        )
        assert quality.misconception_coverage(havuz, min_sample=4, overuse_ratio=0.9).overused == ()

    def test_beklenen_ama_hic_kullanilmayan_etiket_untested_icinde_cikar(self) -> None:
        havuz = _labelled_pool(["çevrim yanılgısı"])
        coverage = quality.misconception_coverage(
            havuz, expected=["çevrim yanılgısı", "Açlık Yanılgısı"]
        )
        assert coverage.untested == ("Açlık Yanılgısı",)
        (finding,) = coverage.findings
        assert finding.code is FindingCode.MISCONCEPTION_UNTESTED
        assert "Açlık Yanılgısı" in finding.message

    def test_beklenen_liste_verilmezse_untested_bilincli_olarak_bos_kalir(self) -> None:
        """ "Gözlenmeyen" ile "test edilmeyen" aynı şey değildir."""
        coverage = quality.misconception_coverage(_labelled_pool(["çevrim"]))
        assert coverage.untested == ()
        assert coverage.findings == ()

    def test_etiketsiz_celdiriciler_ayri_sayilir_ve_paydaya_girmez(self) -> None:
        havuz = [
            _view(
                [
                    _neutral("A", "Doğru şık"),
                    _option("B", "Bir", "çevrim yanılgısı"),
                    _option("C", "İki", None),
                    _option("D", "Üç", "   "),
                ],
                answer_key="A",
            )
        ]
        coverage = quality.misconception_coverage(havuz)
        assert coverage.labelled_distractors == 1
        assert coverage.unlabelled_distractors == 2
        assert coverage.counts == {"çevrim yanılgısı": 1}

    def test_bos_havuz_cokmeden_bos_kapsama_verir(self) -> None:
        coverage = quality.misconception_coverage([], min_sample=0)
        assert coverage.counts == {}
        assert coverage.labelled_distractors == 0
        assert coverage.unlabelled_distractors == 0
        assert coverage.findings == ()


# ---------------------------------------------------------------------------
# review_pool
# ---------------------------------------------------------------------------


class TestReviewPool:
    def test_uc_mekanizmanin_bulgulari_tek_raporda_toplanir(self) -> None:
        havuz = [
            _view(
                [
                    _neutral("A", "İŞLEM Tablosu"),
                    _option("B", "işlem tablosu.", "çevrim yanılgısı"),
                    _option("C", "Kesme vektörü", "çevrim yanılgısı"),
                ],
                answer_key="A",
                question_id="q1",
            ),
            _view(
                [
                    _neutral("A", "Karşılıklı dışlama"),
                    _option("B", "Döngüsel bekleme", "çevrim yanılgısı"),
                ],
                answer_key="A",
                stem=_STEM_REWRITTEN,
                question_id="q2",
            ),
        ]
        report = quality.review_pool(havuz, expected_misconceptions=["açlık yanılgısı"])

        assert [pair.left_id for pair in report.duplicates] == ["q1"]
        assert report.coverage.counts == {"çevrim yanılgısı": 3}
        codes = [finding.code for finding in report.findings]
        assert FindingCode.NEAR_DUPLICATE_QUESTION in codes
        assert FindingCode.DUPLICATE_OPTION in codes
        assert FindingCode.MISCONCEPTION_UNTESTED in codes
        # Yakın-tekrar bulguları başta, kapsama bulguları sonda.
        assert codes[0] is FindingCode.NEAR_DUPLICATE_QUESTION
        assert codes[-1] is FindingCode.MISCONCEPTION_UNTESTED

    def test_bos_havuz_cokmeden_bos_rapor_verir(self) -> None:
        report = quality.review_pool([])
        assert report.findings == ()
        assert report.duplicates == ()
        assert report.coverage.counts == {}

    def test_esikler_sarmalayiciya_gercekten_gecer(self) -> None:
        """`review_pool` kendi kuralı olmayan bir kolaylık sarmalayıcısıdır."""
        havuz = [
            _view([_neutral("A", "Bir")], question_id="q1"),
            _view([_neutral("A", "Bir")], stem=_STEM_REWRITTEN, question_id="q2"),
        ]
        assert quality.review_pool(havuz, threshold=0.99).duplicates == ()
        assert len(quality.review_pool(havuz, threshold=0.1).duplicates) == 1


class TestNgramParametresiFailOpenDegil:
    """Yanlış bir `ngram` değeri kapıyı sessizce açmamalı.

    Bu sınıfın var olma nedeni ölçülmüş bir tuzak: `ngram=0` verildiğinde
    `range(len(normalized) - 0 + 1)` her konumda boş dilim üretiyordu, iki metnin
    n-gram kümesi de `{""}` oluyordu ve `similarity` HER çift için 1.0 dönüyordu.
    Yani tek bir yanlış parametre, yakın-tekrar kapısını "her soru her sorunun
    tekrarıdır" diyecek biçimde açıyordu — hiç kapı olmamasından kötü bir durum.
    """

    @pytest.mark.parametrize("gecersiz", [0, -1, -3])
    def test_sifir_ve_negatif_ngram_reddedilir(self, gecersiz: int) -> None:
        with pytest.raises(ValueError, match="n-gram"):
            quality.similarity("deadlock nedir", "deadlock ne demek", ngram=gecersiz)

    def test_gecersiz_ngram_yakin_tekrar_aramasinda_da_reddedilir(self) -> None:
        """Hata `similarity` sınırında değil, havuz tarayıcısında da yüzeye çıkmalı."""
        havuz = [
            _view([_neutral("A", "Bir")], question_id="q1"),
            _view([_neutral("A", "Bir")], stem=_STEM_REWRITTEN, question_id="q2"),
        ]
        with pytest.raises(ValueError, match="n-gram"):
            quality.find_near_duplicates(havuz, ngram=0)

    def test_gecerli_en_kucuk_ngram_calismaya_devam_eder(self) -> None:
        """Sınır 1'dir; 1 reddedilirse düzeltme gereğinden fazla kısıtlamış olurdu."""
        assert quality.similarity("abc", "abc", ngram=1) == pytest.approx(1.0)
        assert quality.similarity("abc", "xyz", ngram=1) == pytest.approx(0.0)
