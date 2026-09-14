"""`scripts/test_quality_check.py` kapısının kendi testleri.

Kapının değeri, gerçekten ihlal yakalayabilmesinde. Bu yüzden üç kuralın
her biri için hem POZİTİF (uyarı çıkmalı) hem NEGATİF (uyarı çıkmamalı)
bir sentetik örnek kurulur. Örnekler geçici bir dizine yazılır; sabit
``/tmp`` yolu kullanılmaz, paralel koşan şeritler birbirinin dosyasını
ezmesin diye.

Depodaki diğer betik testleri gibi ``unittest`` ile yazılır: hem
``python3 -m unittest scripts.test_test_quality_check`` (bağımlılıksız, CI
bunu koşturur) hem de ``pytest scripts/test_test_quality_check.py``
çalışır.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.test_quality_check import inspect_paths, inspect_source, main

STATUS_ONLY_POSITIVE = """
def test_ders_listesi_doner(client):
    response = client.get("/courses")
    assert response.status_code == 200
"""

STATUS_ONLY_NEGATIVE = """
def test_ders_listesi_doner(client):
    response = client.get("/courses")
    assert response.status_code == 200
    assert response.json()["items"] == []
"""

STATUS_ONLY_NEGATIVE_ASSERTION_HELPER = """
def test_ders_listesi_doner(client, spy):
    response = client.get("/courses")
    assert response.status_code == 200
    spy.assert_called_once()
"""

RAISES_POSITIVE = """
import pytest


def test_yetkisiz_erisim_reddedilir():
    with pytest.raises(PermissionError):
        raise PermissionError("ders üyesi değil")
"""

RAISES_NEGATIVE = """
import pytest


def test_yetkisiz_erisim_reddedilir(service):
    with pytest.raises(PermissionError):
        service.require_membership(course_id=1, user_id=2)
"""

RAISES_NEGATIVE_COMPANION = """
import pytest


def test_is_patlasa_da_kapi_acilir(gate):
    with pytest.raises(RuntimeError), gate.hold("qgen", "k", limit=1):
        raise RuntimeError("üretim patladı")
"""

NO_CALL_POSITIVE = """
def test_atif_sozlesmesi():
    beklenen = {"chunk_id", "page"}
    assert beklenen == {"chunk_id", "page"}
"""

NO_CALL_NEGATIVE = """
def test_atif_sozlesmesi(builder):
    atif = builder.build()
    assert set(atif) == {"chunk_id", "page"}
