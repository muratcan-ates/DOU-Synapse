-- FR-200..203 — kullanıcının kendi sohbet geçmişini silmesi ve üyeliğini
-- kendi isteğiyle sonlandırması için dar RLS yetkileri.
--
-- 0008-0011 production-hardening planında başka şeritlere ayrılmıştır; bu
-- migration onların ardından uygulanır. Yeni politikalar mevcut okuma/yazma
-- yüzeylerini genişletmez: yalnız satırın sahibi DELETE edebilir ve üyelik
-- güncellemesinin tek izinli son durumu `revoked` olur.

BEGIN;

-- PostgreSQL UPDATE/DELETE işlemleri için satırın bir SELECT politikasıyla da
-- görünür olması gerekir. Aktif üyelik sona erdikten sonra mevcut okuma
-- politikası satırı gizlediği için, kullanıcı kendi geçmişini indiremez veya
-- silemezdi. Ders uçları ayrıca aktif üyelik kapısından geçtiğinden bu politika
-- eski ders ekranlarını yeniden açmaz; yalnız `/me` veri hakkı uçlarını mümkün
-- kılar.
CREATE POLICY chat_sessions_privacy_self_read ON chat_sessions
    FOR SELECT USING (user_id = app.current_user_id());

CREATE POLICY chat_sessions_self_delete ON chat_sessions
    FOR DELETE USING (user_id = app.current_user_id());

CREATE POLICY memberships_self_revoke ON course_memberships
    FOR UPDATE USING (user_id = app.current_user_id())
    WITH CHECK (
        user_id = app.current_user_id()
        AND status = 'revoked'
    );

COMMIT;
