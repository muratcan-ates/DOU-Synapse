#!/usr/bin/env bash
#
# rls_isolation.sql'in KIRMIZI YANABİLDİĞİNİN kanıtı — çekirdek şema mutasyon testi.
#
# Neden gerekli: "politika var" demek kanıt değildir; "politika bozulduğunda testim bunu
# yakalar" demek kanıttır. Ölçme katmanında bu açık 6 Ağustos'ta ölçülmüştü
# (rls_assessment_mutation_check.sh başlığı). Çekirdek şemada aynı açık 9 Ağustos'a kadar
# duruyordu: CI yalnız `chunks_member_read`'i bozup FAIL arıyordu, yani `courses`,
# `course_memberships`, `chat_sessions`, `chat_messages` ve `request_logs` politikalarının
# tamamı `USING (true)` yapılsa bile kapı geçiyordu.
#
# Bu betik 0001 ve 0003'ün politikalarını TEKER TEKER bozar ve her seferinde:
#   1. rls_isolation.sql'i koşar,
#   2. BEKLENEN iddianın FAIL'e döndüğünü doğrular.
#
# İkinci adım kritiktir: "bir yerde FAIL çıktı" yetersiz bir kontroldür, çünkü alakasız
# bir bozulma da FAIL üretir. Mutasyonun HANGİ iddiayı düşürdüğü doğrulanmazsa testlerin
# politikalara gerçekten bağlı olduğu gösterilmiş olmaz.
#
# Politikaların yanı sıra dört YARDIMCI FONKSİYON da bozulur (app.is_member,
# app.is_instructor, app.is_instructor_of, app.current_user_id). Politikalar bu
# fonksiyonlara delege ettiği için, fonksiyondaki bir gevşeme her politikayı aynı anda
# gevşetir; hiçbir politika metni değişmeden izolasyonun tamamı kaybolabilir.
#
# Kullanım:
#     supabase/tests/rls_isolation_mutation_check.sh [migrasyonlari_uygulanmis_db]
#
# Varsayılan şablon veritabanı yoksa kurulur. Her mutasyon şablondan kopyalanan geçici
# bir veritabanında koşar; şablon hiç değişmez.

set -euo pipefail

