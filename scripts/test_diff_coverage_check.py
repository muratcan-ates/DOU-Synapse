"""`scripts/diff_coverage_check.py` kapısının kendi testleri.

Bu kapı iki ayrı mekanizmanın kesişimi: `sys.monitoring` satır olayları ve
`git diff --unified=0` çıktısı. İkisi de sahte veriyle "çalışıyor" gibi
gösterilebildiği için testler **gerçek** bir git deposu kurar, **gerçek** diff
üretir ve toplayıcıyı **gerçekten** koşturur. Sentetik olan yalnız kapsam
JSON'udur; o da bilinçli, çünkü asıl sınanan şey kesişim mantığıdır.

En kritik test `test_degisen_satir_yoksa_kapsanacak_satir_yok_denir`: 0/0'ı %100
saymak bu tür araçların klasik yalancı-yeşilidir ve o davranış buradan geri
getirilemesin diye kilitlenmiştir.

Depodaki diğer betik testleri gibi `unittest` ile yazılır; `apps/api` pytest
toplayıcısı `testpaths = ["tests"]` olduğu için `scripts/` dizinine bakmaz.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts.diff_coverage_check import (
    EXIT_BELOW_THRESHOLD,
    EXIT_CLEAN,
    EXIT_UNUSABLE,
    LineCollector,
    build_report,
    changed_lines,
    executable_lines,
    main,
    parse_unified_diff,
)

MODULE_V1 = """\
def topla(a, b):
    # ilk sürüm
    return a + b
"""

MODULE_V2 = """\
def topla(a, b):
    # ilk sürüm
    return a + b


def cikar(a, b):
    return a - b
"""


class _TempGitRepo:
    """Testlerin üzerinde gerçek `git diff` koşturduğu tek kullanımlık depo.

    Global ve sistem git yapılandırması `/dev/null`'a bağlanır: geliştiricinin
    kendi `~/.gitconfig` dosyasındaki `init.templateDir`, imza zorunluluğu ya da
    `diff.renames=false` gibi ayarlar testi makineye bağımlı kılmasın diye.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.environment = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "L8 Test",
            "GIT_AUTHOR_EMAIL": "l8@example.invalid",
            "GIT_COMMITTER_NAME": "L8 Test",
            "GIT_COMMITTER_EMAIL": "l8@example.invalid",
        }
        self.git("-c", "init.defaultBranch=main", "init", "-q", str(root))

    def git(self, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
            env=self.environment,
        )
        return completed.stdout

    def write(self, relative: str, content: str) -> None:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def remove(self, relative: str) -> None:
        (self.root / relative).unlink()

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()


