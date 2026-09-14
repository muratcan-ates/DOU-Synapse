"""`scripts/dead_code_check.py` kapısının kendi testleri.

Bu kapının değeri bulduklarında değil, **basmadıklarında**dır: ölü kod arayan bir
araç framework sihrini bilmiyorsa ilk koşuşunda onlarca sahte bulgu üretir, ekip
aracı kapatır ve gerçek ölü kod bir daha görünmez. Bu yüzden testlerin çoğu bir
şeyin yakalandığını değil, **yakalanmadığını** ölçer: route handler, pydantic
doğrulayıcısı, `__all__` ihracı, pytest fixture'ı, SQLAlchemy modeli.

Her sahte-pozitif testinin yanında, testin boşuna geçmediğini gösteren bir ölü
tanım da vardır: istisna yanlışlıkla "her şeyi muaf tut"a dönüşürse o tanım
listeden düşer ve test kırılır.

Depodaki diğer betik testleri gibi `unittest` ile yazılır; CI onları
`python -m unittest scripts.test_dead_code_check` ile koşturur, `apps/api` pytest
toplayıcısı `testpaths = ["tests"]` olduğu için buraya bakmaz.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import textwrap
import unittest
from collections.abc import Iterable
from pathlib import Path

from scripts.dead_code_check import (
    dead_definitions,
    find_repository_root,
    main,
    survey_paths,
)


class DeadCodeCheckTests(unittest.TestCase):
    def _tree(self, files: dict[str, str]) -> Path:
        """Sentetik bir kaynak ağacı kur ve kökünü döndür."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
        return root

    def _dead(
        self,
        root: Path,
        *,
        ignores: Iterable[str] = (),
        reference_roots: Iterable[Path] = (),
    ) -> set[str]:
        """Verilen ağaçta ölü sayılan tanımların adları."""
        survey = survey_paths([root], ignores, root, reference_roots)
        return {definition.name for definition in dead_definitions(survey)}

    def _main(self, argv: list[str]) -> tuple[int, str]:
        """`main` çağır; çıkış kodunu ve stdout'u birlikte döndür."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    # ------------------------------------------------------------------
    # Yakalaması gerekenler
    # ------------------------------------------------------------------

    def test_gercekten_olu_fonksiyon_yakalanir(self) -> None:
        root = self._tree(
            {
                "modul.py": """
                def canli_yardimci() -> int:
                    return 1


                def olu_yardimci() -> int:
                    return 2


                def cagiran() -> int:
                    return canli_yardimci()
                """
            }
        )
        dead = self._dead(root)
        self.assertIn("olu_yardimci", dead)
        self.assertNotIn("canli_yardimci", dead)

    def test_ozyinelemeli_olu_fonksiyon_kendini_diri_tutamaz(self) -> None:
        """Kendi gövdesindeki kendine atıf referans sayılmaz."""
        root = self._tree(
            {
                "modul.py": """
                def olu_ozyineli(n: int) -> int:
                    if n <= 0:
                        return 0
                    return olu_ozyineli(n - 1)
                """
            }
        )
        self.assertIn("olu_ozyineli", self._dead(root))

    def test_type_checking_ve_try_bloklarindaki_tanimlar_taranir(self) -> None:
        """`if`/`try` gövdeleri de modül yüzeyidir; orada saklanan ölü kod görünmelidir."""
        root = self._tree(
            {
                "modul.py": """
                from typing import TYPE_CHECKING

                if TYPE_CHECKING:

                    def olu_tip_yardimcisi() -> int:
                        return 1

                try:

                    def olu_try_yardimcisi() -> int:
                        return 1

                except ImportError:
                    pass
                """
            }
        )
        dead = self._dead(root)
        self.assertIn("olu_tip_yardimcisi", dead)
        self.assertIn("olu_try_yardimcisi", dead)

    # ------------------------------------------------------------------
    # YakalamaMAsı gerekenler (framework sihri)
    # ------------------------------------------------------------------

    def test_route_handler_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "api.py": """
                from fastapi import APIRouter

                router = APIRouter()


                @router.get("/live")
                async def canlilik() -> dict[str, str]:
                    return {"status": "ok"}


                @router.post("/kayit")
                async def kayit_ol() -> None:
                    return None


                def olu_yardimci() -> int:
                    return 1
                """
            }
        )
        dead = self._dead(root)
        self.assertNotIn("canlilik", dead)
        self.assertNotIn("kayit_ol", dead)
        self.assertNotIn("router", dead)
        # İstisna "her şeyi muaf tut"a dönüşmediğinin kanıtı:
        self.assertIn("olu_yardimci", dead)

    def test_on_event_ve_exception_handler_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "main.py": """
                from fastapi import FastAPI

                app = FastAPI()


                @app.on_event("startup")
                async def baslangicta() -> None:
                    return None


                @app.exception_handler(ValueError)
                async def deger_hatasi(request: object, hata: ValueError) -> None:
                    return None
                """
            }
        )
        dead = self._dead(root)
        self.assertNotIn("baslangicta", dead)
        self.assertNotIn("deger_hatasi", dead)

    def test_all_icindeki_sembol_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "modul.py": """
                __all__ = ["disari_acilan"]


                def disari_acilan() -> int:
                    return 1


                def icerde_kalan_olu() -> int:
                    return 2
                """
            }
        )
        dead = self._dead(root)
        self.assertNotIn("disari_acilan", dead)
        self.assertIn("icerde_kalan_olu", dead)

    def test_init_dosyasinin_re_export_yuzeyi_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "paket/__init__.py": """
                from paket.ic import Ayar


                def kolaylik_yardimcisi() -> int:
                    return 1
                """,
                "paket/ic.py": """
                class Ayar:
                    pass
                """,
            }
        )
        dead = self._dead(root)
        self.assertNotIn("kolaylik_yardimcisi", dead)
        self.assertNotIn("Ayar", dead)

    def test_pydantic_dogrulayicisi_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "config.py": """
                from pydantic import BaseModel, field_validator, model_validator

                CANLI_SABIT = "x"


                class Ayarlar(BaseModel):
                    ad: str

                    @field_validator("ad")
                    @classmethod
                    def adi_dogrula(cls, deger: str) -> str:
                        return deger


                @model_validator(mode="after")
                def modul_duzeyi_dogrulayici(deger: object) -> object:
                    return deger
                """
            }
        )
        dead = self._dead(root)
        self.assertNotIn("modul_duzeyi_dogrulayici", dead)
        # Sınıf içi metotlar zaten rapor yüzeyinde değildir:
        self.assertNotIn("adi_dogrula", dead)

    def test_baska_modulden_import_edilen_sembol_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "modul_a.py": """
                def paylasilan() -> int:
                    return 1


                def hic_kullanilmayan() -> int:
                    return 2
                """,
                "modul_b.py": """
                from modul_a import paylasilan


                def kullanan() -> int:
                    return paylasilan()
                """,
            }
        )
        dead = self._dead(root)
        self.assertNotIn("paylasilan", dead)
        self.assertIn("hic_kullanilmayan", dead)

    def test_depends_icinde_gecen_fonksiyon_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "deps.py": """
                from fastapi import Depends


                def oturum_ver() -> int:
                    return 1


                def olu_bagimlilik() -> int:
                    return 2


                def uc_nokta(oturum: int = Depends(oturum_ver)) -> int:
                    return oturum
                """
            }
        )
        dead = self._dead(root)
        self.assertNotIn("oturum_ver", dead)
        self.assertIn("olu_bagimlilik", dead)

    def test_sqlalchemy_modeli_ve_mapped_takma_adi_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "models.py": """
                from typing import Annotated
                from uuid import UUID

                from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

                uuid_pk = Annotated[UUID, mapped_column(primary_key=True)]


                class Base(DeclarativeBase):
                    pass


                class Ders(Base):
                    __tablename__ = "ders"

                    id: Mapped[uuid_pk]
                """
            }
        )
        dead = self._dead(root)
        self.assertNotIn("Base", dead)
        self.assertNotIn("Ders", dead)
        self.assertNotIn("uuid_pk", dead)

    def test_dunder_ve_main_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "betik.py": """
                __version__ = "1.0.0"


                def __getattr__(ad: str) -> int:
                    return 1


                def main() -> int:
                    return 0


                if __name__ == "__main__":
                    raise SystemExit(main())
                """
            }
        )
        dead = self._dead(root)
        self.assertNotIn("__version__", dead)
        self.assertNotIn("__getattr__", dead)
        self.assertNotIn("main", dead)

    def test_pytest_yuzeyi_yakalanmaz(self) -> None:
        root = self._tree(
            {
                "conftest.py": """
                def toplayiciya_gorunen_kanca() -> int:
                    return 1
                """,
                "test_ornek.py": """
                import pytest


                @pytest.fixture
                def ornek_veri() -> int:
                    return 1


                class TestYetkilendirme:
                    def test_bir_sey(self) -> None:
                        return None


                def test_dogrudan() -> None:
                    return None
                """,
            }
        )
        dead = self._dead(root)
        for ad in ("toplayiciya_gorunen_kanca", "ornek_veri", "TestYetkilendirme", "test_dogrudan"):
            with self.subTest(ad=ad):
                self.assertNotIn(ad, dead)

    def test_dizge_sabitiyle_kullanilan_ad_yakalanmaz(self) -> None:
        """`relationship("Kurs")` gibi dizge başvuruları da kullanım sayılır."""
        root = self._tree(
            {
                "modul.py": """
                class Kurs:
                    pass


                BAGLANTI = {"hedef": "Kurs"}
                """
            }
        )
        dead = self._dead(root)
        self.assertNotIn("Kurs", dead)
        self.assertIn("BAGLANTI", dead)

    def test_bilincli_isaret_tanimi_susturur(self) -> None:
        root = self._tree(
            {
                "modul.py": """
                # ölü-kod: bilinçli
                def kasitli_olu() -> int:
                    return 1


                def ascii_isaretli() -> int:  # olu-kod: bilincli
                    return 2


                def isaretsiz_olu() -> int:
                    return 3
                """
            }
        )
        dead = self._dead(root)
        self.assertNotIn("kasitli_olu", dead)
        self.assertNotIn("ascii_isaretli", dead)
        self.assertIn("isaretsiz_olu", dead)

    # ------------------------------------------------------------------
    # Kapsam, çıkış kodu ve dayanıklılık
    # ------------------------------------------------------------------

    def test_rapor_kapsami_disindaki_kullanim_bulguyu_siler(self) -> None:
        """Yalnız testlerden çağrılan bir kanca ölü değildir; kapı oraya da bakmalı."""
        rapor = self._tree(
            {
                "app/yardimci.py": """
                def sadece_testte_cagrilan() -> int:
                    return 1
                """
            }
        )
        referans = self._tree(
            {
                "tests/test_yardimci.py": """
                from app.yardimci import sadece_testte_cagrilan


                def test_calisir() -> None:
                    assert sadece_testte_cagrilan() == 1
                """
            }
        )
        self.assertIn("sadece_testte_cagrilan", self._dead(rapor))
        self.assertNotIn("sadece_testte_cagrilan", self._dead(rapor, reference_roots=[referans]))

    def test_depo_koku_worktree_git_dosyasini_tanir(self) -> None:
        """Git worktree'de `.git` bir dosyadır; kök bulma bunu da görmelidir."""
        root = self._tree({"apps/api/app/modul.py": "DEGER = 1\n"})
        (root / ".git").write_text("gitdir: /baska/yer\n", encoding="utf-8")
        self.assertEqual(find_repository_root([root / "apps" / "api" / "app"]), root.resolve())
        ic_depo = root / "apps" / "api"
        (ic_depo / ".git").mkdir()
        self.assertEqual(find_repository_root([root / "apps" / "api" / "app"]), ic_depo.resolve())

    def test_strict_kirmizi_yanar_varsayilan_yesil_kalir(self) -> None:
        root = self._tree({"modul.py": "def olu_yardimci() -> int:\n    return 1\n"})
        kod, cikti = self._main([str(root), "--no-repo-references"])
        self.assertEqual(kod, 0)
        self.assertIn("DEAD_CODE_CHECK=WARN", cikti)
        self.assertIn("olu_yardimci", cikti)

        kod, cikti = self._main([str(root), "--no-repo-references", "--strict"])
        self.assertEqual(kod, 1)
        self.assertIn("DEAD_CODE_CHECK=FAIL", cikti)

    def test_bozuk_sozdizimli_dosya_cokertmez(self) -> None:
        root = self._tree(
            {
                "bozuk.py": "def yarim(:\n    return 1\n",
                "saglam.py": "def olu_ama_saglam() -> int:\n    return 1\n",
            }
        )
        survey = survey_paths([root], [], root)
        self.assertEqual(survey.scanned_files, 1)
        self.assertEqual(len(survey.parse_errors), 1)
        self.assertIn("bozuk.py", survey.parse_errors[0])

        kod, cikti = self._main([str(root), "--no-repo-references"])
        self.assertEqual(kod, 1, msg="kör nokta uyarı modunda da rc=1 olmalı")
        self.assertIn("! ayrıştırma", cikti)

    def test_null_bayt_tasiyan_dosya_cokertmez(self) -> None:
        """Null bayt `SyntaxError` değil `ValueError` atar; kapı yine çökmemeli."""
        root = self._tree({"saglam.py": "DEGER = 1\n"})
        (root / "bozuk.py").write_bytes(b"deger = 1\n\x00\n")
        kod, cikti = self._main([str(root), "--no-repo-references"])
        self.assertEqual(kod, 1)
        self.assertIn("ayrıştırılamadı", cikti)

    def test_bos_dizin_cokertmez_ama_pass_da_yazmaz(self) -> None:
        root = self._tree({})
        survey = survey_paths([root], [], root)
        self.assertEqual(survey.definitions, [])
        kod, cikti = self._main([str(root), "--no-repo-references"])
        self.assertEqual(kod, 1)
        self.assertIn("taranacak .py dosyası bulunamadı", cikti)

    def test_ignore_deseni_dosyayi_disarida_birakir(self) -> None:
        root = self._tree(
            {
                "pkg/olu_bir.py": "def olu_bir() -> int:\n    return 1\n",
                "pkg/haric/olu_iki.py": "def olu_iki() -> int:\n    return 2\n",
            }
        )
        self.assertEqual(self._dead(root), {"olu_bir", "olu_iki"})
        self.assertEqual(self._dead(root, ignores=["*/haric/*"]), {"olu_bir"})
        self.assertEqual(self._dead(root, ignores=["olu_bir.py"]), {"olu_iki"})

    def test_olmayan_yol_sessizce_gecmez(self) -> None:
        root = self._tree({"modul.py": "DEGER = 1\n"})
        kod, cikti = self._main([str(root / "yok")])
        self.assertEqual(kod, 1)
        self.assertIn("yol yok", cikti)

        kod, cikti = self._main([str(root), "--reference-path", str(root / "yok")])
        self.assertEqual(kod, 1)
        self.assertIn("yol yok", cikti)


if __name__ == "__main__":
    unittest.main()
