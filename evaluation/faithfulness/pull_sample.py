#!/usr/bin/env python3
"""T047 — faithfulness örneklemini çeker ve etiketleme dosyalarını hazırlar.

Betik ETİKETLEMEZ. Yaptığı iş, insanın önüne karar verebileceği bir dosya koymaktır:
her cevabın metni, gösterdiği atıflar ve o atıfların **kaynak parçaları** yan yana.
Etiketleyicinin veritabanına ya da API'ye dönmesi gerekmezse etiketleme hem hızlanır
hem de "kaynağı okumadan etiketleme" kuralı fiilen uygulanabilir olur.

Örneklem sabit tohumla seçilir (`--seed`, varsayılan 20260809). Rastgelelik şart:
"ilginç görünen" cevapları seçmek örneklemi bozar ve "beğendiğiniz cevapları
seçtiniz" itirazına verecek cevap kalmaz.

**Sahte sağlayıcı damgası:** harness sunucunun ortamını göremez. `--llm-note` içinde
`FAKE_PROVIDER=true` geçiyorsa çekilen her cevap `kanit_degil: true` ile işaretlenir
ve etiketleme dosyalarının başına uyarı basılır. Sahte sağlayıcı getirilen chunk'ları
özetleyip döndürüyor; böyle bir cevabı "kaynağa sadık" diye etiketlemek totolojidir.

    cd apps/api
    uv run python ../../evaluation/faithfulness/pull_sample.py \\
        --corpus /tmp/corpus_e5.json --api-url http://127.0.0.1:8022 \\
        --llm-note "LLM_FAKE_PROVIDER=true"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
GOLD_SET = HERE.parent / "gold_set" / "holdout.json"

#: Faithfulness yalnız CEVAPLANMASI beklenen sorularda anlamlıdır. Reddedilmesi
#: beklenen bir soruda "cevap kaynağa sadık mı" sorusunun karşılığı yoktur.
SAMPLE_CATEGORIES = ("direct", "multi_chunk")


async def pull(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(HERE.parent))
    import goldset

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    course_id = UUID(corpus["course_id"])
    gold = goldset.load(GOLD_SET)

    pool = [item for item in gold.items if item.category in SAMPLE_CATEGORIES]
    # S311: kriptografik değil — tam tersine, örneklemin YENİDEN ÜRETİLEBİLİR olması
    # için sabit tohumlu bir üreteç şart. Tahmin edilemez olsaydı "beğendiğiniz
    # cevapları seçtiniz" itirazına verecek cevap kalmazdı.
    random.Random(args.seed).shuffle(pool)
    chosen = pool[: args.size]

    import os
    from uuid import uuid4

    from evaluate import git_sha
    from provenance import EvidenceError, digest, response_evidence, utc_now
    from runtime_client import EvaluationClient, EvaluationStopped

    if args.dry_run:
        print(", ".join(item.id for item in chosen))
        return 0
    started = datetime.now().astimezone()
    output_dir = (
        args.output_dir
        or HERE.parent / "results" / f"faithfulness-{started.strftime('%Y%m%dT%H%M%S%f')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / "checkpoint.json"
    binding = digest(
        {
            "corpus": corpus,
            "seed": args.seed,
            "size": args.size,
            "items": [item.id for item in chosen],
            "api_url": args.api_url,
        }
    )
    state = (
        json.loads(checkpoint.read_text())
        if checkpoint.exists()
        else {
            "run_id": str(uuid4()),
            "binding": binding,
            "records": [],
            "runtime_manifest": None,
        }
    )
    if state.get("binding") != binding:
        raise EvidenceError("Devam dosyası farklı korpus/örneklem/API ayarlarına ait.")
    token = args.token or f"dev:{corpus.get('student_id', corpus['instructor_id'])}"
    records = state["records"]
    if (output_dir / "sample.json").exists():
        raise EvidenceError(
            "Tamamlanmış örneklem/etiket dosyalarının üzerine yazılmaz; yeni dizin kullanın."
        )
    try:
        async with EvaluationClient(
            args.api_url,
            token,
            secret=os.environ.get("EVAL_RUNTIME_SECRET"),
            run_id=state["run_id"],
            candidate_sha=git_sha(),
            require_real=args.require_real,
            max_requests=args.max_requests,
        ) as client:
            chosen_by_id = {item.id: item for item in chosen}
            seen: set[str] = set()
            for record in records:
                item = chosen_by_id.get(record.get("item_id"))
                if item is None or item.id in seen:
                    raise EvidenceError("Devam dosyasında bilinmeyen/yinelenen örnek var.")
                seen.add(item.id)
                if client.runtime:
                    body = record.get("response_body")
                    evidence = response_evidence(
                        client.runtime,
                        record.get("response_receipt"),
                        body,
                        {"course_id": str(course_id), "question": item.question, "mode": "qa"},
                    )
                    if evidence["classification"] in {"unknown", "fake"} or not isinstance(
                        body, dict
                    ):
                        raise EvidenceError("Devam dosyası başka sunucu/soru isteğine ait.")
                    if record.get("question") != item.question or any(
                        record.get(key) != body.get(key)
                        for key in ("status", "answer", "citations")
                    ):
                        raise EvidenceError("Devam dosyasının etiketlenecek cevabı değiştirilmiş.")
                    record.update(evidence=evidence, kanit_degil=not evidence["quality_eligible"])
                else:
                    record.update(
                        evidence={"classification": "unknown", "quality_eligible": False},
                        kanit_degil=True,
                    )
            state["runtime_manifest"] = client.runtime
            completed = {record["item_id"] for record in records}
            for item in chosen:
                if item.id in completed:
                    continue
                response = await client.post(
                    f"/courses/{course_id}/chat",
                    json={"question": item.question, "mode": "qa"},
                )
                response.raise_for_status()
                body = response.json()
                evidence = client.evidence(response)
                records.append(
                    {
                        "item_id": item.id,
                        "category": item.category,
                        "question": item.question,
                        "expected_sources": [source.label() for source in item.expected_sources],
                        "notes": item.notes,
                        "status": body.get("status"),
                        "answer": body.get("answer", ""),
                        "citations": body.get("citations", []),
                        "kanit_degil": not evidence["quality_eligible"],
                        "response_body": body,
                        "response_receipt": evidence["receipt"],
                        "evidence": evidence,
                    }
                )
                checkpoint.write_text(
                    json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
                )
    except EvaluationStopped as exc:
        checkpoint.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{exc} Devam: --output-dir {output_dir}", file=sys.stderr)
        return 2
    payload = {
        "kind": "faithfulness_sample",
        "pulled_at": utc_now(),
        "seed": args.seed,
        "size": len(records),
        "api_url": args.api_url,
        "course_id": str(course_id),
        "llm_server_note": args.llm_note,
        "fake_provider_declared": None if client.runtime is None else False,
        "runtime_manifest": client.runtime,
        "quality_reportable": False,
        "warning": "İki bağımsız insan etiketi ve gerçek yanıt kanıtı olmadan kalite raporu değildir.",
        "corpus_digest": digest(corpus),
        "records": records,
    }
    sample_path = output_dir / "sample.json"
    with sample_path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    for labeller in ("1", "2"):
        write_label_file(output_dir / f"labels_etiketleyici_{labeller}.md", payload, labeller)
    print(f"örneklem ve bağımsız etiket formları: {output_dir}")
    return 0


def write_label_file(path: Path, payload: dict[str, Any], labeller: str) -> None:
    """Etiketleyici başına AYRI dosya: biri diğerinin kararını görmemeli."""
    lines = [
        f"# Faithfulness etiketleme — {labeller}. etiketleyici",
        "",
        (f"Örneklem: `sample.json` · n={payload['size']} · tohum {payload['seed']}"),
        "",
        "**Bu dosyayı doldururken diğer etiketleyicinin dosyasına BAKMAYIN.** Ham uyum",
        "oranı, tartışma öncesi etiketlerden hesaplanır; sonrasından hesaplanan uyum",
        "her zaman %100 çıkar ve hiçbir şey ölçmez.",
        "",
        "Etiket üç değerlidir, ara değer üretilmez: `destekleniyor` · `kısmen` ·",
        "`desteklenmiyor`. Etiket, cevabın ikna ediciliğine değil **kaynak parçanın",
        "içeriğine** bakılarak verilir.",
        "",
    ]
    if payload.get("fake_provider_declared") is not False or any(
        record.get("kanit_degil") is not False for record in payload["records"]
    ):
        lines += [
            "> **UYARI — GERÇEK YANIT KANITI DOĞRULANMADI.** Bu örneklemde gerçek",
            "> sağlayıcıyla üretildiği doğrulanmayan yanıtlar var. Sahte sağlayıcı,",
            "> önbellek, sağlayıcısız yanıt veya eksik kanıt aynı durum değildir.",
            "> Bu form süreci sınayabilir; **gerçek model faithfulness raporuna giremez**.",
            "> Kabul için doğrulanmış gerçek yanıtlarla yeni örneklem hazırlanmalıdır.",
            "",
        ]
    lines += ["---", ""]

    for index, record in enumerate(payload["records"], start=1):
        lines += [
            f"## {index}. {record['item_id']} ({record['category']})",
            "",
            f"**Soru:** {record['question']}",
            "",
            f"**Durum:** `{record['status']}`",
            "",
            "**Cevap:**",
            "",
            "> " + (record["answer"] or "(boş)").replace("\n", "\n> "),
            "",
            "**Gösterilen kaynaklar:**",
            "",
        ]
        if record["citations"]:
            for citation in record["citations"]:
                lines += [
                    f"- `{citation.get('file_name')}` — {citation.get('location')}",
                    f"  > {str(citation.get('snippet', '')).replace(chr(10), ' ')}",
                ]
        else:
            lines.append("- (atıf gösterilmedi)")
        lines += [
            "",
            "**Etiket:** `destekleniyor` / `kısmen` / `desteklenmiyor` → ______________",
            "",
            "**Not:** ______________",
            "",
        ]
    with path.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T047 faithfulness örneklemi")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--api-url", default="http://127.0.0.1:8022")
    parser.add_argument("--token")
    parser.add_argument("--size", type=int, default=25, help="20-30 arası (brief).")
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--llm-note", help="SUNUCUNUN gerçek LLM ayarı.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Yeni paket dizini veya kesilmiş koşunun devam dizini.",
    )
    parser.add_argument("--max-requests", type=int, default=30)
    parser.add_argument("--require-real", action="store_true")
    args = parser.parse_args(argv)
    if not 20 <= args.size <= 30:
        parser.error("Örneklem 20-30 cevap içermeli.")
    return asyncio.run(pull(args))


if __name__ == "__main__":
    sys.exit(main())
