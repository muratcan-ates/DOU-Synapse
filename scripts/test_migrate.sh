#!/usr/bin/env bash
# scripts/migrate.sh sözleşme testleri — GERÇEK bir PostgreSQL'e karşı koşar.
#
# Neden gerçek veritabanı: bu betiğin iddiaları (idempotans, sha uyuşmazlığı,
# advisory lock, kayıt tablosu) yalnız veritabanı davranışıyla doğrulanabilir.
# Sahte bir psql ile sınanan bir göç koşucusu, kendi kopyasını sınar.
#
# Kendi geçici veritabanını kurar ve SONUNDA siler; var olan bir veritabanına
# dokunmaz.
set -euo pipefail

KOK="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
MIGRATE="$KOK/scripts/migrate.sh"
PSQL_BIN="${PSQL:-psql}"
TEST_DB="dou_a24_l8_migrate_$$"
YONETIM_DSN="${TEST_ADMIN_DSN:-postgresql://localhost/postgres}"

# Hedef DSN yönetim DSN'inden TÜRETİLİR: sabit kodlamak yerelde çalışıp CI'da
# düşer, çünkü CI'daki servis kullanıcı adı ve parola ister. Yalnız veritabanı
# adı değiştirilir; kimlik, host ve port yönetim DSN'inden aynen taşınır.
dsn_veritabanini_degistir() {
  python3 - "$1" "$2" <<'PYEOF'
import sys
from urllib.parse import urlsplit, urlunsplit

dsn, yeni_db = sys.argv[1], sys.argv[2]
parcalar = urlsplit(dsn)
print(urlunsplit(parcalar._replace(path=f"/{yeni_db}")))
PYEOF
}
HEDEF_DSN="$(dsn_veritabanini_degistir "$YONETIM_DSN" "$TEST_DB")"

GECICI_GOC="$(mktemp -d)"
gecti=0
kaldi=0

temizle() {
  "$PSQL_BIN" -q -X -d "$YONETIM_DSN" -c "DROP DATABASE IF EXISTS $TEST_DB" >/dev/null 2>&1 || true
  rm -rf "$GECICI_GOC"
}
trap temizle EXIT

dogrula() {
  local ad="$1" beklenen="$2" gercek="$3"
  if [ "$beklenen" = "$gercek" ]; then
    echo "  GEÇTİ  $ad"
    gecti=$((gecti + 1))
  else
    echo "  KALDI  $ad — beklenen: $beklenen, gelen: $gercek" >&2
    kaldi=$((kaldi + 1))
  fi
}

sorgu() { "$PSQL_BIN" -tAX -d "$HEDEF_DSN" -c "$1" 2>/dev/null || echo "SORGU_HATASI"; }
kayit_sayisi() { sorgu "select count(*) from app.schema_migrations"; }

# Alt dize kontrolü ayrı bir fonksiyonda: `case` bloğunu $( ) içine çok satırlı
# yazmak bash'te sözdizimi hatası veriyor ve iddia sessizce "f" dönüyordu.
icerir() {
  case "$1" in
    *"$2"*) echo t ;;
    *) echo f ;;
  esac
}

echo "Geçici veritabanı: $TEST_DB"
"$PSQL_BIN" -q -X -d "$YONETIM_DSN" -c "CREATE DATABASE $TEST_DB" >/dev/null

# Sentetik göç dosyaları: gerçek supabase/migrations'a bağımlı olmak testi
# depo içeriğine bağlar ve yeni bir göç eklendiğinde sebepsiz kırar.
cat > "$GECICI_GOC/0001_ilk.sql" <<'SQL'
CREATE TABLE ornek_bir (id integer PRIMARY KEY);
SQL
cat > "$GECICI_GOC/0002_ikinci.sql" <<'SQL'
CREATE TABLE ornek_iki (id integer PRIMARY KEY);
SQL
cat > "$GECICI_GOC/0003_ucuncu.sql" <<'SQL'
CREATE TABLE ornek_uc (id integer PRIMARY KEY);
SQL

export DOU_MIGRATIONS_DIR="$GECICI_GOC"
kos() { DATABASE_URL="$HEDEF_DSN" bash "$MIGRATE" "$@"; }

echo "1) Kuru koşu hiçbir şey yazmaz"
kos --dry-run >/dev/null
dogrula "kuru koşudan sonra kayıt tablosu boş" "0" "$(kayit_sayisi)"
dogrula "kuru koşudan sonra tablo yok" "f" "$(sorgu "select to_regclass('public.ornek_bir') is not null")"

echo "2) Temiz veritabanı: hepsi uygulanır"
kos >/dev/null
dogrula "kayıt sayısı = göç dosyası sayısı" "3" "$(kayit_sayisi)"
dogrula "üçüncü tablo gerçekten var" "t" "$(sorgu "select to_regclass('public.ornek_uc') is not null")"

echo "3) No-op: ikinci koşuda hiçbir göç uygulanmaz"
ikinci_cikti="$(kos)"
dogrula "ikinci koşu rc=0" "0" "$?"
dogrula "ikinci koşu 'uygulanacak göç yok' der" "t" \
  "$(icerir "$ikinci_cikti" "Uygulanacak göç yok")"
