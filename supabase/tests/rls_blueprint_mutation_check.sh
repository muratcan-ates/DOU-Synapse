#!/usr/bin/env bash
#
# rls_blueprint.sql'in KIRMIZI YANABİLDİĞİNİN kanıtı — mutasyon testi.
#
# `rls_assessment_mutation_check.sh` ile aynı yöntem ve aynı gerekçe: "politika var"
# demek kanıt değildir, "politika bozulduğunda testim bunu yakalar" demek kanıttır.
# 0008'de bu daha da kritik, çünkü politikaların hiçbiri bozulmasa bile pytest paketi
# yeşil kalır — uygulama katmanı zaten doğru filtreliyor.
#
# İki mutasyon sınıfı var ve ikincisi 0008'e özgü:
#   (a) POLİTİKA mutasyonları — RLS koşulunu gevşetir.
#   (b) YETKİ mutasyonları — 0008'in REVOKE satırlarını geri alır. Bunlar
#       `data-model.md` §2.13'ün "sessiz kalabilecek hata" dediği sınıftır: yetki
#       geri verilse hiçbir davranış testi kırmızı yanmaz.
#
# Kullanım:
#     supabase/tests/rls_blueprint_mutation_check.sh [migrasyonlari_uygulanmis_db]

set -euo pipefail

TEMPLATE_DB="${1:-rls_blueprint_template}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_SQL="${REPO_ROOT}/supabase/tests/rls_blueprint.sql"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"

