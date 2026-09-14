#!/usr/bin/env bash
# Göçleri dosya adı sırasına göre, bir kez ve yalnız bir kez uygular.
#
# Neden ayrı bir betik: `for f in supabase/migrations/*.sql; do psql -f "$f"; done`
# yerel bir kabukta işe yarar, canlıda yaramaz. Üç şeyi bilmez — hangi göçün zaten
# uygulandığını, geçmiş bir göç dosyasının sonradan değiştirilip değiştirilmediğini
# ve aynı anda ikinci bir koşucunun çalışıp çalışmadığını. Üçü de sessizce bozar.
#
# Bu betiğin bilmediği tek şey: `app.schema_migrations` şemasını oluşturacak yetki.
# O yetki hedefte runner'a açılmadıysa betik ANLAŞILIR bir hatayla durur; sessizce
# geçmez, çünkü kayıt tutamayan bir göç koşucusu bir sonraki koşuda her şeyi
# yeniden uygulamaya kalkar.
set -euo pipefail

KOK="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
GOC_DIZINI="${DOU_MIGRATIONS_DIR:-$KOK/supabase/migrations}"
KURU=0
DSN="${DATABASE_URL:-}"

# Advisory lock anahtarı sabittir: aynı veritabanında iki migrate koşusu
# birbirini beklesin diye. Rastgele bir sayı değil, bu betiğe ayrılmış bir kimlik.
# Düz rakam: bash alt tire ayırıcısını SAYI olarak yorumlamaz, dizge olarak taşır.
# PostgreSQL 16 alt tireli sayı literalini kabul ettiği için sorun görünmüyordu,
# ama değer iki yerde farklı yazılırsa kilit sessizce farklı bir anahtara düşer.
KILIT_ANAHTARI=8241090114

kullanim() {
  cat >&2 <<'YARDIM'
Kullanım: scripts/migrate.sh [--database-url DSN] [--dry-run]

  --database-url DSN  Hedef veritabanı (yoksa DATABASE_URL ortam değişkeni)
  --dry-run           Uygulanacak göçleri listeler, hiçbir şey yazmaz
YARDIM
}

while [ $# -gt 0 ]; do
  case "$1" in
    --database-url) DSN="${2:-}"; shift 2 ;;
    --dry-run) KURU=1; shift ;;
    -h|--help) kullanim; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $1" >&2; kullanim; exit 2 ;;
  esac
done

if [ -z "$DSN" ]; then
  echo "HATA: veritabanı adresi yok. --database-url verin ya da DATABASE_URL ayarlayın." >&2
  exit 2
fi

# SQLAlchemy biçimindeki sürücü ekini psql anlamaz.
DSN="${DSN/postgresql+psycopg:\/\//postgresql://}"
DSN="${DSN/postgresql+asyncpg:\/\//postgresql://}"

PSQL_BIN="${PSQL:-psql}"
psql_calistir() { "$PSQL_BIN" -v ON_ERROR_STOP=1 -q -X -d "$DSN" "$@"; }
psql_deger() { psql_calistir -tAc "$1"; }

if ! psql_deger "select 1" >/dev/null 2>&1; then
  echo "HATA: veritabanına bağlanılamadı." >&2
  exit 1
fi

# --- Kayıt tablosu -----------------------------------------------------------
# Ayrı şema: `public` altındaki bir tabloyu uygulama göçleri yanlışlıkla
# düşürebilir. `app` şeması işletim kaydına ait.
if ! psql_calistir <<'SQL' 2>/tmp/dou-migrate-grant.err
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE IF NOT EXISTS app.schema_migrations (
    filename    text PRIMARY KEY,
    sha256      text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
);
SQL
then
  echo "HATA: app.schema_migrations oluşturulamadı — koşucu rolünde CREATE yetkisi yok." >&2
  echo "Hedefte bu yetki açılmadan göç uygulanamaz; kayıt tutamayan koşucu bir" >&2
  echo "sonraki koşuda her göçü yeniden uygulamaya kalkar. Ayrıntı:" >&2
  sed 's/^/  /' /tmp/dou-migrate-grant.err >&2 || true
  exit 1
fi

sha256_hesapla() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

sql_tirnak() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"; }

# --- Tek koşucu garantisi ----------------------------------------------------
# Kilit oturum boyunca tutulur; bu yüzden liste çıkarma, uygulama ve kayıt yazma
# TEK bir psql oturumunda değil ama TEK bir kilit sahibi altında ilerler.
# Kilit alınamazsa beklemek yerine düşüyoruz: dağıtım sırasında asılı kalan bir
# adım, hata veren bir adımdan daha kötüdür.
KILIT_SONUC="$(psql_deger "select pg_try_advisory_lock(${KILIT_ANAHTARI})")"
if [ "$KILIT_SONUC" != "t" ]; then
  echo "HATA: başka bir göç koşusu sürüyor (advisory lock ${KILIT_ANAHTARI} alınamadı)." >&2
  exit 1
