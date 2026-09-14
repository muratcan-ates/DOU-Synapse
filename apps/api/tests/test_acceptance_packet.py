"""E3 kabul paketinin ÇEVRİMDIŞI yarısını sabitleyen testler.

Neden API test paketinin içinde: `evaluation/` altındaki kod hiçbir otomatik koşuya
girmiyor; buraya konunca CI her koşuda paketin tekrar üretilebilirliğini ve etiket
alanlarının boş kaldığını doğruluyor. `test_eval_metrics.py` ve
`test_faithfulness_scoring.py` ile aynı gerekçe, aynı import biçimi.

Bu dosya E3'ü TAMAMLAMAZ. Gerçek sağlayıcı koşusu ve iki bağımsız insan etiketleyici
hâlâ engel; buradaki etiketler test kurgusudur ve hiçbir kalite iddiası taşımaz.
Testler ağ, veritabanı ve sağlayıcı kullanmaz.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

EVALUATION = Path(__file__).resolve().parents[3] / "evaluation"
if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

from acceptance import packet_offline  # noqa: E402

REPO_CASES = EVALUATION / "acceptance" / "assessment_cases.json"
REPO_MATERIAL = EVALUATION.parent / "sample_data" / "isletim-sistemleri"

#: Depodaki taslakta 5 vaka ve toplam 13 (vaka, cevap) çifti var. Sayı testlerde
#: yazılı, çünkü E3'ün "≥25 örnek" ölçütünün bugün neden karşılanmadığı tam olarak
#: bu fark: havuz 13, ölçüt 25.
REPO_POOL_SIZE = 13

ANCHORS = ("correct", "partial", "incorrect")


def _case(case_id: str, *, file_name: str = "ornek.pdf") -> dict[str, Any]:
    """Depodaki `assessment_cases.json` ile AYNI alan kümesine sahip sentetik vaka."""
    return {
        "human_approved_by": None,
        "human_approved_at": None,
        "expected_score": None,
        "expected_missing_points": None,
        "observed_response": None,
        "result": "not_run",
        "id": case_id,
        "question_type": "open",
        "answer_format": "essay",
        "source": {"file_name": file_name},
        "prompt": f"{case_id} sorusu nedir?",
        "student_answers": [
            {
                "anchor": anchor,
                "answer": f"{case_id} için {index}. numaralı öğrenci yanıtı metni.",
                "human_expected_score": None,
            }
            for index, anchor in enumerate(ANCHORS, start=1)
        ],
        "rubric": [{"point": "Ana noktayı açıklar", "weight": 100}],
    }


class Workspace:
    """Sentetik vaka dosyası + materyal dizini; diskte, ağsız ve veritabanısız."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.material_dir = root / "material"
        self.material_dir.mkdir(parents=True, exist_ok=True)
        (self.material_dir / "ornek.pdf").write_bytes(b"%PDF-1.4 sentetik ders materyali")
        self.cases_path = root / "assessment_cases.json"
        self.write([_case(f"GRADE-{index:02d}") for index in range(1, 13)])

    def write(self, cases: list[dict[str, Any]]) -> None:
        payload = {"schema_version": 1, "kind": "assessment_acceptance_draft", "cases": cases}
        self.cases_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def files(self, *, size: int = 25, seed: int = packet_offline.DEFAULT_SEED) -> dict[str, bytes]:
        return packet_offline.packet_files(
            cases_path=self.cases_path, material_dir=self.material_dir, size=size, seed=seed
        )

    def build(
        self, output: Path, *, size: int = 25, seed: int = packet_offline.DEFAULT_SEED
    ) -> int:
        return packet_offline.main(
            [
                "--output-dir",
                str(output),
                "--cases",
                str(self.cases_path),
                "--material-dir",
                str(self.material_dir),
                "--size",
                str(size),
                "--seed",
                str(seed),
            ]
        )

    def verify(
        self, output: Path, *, size: int = 25, seed: int = packet_offline.DEFAULT_SEED
    ) -> int:
        return packet_offline.main(
            [
                "--output-dir",
                str(output),
                "--cases",
                str(self.cases_path),
                "--material-dir",
                str(self.material_dir),
                "--size",
                str(size),
                "--seed",
                str(seed),
                "--verify",
            ]
        )


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path / "workspace")


