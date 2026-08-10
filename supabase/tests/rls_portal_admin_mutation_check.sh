#!/usr/bin/env bash
#
# Platform yonetim konsolu yetki sinirlarinin KIRMIZI YANABILDIGININ kaniti.
#
# Bu betik gercek/ortak `dou_synapse` veritabanina hic baglanmaz. Her kosuda PID ile
# adlandirilmis yeni bir sablon DB kurar, tum migrasyonlari uygular ve her mutasyonu
# sablonun ayri bir klonunda dener. Basarili, hatali veya sinyalle kesilmis kosularda
# olusturdugu klonlari ve sablonu temizler.
#
# Yalniz "bir hata oldu" aramaz: her gevsetmede beklenen kesin sizinti isaretini
# dogrular. Kapsam:
#   1. platform_admins tablo GRANT + RLS birlikte acilirsa kullanici kendini admin yapar,
#   2. app.is_platform_admin() fail-open olursa admin yardimcisi normal kullaniciya acar,
#   3. PUBLIC EXECUTE geri verilirse worker, admin baglami taklit edip yardimciyi cagirir.
#
# Kullanim:
#     supabase/tests/rls_portal_admin_mutation_check.sh
#     supabase/tests/rls_portal_admin_mutation_check.sh rls_portal_admin_ozel_123
#
# Ikinci bicimde ad yine `rls_portal_admin_` ile baslamali ve mevcut olmamalidir.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"
TEMPLATE_DB="${1:-rls_portal_admin_template_$$}"

NORMAL_USER="22222222-2222-2222-2222-222222222222"
ADMIN_USER="11111111-1111-1111-1111-111111111111"

if [[ ! "$TEMPLATE_DB" =~ ^rls_portal_admin_[A-Za-z0-9_]+$ ]]; then
    echo "HATA: sablon DB adi rls_portal_admin_ ile baslayan guvenli bir ad olmali." >&2
    exit 2
fi

if "$PSQL" -lqtA -d postgres 2>/dev/null | cut -d'|' -f1 | grep -qx "$TEMPLATE_DB"; then
    echo "HATA: $TEMPLATE_DB zaten var; mevcut bir DB'ye dokunulmayacak." >&2
    exit 2
fi