fi
# Kilidi bırakmayı çıkışa bağla: hata hâlinde de bırakılsın.
kilidi_birak() { psql_deger "select pg_advisory_unlock(${KILIT_ANAHTARI})" >/dev/null 2>&1 || true; }
trap kilidi_birak EXIT

# --- Uygulanacakları belirle -------------------------------------------------
uygulanacak=()
degisen=()
atlanan=0

for yol in "$GOC_DIZINI"/*.sql; do
  [ -e "$yol" ] || continue
  ad="$(basename "$yol")"
  ozet="$(sha256_hesapla "$yol")"
  kayitli="$(psql_deger "select sha256 from app.schema_migrations where filename = $(sql_tirnak "$ad")")"
  if [ -z "$kayitli" ]; then
    uygulanacak+=("$yol")
  elif [ "$kayitli" != "$ozet" ]; then
    degisen+=("$ad")
  else
    atlanan=$((atlanan + 1))
  fi
done

# Geçmiş göç değişmez ilkesi: uygulanmış bir dosyanın içeriği sonradan
# değiştiyse hedefteki şema ile depodaki kaynak artık aynı şeyi anlatmıyor.
# Bu sessizce geçilecek bir fark değildir.
if [ ${#degisen[@]} -gt 0 ]; then
  echo "HATA: uygulanmış göç dosyaları değiştirilmiş:" >&2
  for ad in "${degisen[@]}"; do echo "  - $ad" >&2; done
  echo "Geçmiş göç yerinde değiştirilmez; düzeltme yeni bir göç dosyasıdır." >&2
  exit 1
fi

if [ ${#uygulanacak[@]} -eq 0 ]; then
  echo "Uygulanacak göç yok (${atlanan} göç zaten uygulanmış)."
  exit 0
fi

if [ "$KURU" -eq 1 ]; then
  echo "Kuru koşu — uygulanacak ${#uygulanacak[@]} göç (${atlanan} zaten uygulanmış):"
  for yol in "${uygulanacak[@]}"; do echo "  + $(basename "$yol")"; done
  echo "Hiçbir şey yazılmadı."
  exit 0
fi

# --- Uygula ------------------------------------------------------------------
# Bazı göç dosyaları kendi `BEGIN; ... COMMIT;` bloğunu taşıyor. Böyle bir dosyayı
# `psql -1` ile koşmak işe yaramaz: dosyanın içindeki COMMIT dıştaki transaction'ı
# kapatır, sonraki ifadeler transaction dışında kalır ve psql "there is already a
# transaction in progress" / "there is no transaction in progress" uyarıları verir.
# Yani `-1`'in verdiği atomiklik o dosyalar için GERÇEKLEŞMEZ — sessizce yanlış bir
# garanti sunmak yerine durumu ayırıyoruz.
kendi_islemini_yonetir() {
  grep -qiE '^[[:space:]]*(BEGIN|COMMIT|END)[[:space:]]*;' "$1"
}

kendi_yoneten=()

for yol in "${uygulanacak[@]}"; do
  ad="$(basename "$yol")"
  ozet="$(sha256_hesapla "$yol")"
  kayit_sql="INSERT INTO app.schema_migrations (filename, sha256) VALUES ($(sql_tirnak "$ad"), $(sql_tirnak "$ozet"))"
  if kendi_islemini_yonetir "$yol"; then
    echo "→ $ad (dosya kendi işlemini yönetiyor)"
    kendi_yoneten+=("$ad")
    # Dosya kendi COMMIT'ini attıktan SONRA kayıt yazılır. Aradaki çökmede göç
    # uygulanmış ama kaydı düşmüş olur; bir sonraki koşu dosyayı yeniden dener
    # ve çoğu DDL bunu kaldırmaz. Bu sınır aşağıda açıkça bildiriliyor.
    psql_calistir -f "$yol"
    psql_calistir -c "$kayit_sql"
  else
    echo "→ $ad"
    # Göç ve kayıt AYNI işlemde: göç geçip kayıt düşerse dosya bir daha uygulanır.
    psql_calistir -1 -f "$yol" -c "$kayit_sql"
  fi
done

echo "Bitti: ${#uygulanacak[@]} göç uygulandı, ${atlanan} göç zaten uygulanmıştı."

if [ ${#kendi_yoneten[@]} -gt 0 ]; then
  echo
  echo "UYARI: ${#kendi_yoneten[@]} göç dosyası kendi BEGIN/COMMIT bloğunu taşıyor."
  echo "Bu dosyalarda göç ile kayıt yazımı TEK işlemde değildir; ikisinin arasında"
  echo "süreç ölürse göç uygulanmış ama kaydı düşmüş olur ve sonraki koşu dosyayı"
  echo "yeniden dener. Yeni göç dosyaları kendi işlemini YÖNETMEMELİDİR."
  for ad in "${kendi_yoneten[@]}"; do echo "  - $ad"; done
fi
