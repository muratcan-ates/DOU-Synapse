"""Türkçe metin katlama — `app/core/text_tr.py`.

Bu dosyanın asıl işi `fold` ile `normalize` arasındaki farkı KİLİTLEMEK. İki
fonksiyon yan yana durduğunda "aynı şeyi yapıyorlar, birleştirelim" refleksi
kaçınılmazdır; birleştirmenin bedeli ise sessizdir ve yalnız sınav puanında
görünür. Aşağıdaki `test_fold_ve_normalize_ayni_sey_degil` tam olarak o
birleştirmeyi kırmızı yakar.
"""

from __future__ import annotations

from app.core import text_tr


class TestKucultme:
    def test_i_harfi_ciftini_bozmaz(self) -> None:
        """`str.lower()` tek başına ikisinde de yanılır (Anayasa V)."""
        assert text_tr.lower_tr("İŞLETİM") == "işletim"
        assert text_tr.lower_tr("IŞIK") == "ışık"

    def test_lower_birlesik_nokta_uretmez(self) -> None:
        """Büyük İ küçültülünce birleşik nokta üretmemeli (U+0307), yoksa "i" ile eşleşmez."""
        assert "̇" not in text_tr.lower_tr("İ")
        assert text_tr.lower_tr("İ") == "i"

    def test_diger_turkce_harfler_dogru_iner(self) -> None:
        assert text_tr.lower_tr("ÇÖZÜM ŞEĞİ") == "çözüm şeği"


class TestNormalize:
    def test_noktalamayi_atar_bosluklari_tekler(self) -> None:
        assert text_tr.normalize("  Yığın,   kuyruk;  liste!  ") == "yığın kuyruk liste"

    def test_aksani_KORUR(self) -> None:
        """Puanlama tarafının tek isteği bu: bilgi kaybetme."""
        assert text_tr.normalize("Çözüm Ağacı") == "çözüm ağacı"


class TestFold:
    def test_aksani_soker(self) -> None:
        assert text_tr.fold("Çözüm Ağacı") == "cozum agaci"

    def test_yabanci_aksanlari_da_soker(self) -> None:
        assert text_tr.fold("Schrödinger café") == "schrodinger cafe"

    def test_tokens_kisa_sozcukleri_eleyebilir(self) -> None:
        assert text_tr.tokens("İşletim sistemi ve çekirdek", min_length=3) == [
            "isletim",
            "sistemi",
            "cekirdek",
        ]

    def test_tokens_sirayi_korur(self) -> None:
        assert text_tr.tokens("b a b") == ["b", "a", "b"]


class TestSeviyeAyrimi:
    """İki seviyenin BİRLEŞTİRİLEMEZ olduğunu kanıtlar."""

    def test_fold_ve_normalize_ayni_sey_degil(self) -> None:
        """ "acı" ile "açı": katlanınca aynı dizeye iner, normalize edilince inmez.

        Kısa cevap sınavında bu çift gerçekten karşımıza çıkabilir ("açı" bir
        geometri cevabı, "acı" değil). Puanlama `fold` kullansaydı yanlış cevap
        100 puan alırdı. Bu testi geçmek için iki fonksiyon ayrı kalmak
        ZORUNDA — `normalize`'ı `fold`'a bağlayan bir "sadeleştirme" burada
        kırmızı yanar.
        """
        assert text_tr.fold("acı") == text_tr.fold("açı")
        assert text_tr.normalize("acı") != text_tr.normalize("açı")

    def test_ikisi_de_ayni_kucultmeyi_kullanir(self) -> None:
        """Fark yalnız aksan sökmede; küçültme kuralı ortak ve tek yerde."""
        assert text_tr.normalize("İŞLETİM") == "işletim"
        assert text_tr.fold("İŞLETİM") == "isletim"