def _example_ids(files: dict[str, bytes]) -> list[str]:
    packet = json.loads(files[packet_offline.PACKET_FILE])
    return [example["example_id"] for example in packet["examples"]]


def _fill(form: str, labels: list[str]) -> str:
    """Boş etiket formunu sırayla doldurur — gerçek insan etiketi DEĞİLDİR."""
    values = iter(labels)
    lines = []
    for line in form.splitlines():
        if line.startswith("**Etiket:**") and "→ ___" in line:
            line = f"{line.split('→')[0]}→ {next(values)}"
        elif line.startswith("**Not:**"):
            line = "**Not:** test kurgusu"
        lines.append(line)
    return "\n".join(lines) + "\n"


class TestDeterminism:
    def test_ayni_tohum_bayt_bayt_ayni_paket(self, workspace: Workspace) -> None:
        """Aynı girdi + aynı tohum → aynı baytlar. `--verify`nin ön koşulu budur."""
        first = workspace.files()
        second = workspace.files()
        assert first == second
        assert set(first) == {
            packet_offline.PACKET_FILE,
            packet_offline.ANSWER_KEY_FILE,
            *packet_offline.LABEL_FILES,
            packet_offline.CHECKSUM_FILE,
        }

    def test_farkli_tohum_farkli_secim(self, workspace: Workspace) -> None:
        """Tohum seçimi belirler; iki tohum aynı örnekleri seçmemeli."""
        first = workspace.files(seed=1)
        second = workspace.files(seed=2)
        assert _example_ids(first) != _example_ids(second)
        assert first[packet_offline.PACKET_FILE] != second[packet_offline.PACKET_FILE]

    def test_paket_zaman_damgasi_ve_git_durumu_tasimaz(self, workspace: Workspace) -> None:
        """`prepare_packet.py`nin aksine: saat ve git durumu bayta girmez.

        Girseydi aynı girdiyle iki koşu farklı çıktı üretirdi ve `--verify`
        hiçbir şey ölçmezdi.
        """
        packet = json.loads(workspace.files()[packet_offline.PACKET_FILE])
        assert "prepared_at" not in packet
        assert "candidate_sha" not in packet
        assert "candidate_dirty" not in packet

    def test_sha256_tekrar_uretilebilir(self, workspace: Workspace, tmp_path: Path) -> None:
        """Paketin özeti hem bellekte hem diskte hem SHA256SUMS içinde aynı."""
        output = tmp_path / "packet"
        assert workspace.build(output) == 0
        files = workspace.files()
        digest = packet_offline.packet_digest(files)
        on_disk = (output / packet_offline.PACKET_FILE).read_bytes()
        # Özet modülün kendi yardımcısıyla değil, doğrudan hashlib ile doğrulanır:
        # modül kendi hesabını kendi hesabıyla onaylasaydı test bir şey ölçmezdi.
        assert hashlib.sha256(on_disk).hexdigest() == digest
        sums = (output / packet_offline.CHECKSUM_FILE).read_text(encoding="utf-8")
        assert f"{digest}  {packet_offline.PACKET_FILE}" in sums


