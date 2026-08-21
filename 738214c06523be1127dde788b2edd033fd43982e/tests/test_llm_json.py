"""LLM çıktısından JSON çıkarma — `app/core/llm_json.py`.

Üç yolun (sohbet üretimi, soru üretimi, sınav puanlaması) aynı kuralı
kullandığını sabitler. Eskiden sohbet yolu tarama, diğer ikisi çit sıyırma
kullanıyordu; `test_onek_cumlesi_kabul_edilir` tam olarak ikisinin ayrıldığı
noktadır ve eski `extract_json_object` ile kırmızı yanardı.
"""

from __future__ import annotations

from app.core.llm_json import first_json_object


class TestGurultuBicimleri:
    def test_saf_json(self) -> None:
        assert first_json_object('{"a": 1}') == {"a": 1}

    def test_kod_citi_siyrilir(self) -> None:
        assert first_json_object('```json\n{"a": 1}\n```') == {"a": 1}

    def test_dilsiz_kod_citi_siyrilir(self) -> None:
        assert first_json_object('```\n{"a": 1}\n```') == {"a": 1}

    def test_onek_cumlesi_kabul_edilir(self) -> None:
        """Eski çit sıyırma bunu `JSONDecodeError` ile reddediyordu."""
        assert first_json_object('İşte sorular: {"questions": []}') == {"questions": []}

    def test_sonek_cumlesi_kabul_edilir(self) -> None:
        assert first_json_object('{"a": 1}\n\nUmarım yardımcı olur.') == {"a": 1}

    def test_ic_ice_nesne_bozulmaz(self) -> None:
        assert first_json_object('{"a": {"b": 2}}') == {"a": {"b": 2}}

    def test_metin_icindeki_suslu_parantez_atlanir(self) -> None:
        """İlk `{` geçerli JSON başlatmıyorsa tarama devam eder."""
        assert first_json_object('şablon {konu} için: {"a": 1}') == {"a": 1}


class TestReddedilenler:
    def test_json_yoksa_none(self) -> None:
        assert first_json_object("Üzgünüm, cevap veremiyorum.") is None

    def test_bos_metin_none(self) -> None:
        assert first_json_object("") is None

    def test_skaler_dizi_none(self) -> None:
        """Şemalarımızın hepsi nesne bekliyor; içinde nesne olmayan `[...]` reddedilir."""
        assert first_json_object("[1, 2, 3]") is None

    def test_dizi_sarmalayicisi_atlanir_ic_nesne_bulunur(self) -> None:
        """`[{...}]` gelirse dizi atlanır, içindeki ilk nesne döner.

        Bu, taramanın bilinçli bir kararı değil doğal sonucudur; burada yazılı
        olması birinin onu kusur sanıp "düzeltmesini" engellemek içindir. Model
        zarfı diziye sarmışsa nesneyi almak, tüm yanıtı çöpe atmaktan iyidir ve
        şema doğrulaması bir sonraki adımda yanlış biçimi zaten reddeder.
        """
        assert first_json_object('[{"a": 1}]') == {"a": 1}
