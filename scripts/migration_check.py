#!/usr/bin/env python3
"""Göç dosyalarının numaralandırma sözleşmesini zorlar.

Neden bir kapı gerekiyor: göçler her yerde **dosya adı sırasıyla** uygulanıyor
(`.github/workflows/ci.yml`, `README.md` kurulum adımı, docker-compose ve yerel
kurulum hepsi `for f in supabase/migrations/*.sql` yazıyor). Sıra dosya adından
geldiği için numara, şemanın uygulanma sırasının **tek** kaydıdır.

Bu depoda aynı numaranın iki dalda birden kullanıldığı ölçüldü:
`0016_api_contract_admin_access.sql` (API sözleşme kapısı) ve
`0016_assessment_integrity.sql` (009 dalı). İkisi de birleşirse dosya adları
farklı olduğu için git çakışma üretmez, ikisi de uygulanır ve aralarındaki sıra
alfabetik bir tesadüfe düşer. Uygulanmış bir veritabanında hangi 0016'nın
koştuğunu söyleyecek hiçbir kayıt da yoktur. Bu kapı, o sessiz durumu
birleşmeden önce gürültülü hâle getirir.

Kontroller:

1. **Biçim** — her dosya `NNNN_ad.sql`; dört hane, küçük harf ve alt çizgi.
2. **Benzersiz numara** — aynı numara iki dosyada olamaz.
3. **Boşluksuz sıra** — 0001'den başlar ve atlamaz. Bir numara rezerve edilip
   başka dalda bekliyorsa burada boşluk görünür; bu bilinçliyse
   `--allow-gap NNNN` ile açıkça söylenir, sessizce geçilmez.

Kullanım:

    python3 scripts/migration_check.py
    python3 scripts/migration_check.py --allow-gap 0017   # 0017 başka dalda

Çıkış kodu 0 temiz, 1 ihlal. Ağ, veritabanı ve bağımlılık gerektirmez.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MIGRATION_DIR = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
NAME_PATTERN = re.compile(r"^(\d{4})_([a-z0-9]+(?:_[a-z0-9]+)*)\.sql$")


def collect(directory: Path) -> tuple[list[tuple[int, str]], list[str]]:
    """Göç dosyalarını (numara, ad) olarak döndür; biçimsiz olanları ayrı ver."""
    numbered: list[tuple[int, str]] = []
    malformed: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        match = NAME_PATTERN.match(path.name)
        if match is None:
            malformed.append(path.name)
            continue
        numbered.append((int(match.group(1)), path.name))
    return numbered, malformed


def check(directory: Path, allowed_gaps: set[int]) -> list[str]:
    """Sözleşme ihlallerini insan diliyle döndür; boş liste temiz demektir."""
    if not directory.is_dir():
        return [f"göç dizini yok: {directory}"]

    numbered, malformed = collect(directory)
    problems = [f"biçim: {name} — beklenen ad `NNNN_kucuk_harf.sql`" for name in sorted(malformed)]

    if not numbered:
        problems.append(f"göç dosyası bulunamadı: {directory}")
        return problems

    by_number: dict[int, list[str]] = {}
    for number, name in numbered:
        by_number.setdefault(number, []).append(name)

    for number in sorted(by_number):
        names = sorted(by_number[number])
        if len(names) > 1:
            joined = ", ".join(names)
            problems.append(
                f"çakışma: {number:04d} numarasını {len(names)} dosya kullanıyor ({joined}). "
                "Göçler dosya adı sırasıyla uygulanır; aynı numara sırayı tesadüfe bırakır."
            )

    ordered = sorted(by_number)
    if ordered[0] != 1:
        problems.append(f"sıra: ilk göç {ordered[0]:04d}, 0001 olmalı")

    # Aralığı tek geçişte tara: `zip`/`pairwise` yerine düz aralık, çünkü bu
    # betik CI'da bare `python3` ile de koşuyor ve o yorumlayıcı 3.9 olabilir
    # (`itertools.pairwise` 3.10+). Kapı, koştuğu sürüme bağlı olmamalı.
    for missing in range(ordered[0], ordered[-1] + 1):
        if missing in by_number or missing in allowed_gaps:
            continue
        problems.append(
            f"boşluk: {missing:04d} yok ({ordered[0]:04d}–{ordered[-1]:04d} aralığında). "
            f"Numara başka dalda rezerveyse `--allow-gap {missing:04d}` ile açıkça bildir."
        )

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-gap",
        action="append",
        default=[],
        metavar="NNNN",
        help="Başka dalda rezerve edildiği için burada bulunmayan numara.",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=MIGRATION_DIR,
        help="Göç dizini (varsayılan: supabase/migrations).",
    )
    arguments = parser.parse_args(argv)

    try:
        allowed_gaps = {int(value) for value in arguments.allow_gap}
    except ValueError:
        print("--allow-gap yalnız sayı alır, örn. --allow-gap 0017", file=sys.stderr)
        return 1

    problems = check(arguments.directory, allowed_gaps)
    if problems:
        print("MIGRATION_CHECK=FAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    count = len(collect(arguments.directory)[0])
    gaps = f", bildirilen boşluk: {sorted(allowed_gaps)}" if allowed_gaps else ""
    print(f"MIGRATION_CHECK=PASS ({count} göç{gaps})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
