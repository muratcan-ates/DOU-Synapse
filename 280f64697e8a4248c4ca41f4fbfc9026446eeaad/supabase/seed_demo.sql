-- Yerel geliştirme demo kullanıcıları.
-- UUID'ler apps/web/app/page.tsx içindeki giriş kartlarıyla eşleşir; değiştirilirse
-- ikisi birlikte değiştirilmelidir. Üretimde bu dosya ÇALIŞTIRILMAZ.

INSERT INTO profiles (id, email, full_name) VALUES
    ('11111111-1111-1111-1111-111111111111', 'ayse@dogus.edu.tr',  'Ayşe Hoca'),
    ('22222222-2222-2222-2222-222222222222', 'burak@dogus.edu.tr', 'Burak Yılmaz')
ON CONFLICT (email) DO UPDATE SET id = EXCLUDED.id, full_name = EXCLUDED.full_name;
