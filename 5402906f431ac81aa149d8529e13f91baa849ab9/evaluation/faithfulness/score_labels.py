"""T047 bağımsız faithfulness etiketlerini doğrular ve uyumu hesaplar.

Bu araç etiketleme yapmaz. İki insanın tartışma öncesi doldurduğu ayrı dosyaları,
gerçek sağlayıcıyla çekilmiş örnekleme bağlar. Geçersiz/fake-provider örneklemi,
eksik etiketi, kimlik/sıra farkını veya aynı etiketleyiciyi sessizce kabul etmez.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVALUATION_ROOT = HERE.parent
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

import metrics  # noqa: E402

ALLOWED_LABELS = ("destekleniyor", "kısmen", "desteklenmiyor")
ITEM_RE = re.compile(r"^##\s+\d+\.\s+([A-Za-z0-9][A-Za-z0-9_-]*)\s+\([^)]+\)\s*$")
LABEL_RE = re.compile(r"^\*\*Etiket:\*\*.*?→\s*(.*?)\s*$")
NOTE_RE = re.compile(r"^\*\*Not:\*\*\s*(.*?)\s*$")


class EvaluationInputError(ValueError):
    """İnsan değerlendirme girdisi kanıt üretmeye uygun değil."""


@dataclass(frozen=True, slots=True)
class Sample:
    file_name: str
    sha256: str
    seed: int
    size: int
    pulled_at: str
    llm_server_note: str
    item_ids: tuple[str, ...]
    questions: dict[str, str]


@dataclass(frozen=True, slots=True)
class LabelEntry:
    item_id: str
    label: str
    note: str


@dataclass(frozen=True, slots=True)
class LabelSet:
    file_name: str
    sha256: str
    entries: tuple[LabelEntry, ...]


def _read_bytes(path: Path, description: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise EvaluationInputError(f"{description} okunamadı: {path}: {exc}") from exc


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_sample(path: Path) -> Sample:
    """Örneklemi yükle ve raporlanabilir olduğuna fail-closed karar ver."""
    content = _read_bytes(path, "Örneklem")
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EvaluationInputError(f"Örneklem geçerli UTF-8 JSON değil: {path}") from exc

    if not isinstance(payload, dict) or payload.get("kind") != "faithfulness_sample":
        raise EvaluationInputError("kind=faithfulness_sample olmayan dosya kullanılamaz.")
    if payload.get("fake_provider_declared") is not False:
        raise EvaluationInputError(
            "Örneklem gerçek sağlayıcıyla çekildiğini açıkça kanıtlamıyor "
            "(fake_provider_declared tam olarak false olmalı)."
        )

    llm_server_note = payload.get("llm_server_note")
    if not isinstance(llm_server_note, str) or not llm_server_note.strip():
        raise EvaluationInputError("Örneklem LLM sağlayıcı notu taşımıyor.")
    upper_note = llm_server_note.upper().replace(" ", "")
    if "FAKE_PROVIDER=FALSE" not in upper_note or "FAKE_PROVIDER=TRUE" in upper_note:
        raise EvaluationInputError(
            "LLM sağlayıcı notu gerçek koşuyu açıkça doğrulamıyor (FAKE_PROVIDER=false gerekli)."
        )

    records = payload.get("records")
    if not isinstance(records, list):
        raise EvaluationInputError("Örneklem records listesi taşımıyor.")
    size = payload.get("size")
    if not isinstance(size, int) or size != len(records):
        raise EvaluationInputError("Örneklem size alanı ile kayıt sayısı eşleşmiyor.")
    if not 20 <= size <= 30:
        raise EvaluationInputError("T047 örneklemi 20-30 cevap içermeli.")

    item_ids: list[str] = []
    questions: dict[str, str] = {}
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise EvaluationInputError(f"Örneklemdeki {index}. kayıt nesne değil.")
        if record.get("kanit_degil") is not False:
            raise EvaluationInputError(
                f"{record.get('item_id', index)} kaydı kanıt olarak işaretlenmemiş."
            )
        item_id = record.get("item_id")
        question = record.get("question")
        if not isinstance(item_id, str) or not item_id:
            raise EvaluationInputError(f"Örneklemdeki {index}. kaydın item_id alanı yok.")
        if item_id in questions:
            raise EvaluationInputError(f"Örneklemde yinelenen item_id: {item_id}")
        if not isinstance(question, str) or not question.strip():
            raise EvaluationInputError(f"{item_id} için soru metni yok.")
        if record.get("status") != "answered":
            raise EvaluationInputError(f"{item_id} gerçek bir answered cevabı taşımıyor.")
        answer = record.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise EvaluationInputError(f"{item_id} cevap metni boş.")
        item_ids.append(item_id)
        questions[item_id] = question.strip()

    seed = payload.get("seed")
    pulled_at = payload.get("pulled_at")
    if not isinstance(seed, int):
        raise EvaluationInputError("Örneklem yeniden üretilebilir bir integer seed taşımıyor.")
    if not isinstance(pulled_at, str) or not pulled_at:
        raise EvaluationInputError("Örneklem pulled_at zaman damgası taşımıyor.")

    return Sample(
        file_name=path.name,
        sha256=_sha256(content),
        seed=seed,
        size=size,
        pulled_at=pulled_at,
        llm_server_note=llm_server_note.strip(),
        item_ids=tuple(item_ids),
        questions=questions,
    )


def _normalise_label(raw: str, item_id: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    if not value or set(value) <= {"_"} or value == "[ETİKETLENMEDİ]":
        raise EvaluationInputError(f"{item_id} henüz etiketlenmemiş.")
    if value not in ALLOWED_LABELS:
        allowed = ", ".join(ALLOWED_LABELS)
        raise EvaluationInputError(f"{item_id} için geçersiz etiket {value!r}; izinli: {allowed}.")
    return value


def load_labels(path: Path) -> LabelSet:
    """pull_sample.py biçimindeki Markdown etiket dosyasını kesin olarak ayrıştır."""
    content = _read_bytes(path, "Etiket dosyası")
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise EvaluationInputError(f"Etiket dosyası UTF-8 değil: {path}") from exc

    current_item: str | None = None
    ordered_ids: list[str] = []
    labels: dict[str, str] = {}
    notes: dict[str, str] = {}

    for line in lines:
        item_match = ITEM_RE.match(line)
        if item_match:
            current_item = item_match.group(1)
            if current_item in ordered_ids:
                raise EvaluationInputError(f"Etiket dosyasında yinelenen item_id: {current_item}")
            ordered_ids.append(current_item)
            continue

        label_match = LABEL_RE.match(line)
        if label_match:
            if current_item is None:
                raise EvaluationInputError("Bir etiket, item başlığından önce yazılmış.")
            if current_item in labels:
                raise EvaluationInputError(f"{current_item} için birden fazla etiket satırı var.")
            labels[current_item] = _normalise_label(label_match.group(1), current_item)
            continue

        note_match = NOTE_RE.match(line)
        if note_match and current_item is not None:
            note = note_match.group(1).strip()
            notes[current_item] = "" if not note or set(note) <= {"_"} else note

    if not ordered_ids:
        raise EvaluationInputError(f"Etiket dosyasında hiçbir item bulunamadı: {path}")
    missing = [item_id for item_id in ordered_ids if item_id not in labels]
    if missing:
        raise EvaluationInputError(f"Etiket satırı olmayan item(lar): {', '.join(missing)}")

    entries = tuple(
        LabelEntry(item_id=item_id, label=labels[item_id], note=notes.get(item_id, ""))
        for item_id in ordered_ids
    )
    return LabelSet(file_name=path.name, sha256=_sha256(content), entries=entries)


def _validate_alignment(sample: Sample, first: LabelSet, second: LabelSet) -> None:
    first_ids = tuple(entry.item_id for entry in first.entries)
    second_ids = tuple(entry.item_id for entry in second.entries)
    if first_ids != sample.item_ids:
        raise EvaluationInputError(
            f"{first.file_name} item kimlikleri/sırası örneklemle birebir eşleşmiyor."
        )
    if second_ids != sample.item_ids:
        raise EvaluationInputError(
            f"{second.file_name} item kimlikleri/sırası örneklemle birebir eşleşmiyor."
        )


def _distribution(entries: tuple[LabelEntry, ...]) -> dict[str, int]:
    counts = Counter(entry.label for entry in entries)
    return {label: counts[label] for label in ALLOWED_LABELS}


def build_report(
    sample: Sample,
    first: LabelSet,
    second: LabelSet,
    *,
    first_name: str,
    second_name: str,
) -> dict[str, Any]:
    """Doğrulanmış girdilerden tartışma öncesi, değişmez uyum kaydı üret."""
    _validate_alignment(sample, first, second)
    first_labels = [entry.label for entry in first.entries]
    second_labels = [entry.label for entry in second.entries]
    agreement = metrics.label_agreement(first_labels, second_labels)

    confusion = {
        first_label: {
            second_label: sum(
                1
                for left, right in zip(first_labels, second_labels, strict=True)
                if left == first_label and right == second_label
            )
            for second_label in ALLOWED_LABELS
        }
        for first_label in ALLOWED_LABELS
    }
    items = [
        {
            "item_id": left.item_id,
            "labeler_1_label": left.label,
            "labeler_2_label": right.label,
            "agreed": left.label == right.label,
        }
        for left, right in zip(first.entries, second.entries, strict=True)
    ]
    disagreements = [
        {
            "item_id": left.item_id,
            "question": sample.questions[left.item_id],
            "labeler_1_label": left.label,
            "labeler_1_note": left.note,
            "labeler_2_label": right.label,
            "labeler_2_note": right.note,
            "resolution_status": "pending",
            "final_label": None,
            "adjudication_note": None,
        }
        for left, right in zip(first.entries, second.entries, strict=True)
        if left.label != right.label
    ]

    return {
        "schema_version": 1,
        "kind": "faithfulness_human_evaluation",
        "generated_at": datetime.now(UTC).isoformat(),
        "reportable": True,
        "methodology": {
            "independent_labeling_attested": True,
            "agreement_basis": "pre_adjudication_labels",
            "allowed_labels": list(ALLOWED_LABELS),
        },
        "sample": {
            "file": sample.file_name,
            "sha256": sample.sha256,
            "seed": sample.seed,
            "size": sample.size,
            "pulled_at": sample.pulled_at,
            "llm_server_note": sample.llm_server_note,
            "fake_provider_declared": False,
        },
        "labelers": [
            {
                "name": first_name,
                "file": first.file_name,
                "sha256": first.sha256,
                "distribution": _distribution(first.entries),
            },
            {
                "name": second_name,
                "file": second.file_name,
                "sha256": second.sha256,
                "distribution": _distribution(second.entries),
            },
        ],
        "agreement": agreement.as_dict(),
        "confusion_matrix": confusion,
        "items": items,
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
    }


def _markdown_cell(value: object) -> str:
    return str(value or "—").replace("|", "\\|").replace("\n", " ")


def render_adjudication(report: dict[str, Any]) -> str:
    """Uyuşmazlık çözümü için boş nihai karar alanları olan Markdown üret."""
    agreement = report["agreement"]
    kappa = agreement["cohens_kappa"]
    kappa_text = "tanımsız" if kappa is None else f"{kappa:.4f}"
    labelers = report["labelers"]
    lines = [
        "# Faithfulness uyuşmazlık çözümü",
        "",
        "> Ham uyum ve Cohen's kappa, tartışma öncesi bağımsız etiketlerden",
        "> dondurulmuştur. Aşağıdaki nihai kararlar bu değerlerin üzerine yazılmaz.",
        "",
        "| Alan | Değer |",
        "|---|---|",
        f"| Örneklem | `{report['sample']['file']}` |",
        f"| Örneklem SHA-256 | `{report['sample']['sha256']}` |",
        f"| Etiketleyici 1 | {_markdown_cell(labelers[0]['name'])} |",
        f"| Etiketleyici 2 | {_markdown_cell(labelers[1]['name'])} |",
        f"| n | {agreement['n']} |",
        f"| Ham uyum | {agreement['raw_agreement']:.4f} |",
        f"| Cohen's kappa | {kappa_text} |",
        f"| Uyuşmazlık | {report['disagreement_count']} |",
        "",
    ]

    disagreements = report["disagreements"]
    if not disagreements:
        lines += ["İki etiketleyici bütün maddelerde aynı etiketi verdi.", ""]
        return "\n".join(lines)

    for index, item in enumerate(disagreements, start=1):
        lines += [
            f"## {index}. {item['item_id']}",
            "",
            f"**Soru:** {_markdown_cell(item['question'])}",
            "",
            (
                f"- **{_markdown_cell(labelers[0]['name'])}:** "
                f"`{item['labeler_1_label']}` — {_markdown_cell(item['labeler_1_note'])}"
            ),
            (
                f"- **{_markdown_cell(labelers[1]['name'])}:** "
                f"`{item['labeler_2_label']}` — {_markdown_cell(item['labeler_2_note'])}"
            ),
            "",
            ("**Nihai etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________"),
            "",
            "**Gerekçe:** ______________",
            "",
            "**Hakem ve tarih:** ______________",
            "",
        ]
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _require_distinct_paths(paths: list[Path]) -> None:
    resolved = [path.resolve() for path in paths]
    if len(resolved) != len(set(resolved)):
        raise EvaluationInputError("Örneklem, etiket ve çıktı yolları birbirinden farklı olmalı.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T047 bağımsız etiket uyumu")
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--labeler-1", required=True)
    parser.add_argument("--labeler-2", required=True)
    parser.add_argument(
        "--attest-independent",
        action="store_true",
        help="İki dosyanın tartışma öncesi, birbirini görmeden doldurulduğunu onayla.",
    )
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--adjudication-out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        first_name = args.labeler_1.strip()
        second_name = args.labeler_2.strip()
        if not args.attest_independent:
            raise EvaluationInputError(
                "Rapor için iki dosyanın bağımsız üretildiği --attest-independent ile onaylanmalı."
            )
        if not first_name or not second_name:
            raise EvaluationInputError("İki etiketleyicinin adı da boş olamaz.")
        if first_name.casefold() == second_name.casefold():
            raise EvaluationInputError("İki bağımsız etiketleyici aynı kişi olamaz.")
        _require_distinct_paths(
            [args.sample, args.first, args.second, args.json_out, args.adjudication_out]
        )

        sample = load_sample(args.sample)
        first = load_labels(args.first)
        second = load_labels(args.second)
        report = build_report(
            sample,
            first,
            second,
            first_name=first_name,
            second_name=second_name,
        )
        _atomic_write(args.json_out, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        _atomic_write(args.adjudication_out, render_adjudication(report))
    except EvaluationInputError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2

    print(
        f"n={report['agreement']['n']} · ham uyum={report['agreement']['raw_agreement']:.4f} "
        f"· uyuşmazlık={report['disagreement_count']}"
    )
    print(f"JSON: {args.json_out}")
    print(f"Hakem formu: {args.adjudication_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
