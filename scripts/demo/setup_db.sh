#!/bin/sh
# Jüri demosu veritabanı: temiz `dou_demo` (yerel PostgreSQL 16 + pgvector),
# scripts/migrate.sh ile göçler, yerel rol kurulumu, sentetik seed.
# Yeniden kurmak için: DOU_DEMO_RESET=1 sh scripts/demo/setup_db.sh
set -eu
KOK="$(cd "$(dirname "$0")/../.." && pwd)"
DB="${DOU_DEMO_DB:-dou_demo}"
if [ "${DOU_DEMO_RESET:-0}" = "1" ]; then dropdb --if-exists "$DB"; fi
psql -d postgres -Atc "select 1 from pg_database where datname='$DB'" | grep -q 1 || createdb "$DB"
DATABASE_URL="postgresql://localhost/$DB" DOU_MIGRATE_PYTHON="$KOK/apps/api/.venv/bin/python" sh "$KOK/scripts/migrate.sh"
psql -X -v ON_ERROR_STOP=1 -q -d "$DB" -f "$KOK/supabase/local_dev_setup.sql"
psql -X -v ON_ERROR_STOP=1 -q -d "$DB" -f "$KOK/supabase/seed_demo.sql"
echo "tablo: $(psql -d "$DB" -Atc "select count(*) from pg_tables where schemaname in ('public','app')") · göç: $(psql -d "$DB" -Atc "select count(*) from app.schema_migrations") · profiles: $(psql -d "$DB" -Atc "select count(*) from profiles")"