TEMPLATE_DB="${1:-rls_isolation_template}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_SQL="${REPO_ROOT}/supabase/tests/rls_isolation.sql"
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
# UTF-8 ayraç her baytında ayrı ayrı böler. Mutasyon SQL'lerinde boru işareti geçmiyor.
#
# Fonksiyon gövdelerindeki `\$\$`: çift tırnak içinde `$$` kabuğun süreç kimliğine
# genişler. Kaçışlı hâli diziye düz `$$` olarak girer.
MUTATIONS=(
# --- profiles ---------------------------------------------------------------
"profiles_self_read acilirsa|DROP POLICY profiles_self_read ON profiles; CREATE POLICY profiles_self_read ON profiles FOR SELECT USING (true);|profiles_read__ogrenci_arkadasinin_profilini_goremez"
"profiles_self_read: egitmen dali duserse|DROP POLICY profiles_self_read ON profiles; CREATE POLICY profiles_self_read ON profiles FOR SELECT USING (id = app.current_user_id());|profiles_read__egitmen_kendi_ogrencilerini_gorur"
"profiles_self_update acilirsa|DROP POLICY profiles_self_update ON profiles; CREATE POLICY profiles_self_update ON profiles FOR UPDATE USING (true);|profiles_update__egitmen_ogrencinin_adini_degistiremez"
"profiles_self_update kaldirilirsa|DROP POLICY profiles_self_update ON profiles;|profiles_update__kendi_adini_degistirebilir"
"profiles: INSERT politikasi eklenirse|CREATE POLICY profiles_insert_leak ON profiles FOR INSERT WITH CHECK (true);|profiles_insert__politika_yok_profil_yaratilamaz"
"profiles: DELETE politikasi eklenirse|CREATE POLICY profiles_delete_leak ON profiles FOR DELETE USING (true);|profiles_delete__politika_yok_profil_silinemez"
# --- courses ----------------------------------------------------------------
"courses_member_read acilirsa|DROP POLICY courses_member_read ON courses; CREATE POLICY courses_member_read ON courses FOR SELECT USING (true);|courses_read__baska_ders_gorunmez"
"courses_instructor_update acilirsa|DROP POLICY courses_instructor_update ON courses; CREATE POLICY courses_instructor_update ON courses FOR UPDATE USING (true);|courses_update__ogrenci_ders_guncelleyemez"
"courses: INSERT politikasi eklenirse|CREATE POLICY courses_insert_leak ON courses FOR INSERT WITH CHECK (true);|courses_insert__politika_yok_dogrudan_yazilamaz"
"courses: DELETE politikasi eklenirse|CREATE POLICY courses_delete_leak ON courses FOR DELETE USING (true);|courses_delete__politika_yok_ders_silinemez"
# --- course_memberships -----------------------------------------------------
"memberships_read acilirsa|DROP POLICY memberships_read ON course_memberships; CREATE POLICY memberships_read ON course_memberships FOR SELECT USING (true);|memberships_read__ogrenci_sinif_listesini_goremez"
"memberships_insert acilirsa|DROP POLICY memberships_insert ON course_memberships; CREATE POLICY memberships_insert ON course_memberships FOR INSERT WITH CHECK (true);|memberships_insert__ogrenci_uye_ekleyemez"
"memberships_instructor_update acilirsa|DROP POLICY memberships_instructor_update ON course_memberships; CREATE POLICY memberships_instructor_update ON course_memberships FOR UPDATE USING (true);|memberships_update__ogrenci_kendini_egitmen_yapamaz"
"memberships_instructor_delete acilirsa|DROP POLICY memberships_instructor_delete ON course_memberships; CREATE POLICY memberships_instructor_delete ON course_memberships FOR DELETE USING (true);|memberships_delete__ogrenci_kendi_uyeligini_silemez"
# --- documents --------------------------------------------------------------
"documents_member_read acilirsa|DROP POLICY documents_member_read ON documents; CREATE POLICY documents_member_read ON documents FOR SELECT USING (true);|documents_read__baska_dersin_belgesi_gorunmez"
"documents_instructor_insert acilirsa|DROP POLICY documents_instructor_insert ON documents; CREATE POLICY documents_instructor_insert ON documents FOR INSERT WITH CHECK (true);|documents_insert__ogrenci_belge_yukleyemez"
"documents_instructor_update acilirsa|DROP POLICY documents_instructor_update ON documents; CREATE POLICY documents_instructor_update ON documents FOR UPDATE USING (true);|documents_update__ogrenci_belge_guncelleyemez"
"documents_instructor_delete acilirsa|DROP POLICY documents_instructor_delete ON documents; CREATE POLICY documents_instructor_delete ON documents FOR DELETE USING (true);|documents_delete__ogrenci_belge_silemez"
# --- chunks -----------------------------------------------------------------
"chunks_member_read acilirsa|DROP POLICY chunks_member_read ON chunks; CREATE POLICY chunks_member_read ON chunks FOR SELECT USING (true);|chunks_read__baska_dersin_chunki_gorunmez"
"chunks: INSERT politikasi eklenirse|CREATE POLICY chunks_insert_leak ON chunks FOR INSERT WITH CHECK (true);|chunks_insert__politika_yok_uygulama_chunk_yazamaz"
"chunks: UPDATE politikasi eklenirse|CREATE POLICY chunks_update_leak ON chunks FOR UPDATE USING (true);|chunks_update__politika_yok_kaynak_degistirilemez"
"chunks: DELETE politikasi eklenirse|CREATE POLICY chunks_delete_leak ON chunks FOR DELETE USING (true);|chunks_delete__politika_yok_kaynak_silinemez"
# --- ingestion_jobs ---------------------------------------------------------
"jobs_instructor_read acilirsa|DROP POLICY jobs_instructor_read ON ingestion_jobs; CREATE POLICY jobs_instructor_read ON ingestion_jobs FOR SELECT USING (true);|jobs_read__ogrenci_is_kuyrugunu_goremez"
"jobs_instructor_insert acilirsa|DROP POLICY jobs_instructor_insert ON ingestion_jobs; CREATE POLICY jobs_instructor_insert ON ingestion_jobs FOR INSERT WITH CHECK (true);|jobs_insert__ogrenci_is_kuyruguna_yazamaz"
"ingestion_jobs: UPDATE politikasi eklenirse|CREATE POLICY jobs_update_leak ON ingestion_jobs FOR UPDATE USING (true);|jobs_update__politika_yok_uygulama_isi_ilerletemez"
"ingestion_jobs: DELETE politikasi eklenirse|CREATE POLICY jobs_delete_leak ON ingestion_jobs FOR DELETE USING (true);|jobs_delete__politika_yok_is_silinemez"
# --- chat_sessions ----------------------------------------------------------
"chat_sessions_self_read acilirsa|DROP POLICY chat_sessions_self_read ON chat_sessions; CREATE POLICY chat_sessions_self_read ON chat_sessions FOR SELECT USING (true);|chat_sessions_read__baska_ogrencinin_oturumu_gorunmez"
"chat_sessions_self_read egitmene acilirsa|CREATE POLICY chat_sessions_instructor_leak ON chat_sessions FOR SELECT USING (app.is_instructor(course_id));|chat_sessions_read__egitmen_ogrenci_oturumunu_goremez"
"chat_sessions_self_insert: uyelik sarti duserse|DROP POLICY chat_sessions_self_insert ON chat_sessions; CREATE POLICY chat_sessions_self_insert ON chat_sessions FOR INSERT WITH CHECK (user_id = app.current_user_id());|chat_sessions_insert__uye_olunmayan_derste_oturum_acilamaz"
"chat_sessions_self_insert acilirsa|DROP POLICY chat_sessions_self_insert ON chat_sessions; CREATE POLICY chat_sessions_self_insert ON chat_sessions FOR INSERT WITH CHECK (true);|chat_sessions_insert__baskasi_adina_oturum_acilamaz"
# `chat_sessions_self_update`in KOŞULLARI bağımsız olarak gözlenemez: okuma politikası
# hem hangi satırın güncellenebileceğini hem de satırın ne hâle gelebileceğini zaten
# sınırlıyor (rls_isolation.sql, OKUMA NOTU 2). Bu yüzden politika "açılmıyor",
# tamamen KALDIRILIYOR: olumlu iddianın politikanın varlığına bağlı olduğu böyle ölçülür.
"chat_sessions_self_update kaldirilirsa|DROP POLICY chat_sessions_self_update ON chat_sessions;|chat_sessions_update__kendi_oturumunu_guncelleyebilir"
# Ders şartı İKİ politikadan birden düşmedikçe oturum yabancı derse taşınamaz; tek
# politikayı bozan bir mutasyon bu iddiayı kırmızıya çeviremez ve testi "ölçmüyor"
# sanmaya yol açar. Mutasyon bu yüzden ikisini birlikte gevşetiyor.
"chat_sessions ders sarti hem okumada hem guncellemede duserse|DROP POLICY chat_sessions_self_update ON chat_sessions; CREATE POLICY chat_sessions_self_update ON chat_sessions FOR UPDATE USING (user_id = app.current_user_id()); DROP POLICY chat_sessions_self_read ON chat_sessions; CREATE POLICY chat_sessions_self_read ON chat_sessions FOR SELECT USING (user_id = app.current_user_id());|chat_sessions_update__oturum_yabanci_derse_tasinamaz"
"chat_sessions: DELETE politikasi eklenirse|CREATE POLICY chat_sessions_delete_leak ON chat_sessions FOR DELETE USING (true);|chat_sessions_delete__politika_yok_oturum_silinemez"
# --- chat_messages ----------------------------------------------------------
"chat_messages_self_read acilirsa|DROP POLICY chat_messages_self_read ON chat_messages; CREATE POLICY chat_messages_self_read ON chat_messages FOR SELECT USING (true);|chat_messages_read__baska_ogrencinin_mesaji_gorunmez"
"chat_messages egitmene acilirsa|CREATE POLICY chat_messages_instructor_leak ON chat_messages FOR SELECT USING (app.is_instructor(course_id));|chat_messages_read__egitmen_ogrenci_sohbetini_okuyamaz"
"chat_messages_self_insert: course_id eslesmesi duserse|DROP POLICY chat_messages_self_insert ON chat_messages; CREATE POLICY chat_messages_self_insert ON chat_messages FOR INSERT WITH CHECK (EXISTS (SELECT 1 FROM chat_sessions s WHERE s.id = chat_messages.session_id AND s.user_id = app.current_user_id()));|chat_messages_insert__sahte_course_id_ile_yazilamaz"
"chat_messages_self_insert acilirsa|DROP POLICY chat_messages_self_insert ON chat_messages; CREATE POLICY chat_messages_self_insert ON chat_messages FOR INSERT WITH CHECK (true);|chat_messages_insert__baskasinin_oturumuna_yazilamaz"
"chat_messages: UPDATE politikasi eklenirse|CREATE POLICY chat_messages_update_leak ON chat_messages FOR UPDATE USING (true);|chat_messages_update__politika_yok_gecmis_degistirilemez"
"chat_messages: DELETE politikasi eklenirse|CREATE POLICY chat_messages_delete_leak ON chat_messages FOR DELETE USING (true);|chat_messages_delete__politika_yok_gecmis_silinemez"
# --- answer_cache -----------------------------------------------------------
"answer_cache_member_read acilirsa|DROP POLICY answer_cache_member_read ON answer_cache; CREATE POLICY answer_cache_member_read ON answer_cache FOR SELECT USING (true);|answer_cache_read__baska_dersin_onbellegi_gorunmez"
"answer_cache_member_insert acilirsa|DROP POLICY answer_cache_member_insert ON answer_cache; CREATE POLICY answer_cache_member_insert ON answer_cache FOR INSERT WITH CHECK (true);|answer_cache_insert__baska_derse_yazilamaz"
"answer_cache_instructor_delete acilirsa|DROP POLICY answer_cache_instructor_delete ON answer_cache; CREATE POLICY answer_cache_instructor_delete ON answer_cache FOR DELETE USING (true);|answer_cache_delete__ogrenci_onbellek_temizleyemez"
"answer_cache: UPDATE politikasi eklenirse|CREATE POLICY answer_cache_update_leak ON answer_cache FOR UPDATE USING (true);|answer_cache_update__politika_yok_onbellek_degistirilemez"
# --- request_logs -----------------------------------------------------------
"request_logs_self_insert acilirsa|DROP POLICY request_logs_self_insert ON request_logs; CREATE POLICY request_logs_self_insert ON request_logs FOR INSERT WITH CHECK (true);|request_logs_insert__baskasi_adina_yazilamaz"
"request_logs: ogrenciye SELECT acilirsa|CREATE POLICY request_logs_read_leak ON request_logs FOR SELECT USING (true);|request_logs_read__ogrenci_hicbir_kaydi_goremez"
"request_logs: ogrenciye SELECT acilirsa RETURNING de acilir|CREATE POLICY request_logs_read_leak ON request_logs FOR SELECT USING (true);|request_logs_insert__ogrenci_baglaminda_returning_calismaz"
"request_logs: UPDATE politikasi eklenirse|CREATE POLICY request_logs_update_leak ON request_logs FOR UPDATE USING (true);|request_logs_update__politika_yok_olcum_degistirilemez"
"request_logs: DELETE politikasi eklenirse|CREATE POLICY request_logs_delete_leak ON request_logs FOR DELETE USING (true);|request_logs_delete__politika_yok_olcum_silinemez"
# --- yardımcı fonksiyonlar (politika metni değişmeden izolasyonu kaldıranlar) --
"app.is_member: status sarti duserse|CREATE OR REPLACE FUNCTION app.is_member(p_course_id uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS \$\$ SELECT EXISTS (SELECT 1 FROM public.course_memberships m WHERE m.course_id = p_course_id AND m.user_id = app.current_user_id()) \$\$;|courses_read__iptal_edilmis_uyelik_ders_gostermez"
"app.is_instructor: rol sarti duserse|CREATE OR REPLACE FUNCTION app.is_instructor(p_course_id uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS \$\$ SELECT app.is_member(p_course_id) \$\$;|documents_insert__ogrenci_belge_yukleyemez"
"app.is_instructor_of acilirsa|CREATE OR REPLACE FUNCTION app.is_instructor_of(p_user_id uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS \$\$ SELECT true \$\$;|profiles_read__egitmen_baska_dersin_ogrencisini_goremez"
"app.current_user_id: GUC yerine sabit kimlik|CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid LANGUAGE sql STABLE AS \$\$ SELECT '22222222-2222-2222-2222-222222222222'::uuid \$\$;|baglamsiz__chunks_gorunmez"
)

