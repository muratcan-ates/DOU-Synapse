#!/usr/bin/env bash
#
# rls_assessment.sql'in KIRMIZI YANABİLDİĞİNİN kanıtı — mutasyon testi.
#
# Neden gerekli: "politika var" demek kanıt değildir; "politika bozulduğunda testim
# bunu yakalar" demek kanıttır. 6 Ağustos PR incelemesinde ölçülen açık tam buydu —
# `questions_read`'den `AND status = 'approved'` düşürüldüğünde 92 test yeşil kalıyor,
# `rls_isolation.sql` 8/8 PASS veriyor ve CI kapısı geçiyordu. Yanmayan test hiçbir
# şey kanıtlamaz (Anayasa II, III).
#
# Bu betik 0004'ün politikalarını TEKER TEKER bozar ve her seferinde:
#   1. rls_assessment.sql'i koşar,
#   2. BEKLENEN iddianın FAIL'e döndüğünü doğrular.
#
# İkinci adım kritiktir: "bir yerde FAIL çıktı" yetersiz bir kontroldür, çünkü
# alakasız bir bozulma da FAIL üretir. Mutasyonun HANGİ iddiayı düşürdüğü
# doğrulanmazsa testlerin politikalara gerçekten bağlı olduğu gösterilmiş olmaz.
#
# Kullanım:
#     supabase/tests/rls_assessment_mutation_check.sh [migrasyonlari_uygulanmis_db]
#
# Varsayılan şablon veritabanı yoksa kurulur. Her mutasyon şablondan kopyalanan
# geçici bir veritabanında koşar; şablon hiç değişmez.

set -euo pipefail

TEMPLATE_DB="${1:-rls_assessment_template}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_SQL="${REPO_ROOT}/supabase/tests/rls_assessment.sql"
PSQL="${PG_BIN:+${PG_BIN}/}psql"
CREATEDB="${PG_BIN:+${PG_BIN}/}createdb"
DROPDB="${PG_BIN:+${PG_BIN}/}dropdb"