"""


class InspectSourceTests(unittest.TestCase):
    """Üç kural da sentetik kaynak üstünde iki yönlü doğrulanır."""

    def _codes(self, source: str) -> list[str]:
        findings = inspect_source(source, Path("sentetik.py"))
        return [finding.code for finding in findings]

    def test_yalniz_durum_kodu_iddiasi_yakalanir(self) -> None:
        self.assertEqual(self._codes(STATUS_ONLY_POSITIVE), ["STATUS_ONLY_ASSERT"])

    def test_govde_de_sinayan_test_yakalanmaz(self) -> None:
        self.assertEqual(self._codes(STATUS_ONLY_NEGATIVE), [])

    def test_iddia_yardimcisi_olan_test_yakalanmaz(self) -> None:
        self.assertEqual(self._codes(STATUS_ONLY_NEGATIVE_ASSERTION_HELPER), [])

    def test_raises_totolojisi_yakalanir(self) -> None:
        self.assertEqual(self._codes(RAISES_POSITIVE), ["TAUTOLOGICAL_RAISES"])

    def test_sinanan_kodu_cagiran_raises_yakalanmaz(self) -> None:
        self.assertEqual(self._codes(RAISES_NEGATIVE), [])

    def test_eslikci_baglam_yoneticisi_totoloji_saymaz(self) -> None:
        """`with pytest.raises(X), gate.hold(...)` sınanan kodu çağırıyor."""
        self.assertEqual(self._codes(RAISES_NEGATIVE_COMPANION), [])

    def test_cagrisiz_test_yakalanir(self) -> None:
        self.assertEqual(self._codes(NO_CALL_POSITIVE), ["NO_CALL_TEST"])

    def test_cagri_iceren_test_yakalanmaz(self) -> None:
        self.assertEqual(self._codes(NO_CALL_NEGATIVE), [])

    def test_async_test_de_denetlenir(self) -> None:
        source = (
            "async def test_ders_listesi_doner(client):\n"
            "    response = await client.get('/courses')\n"
            "    assert response.status_code == 200\n"
        )
        self.assertEqual(self._codes(source), ["STATUS_ONLY_ASSERT"])

    def test_ters_yazilmis_karsilastirma_da_yakalanir(self) -> None:
        source = (
            "def test_ders_listesi_doner(client):\n"
            "    response = client.get('/courses')\n"
            "    assert 200 == response.status_code\n"
        )
        self.assertEqual(self._codes(source), ["STATUS_ONLY_ASSERT"])

    def test_raise_ifadesindeki_cagri_muafiyet_saymaz(self) -> None:
        """``raise X(str(y))`` hâlâ totolojidir: sınanan kod çağrılmadı."""
        source = (
            "import pytest\n"
            "\n"
            "\n"
            "def test_hata_mesaji():\n"
            "    with pytest.raises(ValueError):\n"
            "        raise ValueError(str(3))\n"
        )
        self.assertEqual(self._codes(source), ["TAUTOLOGICAL_RAISES"])

    def test_pytest_olmayan_yardimci_fonksiyon_denetlenmez(self) -> None:
        """Ortasında ``test_`` geçen yardımcı pytest tarafından koşulmaz."""
        source = "def make_test_payload():\n    return {'a': 1}\n"
        self.assertEqual(self._codes(source), [])

    def test_bulgu_satir_numarasi_ve_fonksiyon_adi_tasir(self) -> None:
        findings = inspect_source(STATUS_ONLY_POSITIVE, Path("sentetik.py"))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].function, "test_ders_listesi_doner")
        self.assertEqual(findings[0].line, 4)

    def test_ayristirilamayan_dosya_sessizce_temiz_sayilmaz(self) -> None:
        self.assertEqual(self._codes("def test_bozuk(:\n"), ["UNPARSEABLE"])


class InspectPathsTests(unittest.TestCase):
    """Dizin gezme ve CLI davranışı geçici dizinle doğrulanır."""

    def _tree(self, **files: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name, source in files.items():
            path = root / f"{name}.py"
            path.write_text(source, encoding="utf-8")
        return root

    def test_dizindeki_ihlaller_toplanir(self) -> None:
        root = self._tree(
            test_kotu=STATUS_ONLY_POSITIVE,
            test_iyi=STATUS_ONLY_NEGATIVE,
            test_raises=RAISES_POSITIVE,
        )
        codes = sorted(finding.code for finding in inspect_paths([root]))
        self.assertEqual(codes, ["STATUS_ONLY_ASSERT", "TAUTOLOGICAL_RAISES"])

    def test_temiz_dizinde_bulgu_yok(self) -> None:
        root = self._tree(test_iyi=STATUS_ONLY_NEGATIVE, test_raises=RAISES_NEGATIVE)
        self.assertEqual(inspect_paths([root]), [])

    def test_olmayan_yol_fail_closed_bildirilir(self) -> None:
        root = self._tree(test_iyi=STATUS_ONLY_NEGATIVE)
        findings = inspect_paths([root / "yok"])
        self.assertEqual([finding.code for finding in findings], ["MISSING_PATH"])

    def _run(self, *argv: str) -> tuple[int, str]:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(list(argv))
        return code, stream.getvalue()

    def test_varsayilan_mod_uyari_verir_ama_dusurmez(self) -> None:
        root = self._tree(test_kotu=STATUS_ONLY_POSITIVE)
        code, output = self._run(str(root))
        self.assertEqual(code, 0)
        self.assertIn("STATUS_ONLY_ASSERT", output)
        self.assertIn("TEST_QUALITY_WARNINGS=1", output)

    def test_fail_on_warn_ile_rc_bir_olur(self) -> None:
        root = self._tree(test_kotu=STATUS_ONLY_POSITIVE)
        code, output = self._run(str(root), "--fail-on-warn")
        self.assertEqual(code, 1)
        self.assertIn("TEST_QUALITY_WARNINGS=1", output)

    def test_temiz_agacta_fail_on_warn_gecer(self) -> None:
        root = self._tree(test_iyi=STATUS_ONLY_NEGATIVE)
        code, output = self._run(str(root), "--fail-on-warn")
        self.assertEqual(code, 0)
        self.assertIn("TEST_QUALITY_WARNINGS=0", output)


if __name__ == "__main__":
    unittest.main()
