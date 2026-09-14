"""`scripts/test_quality_check.py` kapısının kendi testleri.

Bu kapının değeri iki yönlüdür ve ikisi de ayrı ayrı sınanır:

* **Yakalıyor mu** — üç kusurun her biri için, kusurlu sentetik bir test yazılır
  ve kapının onu bulduğu doğrulanır.
* **Susuyor mu** — aynı kusurun MEŞRU biçimleri için kapının hiçbir şey
  söylemediği doğrulanır. Bu ikinci grup daha uzun, çünkü kapının asıl riski
  yanlış alarm: gürültü üreten bir kapı kapatılır ve o andan sonra hiçbir şey
  ölçmez. Buradaki meşru biçimlerin hepsi depodaki gerçek testlerden alındı
  (`test_admin_readiness.py:137` kasıtlı rollback, `test_upload_safety.py:234`
  değişkene konmuş coroutine, `test_rate_limit.py:79` ikinci context manager,
  `test_embedding_prefix.py:35` yerel yardımcı, `test_mastery.py:39` üretim
  sabiti) — her biri ilk sürümde yanlış alarm üretmişti.

Muafiyet mekanizması da sınanır: gerekçesiz muafiyet kapıyı susturamaz, yoksa
mekanizma bir kaçış yolu olur.

Depodaki diğer betik testleri gibi `unittest` ile yazılır:

    python3 -m unittest scripts.test_test_quality_check
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.test_quality_check import (
    RULE_CALL_FREE,
    RULE_RAISES_TAUTOLOGY,
    RULE_STATUS_ONLY,
    check_source,
    main,
)

#: Sentetik dosyaların başı: kapının "uygulama ismi" saydığı içe aktarmalar.
HEADER = """
import pytest

from app.modules.mastery.service import HINT_MULTIPLIERS, compute_new_score
"""


def rules(source: str) -> list[str]:
    """Sentetik kaynaktaki bulguların kural adları."""
    return [finding.rule for finding in check_source(HEADER + source, "sentetik.py")]


class StatusOnlyTests(unittest.TestCase):
    """Kural 1 — yalnız başarı kodu iddia eden test."""

    def test_yalnizca_200_iddia_eden_test_yakalanir(self) -> None:
        self.assertEqual(
            rules("""
def test_uc_cevap_veriyor(client):
    response = client.get("/courses")
    assert response.status_code == 200
"""),
            [RULE_STATUS_ONLY],
        )

    def test_birden_cok_200_iddiasi_da_yakalanir(self) -> None:
        self.assertEqual(
            rules("""
def test_iki_cagri(client):
    assert client.get("/a").status_code == 200
    assert client.get("/b").status_code == 201
"""),
            [RULE_STATUS_ONLY],
        )

    def test_ters_yazilmis_karsilastirma_da_yakalanir(self) -> None:
        self.assertEqual(
            rules("""
def test_ters(client):
    response = client.get("/courses")
    assert 200 == response.status_code
"""),
            [RULE_STATUS_ONLY],
        )

    def test_403_iddiasi_yakalanmaz(self) -> None:
        """Reddin gövdesi zaten boştur; durum kodu tek başına bir şey ölçer."""
        self.assertEqual(
            rules("""
def test_uye_olmayan_goremez(client):
    assert client.get("/courses/1").status_code == 403
"""),
            [],
        )

    def test_govde_de_sinanirsa_yakalanmaz(self) -> None:
        self.assertEqual(
            rules("""
def test_govde(client):
    response = client.get("/courses")
    assert response.status_code == 200
    assert response.json()["items"] == []
"""),
            [],
        )

    def test_bilesik_iddia_yakalanmaz(self) -> None:
        self.assertEqual(
            rules("""
def test_bilesik(client):
    response = client.get("/courses")
    assert response.status_code == 200 and response.json()["items"]
"""),
            [],
        )

    def test_iddiasiz_test_bu_kurala_girmez(self) -> None:
        """İddiası olmayan test bu kuralın konusu değildir (kurulum yardımcısı)."""
        self.assertEqual(
            rules("""
def test_yalnizca_cagirir(client):
    client.get("/courses")
"""),
            [],
        )


class RaisesTautologyTests(unittest.TestCase):
    """Kural 2 — `pytest.raises` bloğu hiçbir üretim yolu yürütmüyor."""

    def test_kendi_raise_eden_blok_yakalanir(self) -> None:
        self.assertEqual(
            rules("""
