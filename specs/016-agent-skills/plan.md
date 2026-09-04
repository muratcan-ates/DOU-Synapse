# Plan — 016

Dal 016-agent-skills; temel ed6103fbe53be3888252074db0a722cfe1be617c. Kaynak015 adayı ve önceki başarısız aday korunur. Göç yok; test DB'si gerekmiyor. İzole davranış denemeleri geçici dizinlerde yapılır.

## Sahiplik

- root: 3 DOU becerisi ve Claude karşılığı, doğrulama aracı/testi, CI ve docs/spec/ledger.
- mail_requirements: 9 çekirdek Speckit Codex becerisi.
- student_api_audit: 5 Git Speckit Codex becerisi.
- bağımsız inceleyici: yalnız geçici deney ve geri bildirim.

## Sıra

1. Kaynakları ve yan etkileri incele; mevcut görev pimi ve scriptlerin davranışını doğrula.
2. 17 Codex sürümünü oluştur, DOU yönergelerini güncelle.
3. Yapısal/dosya bağlantı kontrolü, bozulan fixture karşı testleri ve bağımsız kullanım denemesi.
4. Belge/env/CI bütünlüğünü kapsamla orantılı doğrula, uzun planı ve envanteri güncelle.
5. Temiz yerel commit ve bu farkın kesin denetimini kaydet. Main/dağıtım ve gerçek sağlayıcı kabulünü ayrı bırak.

Codex yerel repo keşfi için resmi `.agents/skills` yolu kullanılır. Küresel17 kopya oluşturulmaz; aynı adların iki kez görünmesi önlenir. Bu projede çalışmayan sohbet, skill dosyasını açık yoluyla okuyabilir.