class TestIntegrity:
    def test_eksik_alan_yakalanir(self, workspace: Workspace) -> None:
        """Soru metni olmayan bir vaka pakete giremez."""
        cases = [_case("GRADE-01")]
        del cases[0]["prompt"]
        workspace.write(cases)
        with pytest.raises(packet_offline.PacketError, match="soru metni"):
            workspace.files(size=1)

    def test_eksik_etiketleyici_alani_yakalanir(self, workspace: Workspace) -> None:
        """Etiketleyiciye sorulan alan hiç yoksa da reddedilir; sessizce eklenmez."""
        cases = [_case("GRADE-01")]
        del cases[0]["expected_score"]
        workspace.write(cases)
        with pytest.raises(packet_offline.PacketError, match="expected_score"):
            workspace.files(size=1)

    def test_gosterilen_kaynak_diskte_yoksa_reddedilir(self, workspace: Workspace) -> None:
        """Okunamayan bir kaynağa bakılarak etiket verilemez."""
        workspace.write([_case("GRADE-01", file_name="olmayan.pdf")])
        with pytest.raises(packet_offline.PacketError, match="materyalde bulunamadı"):
            workspace.files(size=1)

    def test_dolu_vaka_etiket_alani_reddedilir(self, workspace: Workspace) -> None:
        """Dolu `expected_score` REDDEDİLİR — sessizce boşaltılmaz."""
        cases = [_case("GRADE-01")]
        cases[0]["expected_score"] = 85
        workspace.write(cases)
        with pytest.raises(packet_offline.PacketError, match="dolu"):
            workspace.files(size=1)

    def test_dolu_cevap_etiket_alani_reddedilir(self, workspace: Workspace) -> None:
        """Öğrenci cevabının `human_expected_score` alanı da boş olmalı."""
        cases = [_case("GRADE-01")]
        cases[0]["student_answers"][1]["human_expected_score"] = 50
        workspace.write(cases)
        with pytest.raises(packet_offline.PacketError, match="human_expected_score"):
            workspace.files(size=1)

    def test_kosulmamis_vaka_sonuc_uyduramaz(self, workspace: Workspace) -> None:
        """`result` yalnız `not_run` olabilir; koşulmamış bir sonuç geçmiş sayılmaz."""
        cases = [_case("GRADE-01")]
        cases[0]["result"] = "passed"
        workspace.write(cases)
        with pytest.raises(packet_offline.PacketError, match="not_run"):
            workspace.files(size=1)

    def test_diskteki_pakete_yazilan_etiket_reddedilir(self, workspace: Workspace) -> None:
        """Elle doldurulmuş bir `labeler_fields` bütünlük kontrolünden geçemez."""
        packet = json.loads(workspace.files()[packet_offline.PACKET_FILE])
        packet["examples"][0]["labeler_fields"]["label"] = "doğru"
        with pytest.raises(packet_offline.PacketError, match="dolu"):
            packet_offline.check_packet_integrity(packet)

    def test_bos_girdi_cokertmez(self, workspace: Workspace, tmp_path: Path) -> None:
        """Boş vaka listesi yığın izi değil, anlamlı Türkçe hata üretir."""
        workspace.write([])
        with pytest.raises(packet_offline.PacketError, match="hiç örnek yok"):
            workspace.files(size=1)
        assert workspace.build(tmp_path / "bos") == 2

    def test_yetersiz_ornek_anlamli_hata(self, tmp_path: Path) -> None:
        """Depodaki gerçek taslakta 13 örnek var; 25 istenirse paket üretilmez."""
        with pytest.raises(packet_offline.PacketError) as error:
            packet_offline.packet_files(
                cases_path=REPO_CASES,
                material_dir=REPO_MATERIAL,
                size=packet_offline.E3_MINIMUM_EXAMPLES,
            )
        message = str(error.value)
        assert str(REPO_POOL_SIZE) in message
        assert str(packet_offline.E3_MINIMUM_EXAMPLES) in message