dogrula "kayıt sayısı değişmedi" "3" "$(kayit_sayisi)"

echo "4) N-1 → N: yalnız eksik göç uygulanır"
"$PSQL_BIN" -q -X -d "$HEDEF_DSN" -c "DELETE FROM app.schema_migrations WHERE filename = '0003_ucuncu.sql'" >/dev/null
"$PSQL_BIN" -q -X -d "$HEDEF_DSN" -c "DROP TABLE ornek_uc" >/dev/null
dortuncu_cikti="$(kos)"
dogrula "yalnız bir göç uygulandı" "t" \
  "$(icerir "$dortuncu_cikti" "1 göç uygulandı")"
dogrula "kayıt sayısı yeniden 3" "3" "$(kayit_sayisi)"

echo "5) NEGATİF KANIT: uygulanmış göç değiştirilirse betik durur"
"$PSQL_BIN" -q -X -d "$HEDEF_DSN" \
  -c "UPDATE app.schema_migrations SET sha256 = 'bozuk' WHERE filename = '0002_ikinci.sql'" >/dev/null
set +e
bozuk_cikti="$(kos 2>&1)"
bozuk_rc=$?
set -e
dogrula "sha uyuşmazlığında rc != 0" "t" "$([ "$bozuk_rc" -ne 0 ] && echo t || echo f)"
dogrula "hata mesajı değişen dosyayı söyler" "t" \
  "$(icerir "$bozuk_cikti" "0002_ikinci.sql")"
"$PSQL_BIN" -q -X -d "$HEDEF_DSN" \
  -c "DELETE FROM app.schema_migrations WHERE filename = '0002_ikinci.sql'" >/dev/null
"$PSQL_BIN" -q -X -d "$HEDEF_DSN" -c "DROP TABLE ornek_iki" >/dev/null
kos >/dev/null

echo "6) NEGATİF KANIT: advisory lock tutulurken ikinci koşu düşer"
LOCK_FIFO="$(mktemp -u)"; mkfifo "$LOCK_FIFO"
"$PSQL_BIN" -tAX -d "$HEDEF_DSN" -f - < <(
  printf "select pg_advisory_lock(8241090114);\n\\! echo hazir > %s\n select pg_sleep(6);\n" "$LOCK_FIFO"
) >/dev/null 2>&1 &
kilit_pid=$!
read -r _ < "$LOCK_FIFO" || true
rm -f "$LOCK_FIFO"
set +e
kilitli_cikti="$(kos --dry-run 2>&1)"
kilitli_rc=$?
set -e
kill "$kilit_pid" 2>/dev/null || true
wait "$kilit_pid" 2>/dev/null || true
# Süreci öldürmek kilidi ANINDA bırakmaz: arka uç bağlantısı kapanana kadar
# advisory lock durur. Beklemeden sonraki teste geçmek, o testi sebepsiz kırar.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  # Tek argümanlı advisory lock anahtarı pg_locks'ta classid/objid olarak İKİYE
  # bölünür ve objid `oid` tipindedir; 8241090114 o tipe sığmaz, doğrudan
  # karşılaştırma sorguyu hata ile düşürür. Bu veritabanında başka advisory
  # lock kullanılmadığı için toplam sayıyı saymak yeterli ve doğru.
  hala="$(sorgu "select count(*) from pg_locks where locktype = 'advisory'")"
  [ "$hala" = "0" ] && break
  sleep 1
done
dogrula "kilit test sonunda bırakıldı" "0" "$hala"
dogrula "kilit tutulurken rc != 0" "t" "$([ "$kilitli_rc" -ne 0 ] && echo t || echo f)"
dogrula "mesaj eşzamanlı koşuyu söyler" "t" \
  "$(icerir "$kilitli_cikti" "başka bir göç koşusu")"

echo "7) Kendi BEGIN/COMMIT'ini taşıyan göç: uyarısız uygulanır ve bildirilir"
cat > "$GECICI_GOC/0004_kendi_islemi.sql" <<'SQL'
BEGIN;
CREATE TABLE ornek_dort (id integer PRIMARY KEY);
COMMIT;
SQL
kendi_cikti="$(kos 2>&1)"
dogrula "tablo oluştu" "t" "$(sorgu "select to_regclass('public.ornek_dort') is not null")"
dogrula "kaydı yazıldı" "4" "$(kayit_sayisi)"
dogrula "psql işlem uyarısı YOK" "f" "$(icerir "$kendi_cikti" "transaction in progress")"
dogrula "sınır açıkça bildirildi" "t" "$(icerir "$kendi_cikti" "kendi BEGIN/COMMIT")"
dogrula "dosya adı sayıldı" "t" "$(icerir "$kendi_cikti" "0004_kendi_islemi.sql")"

echo
echo "ÖZET: $gecti geçti, $kaldi kaldı"
[ "$kaldi" -eq 0 ]
