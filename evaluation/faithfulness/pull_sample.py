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
    import httpx

    sys.path.insert(0, str(HERE.parent))
    import goldset

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    course_id = UUID(corpus["course_id"])
    gold = goldset.load(GOLD_SET)

    pool = [item for item in gold.items if item.category in SAMPLE_CATEGORIES]
    random.Random(args.seed).shuffle(pool)
    chosen = pool[: args.size]

    fake = bool(args.llm_note and "FAKE_PROVIDER=TRUE" in args.llm_note.upper())
    started = datetime.now().astimezone()
    print(f"örneklem: {len(chosen)} soru · tohum {args.seed} · sahte sağlayıcı: {fake}")
    if args.dry_run:
        print(", ".join(item.id for item in chosen))
        return 0

    token = args.token or f"dev:{corpus['instructor_id']}"
    records: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        base_url=args.api_url.rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=90.0,
    ) as client:
        for item in chosen:
            for attempt in range(6):
                response = await client.post(
                    f"/courses/{course_id}/chat",
                    json={"question": item.question, "mode": "qa"},
                )
                if response.status_code != 429:
                    break
                await asyncio.sleep(min(60.0, 5.0 * (attempt + 1)))
            response.raise_for_status()
            body = response.json()
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
                    "kanit_degil": fake,
                }
            )
            print(f"  {item.id} · {body.get('status')} · {len(body.get('citations', []))} atıf")

    payload = {
        "kind": "faithfulness_sample",
        "pulled_at": started.isoformat(),
        "seed": args.seed,
        "size": len(records),
        "api_url": args.api_url,
        "course_id": str(course_id),
        "llm_server_note": args.llm_note,
        "fake_provider_declared": fake,
        "warning": (
            "Sahte sağlayıcıyla çekilmiş cevaplar faithfulness KANITI DEĞİLDİR. Sahte "
            "sağlayıcı getirilen chunk'ları özetleyip döndürüyor; böyle bir cevabı "
            "'kaynağa sadık' diye etiketlemek totolojidir."
        )
        if fake
        else None,
        "records": records,
    }
    sample_path = HERE / f"sample_{started.strftime('%Y-%m-%d')}.json"
    sample_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for labeller in ("1", "2"):
        write_label_file(HERE / f"labels_etiketleyici_{labeller}.md", payload, labeller)

    print(f"\nörneklem: {sample_path}")
    print("etiketleme dosyaları: labels_etiketleyici_1.md, labels_etiketleyici_2.md")
    return 0


def write_label_file(path: Path, payload: dict[str, Any], labeller: str) -> None:
    """Etiketleyici başına AYRI dosya: biri diğerinin kararını görmemeli."""
    lines = [
        f"# Faithfulness etiketleme — {labeller}. etiketleyici",
        "",
        f"Örneklem: `sample_{payload['pulled_at'][:10]}.json` · n={payload['size']} · "
        f"tohum {payload['seed']}",
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
    if payload["fake_provider_declared"]:
        lines += [
            "> **UYARI — bu örneklem SAHTE SAĞLAYICIYLA çekildi.** Cevaplar modelin",
            "> ürettiği metin değil, getirilen chunk'ların özetidir. Bu dosyayı",
            "> doldurmak süreci sınar ama **faithfulness ölçmez**; sonuç rapora",
            "> giremez. Gerçek anahtar geldiğinde örneklem yeniden çekilmelidir.",
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
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T047 faithfulness örneklemi")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--api-url", default="http://127.0.0.1:8022")
    parser.add_argument("--token")
    parser.add_argument("--size", type=int, default=25, help="20-30 arası (brief).")
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--llm-note", help="SUNUCUNUN gerçek LLM ayarı.")
    parser.add_argument("--dry-run", action="store_true")
    return asyncio.run(pull(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
