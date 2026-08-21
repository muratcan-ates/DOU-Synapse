"""T047 insan etiketlerinin kanıt kapısını sabitleyen testler."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

FAITHFULNESS_ROOT = Path(__file__).resolve().parents[3] / "evaluation" / "faithfulness"
if str(FAITHFULNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(FAITHFULNESS_ROOT))

import score_labels  # noqa: E402


def _sample(*, fake: bool = False) -> dict[str, Any]:
    records = [
        {
            "item_id": f"H-{index:03d}",
            "question": f"Soru {index}?",
            "status": "answered",
            "answer": f"Gerçek sağlayıcı cevabı {index}.",
            "kanit_degil": fake,
        }
        for index in range(1, 21)
    ]
    return {
        "kind": "faithfulness_sample",
        "pulled_at": "2026-08-10T00:30:00+03:00",
        "seed": 20260809,
        "size": len(records),
        "llm_server_note": "LLM_FAKE_PROVIDER=false; primary=groq/test",
        "fake_provider_declared": fake,
        "records": records,
    }


def _labels(values: list[str], *, reverse: bool = False) -> str:
    item_ids = [f"H-{index:03d}" for index in range(1, 21)]
    if reverse:
        item_ids.reverse()
    sections = ["# Etiketler", ""]
    for index, (item_id, label) in enumerate(zip(item_ids, values, strict=True), start=1):
        sections += [
            f"## {index}. {item_id} (direct)",
            "",
            f"**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → {label}",
            "",
            f"**Not:** not {index}",
            "",
        ]
    return "\n".join(sections)


def _write_inputs(
    tmp_path: Path,
    *,
    fake: bool = False,
    first_values: list[str] | None = None,
    second_values: list[str] | None = None,
    reverse_second: bool = False,
) -> tuple[Path, Path, Path, Path, Path]:
    sample_path = tmp_path / "sample.json"
    first_path = tmp_path / "first.md"
    second_path = tmp_path / "second.md"
    json_out = tmp_path / "result.json"
    adjudication_out = tmp_path / "adjudication.md"
    sample_path.write_text(json.dumps(_sample(fake=fake)), encoding="utf-8")
    first_path.write_text(_labels(first_values or ["destekleniyor"] * 20), encoding="utf-8")
    second_path.write_text(
        _labels(second_values or ["destekleniyor"] * 20, reverse=reverse_second),
        encoding="utf-8",
    )
    return sample_path, first_path, second_path, json_out, adjudication_out


def _argv(paths: tuple[Path, Path, Path, Path, Path]) -> list[str]:
    sample, first, second, json_out, adjudication_out = paths
    return [
        "--sample",
        str(sample),
        "--first",
        str(first),
        "--second",
        str(second),
        "--labeler-1",
        "Ayşe",
        "--labeler-2",
        "Burak",
        "--attest-independent",
        "--json-out",
        str(json_out),
        "--adjudication-out",
        str(adjudication_out),
    ]


def test_gecerli_iki_etiket_agreement_ve_hakem_formu_uretir(tmp_path: Path) -> None:
    first = ["destekleniyor"] * 19 + ["kısmen"]
    second = ["destekleniyor"] * 20
    paths = _write_inputs(tmp_path, first_values=first, second_values=second)

    assert score_labels.main(_argv(paths)) == 0

    report = json.loads(paths[3].read_text(encoding="utf-8"))
    assert report["reportable"] is True
    assert report["methodology"]["agreement_basis"] == "pre_adjudication_labels"
    assert report["agreement"]["n"] == 20
    assert report["agreement"]["raw_agreement"] == pytest.approx(0.95)
    assert report["disagreement_count"] == 1
    assert len(report["items"]) == 20
    assert sum(not item["agreed"] for item in report["items"]) == 1
    assert report["disagreements"][0]["item_id"] == "H-020"
    assert len(report["sample"]["sha256"]) == 64
    adjudication = paths[4].read_text(encoding="utf-8")
    assert "Ham uyum | 0.9500" in adjudication
    assert "## 1. H-020" in adjudication
    assert "**Nihai etiket:**" in adjudication


def test_fake_provider_orneklemi_sonuc_uretmeden_reddedilir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _write_inputs(tmp_path, fake=True)

    assert score_labels.main(_argv(paths)) == 2

    assert "gerçek sağlayıcıyla" in capsys.readouterr().err
    assert not paths[3].exists()
    assert not paths[4].exists()


def test_eksik_etiket_fail_closed_reddedilir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = ["destekleniyor"] * 19 + ["______________"]
    paths = _write_inputs(tmp_path, second_values=labels)

    assert score_labels.main(_argv(paths)) == 2

    assert "H-020 henüz etiketlenmemiş" in capsys.readouterr().err
    assert not paths[3].exists()


def test_item_sirasi_orneklemle_eslesmek_zorunda(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _write_inputs(tmp_path, reverse_second=True)

    assert score_labels.main(_argv(paths)) == 2

    assert "kimlikleri/sırası" in capsys.readouterr().err


def test_ayni_kisi_iki_etiketleyici_olamaz(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _write_inputs(tmp_path)
    argv = _argv(paths)
    argv[argv.index("Burak")] = "ayşe"

    assert score_labels.main(argv) == 2

    assert "aynı kişi olamaz" in capsys.readouterr().err


def test_bagimsizlik_onayi_olmadan_rapor_yazilmaz(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _write_inputs(tmp_path)
    argv = _argv(paths)
    argv.remove("--attest-independent")

    assert score_labels.main(argv) == 2

    assert "--attest-independent" in capsys.readouterr().err
    assert not paths[3].exists()


def test_answered_olmayan_kayit_ornekleme_sizmaz(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    payload["records"][0]["status"] = "insufficient_context"
    paths[0].write_text(json.dumps(payload), encoding="utf-8")

    assert score_labels.main(_argv(paths)) == 2

    assert "gerçek bir answered cevabı" in capsys.readouterr().err
    assert not paths[3].exists()
