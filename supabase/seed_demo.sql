-- Yerel geliştirme demo kullanıcıları.
-- UUID'ler apps/web/app/page.tsx içindeki giriş kartlarıyla eşleşir.
-- Üretimde bu dosya ÇALIŞTIRILMAZ. Ders rolleri course_memberships'tedir.

INSERT INTO profiles (id, email, full_name) VALUES
    ('11111111-1111-1111-1111-111111111111', 'ayse@dogus.edu.tr', 'Ayşe Hoca'),
    ('22222222-2222-2222-2222-222222222222', 'burak@dogus.edu.tr', 'Burak Yılmaz'),
    ('33333333-3333-3333-3333-333333333333', 'bilgi-islem@demo.dogus.edu.tr', 'Bilgi İşlem')
ON CONFLICT (email) DO UPDATE SET id = EXCLUDED.id, full_name = EXCLUDED.full_name;

-- Eski demo Ayşe'ye operatör yetkisi veriyordu. Tekrar kurulumda da ayrımı düzelt.
-- Yalnız sabit demo kimliği etkilenir; ders üyelikleri korunur.
DELETE FROM platform_admins WHERE user_id = '11111111-1111-1111-1111-111111111111';

-- Teknik gözlem hesabının ders üyeliği yoktur. Yönetim, ders içeriğini açmaz.
-- Üretimde bu atama kontrollü DBA/kurulum adımıyla yapılır.
INSERT INTO platform_admins (user_id)
VALUES ('33333333-3333-3333-3333-333333333333')
ON CONFLICT (user_id) DO NOTHING;