def test_hata_veriyor():
    with pytest.raises(ValueError):
        raise ValueError("test kendi kurdu")
"""),
            [RULE_RAISES_TAUTOLOGY],
        )

    def test_cagrisiz_blok_yakalanir(self) -> None:
        self.assertEqual(
            rules("""
def test_bos_blok(sozluk):
    with pytest.raises(KeyError):
        sozluk["yok"]
"""),
            [RULE_RAISES_TAUTOLOGY],
        )

    def test_govdede_cagri_varsa_yakalanmaz(self) -> None:
        self.assertEqual(
            rules("""
def test_gercek_cagri():
    with pytest.raises(ValueError):
        compute_new_score(previous_score=2.0, previous_answer_count=0, raw_score=0, hint_level=0)
"""),
            [],
        )

    def test_kasitli_rollback_yakalanmaz(self) -> None:
        """`test_admin_readiness.py:137`: raise'in yanında gerçek çağrı var."""
        self.assertEqual(
            rules("""
async def test_rollback(connection):
    with pytest.raises(RuntimeError, match="synthetic rollback"):
        async with connection.begin():
            await connection.execute("INSERT INTO request_logs VALUES (1)")
            raise RuntimeError("synthetic rollback")
"""),
            [],
        )

    def test_degiskene_konmus_coroutine_yakalanmaz(self) -> None:
        """`test_upload_safety.py:234`: blokta `ast.Call` yok, `await` var."""
        self.assertEqual(
            rules("""
async def test_await_degisken(client):
    request = client.post("/courses/1/documents")
    with pytest.raises(RuntimeError, match="synthetic document flush"):
        await request
"""),
            [],
        )

    def test_ikinci_context_manager_yakalanmaz(self) -> None:
        """`test_rate_limit.py:79`: sınanan şey `with` öğesindeki çağrıdır."""
        self.assertEqual(
            rules("""
def test_finally_dali(gate):
    with pytest.raises(RuntimeError), gate.hold("qgen", "k", limit=1, message="s"):
        raise RuntimeError("üretim patladı")
"""),
            [],
        )

    def test_kasitli_totoloji_gerekceyle_susturulur(self) -> None:
        """`test_study_continuity.py:139`: mutasyon kanıtı olarak totoloji."""
        self.assertEqual(
            rules("""
def test_mutasyon_kaniti(mutated):
    # test-quality: raises-totolojisi — korumanın kaldırıldığı gösteriliyor
    with pytest.raises(AssertionError):
        assert mutated.status_code == 403
"""),
            [],
        )


class CallFreeTests(unittest.TestCase):
    """Kural 3 — test kendi kurduğu değişmezleri birbirine eşitliyor."""

    def test_yalnizca_sabit_karsilastiran_test_yakalanir(self) -> None:
        self.assertEqual(
            rules("""
def test_hicbir_seye_dokunmuyor():
    beklenen = {"a": 1}
    gelen = {"a": 1}
    assert beklenen == gelen
"""),
            [RULE_CALL_FREE],
        )

    def test_uretim_sabiti_okuyan_test_yakalanmaz(self) -> None:
        """`test_mastery.py:39`: çağrı yok ama sabit değişirse test kırmızı yanar."""
        self.assertEqual(
            rules("""
def test_carpan_tablosu():
    assert HINT_MULTIPLIERS == {0: 1.00, 1: 0.85}
"""),
            [],
        )

    def test_yerel_yardimci_cagiran_test_yakalanmaz(self) -> None:
        """`test_embedding_prefix.py:35`: yardımcı üretim koduna testin adına dokunur."""
        self.assertEqual(
            rules("""
def _provider_with_fake(name):
    return compute_new_score, []

def test_yardimciyla():
    provider, fake = _provider_with_fake("e5")
    assert fake == []
"""),
            [],
        )

    def test_fixture_alan_test_yakalanmaz(self) -> None:
        self.assertEqual(
            rules("""
def test_fixture_var(settings):
    assert 1 == 1
"""),
            [],
        )


