"""Kanıt eşiğinin embedding sağlayıcısına bağlı çözülmesi.

Neden ayrı bir test dosyası: 9 Ağustos'ta canlı koşuda eşik HER SORUYU
reddediyordu — kapsam içindekiler dahil. Sebep bir kod hatası değil, bir
KATEGORİ hatasıydı: 0.81 `fastembed` (E5) uzayında kalibre edilmişti, dev
veritabanı ise `hashing` ile ingest edilmişti ve o uzayda en iyi skorlar
0.07–0.37 arasındaydı.

Bu hatanın en kötü yanı sessiz olmasıydı: sistem "materyalde dayanak yok"
diyordu, yani BOZUKKEN DOĞRU ÇALIŞIYOR GİBİ görünüyordu. Abstention'ı ürünün
başarısı sayan bir tasarımda (Anayasa VII) bu, fark edilmesi en zor arıza
biçimi. Aşağıdaki iddialar o sessizliği kaldırır.
"""

from __future__ import annotations

from app.core.config import EVIDENCE_THRESHOLD_BY_PROVIDER, Settings


def _settings(**kwargs: object) -> Settings:
    # `_env_file=None`: geliştiricinin .env'i testin sonucunu belirlememeli.
    return Settings(dev_auth_enabled=True, _env_file=None, **kwargs)  # type: ignore[arg-type]


class TestEsikSaglayicidanCozulur:
    def test_fastembed_kalibre_edilmis_degeri_alir(self) -> None:
        assert _settings(embedding_provider="fastembed").evidence_threshold == 0.81

    def test_hashing_kendi_degerini_alir(self) -> None:
        """Kalibre edilmiş E5 eşiği karma uzayına TAŞINMAZ."""
        ayarlar = _settings(embedding_provider="hashing")

        assert ayarlar.evidence_threshold == EVIDENCE_THRESHOLD_BY_PROVIDER["hashing"]
        assert ayarlar.evidence_threshold != EVIDENCE_THRESHOLD_BY_PROVIDER["fastembed"]

    def test_acik_verilen_deger_kazanir(self) -> None:
        """Kalibrasyon taramaları eşiği açıkça verir; çözümleme onu ezmemeli."""
        ayarlar = _settings(embedding_provider="hashing", evidence_threshold=0.55)

        assert ayarlar.evidence_threshold == 0.55

    def test_her_saglayici_icin_bir_deger_var(self) -> None:
        """Yeni bir sağlayıcı eklenirse eşiği de tanımlanmalı.

        Tanımlanmazsa sınıf varsayılanı (E5'in sayısı) sessizce devreye girer ve
        9 Ağustos'taki hata aynen tekrarlanır.
        """
        saglayicilar = set(
            Settings.model_fields["embedding_provider"].annotation.__args__  # type: ignore[union-attr]
        )

        assert saglayicilar <= set(EVIDENCE_THRESHOLD_BY_PROVIDER), (
            "eşiği tanımlanmamış embedding sağlayıcısı var"
        )