class TestNoAnswerLeak:
    def test_etiket_formu_cevap_anahtarini_sizdirmaz(self, workspace: Workspace) -> None:
        """Form çıpayı hiçbir biçimde taşımamalı — kimlikte bile."""
        files = workspace.files()
        for name in packet_offline.LABEL_FILES:
            form = files[name].decode("utf-8")
            for anchor in ANCHORS:
                assert anchor not in form
            assert "anchor" not in form

    def test_paket_cikpayi_tasimaz_anahtar_ayri_dosyada(self, workspace: Workspace) -> None:
        """`packet.json` çıpasız; çıpalar yalnız `answer_key.json` içinde."""
        files = workspace.files()
        packet_text = files[packet_offline.PACKET_FILE].decode("utf-8")
        assert "anchor" not in packet_text
        key = json.loads(files[packet_offline.ANSWER_KEY_FILE])
        assert key["kind"] == packet_offline.ANSWER_KEY_KIND
        assert set(key["anchors"]) == set(_example_ids(files))

    def test_ornek_kimligi_sirayi_da_ele_vermez(self, workspace: Workspace) -> None:
        """Kimlik içerikten türer: ne çıpayı ne de taslaktaki sırayı yazar.

        Sıra numarası kullanılsaydı `-1` her zaman `correct` demek olurdu; içerik
        özeti bunu yapmaz ama örneğe her koşuda aynı kimliği verir — tohum değişip
        sıralama değişse bile. Test tam olarak bu iki özelliği birlikte sabitler.
        """
        first = json.loads(workspace.files(seed=1)[packet_offline.PACKET_FILE])
        second = json.loads(workspace.files(seed=2)[packet_offline.PACKET_FILE])
        answers = {}
        for packet in (first, second):
            for example in packet["examples"]:
                suffix = example["example_id"].rsplit("-", 1)[1]
                assert len(suffix) == 8
                assert set(suffix) <= set("0123456789abcdef")
                # Aynı kimlik iki pakette de AYNI cevabı gösteriyor: kimlik konumdan
                # değil içerikten geliyor demektir.
                previous = answers.setdefault(example["example_id"], example["answer"])
                assert previous == example["answer"]
        shared = {example["example_id"] for example in first["examples"]} & {
            example["example_id"] for example in second["examples"]
        }
        assert shared


class TestVerify:
    def test_verify_ayni_pakette_fark_gormez(self, workspace: Workspace, tmp_path: Path) -> None:
        output = tmp_path / "packet"
        assert workspace.build(output) == 0
        assert workspace.verify(output) == 0
        result = packet_offline.verify_packet(output, workspace.files())
        assert result["identical"] is True
        assert result["differences"] == []

    def test_verify_degisen_icerigi_gorur(self, workspace: Workspace, tmp_path: Path) -> None:
        """Etiket formuna tek satır eklenmesi bile farktır."""
        output = tmp_path / "packet"
        assert workspace.build(output) == 0
        form = output / packet_offline.LABEL_FILES[0]
        form.write_text(form.read_text(encoding="utf-8") + "\nelle eklendi\n", encoding="utf-8")
        assert workspace.verify(output) == 3
        result = packet_offline.verify_packet(output, workspace.files())
        assert result["identical"] is False
        assert [difference["kind"] for difference in result["differences"]] == ["content"]

    def test_verify_eksik_ve_fazla_dosyayi_gorur(
        self, workspace: Workspace, tmp_path: Path
    ) -> None:
        output = tmp_path / "packet"
        assert workspace.build(output) == 0
        (output / packet_offline.ANSWER_KEY_FILE).unlink()
        (output / "elle_eklenen.md").write_text("fazladan", encoding="utf-8")
        result = packet_offline.verify_packet(output, workspace.files())
        kinds = {difference["file"]: difference["kind"] for difference in result["differences"]}
        assert kinds[packet_offline.ANSWER_KEY_FILE] == "missing"
        assert kinds["elle_eklenen.md"] == "extra"

    def test_verify_farkli_tohumu_fark_sayar(self, workspace: Workspace, tmp_path: Path) -> None:
        """Başka tohumla üretilmiş paket "aynı" sayılmaz."""
        output = tmp_path / "packet"
        assert workspace.build(output, seed=1) == 0
        assert workspace.verify(output, seed=2) == 3

    def test_var_olan_dizinin_uzerine_yazilmaz(self, workspace: Workspace, tmp_path: Path) -> None:
        """Doldurulmuş etiket dosyaları boş formla ezilmemeli."""
        output = tmp_path / "packet"
        assert workspace.build(output) == 0
        assert workspace.build(output) == 2


