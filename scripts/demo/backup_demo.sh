#!/bin/sh
# Demo yedeği (14 Eylül 2026): dou_demo pg_dump paketi + apps/api/.env kopyası +
# model önbelleği ve demo depolama yollarının notu. Hepsi DEPO DIŞINA yazılır:
# .env anahtar taşır, paket kişisel veri ve çalıştırılabilir SQL içerir —
# paylaşılmaz, git'e girmez. Klasörü sonra USB/iCloud gibi makine DIŞINA kopyala.
#
# recovery.py Python 3.12 ister; macOS'un sistem python3'ü (3.9) f-string
# sözdizimi hatası verir. Bu yüzden API venv'inin yorumlayıcısı kullanılır.
set -eu
KOK="$(cd "$(dirname "$0")/../.." && pwd)"
HEDEF="${DOU_BACKUP_DIR:-$HOME/Desktop/dou-yedek-$(date +%Y%m%d-%H%M)}"
mkdir -p "$HEDEF"

# recovery.py düz PG* değişkenlerini bilerek yok sayar (yanlışlıkla miras kalan
# bağlantı yolu olmasın diye); yalnız DOU_BACKUP_ önekli açık bağlantıyı okur ve
# sunucu adresi olarak sayısal loopback ister ("localhost" reddedilir).
export DOU_BACKUP_PGHOST="${DOU_BACKUP_PGHOST:-127.0.0.1}"
export DOU_BACKUP_PGPORT="${DOU_BACKUP_PGPORT:-5432}"
export DOU_BACKUP_PGDATABASE="${DOU_DEMO_DB:-dou_demo}"
export DOU_BACKUP_PGUSER="${DOU_BACKUP_PGUSER:-$(id -un)}"
PGDATABASE="$DOU_BACKUP_PGDATABASE"

DOU_RECOVERY_PYTHON="$KOK/apps/api/.venv/bin/python" \
  sh "$KOK/scripts/backup.sh" --bundle "$HEDEF/dou_demo.bundle" --execute

if [ -f "$KOK/apps/api/.env" ]; then
  cp "$KOK/apps/api/.env" "$HEDEF/api.env"
  chmod 600 "$HEDEF/api.env"
fi

cat > "$HEDEF/OKU.md" <<EOF
# DOU-Synapse demo yedeği — $(date '+%Y-%m-%d %H:%M')

- \`dou_demo.bundle\`: PostgreSQL 16 \`pg_dump\` (custom format) — $PGDATABASE.
  Geri yükleme: \`DOU_RECOVERY_PYTHON=apps/api/.venv/bin/python sh scripts/restore.sh --bundle <yol> --execute\`
- \`api.env\`: \`apps/api/.env\` kopyası (GROQ_API_KEY vb. taşır — PAYLAŞMA).
- Model önbelleği: \`$HOME/.cache/dou-synapse/fastembed\` (E5 embedding, ~2 GB).
  Yoksa ilk açılışta indirilir; ağsız provada bu klasörün yerinde olması ŞART.
- Demo dosya depolama: \`$HOME/.cache/dou-synapse/demo-storage\` (yüklenen materyaller).

Bu klasörü USB ya da iCloud gibi makine DIŞINA kopyala.
EOF

echo "[yedek] $HEDEF"
ls -la "$HEDEF"
