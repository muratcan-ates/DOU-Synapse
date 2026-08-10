"""Türkçe metin katlama — `app/core/text_tr.py`.

Üç fonksiyonun üçü de aynı katlamaya dayanır; farkları yalnız çıktının biçimi.
Bu dosyanın asıl işi katlamanın İKİ ayrı tuzağa düşmediğini kilitlemek: i/İ
çiftinin bozulmaması (Anayasa V) ve karşılaştırmanın noktalama/boşluk yüzünden
kaçmaması.

`TestPuanlamaKarari`, aksan sökmenin bir ürün kararı olduğunu ve bedelinin
bilindiğini kayda geçirir — o testler kırmızı yanarsa karar sessizce geri
alınmış demektir.
"""

from __future__ import annotations

from app.core import text_tr


class TestKucultme:
    def test_i_harfi_ciftini_bozmaz(self) -> None:
        """`str.lower()` tek başına ikisinde de yanılır (Anayasa V).

        Özel tabloyu doğrudan sınıyoruz çünkü katlanmış çıktıda iz bırakmıyor:
        "IŞIK" ile "İŞİK" katlandıktan sonra ikisi de "isik". Tablo yine de
        duruyor — `fold` bir gün aksan sökmeyi bıraksa ilk kırılacak yer orası
        olurdu ve o gün sessizce kırılmasın.
        """
        assert text_tr._lower_tr("İŞLETİM") == "işletim"
        assert text_tr._lower_tr("IŞIK") == "ışık"

    def test_lower_birlesik_nokta_uretmez(self) -> None:
        """Büyük İ küçültülünce birleşik nokta (U+0307) üretmemeli."""
        assert "̇" not in text_tr._lower_tr("İ")
        assert text_tr._lower_tr("İ") == "i"

    def test_diger_turkce_harfler_dogru_iner(self) -> None:
        assert text_tr._lower_tr("ÇÖZÜM ŞEĞİ") == "çözüm şeği"


class TestFold:
    def test_aksani_soker(self) -> None:
        assert text_tr.fold("Çözüm Ağacı") == "cozum agaci"

    def test_yabanci_aksanlari_da_soker(self) -> None:
        assert text_tr.fold("Schrödinger café") == "schrodinger cafe"

    def test_noktalamayi_BIRAKIR(self) -> None:
        """`fold` bir dize dönüştürücüsüdür, tokenleştirici değil.

        Karşılaştırma yapan çağıranların `fold` değil `normalize` kullanmasının
        sebebi budur: "Döngüsel bekleme." katlandığında sondaki nokta durur.
        """
        assert text_tr.fold("Döngüsel bekleme.") == "dongusel bekleme."


class TestTokens:
    def test_kisa_sozcukleri_eleyebilir(self) -> None:
        assert text_tr.tokens("İşletim sistemi ve çekirdek", min_length=3) == [
            "isletim",
            "sistemi",
            "cekirdek",
        ]

    def test_sirayi_korur(self) -> None:
        assert text_tr.tokens("b a b") == ["b", "a", "b"]


class TestNormalize:
    def test_noktalamayi_atar_bosluklari_tekler(self) -> None:
        assert text_tr.normalize("  Yığın,   kuyruk;  liste!  ") == "yigin kuyruk liste"

    def test_noktali_cevap_noktasiz_anahtara_esitlenir(self) -> None:
        """Kısa cevap eşleşmesinin `fold` yerine buna dayanmasının sebebi."""
        assert text_tr.normalize("Döngüsel bekleme.") == text_tr.normalize("döngüsel bekleme")


class TestPuanlamaKarari:
    """Aksan sökme bir ürün kararıdır; kazancı ve bedeli birlikte yazılı.

    10 Ağustos'a kadar kısa cevap puanlaması aksanı koruyordu. Karar
    değiştirildi: Türkçe klavyesi olmayan öğrencinin haksız sıfır alması,
    aksanla ayrılan bir cevap çiftinin anahtar olmasından daha sık.
    """

    def test_aksansiz_yazim_anahtara_esitlenir(self) -> None:
        """Kararın KAZANCI — geri alınırsa bu test kırmızı yanar."""
        assert text_tr.normalize("cozum") == text_tr.normalize("çözüm")
        assert text_tr.normalize("dongusel bekleme") == text_tr.normalize("döngüsel bekleme")

    def test_aksanla_ayrilan_cift_ayirt_edilemez(self) -> None:
        """Kararın BEDELİ. Bu testin varlığı bedelin bilindiğinin kaydıdır.

        "acı" ile "açı" artık aynı dizeye iniyor. Kısa cevap anahtarı böyle bir
        çift olursa yanlış cevap 100 alır; kaçınma yolu soru üretiminde, burada
        değil (`text_tr.normalize` docstring'i).
        """
        assert text_tr.normalize("acı") == text_tr.normalize("açı")

    def test_veritabaniyla_ayni_aynilik_tanimi(self) -> None:
        """`chunks.fts` `app.immutable_unaccent` üzerinden üretiliyor (0001).

        Karar tam olarak buna hizalanmak içindi: retrieval'da eşdeğer sayılan
        iki yazım, puanlamada da eşdeğer sayılsın.
        """
        assert text_tr.normalize("işletim sistemleri") == text_tr.normalize("isletim sistemleri")
