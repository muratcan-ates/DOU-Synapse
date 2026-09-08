#!/usr/bin/env python3
"""Dalın tamamını hedef dala karşı kapsayan toplayıcı yönetişim kaydını yeniler.

Neden gerekiyor: `ai_sdlc_check.py` bir dossier'i yalnız **HEAD'de tanıtıldığı**
commit'te uygun sayar. Çok commit'li bir dalda her commit kendi dossier'ini
getirir, ama PR `main`'e açıldığında doğrulayıcı `merge-base(main, HEAD)`
tabanına bakar ve o tabana göre önceki commit'lerin hassas dosyaları KAPSAMSIZ
kalır. Bu, dalda her şey yeşilken PR'da kapının kırmızı yanması demektir ve
elle düzeltmesi her yeni commit'te tekrarlanır.

Bu betik o tekrarı ortadan kaldırır: doğrulayıcıyı çalıştırır, kapsamsız kalan
dosyaları toplar ve hepsini kapsayan tek bir toplayıcı kayıt üretir. Kayıt
append-only kuralına uyar — var olan hiçbir dossier düzenlenmez, her koşuda
YENİ bir numara alınır.

Kullanım:

    python3 scripts/refresh_aggregate_dossier.py --title "..." --summary "..."
    python3 scripts/refresh_aggregate_dossier.py --dry-run     # yalnız raporla

Ardından üretilen dosyaları commit'e dahil et ve doğrulayıcıyı yeniden koştur.
Betik commit ATMAZ: kanıt cümlesini yazan da, sonucu görecek olan da insandır.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHANGES = REPO / ".ai" / "changes"
EVIDENCE = REPO / ".ai" / "evidence"
TZ3 = datetime.timezone(datetime.timedelta(hours=3))


GIT = shutil.which("git") or "/usr/bin/git"


def git(*args: str) -> str:
    """Depo içi git çağrısı.

    Argümanlar bu betiğin kendi sabitleri ve dal adlarıdır; kullanıcıdan gelen
    serbest metin kabuk üzerinden geçmez (`shell=False`) ve çalıştırılabilir yol
    `shutil.which` ile çözülür.
    """
    return subprocess.run(  # noqa: S603 - shell=False, argümanlar depo içi
        [GIT, "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def uncovered(base: str, head: str) -> list[str]:
    """Doğrulayıcının kapsamsız bulduğu hassas dosyalar."""
    result = subprocess.run(  # noqa: S603 - shell=False, yorumlayıcı sys.executable
        [sys.executable, "scripts/ai_sdlc_check.py", "--base-sha", base, "--head-sha", head],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return sorted(
        {
            line.split(":", 1)[1]
            for line in result.stdout.splitlines()
            if line.startswith("UNCOVERED:")
        }
    )


def next_number() -> int:
    """Kullanılmamış en küçük dossier numarası; var olan kayıt asla yeniden kullanılmaz."""
    used = {
        int(match.group(1))
        for path in CHANGES.glob("*.json")
        if (match := re.match(r"^(\d{3})-", path.name))
    }
    return max(used) + 1 if used else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="origin/main", help="PR'ın hedef dalı.")
    parser.add_argument("--title", default="Dalın hedef dala karşı toplayıcı yönetişim kaydı")
    parser.add_argument(
        "--summary",
        default=(
            "Dalın bütün commit'lerindeki hassas dosyalar hedef dal tabanına karşı tek "
            "kayıtta kapsanır. Önceki dossier'lar değiştirilmez; bu kayıt onların üstüne "
            "toplayıcı olarak eklenir."
        ),
    )
    parser.add_argument("--owner", default="Muratcan Ateş")
    parser.add_argument("--dry-run", action="store_true", help="Yalnız raporla, dosya yazma.")
    arguments = parser.parse_args(argv)

    base = git("merge-base", arguments.target, "HEAD")
    head = git("rev-parse", "HEAD")
    missing = uncovered(base, head)

    if not missing:
        print(f"AGGREGATE=OK ({arguments.target} tabanına karşı kapsamsız dosya yok)")
        return 0

    present = [p for p in missing if (REPO / p).exists()]
    deleted = [p for p in missing if not (REPO / p).exists()]
    print(f"kapsamsız: {len(missing)} dosya ({len(present)} mevcut, {len(deleted)} silinmiş)")
    if arguments.dry_run:
        for path in missing:
            print(f"  - {path}")
        return 1

    number = next_number()
    change_id = f"{number:03d}-branch-aggregate-r1"
    now = datetime.datetime.now(datetime.UTC)
    evidence_path = EVIDENCE / f"{change_id}.json"

    evidence = {
        "schema_version": 1,
        "evidence_label": "fake-provider",
        "result": "not-run",
        "change_id": change_id,
        "captured_at": now.isoformat(timespec="seconds"),
        "candidate_sha": "SELF",
        "command": (
            f"python3 scripts/refresh_aggregate_dossier.py --target {arguments.target}; "
            "ardından dalın kendi kapıları koşulur"
        ),
        "environment": "toplayıcı kayıt: kapsam birleştirir, yeni ölçüm üretmez",
        "results": {"aggregated_files": len(missing)},
        "governance_note": (
            "Bu kayıt YENİ bir ölçüm iddia etmez; dalın commit'lerine dağılmış hassas "
            "dosyaları hedef dal tabanına karşı tek kapsam altında toplar. Her dilimin "
            "kendi kanıtı kendi dossier'inde durur ve değiştirilmez. Doğrulayıcı bir "
            "dossier'i yalnız HEAD'de tanıtıldığı commit'te uygun saydığı için, dalın "
            "üstüne yeni commit geldikçe bu kayıt yenilenmelidir; PR'dan önceki son "
            "commit'te bir kez koşturmak yeterlidir."
        ),
        "limitations": (
            "Kapsam birleştirmesidir, kalite kanıtı değildir. Gerçek sağlayıcı, staging ve "
            "insan kabulü bu kayıtla ilerlemez."
        ),
        "privacy": "içerik yok; yalnız dosya yolları",
    }
    evidence_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    template = json.loads((CHANGES / "example.json").read_text(encoding="utf-8"))
    template.update(
        {
            "change_id": change_id,
            # Soy kütüğü kayda özgüdür: aynı lineage + revision ikinci kez
            # yazılırsa doğrulayıcı LINEAGE_DUPLICATE_REVISION verir ve depo
            # geleneği zaten `supersedes` zinciri değil bağımsız kayıt kullanıyor.
            "lineage_id": f"branch-aggregate-{number:03d}",
            "revision": 1,
            "supersedes": None,
            "previous_status": None,
            "governance_record_risk": "R3",
            "title": arguments.title,
            "summary": arguments.summary,
            "owner": arguments.owner,
            "created_at": now.astimezone(TZ3).isoformat(timespec="seconds"),
            "review_by": (now + datetime.timedelta(days=30))
            .astimezone(TZ3)
            .isoformat(timespec="seconds"),
            "base_sha": base,
            "candidate_sha": "SELF",
            "risk_tier": "R3",
            "status": "draft",
        }
    )
    for key in template.get("behavior", {}):
        template["behavior"][key] = f"unchanged-from-base-{base[:8]} (toplayıcı kapsam kaydı)"
    template["artifacts"] = [
        {"path": path, "state": "present", "sha256": sha256(REPO / path)} for path in present
    ] + [{"path": path, "state": "absent", "sha256": None} for path in deleted]
    template["evidence"] = [
        {
            "label": "fake-provider",
            "result": "not-run",
            "report_path": str(evidence_path.relative_to(REPO)),
            "report_sha256": sha256(evidence_path),
            "candidate_sha": "SELF",
        }
    ]
    (CHANGES / f"{change_id}.json").write_text(
        json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"AGGREGATE=WROTE {change_id} ({len(missing)} dosya kapsandı)")
    print("Şimdi: değerlendirme referanslarını gözden geçir, commit'e ekle, doğrulayıcıyı koştur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
