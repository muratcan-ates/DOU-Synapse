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
    # Synthetic transport receipts exercise the scorer; this fixture is not model evidence.
    from provenance import evaluation_request_digest

    from tests.test_eval_readiness import receipt_fixture, runtime_fixture

    runtime = runtime_fixture()
    for record in records:
        body = {"status": record["status"], "answer": record["answer"], "citations": []}
        receipt = receipt_fixture(runtime, body)
        receipt["request_digest"] = evaluation_request_digest(
            course_id="course", question=record["question"], mode="qa"
        )
        record.update(citations=[], response_body=body, response_receipt=receipt)
    return {
        "course_id": "course",
        "runtime_manifest": runtime,
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


@pytest.mark.parametrize("existing_index", [3, 4])
def test_existing_report_or_human_adjudication_is_never_overwritten(
    tmp_path: Path, existing_index: int
) -> None:
    paths = _write_inputs(tmp_path)
    existing = paths[existing_index]
    original = "İnsan kararı: desteklenmiyor; 7 Eylül.\n".encode()
    existing.write_bytes(original)

    assert score_labels.main(_argv(paths)) == 2
    assert existing.read_bytes() == original
    assert not paths[4 if existing_index == 3 else 3].exists()


def test_rerun_preserves_completed_reports_and_human_decision(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    assert score_labels.main(_argv(paths)) == 0
    original_report = paths[3].read_bytes()
    human_decision = b"Hakem: kaynak desteklemiyor.\n"
    paths[4].write_bytes(human_decision)

    assert score_labels.main(_argv(paths)) == 2
    assert paths[3].read_bytes() == original_report
    assert paths[4].read_bytes() == human_decision


@pytest.mark.parametrize("edit_first", [False, True])
def test_concurrent_output_creation_preserves_all_published_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, edit_first: bool
) -> None:
    import os

    paths = _write_inputs(tmp_path)
    original_link = os.link
    human_decision = b"Concurrent human decision"

    def concurrent_link(source: Any, destination: Any, **kwargs: Any) -> None:
        if Path(destination) == paths[4]:
            paths[4].write_bytes(human_decision)
            if edit_first:
                paths[3].write_bytes(human_decision)
        original_link(source, destination, **kwargs)

    monkeypatch.setattr(os, "link", concurrent_link)
    assert score_labels.main(_argv(paths)) == 2
    assert paths[4].read_bytes() == human_decision
    if edit_first:
        assert paths[3].read_bytes() == human_decision
    else:
        assert json.loads(paths[3].read_text())["reportable"] is True
    assert not list(tmp_path.glob(".faithfulness-*"))


def test_dangling_output_symlink_is_not_followed(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    outside = tmp_path / "missing-human-decision.md"
    paths[4].symlink_to(outside)

    assert score_labels.main(_argv(paths)) == 2
    assert paths[4].is_symlink()
    assert not outside.exists()
    assert not paths[3].exists()