if ! "$PSQL" -lqtA -d postgres 2>/dev/null | cut -d'|' -f1 | grep -qx "$TEMPLATE_DB"; then
    echo "şablon veritabanı kuruluyor: $TEMPLATE_DB"
    "$CREATEDB" "$TEMPLATE_DB"
    for migration in "${REPO_ROOT}"/supabase/migrations/*.sql; do
        "$PSQL" -v ON_ERROR_STOP=1 -q -d "$TEMPLATE_DB" -f "$migration"
    done
fi

# Her girdi: mutasyon adı | bozma SQL'i | FAIL'e dönmesi BEKLENEN iddianın adı.
#
# Ayraç tek baytlık olmak zorunda: `read -r` IFS'i bayt bayt uygular, çok baytlı bir
# UTF-8 ayraç (ör. ¦) her baytında ayrı ayrı böler. Mutasyon SQL'lerinde boru işareti
# geçmediği için `|` güvenli.
MUTATIONS=(
"topics_member_read acilirsa|DROP POLICY topics_member_read ON topics; CREATE POLICY topics_member_read ON topics FOR SELECT USING (true);|topics_read__baska_dersin_konusu_gorunmez"
"topics_instructor_write acilirsa|DROP POLICY topics_instructor_write ON topics; CREATE POLICY topics_instructor_write ON topics FOR INSERT WITH CHECK (true);|topics_write__ogrenci_konu_acamaz"
"topics_instructor_update acilirsa|DROP POLICY topics_instructor_update ON topics; CREATE POLICY topics_instructor_update ON topics FOR UPDATE USING (true);|topics_update__ogrenci_konu_guncelleyemez"
"topics_instructor_delete acilirsa|DROP POLICY topics_instructor_delete ON topics; CREATE POLICY topics_instructor_delete ON topics FOR DELETE USING (true);|topics_delete__ogrenci_konu_silemez"
"questions_read: approved sarti duserse|DROP POLICY questions_read ON questions; CREATE POLICY questions_read ON questions FOR SELECT USING (app.is_member(course_id));|questions_read__ogrenci_taslak_soruyu_goremez"
"questions_read tamamen acilirsa|DROP POLICY questions_read ON questions; CREATE POLICY questions_read ON questions FOR SELECT USING (true);|questions_read__baska_dersin_ogrencisi_goremez"
"questions_instructor_write acilirsa|DROP POLICY questions_instructor_write ON questions; CREATE POLICY questions_instructor_write ON questions FOR INSERT WITH CHECK (true);|questions_write__ogrenci_soru_ekleyemez"
"questions_instructor_update acilirsa|DROP POLICY questions_instructor_update ON questions; CREATE POLICY questions_instructor_update ON questions FOR UPDATE USING (true);|questions_update__ogrenci_onayli_soruyu_degistiremez"
"questions: DELETE politikasi eklenirse|CREATE POLICY questions_delete_leak ON questions FOR DELETE USING (true);|questions_delete__politika_yok_kimse_silemez"
"exam_sessions_self_read acilirsa|DROP POLICY exam_sessions_self_read ON exam_sessions; CREATE POLICY exam_sessions_self_read ON exam_sessions FOR SELECT USING (true);|exam_sessions_read__baska_ogrencinin_oturumu_gorunmez"
"exam_sessions_self_insert acilirsa|DROP POLICY exam_sessions_self_insert ON exam_sessions; CREATE POLICY exam_sessions_self_insert ON exam_sessions FOR INSERT WITH CHECK (true);|exam_sessions_insert__baskasi_adina_oturum_acilamaz"
"exam_sessions_self_update: WITH CHECK duserse|DROP POLICY exam_sessions_self_update ON exam_sessions; CREATE POLICY exam_sessions_self_update ON exam_sessions FOR UPDATE USING (user_id = app.current_user_id());|exam_sessions_update__oturum_yabanci_derse_tasinamaz"
"exam_sessions_self_update acilirsa|DROP POLICY exam_sessions_self_update ON exam_sessions; CREATE POLICY exam_sessions_self_update ON exam_sessions FOR UPDATE USING (true) WITH CHECK (true);|exam_sessions_update__egitmen_ogrenci_oturumunu_guncelleyemez"
"answers_self_read acilirsa|DROP POLICY answers_self_read ON answers; CREATE POLICY answers_self_read ON answers FOR SELECT USING (true);|answers_read__baska_ogrencinin_cevabi_gorunmez"
"answers_self_insert: course_id eslesmesi duserse|DROP POLICY answers_self_insert ON answers; CREATE POLICY answers_self_insert ON answers FOR INSERT WITH CHECK (EXISTS (SELECT 1 FROM exam_sessions s WHERE s.id = answers.session_id AND s.user_id = app.current_user_id()));|answers_insert__sahte_course_id_ile_yazilamaz"
"answers_self_insert acilirsa|DROP POLICY answers_self_insert ON answers; CREATE POLICY answers_self_insert ON answers FOR INSERT WITH CHECK (true);|answers_insert__baskasinin_oturumuna_yazilamaz"
"answers: UPDATE politikasi eklenirse|CREATE POLICY answers_update_leak ON answers FOR UPDATE USING (true);|answers_update__politika_yok_cevap_degistirilemez"
"mastery_self_read acilirsa|DROP POLICY mastery_self_read ON mastery; CREATE POLICY mastery_self_read ON mastery FOR SELECT USING (true);|mastery_read__baska_ogrencinin_skoru_gorunmez"
"mastery_self_insert: uyelik sarti duserse|DROP POLICY mastery_self_insert ON mastery; CREATE POLICY mastery_self_insert ON mastery FOR INSERT WITH CHECK (user_id = app.current_user_id());|mastery_insert__uye_olunmayan_derse_yazilamaz"
"mastery_self_update acilirsa|DROP POLICY mastery_self_update ON mastery; CREATE POLICY mastery_self_update ON mastery FOR UPDATE USING (true) WITH CHECK (true);|mastery_update__egitmen_ogrenci_skorunu_guncelleyemez"
"mastery: DELETE politikasi eklenirse|CREATE POLICY mastery_delete_leak ON mastery FOR DELETE USING (true);|mastery_delete__politika_yok_gecmis_silinemez"
)

# Referans koşu: bozulmamış şemada hiçbir iddia kırmızı olmamalı. Bu kontrol olmadan
# "mutasyonda FAIL çıktı" bulgusu anlamsızdır — belki test zaten kırmızıydı.
baseline=$("$PSQL" -d "$TEMPLATE_DB" -f "$TEST_SQL" 2>&1 || true)
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
    scratch="rls_mut_$$_${total}"
    "$CREATEDB" -T "$TEMPLATE_DB" "$scratch"
    "$PSQL" -v ON_ERROR_STOP=1 -q -d "$scratch" -c "$mutation"
    output=$("$PSQL" -d "$scratch" -f "$TEST_SQL" 2>&1 || true)
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
    echo "KAÇIRILAN MUTASYON VAR — rls_assessment.sql o politikayı gerçekten sınamıyor."
    exit 1
fi
echo "Her politika bozulduğunda ilgili iddia kırmızı yanıyor."