created_databases=()
cleanup() {
    local db
    for ((db_index=${#created_databases[@]} - 1; db_index >= 0; db_index--)); do
        db="${created_databases[$db_index]}"
        "$DROPDB" --if-exists "$db" >/dev/null 2>&1 || true
    done
}
trap cleanup EXIT INT TERM

create_database() {
    local db="$1"
    shift
    "$CREATEDB" "$@" "$db"
    created_databases+=("$db")
}

seed_fixture() {
    local db="$1"
    "$PSQL" -v ON_ERROR_STOP=1 -q -d "$db" <<SQL
INSERT INTO public.profiles (id, email, full_name) VALUES
    ('$ADMIN_USER', 'admin@dogus.edu.tr', 'Platform Yoneticisi'),
    ('$NORMAL_USER', 'normal@dogus.edu.tr', 'Normal Kullanici');
INSERT INTO public.platform_admins (user_id) VALUES ('$ADMIN_USER');
SQL
}

expect_denied() {
    local name="$1"
    local expected="$2"
    local sql="$3"
    local output

    if output=$("$PSQL" -v ON_ERROR_STOP=1 -qAt -d "$TEMPLATE_DB" -c "$sql" 2>&1); then
        echo "HATA: referans kosuda $name reddedilmedi." >&2
        echo "$output" >&2
        exit 1
    fi
    if ! grep -Fq "$expected" <<<"$output"; then
        echo "HATA: $name yanlis nedenle reddedildi; '$expected' bekleniyordu." >&2
        echo "$output" >&2
        exit 1
    fi
    printf 'REFERANS   %-42s -> dogru nedenle kapali\n' "$name"
}

run_mutation() {
    local sequence="$1"
    local name="$2"
    local mutation_sql="$3"
    local probe_sql="$4"
    local expected_marker="$5"
    local scratch="rls_portal_admin_mut_$$_${sequence}"
    local output

    create_database "$scratch" -T "$TEMPLATE_DB"
    "$PSQL" -v ON_ERROR_STOP=1 -q -d "$scratch" -c "$mutation_sql"
    output=$("$PSQL" -v ON_ERROR_STOP=1 -qAt -d "$scratch" -c "$probe_sql" 2>&1 || true)

    if ! grep -Fxq "$expected_marker" <<<"$output"; then
        printf 'KACIRILDI  %-42s -> %s gelmedi\n' "$name" "$expected_marker" >&2
        echo "$output" >&2
        return 1
    fi
    printf 'YAKALANDI  %-42s -> %s\n' "$name" "$expected_marker"

    # Dizide birakmak kasitlidir: EXIT trap'i --if-exists ile ikinci temizligi
    # zararsizca dener ve aradaki herhangi bir kesintide klonun kalmamasini saglar.
    "$DROPDB" "$scratch"
}

echo "gecici sablon kuruluyor: $TEMPLATE_DB"
create_database "$TEMPLATE_DB"
for migration in "$REPO_ROOT"/supabase/migrations/*.sql; do
    "$PSQL" -v ON_ERROR_STOP=1 -q -d "$TEMPLATE_DB" -f "$migration"
done
seed_fixture "$TEMPLATE_DB"

# Bozulmamis referans: her kapinin hem reddetmesi hem de beklenen nedenle reddetmesi
# gerekir. Boylece mutasyon sonucundaki sizinti, onceden kirik bir sablondan kaynaklanmaz.
expect_denied \
    "dogrudan kendini admin yapma" \
    "permission denied for table platform_admins" \
    "SET ROLE dou_app; SET app.current_user_id = '$NORMAL_USER'; INSERT INTO public.platform_admins (user_id) VALUES ('$NORMAL_USER');"

expect_denied \
    "normal kullanicinin admin yardimcisi" \
    "platform yöneticisi değil" \
    "SET ROLE dou_app; SET app.current_user_id = '$NORMAL_USER'; SELECT app.admin_overview();"

expect_denied \
    "worker icin PUBLIC EXECUTE" \
    "permission denied for function admin_overview" \
    "SET ROLE dou_worker; SET app.current_user_id = '$ADMIN_USER'; SELECT app.admin_overview();"

echo "referans kosu temiz (uc kapinin tamami kapali)"
echo

failures=0

run_mutation 1 \
    "tablo GRANT ve RLS birlikte acilirsa" \
    "GRANT INSERT ON public.platform_admins TO dou_app; CREATE POLICY platform_admins_self_insert_leak ON public.platform_admins FOR INSERT TO dou_app WITH CHECK (user_id = app.current_user_id());" \
    "SET ROLE dou_app; SET app.current_user_id = '$NORMAL_USER'; INSERT INTO public.platform_admins (user_id) VALUES ('$NORMAL_USER'); RESET ROLE; SELECT CASE WHEN EXISTS (SELECT 1 FROM public.platform_admins WHERE user_id = '$NORMAL_USER') THEN 'LEAK__PLATFORM_ADMIN_SELF_PROMOTION' ELSE 'SAFE' END;" \
    "LEAK__PLATFORM_ADMIN_SELF_PROMOTION" || failures=$((failures + 1))

run_mutation 2 \
    "yetki yardimcisi fail-open olursa" \
    "CREATE OR REPLACE FUNCTION app.is_platform_admin() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, app AS \$\$ SELECT true \$\$;" \
    "SET ROLE dou_app; SET app.current_user_id = '$NORMAL_USER'; SELECT CASE WHEN (app.admin_overview()->>'users_total')::integer = 2 THEN 'LEAK__ADMIN_HELPER_AUTHORIZATION' ELSE 'SAFE' END;" \
    "LEAK__ADMIN_HELPER_AUTHORIZATION" || failures=$((failures + 1))

run_mutation 3 \
    "PUBLIC EXECUTE geri verilirse" \
    "GRANT EXECUTE ON FUNCTION app.admin_overview() TO PUBLIC;" \
    "SET ROLE dou_worker; SET app.current_user_id = '$ADMIN_USER'; SELECT CASE WHEN (app.admin_overview()->>'users_total')::integer = 2 THEN 'LEAK__PUBLIC_EXECUTE_ADMIN_HELPER' ELSE 'SAFE' END;" \
    "LEAK__PUBLIC_EXECUTE_ADMIN_HELPER" || failures=$((failures + 1))

echo
if ((failures > 0)); then
    echo "$failures mutasyon beklenen kesin sizintiyi uretmedi."
    exit 1
fi

echo "3 mutasyon denendi, 3 kesin sizinti yakalandi."
echo "Gecici mutasyon DB'leri temizlendi; sablon cikista temizlenecek."