created_databases=()
cleanup() {
    local db_index
    local cleanup_db
    for ((db_index=${#created_databases[@]} - 1; db_index >= 0; db_index--)); do
        cleanup_db="${created_databases[$db_index]}"
        "$DROPDB" --if-exists "$cleanup_db" >/dev/null 2>&1 || true
    done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if ! "$PSQL" -lqtA -d postgres 2>/dev/null | cut -d'|' -f1 | grep -qx "$TEMPLATE_DB"; then
    echo "şablon veritabanı kuruluyor: $TEMPLATE_DB"
    "$CREATEDB" "$TEMPLATE_DB"
    created_databases+=("$TEMPLATE_DB")
    for migration in "${REPO_ROOT}"/supabase/migrations/*.sql; do
        "$PSQL" -v ON_ERROR_STOP=1 -q -d "$TEMPLATE_DB" -f "$migration"
    done
fi

# Her girdi: mutasyon adı | bozma SQL'i | FAIL'e dönmesi BEKLENEN iddianın adı.
# Ayraç tek baytlık olmak zorunda (IFS bayt bayt uygular); SQL'lerde `|` geçmiyor.
MUTATIONS=(
"learning_outcomes_member_read acilirsa|DROP POLICY learning_outcomes_member_read ON learning_outcomes; CREATE POLICY learning_outcomes_member_read ON learning_outcomes FOR SELECT USING (true);|learning_outcomes_read__baska_dersin_ciktisi_gorunmez"
"learning_outcomes_instructor_write acilirsa|DROP POLICY learning_outcomes_instructor_write ON learning_outcomes; CREATE POLICY learning_outcomes_instructor_write ON learning_outcomes FOR INSERT WITH CHECK (true);|learning_outcomes_write__ogrenci_cikti_ekleyemez"
"learning_outcomes_instructor_update acilirsa|DROP POLICY learning_outcomes_instructor_update ON learning_outcomes; CREATE POLICY learning_outcomes_instructor_update ON learning_outcomes FOR UPDATE USING (true) WITH CHECK (true);|learning_outcomes_update__ogrenci_cikti_guncelleyemez"
"learning_outcomes_instructor_delete acilirsa|DROP POLICY learning_outcomes_instructor_delete ON learning_outcomes; CREATE POLICY learning_outcomes_instructor_delete ON learning_outcomes FOR DELETE USING (true);|learning_outcomes_delete__ogrenci_cikti_silemez"
"exam_blueprints_read tamamen acilirsa|DROP POLICY exam_blueprints_read ON exam_blueprints; CREATE POLICY exam_blueprints_read ON exam_blueprints FOR SELECT USING (true);|exam_blueprints_read__baska_dersin_ogrencisi_goremez"
"exam_blueprints_read: yayin sarti duserse|DROP POLICY exam_blueprints_read ON exam_blueprints; CREATE POLICY exam_blueprints_read ON exam_blueprints FOR SELECT USING (app.is_instructor(course_id) OR app.is_member(course_id));|exam_blueprints_read__uye_taslak_sinavi_goremez"
"exam_blueprints_instructor_insert acilirsa|DROP POLICY exam_blueprints_instructor_insert ON exam_blueprints; CREATE POLICY exam_blueprints_instructor_insert ON exam_blueprints FOR INSERT WITH CHECK (true);|exam_blueprints_insert__ogrenci_sinav_kuramaz"
"exam_blueprints_instructor_update acilirsa|DROP POLICY exam_blueprints_instructor_update ON exam_blueprints; CREATE POLICY exam_blueprints_instructor_update ON exam_blueprints FOR UPDATE USING (true) WITH CHECK (true);|exam_blueprints_update__ogrenci_sureyi_uzatamaz"
"exam_blueprints_instructor_delete acilirsa|DROP POLICY exam_blueprints_instructor_delete ON exam_blueprints; CREATE POLICY exam_blueprints_instructor_delete ON exam_blueprints FOR DELETE USING (true);|exam_blueprints_delete__ogrenci_sinav_silemez"
"blueprint_cells_instructor_read acilirsa|DROP POLICY blueprint_cells_instructor_read ON blueprint_cells; CREATE POLICY blueprint_cells_instructor_read ON blueprint_cells FOR SELECT USING (app.is_member(course_id));|blueprint_cells_read__ogrenci_dagilimi_GOREMEZ"
"blueprint_cells_instructor_insert acilirsa|DROP POLICY blueprint_cells_instructor_insert ON blueprint_cells; CREATE POLICY blueprint_cells_instructor_insert ON blueprint_cells FOR INSERT WITH CHECK (true);|blueprint_cells_insert__ogrenci_hucre_ekleyemez"
"YETKI: blueprint_cells UPDATE geri verilirse|GRANT UPDATE ON blueprint_cells TO dou_app; CREATE POLICY bc_upd_leak ON blueprint_cells FOR UPDATE USING (true) WITH CHECK (true);|blueprint_cells_update__YETKI_CEKILI_egitmen_bile_guncelleyemez"
"exam_versions_read tamamen acilirsa|DROP POLICY exam_versions_read ON exam_versions; CREATE POLICY exam_versions_read ON exam_versions FOR SELECT USING (true);|exam_versions_read__uye_taslak_surumu_goremez"
"exam_versions_read: KENDI OTURUMU dali duserse|DROP POLICY exam_versions_read ON exam_versions; CREATE POLICY exam_versions_read ON exam_versions FOR SELECT USING (app.is_instructor(course_id) OR (app.is_member(course_id) AND app.is_exam_open(id, course_id)));|exam_versions_read__YURUYEN_OTURUM_pencere_kapansa_da_surumunu_gorur"
"exam_versions_read: pencere sarti duserse|DROP POLICY exam_versions_read ON exam_versions; CREATE POLICY exam_versions_read ON exam_versions FOR SELECT USING (app.is_instructor(course_id) OR app.is_member(course_id));|exam_versions_read__oturumsuz_uye_kapanmis_surumu_goremez"
"exam_versions_instructor_insert acilirsa|DROP POLICY exam_versions_instructor_insert ON exam_versions; CREATE POLICY exam_versions_instructor_insert ON exam_versions FOR INSERT WITH CHECK (true);|exam_versions_insert__ogrenci_surum_acamaz"
"YETKI: exam_versions version_no yazilabilir olursa|GRANT UPDATE (version_no) ON exam_versions TO dou_app;|exam_versions_update__KOLON_GRANT_version_no_yazilamaz"
"exam_versions_delete: draft sarti duserse|DROP POLICY exam_versions_instructor_delete ON exam_versions; CREATE POLICY exam_versions_instructor_delete ON exam_versions FOR DELETE USING (app.is_instructor(course_id));|exam_versions_delete__yayinlanmis_surum_silinemez"
"exam_items_read acilirsa|DROP POLICY exam_items_read ON exam_items; CREATE POLICY exam_items_read ON exam_items FOR SELECT USING (app.is_member(course_id));|exam_items_read__oturumsuz_uye_kagidi_GOREMEZ"
"YETKI: exam_items UPDATE geri verilirse|GRANT UPDATE ON exam_items TO dou_app; CREATE POLICY ei_upd_leak ON exam_items FOR UPDATE USING (true) WITH CHECK (true);|exam_items_update__YETKI_CEKILI_puan_degistirilemez"
"exam_items_insert: draft sarti duserse|DROP POLICY exam_items_instructor_insert ON exam_items; CREATE POLICY exam_items_instructor_insert ON exam_items FOR INSERT WITH CHECK (app.is_instructor(course_id));|exam_items_insert__yayinlanmis_kagida_soru_eklenemez"
"exam_sessions_self_insert: RLS ve trigger pencere sarti birlikte duserse|DROP TRIGGER exam_sessions_feedback_schedule_guard ON exam_sessions; DROP POLICY exam_sessions_self_insert ON exam_sessions; CREATE POLICY exam_sessions_self_insert ON exam_sessions FOR INSERT WITH CHECK (user_id = app.current_user_id() AND app.is_member(course_id));|exam_sessions_insert__PENCERE_KAPALI_oturum_acilamaz"
"exam_sessions_self_insert: user_id sarti duserse|DROP POLICY exam_sessions_self_insert ON exam_sessions; CREATE POLICY exam_sessions_self_insert ON exam_sessions FOR INSERT WITH CHECK (app.is_member(course_id) AND (exam_version_id IS NULL OR app.is_exam_open(exam_version_id, course_id)));|exam_sessions_insert__baskasi_adina_oturum_acilamaz"
)

# Referans koşu: bozulmamış şemada hiçbir iddia kırmızı olmamalı. Bu kontrol olmadan
# "mutasyonda FAIL çıktı" bulgusu anlamsızdır — belki test zaten kırmızıydı.
if ! baseline=$("$PSQL" -X -v ON_ERROR_STOP=1 -d "$TEMPLATE_DB" -f "$TEST_SQL" 2>&1); then
    echo "HATA: bozulmamış şemadaki referans koşu tamamlanamadı." >&2
    echo "$baseline" >&2
    exit 1
fi
if grep -q FAIL <<<"$baseline"; then
    echo "HATA: bozulmamış şemada FAIL var — mutasyon testi anlamsız."
    grep FAIL <<<"$baseline"
    exit 1
fi
echo "referans koşu temiz (bozulmamış şemada FAIL yok)"
echo

failures=0
total=0
for entry in "${MUTATIONS[@]}"; do
    IFS='|' read -r name mutation expected <<<"$entry"
    total=$((total + 1))
    scratch="rls_bp_mut_$$_${total}"
    "$CREATEDB" -T "$TEMPLATE_DB" "$scratch"
    created_databases+=("$scratch")
    "$PSQL" -v ON_ERROR_STOP=1 -q -d "$scratch" -c "$mutation"
    if ! output=$("$PSQL" -X -v ON_ERROR_STOP=1 -d "$scratch" -f "$TEST_SQL" 2>&1); then
        "$DROPDB" "$scratch"
        printf 'KAÇIRILDI  %-52s -> SQL kanıtı tamamlanamadı\n' "$name"
        echo "$output" >&2
        failures=$((failures + 1))
        continue
    fi
    "$DROPDB" "$scratch"

    if grep -q "FAIL  ${expected}" <<<"$output"; then
        printf 'YAKALANDI  %-52s -> %s\n' "$name" "$expected"
    else
        printf 'KAÇIRILDI  %-52s -> %s beklenen FAIL gelmedi\n' "$name" "$expected"
        failures=$((failures + 1))
    fi
done

echo
echo "${total} mutasyon denendi, $((total - failures)) tanesi yakalandı."
if [ "$failures" -gt 0 ]; then
    echo "KAÇIRILAN MUTASYON VAR — rls_blueprint.sql o politikayı gerçekten sınamıyor."
    exit 1
fi
echo "Her politika ve yetki bozulduğunda ilgili iddia kırmızı yanıyor."
