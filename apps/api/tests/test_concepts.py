"""Kavram haritası çıkarımı: sıralama, Türkçe ek birleştirme ve kenarlar.

Bu dosya yalnız SAF katmanı sınar — veritabanı yok, model çağrısı yok. Çıkarımın
tamamı deterministik olduğu için aynı girdi her koşuda aynı çıktıyı vermeli;
birkaç test bunu doğrudan ölçüyor.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.modules.retrieval.concepts import (
    MAX_EDGES,
    MAX_TERMS,
    ChunkText,
    analyze,
)


def pasaj(text: str, chunk_id: UUID | None = None) -> ChunkText:
    return ChunkText(chunk_id=chunk_id or uuid4(), text=text)


def terimler(*texts: str, max_terms: int = MAX_TERMS) -> list[str]:
    found, _ = analyze([pasaj(text) for text in texts], max_terms=max_terms)
    return [term.key for term in found]


class TestEleme:
    def test_tek_pasajda_gecen_sozcuk_terim_sayilmaz(self) -> None:
        """Bir kez geçen sözcük kavram değil, cümledir."""
        assert terimler("semafor mutex", "mutex kilit") == ["mutex"]

    def test_islev_sozcukleri_elenir(self) -> None:
        keys = terimler(
            "süreç için gerekli olan bellek",
            "süreç için ayrılan bellek alanı",
        )

        assert "icin" not in keys
        assert "olan" not in keys
        assert "surec" in keys
        assert "bellek" in keys

    def test_kisa_sozcuk_ve_sayilar_elenir(self) -> None:
        keys = terimler("CPU 2024 bellek yönetimi", "CPU 2024 bellek tahsisi")

        assert "2024" not in keys
        assert "cpu" not in keys  # üç harf, eşiğin altında
        assert "bellek" in keys

    def test_belge_iskeleti_sozcukleri_elenir(self) -> None:
        """`bölüm`, `slayt`, `konu` hangi alanda olursa olsun sunumu anlatır."""
        keys = terimler("Bölüm 3 slayt konu semafor", "Bölüm 4 slayt konu semafor")

        assert "bolum" not in keys
        assert "slayt" not in keys
        assert "konu" not in keys
        assert "semafor" in keys

    def test_alan_terimi_olabilecek_sozcuk_elenmez(self) -> None:
        """`sayfa` ve `tablo` işletim sistemlerinde kavramın kendisidir.

        Sayfa tablosu, sayfa hatası, süreç tablosu — eleme listesi bunları
        silseydi öğrencinin görmesi gereken terimleri sessizce kaldırırdı.
        """
        keys = terimler("sayfa tablosu yönetimi", "sayfa hatası ve tablo girdisi")

        assert "sayfa" in keys
        assert "tablo" in keys

    def test_cekimli_islev_sozcugu_de_elenir(self) -> None:
        """Eleme birleştirmeden SONRA: `konu` elenirse `konusu` da elenmeli.

        Eleme önce yapılırken `konu` düşüyor ama `konusu` terim sayılıyordu.
        """
        keys = terimler("konu başlığı semafor", "konusu semafor", "konular semafor")

        assert "konu" not in keys
        assert "konusu" not in keys
        assert "konular" not in keys

    def test_unsuz_yumusamasi_yakalanmaz_kabul_edilen_sinir(self) -> None:
        """`başlık` → `başlığı` önek kuralıyla eşleşmez (k/ğ değişimi).

        Bu bir kusur değil, yazılı kabul edilen sınır: gerçek gövdeleyici
        bağımlılık ister. Testin işi sınırın sessizce kaybolmasını engellemek.
        """
        keys = terimler("başlığı semafor", "başlığı mutex")

        assert "basligi" in keys


class TestTurkceEkBirlestirme:
    def test_tekil_ve_cogul_tek_terimde_toplanir(self) -> None:
        keys = terimler("süreç tablosu", "süreçler listesi", "süreç durumu")

        assert keys.count("surec") == 1
        assert "surecler" not in keys

    def test_iki_ekli_sozcuk_zincirle_iner(self) -> None:
        """`süreçlerin` eki 5 harf; tek adımda inemez, `süreçler` üzerinden iner."""
        found, _ = analyze(
            [pasaj("süreç yönetimi"), pasaj("süreçler tablosu"), pasaj("süreçlerin durumu")]
        )
        keys = [term.key for term in found]

        assert keys.count("surec") == 1
        assert "sureclerin" not in keys
        surec = next(term for term in found if term.key == "surec")
        assert surec.chunk_count == 3

    def test_kisa_govde_uzun_kavrami_yutmaz(self) -> None:
        """`veri` (4 harf) gövde olamaz; `veritabanı` ayrı kavram olarak kalır."""
        keys = terimler("veri yapısı", "veri tipi", "veritabanı motoru", "veritabanı indeksi")

        assert "veri" in keys
        assert "veritabani" in keys

    def test_uzun_ek_birlestirilmez(self) -> None:
        """`kanal` + `izasyon` (7 harf) birleşmez; farklı kavramlar."""
        keys = terimler("kanal kapasitesi", "kanal genişliği", "kanalizasyon", "kanalizasyon")

        assert "kanal" in keys
        assert "kanalizasyon" in keys

    def test_yuzey_bicimi_materyaldeki_yazimdir(self) -> None:
        """Ekranda `süreç` görünür, katlanmış `surec` değil."""
        found, _ = analyze([pasaj("Süreç tablosu"), pasaj("süreç durumu"), pasaj("süreç kimliği")])

        surec = next(term for term in found if term.key == "surec")
        assert surec.surface in {"süreç", "Süreç"}
        assert surec.surface.lower() == "süreç"


class TestSiralama:
    def test_en_cok_pasajda_gecen_terim_basta(self) -> None:
        """Merkezî kavram çoğu pasajda geçer; TF-IDF onu dibe atardı, biz başa alıyoruz."""
        keys = terimler(
            "süreç ve semafor",
            "süreç yönetimi",
            "süreç durumu",
            "semafor kullanımı",
        )

        assert keys[0] == "surec"
        assert keys[1] == "semafor"

    def test_esitlikte_toplam_gecis_bozar(self) -> None:
        found, _ = analyze(
            [pasaj("mutex mutex semafor"), pasaj("mutex semafor")],
        )
        keys = [term.key for term in found]

        assert keys == ["mutex", "semafor"]
        assert found[0].total_count == 3
        assert found[1].total_count == 2

    def test_kaynak_pasaji_terimin_en_yogun_gectigi_pasajdir(self) -> None:
        yogun = uuid4()
        found, _ = analyze(
            [
                pasaj("semafor kilit", uuid4()),
                pasaj("semafor semafor semafor kilit", yogun),
            ]
        )

        semafor = next(term for term in found if term.key == "semafor")
        assert semafor.chunk_id == yogun

    def test_ust_sinir_uygulanir(self) -> None:
        metin = " ".join(f"terim{index}kavram" for index in range(30))
        found, _ = analyze([pasaj(metin), pasaj(metin)], max_terms=5)

        assert len(found) == 5


class TestKenarlar:
    def test_ayni_pasajda_gecen_terimler_baglanir(self) -> None:
        _, edges = analyze([pasaj("semafor ve mutex"), pasaj("semafor mutex kilit")])

        assert [(edge.left, edge.right, edge.chunk_count) for edge in edges] == [
            ("mutex", "semafor", 2)
        ]

    def test_tek_pasaji_paylasan_cift_kenar_olmaz(self) -> None:
        _, edges = analyze(
            [
                pasaj("semafor mutex"),
                pasaj("semafor mutex"),
                pasaj("semafor kilit"),
                pasaj("kilit sayaci"),
            ]
        )
        ciftler = {(edge.left, edge.right) for edge in edges}

        assert ("mutex", "semafor") in ciftler
        assert ("kilit", "semafor") not in ciftler  # yalnız bir pasajı paylaşıyorlar

    def test_kenarlar_yalniz_secili_terimler_arasinda_kurulur(self) -> None:
        """Elenen terimin kenarı ekranda kaynaksız kalırdı."""
        found, edges = analyze(
            [pasaj("semafor mutex kilit"), pasaj("semafor mutex kilit")],
            max_terms=2,
        )
        secili = {term.key for term in found}

        assert len(secili) == 2
        for edge in edges:
            assert edge.left in secili and edge.right in secili

    def test_kenar_ust_siniri_uygulanir(self) -> None:
        metin = " ".join(f"kavram{index}sozcuk" for index in range(12))
        _, edges = analyze([pasaj(metin), pasaj(metin)], max_edges=7)

        assert len(edges) == 7

    def test_birlestirilmis_terimin_kenari_da_birlesir(self) -> None:
        """Kenar sayımı terimlerle AYNI taramadan çıkar; ayrı tarama sayıları bölerdi."""
        _, edges = analyze(
            [pasaj("süreç semafor"), pasaj("süreçler semafor"), pasaj("süreçlerin semafor")]
        )

        assert [(edge.left, edge.right, edge.chunk_count) for edge in edges] == [
            ("semafor", "surec", 3)
        ]


class TestDeterminizm:
    def test_ayni_girdi_ayni_cikti(self) -> None:
        pasajlar = [
            pasaj("süreç semafor mutex", UUID(int=1)),
            pasaj("süreç mutex kilit", UUID(int=2)),
            pasaj("semafor kilit süreç", UUID(int=3)),
        ]

        birinci = analyze(pasajlar)
        ikinci = analyze(pasajlar)

        assert birinci == ikinci

    def test_bos_girdi_bos_harita(self) -> None:
        assert analyze([]) == ([], [])

    def test_terimsiz_metin_cokmez(self) -> None:
        found, edges = analyze([pasaj("ve bu da"), pasaj("!!! ...")])

        assert (found, edges) == ([], [])

    def test_varsayilan_sinirlar_asilmaz(self) -> None:
        metin = " ".join(f"kavram{index}terim" for index in range(80))
        found, edges = analyze([pasaj(metin), pasaj(metin)])

        assert len(found) <= MAX_TERMS
        assert len(edges) <= MAX_EDGES