# Referans koşu: bozulmamış şemada hiçbir iddia kırmızı olmamalı. Bu kontrol olmadan
# "mutasyonda FAIL çıktı" bulgusu anlamsızdır — belki test zaten kırmızıydı.
baseline=$("$PSQL" -d "$TEMPLATE_DB" -f "$TEST_SQL" 2>&1 || true)
if grep -q FAIL <<<"$baseline"; then
    echo "HATA: bozulmamış şemada FAIL var — mutasyon testi anlamsız."
    grep FAIL <<<"$baseline"
    exit 1
fi
assertions=$(grep -cE 'PASS  ' <<<"$baseline")
echo "referans koşu temiz: ${assertions} iddia, FAIL yok"
echo

failures=0
total=0
for entry in "${MUTATIONS[@]}"; do
    IFS='|' read -r name mutation expected <<<"$entry"
    total=$((total + 1))
    scratch="rls_iso_mut_$$_${total}"
    "$CREATEDB" -T "$TEMPLATE_DB" "$scratch"
    "$PSQL" -v ON_ERROR_STOP=1 -q -d "$scratch" -c "$mutation"
    output=$("$PSQL" -d "$scratch" -f "$TEST_SQL" 2>&1 || true)
    "$DROPDB" "$scratch"

    # Erken duran koşu, "yakalanmadı" ile karıştırılmamalı: mutasyon bir iddiayı
    # gevşetince ilerideki bir deyim beklenmedik bir hataya (ör. birincil anahtar
    # çakışması) düşebilir ve ON_ERROR_STOP betiği orada keser. Bu, testin politikayı
    # ölçmediği anlamına GELMEZ — nitekim ilk koşuda tam olarak bu oldu ve iki
    # mutasyon yanlışlıkla "kaçırıldı" göründü.
    produced=$(grep -cE '(PASS|FAIL)  ' <<<"$output" || true)
    if [ "$produced" -lt "$assertions" ] && ! grep -q "FAIL  ${expected}" <<<"$output"; then
        printf 'ERKEN DURDU %-57s -> %s/%s iddia koştu\n' "$name" "$produced" "$assertions"
        failures=$((failures + 1))
        continue
    fi

    if grep -q "FAIL  ${expected}" <<<"$output"; then
        printf 'YAKALANDI  %-58s -> %s\n' "$name" "$expected"
    else
        printf 'KAÇIRILDI  %-58s -> %s beklenen FAIL gelmedi\n' "$name" "$expected"
        failures=$((failures + 1))
    fi
done

echo
echo "${total} mutasyon denendi, $((total - failures)) tanesi yakalandı."
if [ "$failures" -gt 0 ]; then
    echo "KAÇIRILAN MUTASYON VAR — rls_isolation.sql o politikayı gerçekten sınamıyor."
    exit 1
fi
echo "Her politika bozulduğunda ilgili iddia kırmızı yanıyor (${assertions} iddia)."