class WaiverTests(unittest.TestCase):
    """Muafiyet bir kaçış yolu değil, yazılı gerekçedir."""

    def test_gerekceli_muafiyet_susturur(self) -> None:
        self.assertEqual(
            rules("""
def test_muaf(client):
    # test-quality: sadece-durum-kodu — bu uç gövdesizdir (204)
    assert client.get("/x").status_code == 200
"""),
            [],
        )

    def test_gerekcesiz_muafiyet_susturmaz(self) -> None:
        """Boş gerekçe kapıyı susturamaz; yoksa muafiyet sessizliğe dönüşür."""
        for silik in ("# test-quality: sadece-durum-kodu —", "# test-quality: sadece-durum-kodu"):
            with self.subTest(silik=silik):
                self.assertEqual(
                    rules(f"""
def test_muaf(client):
    {silik}
    assert client.get("/x").status_code == 200
"""),
                    [RULE_STATUS_ONLY],
                )

    def test_baska_kuralin_muafiyeti_susturmaz(self) -> None:
        self.assertEqual(
            rules("""
def test_muaf(client):
    # test-quality: cagrisiz-test — yanlış kural adı
    assert client.get("/x").status_code == 200
"""),
            [RULE_STATUS_ONLY],
        )

    def test_komsu_testin_muafiyeti_sizmaz(self) -> None:
        """Muafiyet yalnız yazıldığı testin gövdesinde geçerlidir."""
        self.assertEqual(
            rules("""
def test_muaf(client):
    # test-quality: sadece-durum-kodu — bilinçli
    assert client.get("/x").status_code == 200

def test_muaf_degil(client):
    assert client.get("/y").status_code == 200
"""),
            [RULE_STATUS_ONLY],
        )


class ScopeTests(unittest.TestCase):
    """Kapı neyi tarar, neyi taramaz."""

    def test_test_olmayan_fonksiyon_taranmaz(self) -> None:
        self.assertEqual(
            rules("""
def yardimci(client):
    assert client.get("/x").status_code == 200
"""),
            [],
        )

    def test_async_test_taranir(self) -> None:
        self.assertEqual(
            rules("""
async def test_async(client):
    response = await client.get("/x")
    assert response.status_code == 200
"""),
            [RULE_STATUS_ONLY],
        )

    def test_sinif_icindeki_test_taranir(self) -> None:
        self.assertEqual(
            rules("""
class TestGrup:
    def test_metot(self, client):
        assert client.get("/x").status_code == 200
"""),
            [RULE_STATUS_ONLY],
        )

    def test_ayristirilamayan_dosya_sessizce_gecmez(self) -> None:
        """Bozuk dosya bulgu değil HATA'dır; atlanırsa kapı üzerinden yeşil geçer."""
        with self.assertRaises(SyntaxError):
            check_source("def test_bozuk(:\n    pass\n", "bozuk.py")


class MainTests(unittest.TestCase):
    """Komut satırı sözleşmesi: çıkış kodu ve yol doğrulaması."""

    def _directory(self, **files: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name, body in files.items():
            (root / name).write_text(HEADER + body, encoding="utf-8")
        return root

    def test_temiz_dizin_sifir_doner(self) -> None:
        root = self._directory(
            test_temiz_py="""
def test_govde(client):
    response = client.get("/x")
    assert response.json() == {}
"""
        )
        (root / "test_temiz_py").rename(root / "test_temiz.py")
        self.assertEqual(main([str(root)]), 0)

    def test_bulgulu_dizin_bir_doner(self) -> None:
        root = self._directory(
            bozuk="""
def test_zayif(client):
    assert client.get("/x").status_code == 200
"""
        )
        (root / "bozuk").rename(root / "test_zayif.py")
        self.assertEqual(main([str(root)]), 1)

    def test_test_olmayan_dosya_taranmaz(self) -> None:
        """Toplama kuralı pytest'inkiyle aynı: `test_` öneki olmayan dosya atlanır."""
        root = self._directory(
            yardimci="""
def test_zayif(client):
    assert client.get("/x").status_code == 200
"""
        )
        (root / "yardimci").rename(root / "yardimci.py")
        self.assertEqual(main([str(root)]), 0)

    def test_olmayan_yol_bir_doner(self) -> None:
        self.assertEqual(main(["/olmayan/dizin/xyz"]), 1)

    def test_json_biciminde_de_cikis_kodu_korunur(self) -> None:
        root = self._directory(
            bozuk="""
def test_zayif(client):
    assert client.get("/x").status_code == 200
"""
        )
        (root / "bozuk").rename(root / "test_zayif.py")
        self.assertEqual(main([str(root), "--format", "json"]), 1)


if __name__ == "__main__":
    unittest.main()