class _Base(unittest.TestCase):
    def _repo(self) -> _TempGitRepo:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return _TempGitRepo(Path(temporary.name).resolve())

    def _coverage(self, files: dict[str, list[int]]) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "coverage.json"
        payload = {
            "schema": "dou-synapse-diff-coverage/1",
            "root": "/yok",
            "mechanism": "sys.monitoring",
            "files": files,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _raw(self, text: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "coverage.json"
        path.write_text(text, encoding="utf-8")
        return path

    def _run_main(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def _report_args(self, repo: _TempGitRepo, coverage: Path, base: str = "HEAD~1") -> list[str]:
        return [
            "--root",
            str(repo.root),
            "report",
            "--coverage",
            str(coverage),
            "--base",
            base,
        ]


class DegisenSatirTespitiTests(_Base):
    def test_kapsanmayan_eklenen_satir_bulunur(self) -> None:
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("modul.py", MODULE_V2)
        repo.commit("cikar eklendi")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        report = build_report(repo.root, changed, {"modul.py": {1, 2, 3}})

        self.assertEqual([outcome.path for outcome in report.files], ["modul.py"])
        self.assertEqual(report.files[0].missing, (6, 7))
        self.assertEqual(report.total_covered, 0)
        self.assertEqual(report.total_changed, 2)

    def test_kapsanan_satir_sayilir(self) -> None:
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("modul.py", MODULE_V2)
        repo.commit("cikar eklendi")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        report = build_report(repo.root, changed, {"modul.py": {6, 7}})

        self.assertEqual(report.files[0].covered, (6, 7))
        self.assertEqual(report.files[0].missing, ())
        self.assertEqual(report.percent, 100.0)

    def test_yeni_dosyanin_tum_calistirilabilir_satirlari_sayilir(self) -> None:
        repo = self._repo()
        repo.write("okuma.md", "# taban\n")
        repo.commit("taban")
        repo.write("yeni.py", MODULE_V2)
        repo.commit("yeni dosya")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        report = build_report(repo.root, changed, {"yeni.py": {1, 3}})

        self.assertEqual(report.files[0].path, "yeni.py")
        self.assertEqual(report.files[0].measurable, (1, 3, 6, 7))
        self.assertEqual(report.files[0].covered, (1, 3))


class PaydaTests(_Base):
    def test_yalniz_yorum_degisikligi_paydaya_girmez(self) -> None:
        """Yorum satırı LINE olayı üretemez; paydaya girseydi düzeltilemez bir kırmızı doğardı."""
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("modul.py", MODULE_V1.replace("# ilk sürüm", "# ikinci sürüm, açıklama"))
        repo.commit("yalniz yorum")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        self.assertEqual(changed, {"modul.py": {2}})

        report = build_report(repo.root, changed, {"modul.py": {1, 3}})
        self.assertEqual(report.files, [])
        self.assertEqual(report.total_changed, 0)
        self.assertIsNone(report.percent)

    def test_bos_satir_eklenmesi_paydaya_girmez(self) -> None:
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("modul.py", MODULE_V1 + "\n\n\n")
        repo.commit("bos satirlar")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        report = build_report(repo.root, changed, {"modul.py": {1, 3}})
        self.assertEqual(report.total_changed, 0)

    def test_python_disi_dosya_paydaya_girmez(self) -> None:
        repo = self._repo()
        repo.write("README.md", "# taban\n")
        repo.commit("taban")
        repo.write("README.md", "# taban\n\nyeni paragraf\n")
        repo.commit("belge")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        report = build_report(repo.root, changed, {"modul.py": {1}})
        self.assertEqual(report.total_changed, 0)
        self.assertTrue(any("Python dosyası değil" in note for note in report.skipped))

    def test_test_dosyasi_varsayilan_olarak_haric_tutulur(self) -> None:
        repo = self._repo()
        repo.write("tests/test_bir.py", "def test_a():\n    assert True\n")
        repo.commit("taban")
        repo.write(
            "tests/test_bir.py",
            "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n",
        )
        repo.commit("ikinci test")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        report = build_report(repo.root, changed, {})
        self.assertEqual(report.total_changed, 0)
        self.assertTrue(any("test dosyası" in note for note in report.skipped))

    def test_include_tests_ile_test_dosyasi_sayilir(self) -> None:
        repo = self._repo()
        repo.write("tests/test_bir.py", "def test_a():\n    assert True\n")
        repo.commit("taban")
        repo.write(
            "tests/test_bir.py",
            "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n",
        )
        repo.commit("ikinci test")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        report = build_report(repo.root, changed, {}, include_tests=True)
        self.assertEqual(report.total_changed, 2)
        self.assertEqual(report.total_covered, 0)

    def test_exclude_kalibi_dosyayi_dusurur(self) -> None:
        repo = self._repo()
        repo.write("uretim/modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("uretim/modul.py", MODULE_V2)
        repo.commit("degisiklik")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        report = build_report(repo.root, changed, {}, excludes=("uretim/*",))
        self.assertEqual(report.total_changed, 0)
        self.assertTrue(any("--exclude" in note for note in report.skipped))


class SifirBolenSifirTests(_Base):
    def test_degisen_satir_yoksa_kapsanacak_satir_yok_denir(self) -> None:
        """0/0 asla %100 değildir — yüzde hiç basılmaz ve çıkış kodu 0'dır."""
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.write("NOTLAR.md", "# taban\n")
        repo.commit("taban")
        repo.write("NOTLAR.md", "# taban\n\nyeni satır\n")
        repo.commit("yalniz belge")

        coverage = self._coverage({"modul.py": [1, 3]})
        code, out, _ = self._run_main(self._report_args(repo, coverage))

        self.assertEqual(code, EXIT_CLEAN)
        self.assertIn("kapsanacak satır yok", out)
        self.assertNotIn("%", out)
        self.assertIn("PASS", out)

    def test_sifir_bolen_sifir_esikle_de_yesil_kalir(self) -> None:
        """Eşik verilse bile 0/0 kırmızı yanmaz; ölçülecek bir şey yoktur."""
        repo = self._repo()
        repo.write("NOTLAR.md", "# taban\n")
        repo.commit("taban")
        repo.write("NOTLAR.md", "# taban\n\nyeni satır\n")
        repo.commit("yalniz belge")

        coverage = self._coverage({"modul.py": [1]})
        code, out, _ = self._run_main([*self._report_args(repo, coverage), "--fail-under", "85"])
        self.assertEqual(code, EXIT_CLEAN)
        self.assertIn("kapsanacak satır yok", out)
        self.assertNotIn("%", out)


class EsikTests(_Base):
    def _yarim_kapsanan_depo(self) -> tuple[_TempGitRepo, Path]:
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("modul.py", MODULE_V2)
        repo.commit("cikar eklendi")
        coverage = self._coverage({"modul.py": [6]})  # 6 kapsandı, 7 kapsanmadı → %50
        return repo, coverage

    def test_fail_under_altinda_rc_1(self) -> None:
        repo, coverage = self._yarim_kapsanan_depo()
        code, out, _ = self._run_main([*self._report_args(repo, coverage), "--fail-under", "85"])
        self.assertEqual(code, EXIT_BELOW_THRESHOLD)
        self.assertIn("DIFF_COVERAGE_CHECK=FAIL", out)
        self.assertIn("%50.0", out)

    def test_fail_under_ustunde_rc_0(self) -> None:
        repo, coverage = self._yarim_kapsanan_depo()
        code, out, _ = self._run_main([*self._report_args(repo, coverage), "--fail-under", "40"])
        self.assertEqual(code, EXIT_CLEAN)
        self.assertIn("DIFF_COVERAGE_CHECK=PASS", out)

    def test_esik_verilmezse_rapor_basilir_ve_rc_0(self) -> None:
        """Varsayılan eşik yok: A8' hâlâ insan onayı bekliyor, kapı kendi kendine kırmızı yanmaz."""
        repo, coverage = self._yarim_kapsanan_depo()
        code, out, _ = self._run_main(self._report_args(repo, coverage))
        self.assertEqual(code, EXIT_CLEAN)
        self.assertIn("%50.0", out)
        self.assertIn("eşik verilmedi", out)


class BozukGirdiTests(_Base):
    def test_silinen_dosya_cokertmez(self) -> None:
        repo = self._repo()
        repo.write("silinecek.py", MODULE_V1)
        repo.write("kalan.py", MODULE_V1)
        repo.commit("taban")
        repo.remove("silinecek.py")
        repo.write("kalan.py", MODULE_V2)
        repo.commit("silme ve ekleme")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        self.assertNotIn("silinecek.py", changed)

        report = build_report(repo.root, changed, {"kalan.py": {6, 7}})
        self.assertEqual([outcome.path for outcome in report.files], ["kalan.py"])
        self.assertEqual(report.percent, 100.0)

    def test_yeniden_adlandirma_cokertmez(self) -> None:
        repo = self._repo()
        repo.write("eski.py", MODULE_V2)
        repo.commit("taban")
        repo.remove("eski.py")
        repo.write("yeni.py", MODULE_V2 + "\n\ndef carp(a, b):\n    return a * b\n")
        repo.commit("yeniden adlandirma ve ekleme")

        changed = changed_lines(repo.root, "HEAD~1", "HEAD")
        report = build_report(repo.root, changed, {"yeni.py": {10, 11}})

        paths = [outcome.path for outcome in report.files]
        self.assertIn("yeni.py", paths)
        self.assertNotIn("eski.py", paths)
        self.assertGreater(report.total_changed, 0)

    def test_bozuk_kapsam_json_anlamli_hata_verir(self) -> None:
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("modul.py", MODULE_V2)
        repo.commit("degisiklik")

        bozuk = self._raw("{ bu json degil")
        code, _, err = self._run_main(self._report_args(repo, bozuk))
        self.assertEqual(code, EXIT_UNUSABLE)
        self.assertIn("geçerli JSON değil", err)
        self.assertIn(str(bozuk), err)

    def test_bos_kapsam_json_anlamli_hata_verir(self) -> None:
        """Boş toplama sessizce %0'a düşmemeli; araç çalışmamış demektir."""
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("modul.py", MODULE_V2)
        repo.commit("degisiklik")

        bos = self._coverage({})
        code, _, err = self._run_main(self._report_args(repo, bos))
        self.assertEqual(code, EXIT_UNUSABLE)
        self.assertIn("kapsam dosyası boş", err)
        self.assertIn("hiç satır görmedi", err)

    def test_files_anahtari_olmayan_json_reddedilir(self) -> None:
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("modul.py", MODULE_V2)
        repo.commit("degisiklik")

        yabanci = self._raw(json.dumps({"coverage": {"modul.py": [1]}}))
        code, _, err = self._run_main(self._report_args(repo, yabanci))
        self.assertEqual(code, EXIT_UNUSABLE)
        self.assertIn("`files` sözlüğü yok", err)

    def test_olmayan_taban_referansi_anlamli_hata_verir(self) -> None:
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")

        coverage = self._coverage({"modul.py": [1, 3]})
        code, _, err = self._run_main(self._report_args(repo, coverage, base="boyle-bir-dal-yok"))
        self.assertEqual(code, EXIT_UNUSABLE)
        self.assertIn("git komutu düştü", err)

    def test_iki_kapsam_dosyasi_birlestirilir(self) -> None:
        repo = self._repo()
        repo.write("modul.py", MODULE_V1)
        repo.commit("taban")
        repo.write("modul.py", MODULE_V2)
        repo.commit("degisiklik")

        birinci = self._coverage({"modul.py": [6]})
        ikinci = self._coverage({"modul.py": [7]})
        code, out, _ = self._run_main(
            [
                "--root",
                str(repo.root),
                "report",
                "--coverage",
                str(birinci),
                "--coverage",
                str(ikinci),
                "--base",
                "HEAD~1",
                "--fail-under",
                "100",
            ]
        )
        self.assertEqual(code, EXIT_CLEAN)
        self.assertIn("%100.0", out)


class DiffAyristirmaTests(unittest.TestCase):
    def test_dev_null_hedefi_atlanir_ve_yeni_ad_kullanilir(self) -> None:
        patch = (
            "diff --git a/silinen.py b/silinen.py\n"
            "deleted file mode 100644\n"
            "--- a/silinen.py\n"
            "+++ /dev/null\n"
            "@@ -1,3 +0,0 @@\n"
            "-bir\n"
            "diff --git a/eski.py b/yeni.py\n"
            "similarity index 90%\n"
            "rename from eski.py\n"
            "rename to yeni.py\n"
            "--- a/eski.py\n"
            "+++ b/yeni.py\n"
            "@@ -4,0 +5,2 @@\n"
            "+iki\n"
            "+uc\n"
            "@@ -9 +10 @@\n"
            "+dort\n"
        )
        parsed = parse_unified_diff(patch)
        self.assertEqual(parsed, {"yeni.py": {5, 6, 10}})
        self.assertNotIn("silinen.py", parsed)


class ToplayiciTests(unittest.TestCase):
    """Toplayıcının gerçekten satır gördüğünü kanıtlar — boş JSON üreten bir araç işe yaramaz."""

    def _calistir(self, source: str) -> tuple[Path, dict[str, set[int]]]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        module = root / "olculen.py"
        module.write_text(source, encoding="utf-8")

        collector = LineCollector(root)
        collector.start()
        try:
            namespace: dict[str, object] = {}
            code = compile(module.read_bytes(), str(module), "exec", dont_inherit=True)
            exec(code, namespace)  # noqa: S102 — ölçülen kaynak testin kendi yazdığı dosya
            namespace["kullanilan"](2)
        finally:
            collector.stop()
        return module, collector.files

    def test_toplayici_calistirilan_satirlari_kaydeder(self) -> None:
        module, files = self._calistir(
            "def kullanilan(x):\n"
            "    y = x + 1\n"
            "    return y\n"
            "\n"
            "\n"
            "def kullanilmayan():\n"
            "    return 0\n"
        )
        self.assertIn("olculen.py", files)
        self.assertTrue({1, 2, 3}.issubset(files["olculen.py"]))
        self.assertEqual(files["olculen.py"] & {7}, set())
        self.assertEqual(module.name, "olculen.py")

    def test_toplayici_json_yazar_ve_geri_okunur(self) -> None:
        _module, files = self._calistir(
            "def kullanilan(x):\n    return x\n\n\ndef kullanilmayan():\n    return 0\n"
        )
        self.assertTrue(files)
        collector = LineCollector(Path("/yok"))
        collector.files = files
        payload = collector.payload()
        self.assertEqual(payload["mechanism"], "sys.monitoring")
        self.assertIn("olculen.py", payload["files"])

    def test_toplayicinin_gordugu_satirlar_calistirilabilir_kumesinin_altkumesidir(self) -> None:
        """Pay ve payda aynı mekanizmadan gelmeli; aksi hâlde haksız kırmızı doğar."""
        module, files = self._calistir(
            "def kullanilan(x):\n"
            "    return sum(\n"
            "        [\n"
            "            x,\n"
            "            x + 1,\n"
            "        ]\n"
            "    )\n"
            "\n"
            "\n"
            "def kullanilmayan():\n"
            "    return 0\n"
        )
        available = executable_lines(module)
        self.assertTrue(files["olculen.py"].issubset(available))
        self.assertNotIn(11, files["olculen.py"])
        self.assertIn(11, available)


class CalistirilabilirSatirTests(unittest.TestCase):
    def test_yorum_ve_bos_satirlar_calistirilabilir_sayilmaz(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "ornek.py"
        path.write_text(
            "# bas yorum\n\ndef f():\n    # ic yorum\n    return 1\n",
            encoding="utf-8",
        )
        lines = executable_lines(path)
        self.assertIn(3, lines)
        self.assertIn(5, lines)
        self.assertNotIn(1, lines)
        self.assertNotIn(2, lines)
        self.assertNotIn(4, lines)


if __name__ == "__main__":
    unittest.main()