class TestReconcile:
    def _packet(self, workspace: Workspace, tmp_path: Path) -> tuple[Path, dict[str, bytes]]:
        output = tmp_path / "packet"
        assert workspace.build(output) == 0
        return output, workspace.files()

    def _labels(self, output: Path, first: list[str], second: list[str]) -> tuple[Path, Path]:
        paths = []
        for name, values in zip(packet_offline.LABEL_FILES, (first, second), strict=True):
            path = output.parent / f"dolu_{name}"
            path.write_text(
                _fill((output / name).read_text(encoding="utf-8"), values), encoding="utf-8"
            )
            paths.append(path)
        return paths[0], paths[1]

    def test_uyum_hesaplanir_ve_rapor_edilemez_damgasi_tasir(
        self, workspace: Workspace, tmp_path: Path
    ) -> None:
        output, files = self._packet(workspace, tmp_path)
        packet = json.loads(files[packet_offline.PACKET_FILE])
        key = json.loads(files[packet_offline.ANSWER_KEY_FILE])
        labels = ["doğru", "kısmen", "yanlış"] * 9
        first, second = self._labels(output, labels[:25], labels[:25])
        report = packet_offline.reconcile(
            packet,
            key,
            first,
            second,
            first_name="A Kişisi",
            second_name="B Kişisi",
            attested=True,
        )
        assert report["agreement"]["n"] == 25
        assert report["agreement"]["raw_agreement"] == pytest.approx(1.0)
        assert report["disagreement_count"] == 0
        assert report["reportable"] is False
        assert report["blockers"]

    def test_uyusmazlik_ayri_listeye_cikar(self, workspace: Workspace, tmp_path: Path) -> None:
        output, files = self._packet(workspace, tmp_path)
        packet = json.loads(files[packet_offline.PACKET_FILE])
        base = ["doğru", "kısmen", "yanlış"] * 9
        other = list(base)
        other[0] = "yanlış"
        first, second = self._labels(output, base[:25], other[:25])
        report = packet_offline.reconcile(
            packet, None, first, second, first_name="A", second_name="B", attested=True
        )
        assert report["disagreement_count"] == 1
        assert report["agreement"]["agreed"] == 24
        assert report["disagreements"][0]["resolution_status"] == "pending"
        assert report["disagreements"][0]["final_label"] is None
        assert report["anchor_concordance"] is None

    def test_sirali_uyum_rater_agreement_kullanir(
        self, workspace: Workspace, tmp_path: Path
    ) -> None:
        """`rater_agreement` varsa QWK oradan gelir; arka uç rapora YAZILIR."""
        output, files = self._packet(workspace, tmp_path)
        packet = json.loads(files[packet_offline.PACKET_FILE])
        base = ["doğru", "kısmen", "yanlış"] * 9
        other = ["kısmen", "kısmen", "yanlış"] * 9
        first, second = self._labels(output, base[:25], other[:25])
        report = packet_offline.reconcile(
            packet, None, first, second, first_name="A", second_name="B", attested=True
        )
        ordinal = report["ordinal_agreement"]
        assert ordinal["backend"] == "rater_agreement.agreement_report"
        assert ordinal["categories"] == [0, 1, 2]
        # Kuadratik ağırlık yakın anlaşmazlığı nominalden daha az cezalandırır.
        assert ordinal["quadratic_weighted_kappa"] > ordinal["nominal_kappa"]
        assert ordinal["nominal_kappa"] == pytest.approx(report["agreement"]["cohens_kappa"])

    def test_bagimsizlik_beyani_ve_iki_ayri_kisi_zorunlu(
        self, workspace: Workspace, tmp_path: Path
    ) -> None:
        output, files = self._packet(workspace, tmp_path)
        packet = json.loads(files[packet_offline.PACKET_FILE])
        labels = ["doğru"] * 25
        first, second = self._labels(output, labels, labels)
        with pytest.raises(packet_offline.PacketError, match="attest-independent"):
            packet_offline.reconcile(
                packet, None, first, second, first_name="A", second_name="B", attested=False
            )
        with pytest.raises(packet_offline.PacketError, match="aynı kişi"):
            packet_offline.reconcile(
                packet, None, first, second, first_name="A", second_name="a", attested=True
            )

    def test_eksik_ve_gecersiz_etiket_reddedilir(
        self, workspace: Workspace, tmp_path: Path
    ) -> None:
        """Doldurulmamış satır atlanmaz; ölçek dışı değer kabul edilmez."""
        output, _ = self._packet(workspace, tmp_path)
        blank = output / packet_offline.LABEL_FILES[0]
        with pytest.raises(packet_offline.PacketError, match="etiketlenmemiş"):
            packet_offline.load_labels(blank)
        invalid = output.parent / "gecersiz.md"
        invalid.write_text(
            _fill(blank.read_text(encoding="utf-8"), ["destekleniyor"] * 25), encoding="utf-8"
        )
        with pytest.raises(packet_offline.PacketError, match="geçersiz etiket"):
            packet_offline.load_labels(invalid)

    def test_sira_farki_yakalanir(self, workspace: Workspace, tmp_path: Path) -> None:
        """İki dosya farklı sırada doldurulmuşsa etiketler yanlış örneğe düşer."""
        output, files = self._packet(workspace, tmp_path)
        packet = json.loads(files[packet_offline.PACKET_FILE])
        labels = ["doğru"] * 25
        first, second = self._labels(output, labels, labels)
        blocks = second.read_text(encoding="utf-8").split("\n## ")
        shuffled = "\n## ".join([blocks[0], blocks[2], blocks[1], *blocks[3:]])
        second.write_text(shuffled, encoding="utf-8")
        with pytest.raises(packet_offline.PacketError, match="sırası paketle"):
            packet_offline.reconcile(
                packet, None, first, second, first_name="A", second_name="B", attested=True
            )

    def test_cli_raporu_var_olan_yolun_uzerine_yazmaz(
        self, workspace: Workspace, tmp_path: Path
    ) -> None:
        output, _ = self._packet(workspace, tmp_path)
        labels = ["doğru"] * 25
        first, second = self._labels(output, labels, labels)
        report_path = tmp_path / "rapor.json"
        arguments = [
            "--output-dir",
            str(output),
            "--cases",
            str(workspace.cases_path),
            "--material-dir",
            str(workspace.material_dir),
            "--first",
            str(first),
            "--second",
            str(second),
            "--labeler-1",
            "A Kişisi",
            "--labeler-2",
            "B Kişisi",
            "--attest-independent",
            "--report-out",
            str(report_path),
        ]
        assert packet_offline.main(arguments) == 0
        assert json.loads(report_path.read_text(encoding="utf-8"))["reportable"] is False
        assert packet_offline.main(arguments) == 2


