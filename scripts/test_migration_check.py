"""`scripts/migration_check.py` kapısının kendi testleri.

Kapının değeri, deponun gerçekten yaşadığı durumu yakalamasında: `0016` numarası
iki dalda birden kullanıldı (`api_contract_admin_access` ve `assessment_integrity`)
ve hiçbir kontrol bunu görmedi. İlk test tam o durumu kurar.

Depodaki diğer betik testleri gibi `unittest` ile yazılır; CI onları
`python -m unittest scripts.test_...` ile koşturur, `apps/api` pytest
toplayıcısı `testpaths = ["tests"]` olduğu için buraya bakmaz.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.migration_check import check, main


class MigrationCheckTests(unittest.TestCase):
    def _directory(self, *names: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in names:
            (root / name).write_text("SELECT 1;\n", encoding="utf-8")
        return root

    def test_ayni_numarayi_kullanan_iki_goc_yakalanir(self) -> None:
        directory = self._directory(
            "0001_core_schema.sql",
            "0016_api_contract_admin_access.sql",
            "0016_assessment_integrity.sql",
        )
        problems = check(directory, allowed_gaps=set(range(2, 16)))
        birlesik = " ".join(problems)
        self.assertIn("çakışma: 0016", birlesik)
        self.assertIn("api_contract_admin_access", birlesik)
        self.assertIn("assessment_integrity", birlesik)

    def test_temiz_dizin_gecer(self) -> None:
        directory = self._directory("0001_core_schema.sql", "0002_chat.sql")
        self.assertEqual(check(directory, allowed_gaps=set()), [])

    def test_bildirilmemis_bosluk_yakalanir(self) -> None:
        directory = self._directory("0001_core_schema.sql", "0003_chat.sql")
        problems = check(directory, allowed_gaps=set())
        self.assertIn("boşluk: 0002", " ".join(problems))

    def test_bildirilmis_bosluk_gecer(self) -> None:
        directory = self._directory("0001_core_schema.sql", "0003_chat.sql")
        self.assertEqual(check(directory, allowed_gaps={2}), [])

    def test_bicimsiz_ad_yakalanir(self) -> None:
        for name in ("16_chat.sql", "0016-chat.sql", "0016_Chat.sql", "chat.sql"):
            with self.subTest(name=name):
                directory = self._directory("0001_core_schema.sql", name)
                problems = check(directory, allowed_gaps=set(range(2, 100)))
                self.assertTrue(
                    any("biçim" in problem for problem in problems),
                    msg=f"{name} için biçim ihlali beklendi: {problems}",
                )

    def test_ilk_goc_0001_degilse_yakalanir(self) -> None:
        directory = self._directory("0002_chat.sql")
        problems = check(directory, allowed_gaps=set())
        self.assertIn("ilk göç", " ".join(problems))

    def test_bos_dizin_sessizce_gecmez(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.assertNotEqual(check(Path(temporary.name), allowed_gaps=set()), [])

    def test_olmayan_dizin_sessizce_gecmez(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        yok = Path(temporary.name) / "yok"
        self.assertNotEqual(check(yok, allowed_gaps=set()), [])

    def test_deponun_kendi_goclerini_dogrular(self) -> None:
        """Bu depo bugün 0017'yi başka dalda tutuyor; kapı bildirimle geçmeli."""
        self.assertEqual(main(["--allow-gap", "0017"]), 0)

    def test_bildirimsiz_kosumda_depo_kapisi_kirmizi_yanar(self) -> None:
        """Rezerve numara bildirilmezse kapı sessiz kalmaz."""
        self.assertEqual(main([]), 1)


if __name__ == "__main__":
    unittest.main()