class TestRepositoryDraft:
    def test_depodaki_taslak_bos_etiketlerle_geliyor(self) -> None:
        """Depodaki `assessment_cases.json` bugün hiçbir dolu insan alanı taşımamalı."""
        draft = packet_offline.load_cases(REPO_CASES)
        for case in draft["cases"]:
            packet_offline.check_blank_labels(case)
        examples = packet_offline.build_examples(draft["cases"], material_dir=REPO_MATERIAL)
        assert len(examples) == REPO_POOL_SIZE

    def test_depodaki_taslaktan_uretilen_paket_e3_olcutunu_karsilamiyor(
        self, tmp_path: Path
    ) -> None:
        """Ölçülen gerçek: havuz 13, ölçüt 25. Paket bunu KENDİ İÇİNDE yazıyor."""
        files = packet_offline.packet_files(
            cases_path=REPO_CASES, material_dir=REPO_MATERIAL, size=REPO_POOL_SIZE
        )
        packet = json.loads(files[packet_offline.PACKET_FILE])
        assert packet["acceptance"]["meets_minimum"] is False
        assert packet["acceptance"]["real_provider_quality"] == "pending"
        assert packet["acceptance"]["independent_human_review"] == "pending"
        assert packet["acceptance"]["grading_run"] == "not_run"
        form = files[packet_offline.LABEL_FILES[0]].decode("utf-8")
        assert "ÖRNEK SAYISI YETERSİZ" in form
