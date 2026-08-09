"""Uygulama ayarları.

Tüm gizli değerler ortam değişkenlerinden gelir; depoda yalnızca `.env.example` bulunur.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    DEMO = "demo"
    PRODUCTION = "production"


#: Sağlayıcı başına kanıt eşiği. Kosinüs skorları vektör uzayına özgüdür; bir uzayda
#: kalibre edilmiş sayı diğerinde anlamsızdır (bkz. `Settings.evidence_threshold`).
#:
#: `fastembed` (E5)  — **KALİBRE EDİLDİ** (T043, 9 Ağustos). 15 soruluk kalibrasyon
#:   setinde iki sınıfı ayıran değer; karar holdout'a BAKILMADAN önce donduruldu
#:   (`evaluation/calibration.md`). Dürüst sınır (Anayasa III): 55 soruluk holdout'ta
#:   temiz ayrışma TUTMADI — doğru ret %80, hedef %90. Tarama 0.820'nin 10/10
#:   yakaladığını gösteriyor ama oraya geçmek holdout'u ikinci bir kalibrasyon setine
#:   çevirirdi, o yüzden geçilmedi.
#:
#: `hashing` — **KALİBRE EDİLMEMİŞTİR ve edilemez.** Deterministik yerel sağlayıcı;
#:   anlamsal değil, karma tabanlı. Testler ve çevrimdışı geliştirme içindir, bu
#:   uzayda ölçülen hiçbir sayı raporlanamaz. Buradaki değer yalnız "kapsam dışı
#:   soruyu ele, kapsam içindekini geçir" davranışını yaklaşık tutmak için var.
#:   **Demo bu sağlayıcıyla koşulmamalıdır** — ayırt etme gücü zayıf.
EVIDENCE_THRESHOLD_BY_PROVIDER: dict[str, float] = {
    "fastembed": 0.81,
    "hashing": 0.10,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    api_title: str = "DOU-Synapse API"
    api_version: str = "0.1.0"

    # --- Veritabanı ---------------------------------------------------------
    # API bağlantısı `dou_app` rolüyle kurulmalıdır: bu rol tabloların sahibi değildir ve
    # BYPASSRLS taşımaz, dolayısıyla RLS politikaları gerçekten uygulanır.
    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+psycopg://dou_app@localhost:5432/dou_synapse"),
    )
    # Worker, chunks tablosuna yazabilmek için RLS'i atlayan ayrı bir rolle bağlanır.
    worker_database_url: PostgresDsn | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_echo: bool = False

    # --- Kimlik doğrulama ---------------------------------------------------
    # Supabase JWT'lerini doğrulamak için proje JWT secret'ı (HS256).
    supabase_jwt_secret: str | None = None
    jwt_audience: str = "authenticated"
    jwt_algorithms: list[str] = ["HS256"]

    # Çevrimdışı demo ve yerel geliştirme için kimlik doğrulama bypass'ı.
    # Üretimde açılması ayarların yüklenmesini engeller (aşağıdaki doğrulayıcı).
    dev_auth_enabled: bool = False

    # --- CORS ---------------------------------------------------------------
    # Yerel varsayılan iki portu kapsar: 3000 geliştirme sunucusu, 3100 uçtan uca
    # test sunucusu. E2E ayrı portta koşar çünkü Next 16 aynı dizinde ikinci bir
    # dev sunucusuna izin vermiyor; test portu izinli olmazsa tarayıcı istekleri
    # CORS'a takılır ve testler ürün hatası gibi görünen bir kararsızlık üretir.
    # Üretimde bu liste ortam değişkeninden gelir ve yalnız gerçek alan adını içerir.
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3100"]

    # --- Yükleme ve depolama ------------------------------------------------
    max_upload_bytes: int = 20 * 1024 * 1024
    # Yerel belge deposu. Bulutta Supabase Storage adaptörüyle değiştirilir.
    storage_root: str = "./storage"
    # Worker'ın tek turda işleyeceği azami iş sayısı; bir belgenin kuyruğu tıkamaması için.
    worker_batch_size: int = 5

    # --- Embedding ----------------------------------------------------------
    # DİKKAT: Bu ayar ingest zamanına aittir. Değiştirmek vektör uzayını değiştirir ve
    # tüm korpusun yeniden işlenmesini gerektirir; çalışma zamanı yedeği olarak kullanılamaz.
    # "fastembed" = multilingual-e5-large (üretim), "hashing" = deterministik yerel (test).
    #
    # AÇIK RİSK (9 Ağustos, ölçüldü): fastembed bu modeli artık **mean pooling** ile
    # çalıştırıyor, eski sürümler **CLS** kullanıyordu ve kütüphane bunu yalnız bir
    # UserWarning ile söylüyor. Pooling değişikliği vektör uzayını değiştirir; yani
    # farklı fastembed sürümleriyle ingest edilmiş bir korpusla sorgu yapmak, sessizce
    # yanlış komşuları döndürür. Kanıt eşiğinin sağlayıcıya bağlı olması bu sınıfın
    # yalnız bir yarısını kapatıyor — ikinci yarısı SÜRÜM.
    #
    # Kapatılması gereken: chunk'ın hangi sağlayıcı VE hangi sürümle embed edildiği
    # kayda geçmeli, sorgu zamanında uyuşmazlık fail-closed davranmalı. Şema
    # değişikliği gerektiriyor (R4'ün `0006`'sı) ve R2'nin ölçüm koşularını da
    # ilgilendiriyor; ikisine de iletildi.
    embedding_provider: Literal["fastembed", "hashing"] = "hashing"
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_cache_dir: str | None = None
    embedding_batch_size: int = 32
    allowed_upload_extensions: set[str] = {
        ".pdf",
        ".pptx",
        ".md",
        ".txt",
        ".py",
        ".java",
        ".js",
        ".ts",
        ".c",
        ".h",
        ".cpp",
    }

    # --- Assessment ---------------------------------------------------------
    exam_question_count: int = 10
    exam_duration_minutes: int = 20
    question_generation_batch: int = 5
    mastery_alpha: float = 0.3  # yeni = (1-alpha)*eski + alpha*son

    # --- Retrieval (Faz A) --------------------------------------------------
    # Bu blok, paralel geliştirme başlamadan ÖNCE tek seferde eklendi: beş oturum
    # aynı dosyaya ayrı ayrı alan eklemeye kalksaydı her birleştirmede çakışırdı.
    # Değerler ilk tahmindir; T043 kalibrasyon setiyle ayarlanacak ve seçilen
    # değerin gerekçesi evaluation/calibration.md'ye yazılacaktır (Anayasa III).
    retrieval_top_k: int = 8
    retrieval_dense_candidates: int = 24
    retrieval_fts_candidates: int = 24
    #: RRF sabiti: k büyüdükçe sıralama farkları yumuşar (standart başlangıç 60).
    retrieval_rrf_k: int = 60
    #: Kanıt eşiği: altında kalan sorgu cevaplanmaz, abstention döner.
    #:
    #: **EŞİK EMBEDDING SAĞLAYICISINA BAĞLIDIR** ve bu bağ 9 Ağustos'ta canlı koşuda
    #: pahalıya patladı: 0.81 `fastembed` (E5) vektör uzayında kalibre edildi, dev
    #: veritabanı ise `hashing` sağlayıcısıyla ingest edilmişti. O uzayda ölçülen en
    #: iyi skorlar 0.07–0.37 arasında; yani eşik HER SORUYU reddediyordu — kapsam
    #: içindekiler dahil. Arayüzde her soru "materyalde dayanak bulunamadı" dönüyordu
    #: ve bu, bozuk bir sistemin doğru çalışıyor gibi görünmesinin ta kendisiydi.
    #:
    #: Bu yüzden değer artık tek bir sayı değil, sağlayıcı başına çözülür. Kosinüs
    #: benzerliği farklı vektör uzaylarında karşılaştırılabilir bir büyüklük değildir;
    #: bir uzayda kalibre edilmiş eşiği diğerine taşımak sessiz bir hatadır.
    #:
    #: `.env`'de `EVIDENCE_THRESHOLD` açıkça verilirse o kazanır (kalibrasyon
    #: taramaları bunu kullanır); verilmezse sağlayıcıdan çözülür.
    evidence_threshold: float = EVIDENCE_THRESHOLD_BY_PROVIDER["fastembed"]

    # --- Değerlendirme koşuları (Faz F) -------------------------------------
    #: Ölçüm koşularının kullandığı LLM anahtarı. Üretim anahtarından AYRI tutulur:
    #: bir ölçüm koşusu üretim kotasını tüketmemeli ve tersi de olmamalı.
    eval_llm_api_key: str | None = None

    # --- Worker tetiği (Faz G) ----------------------------------------------
    #: `POST /internal/drain` ucunu koruyan paylaşılan sır. Tanımsızsa uç KAPALIDIR
    #: (fail-closed): sırsız açık bir drain ucu, dışarıdan iş kuyruğu tetiklemeye
    #: izin verirdi.
    worker_drain_secret: str | None = None

    # --- LLM (Faz B) --------------------------------------------------------
    #: Sağlayıcı sırası: ilki denenir, hata/kota durumunda sıradakine düşülür.
    llm_primary_model: str = "groq/llama-3.3-70b-versatile"
    llm_fallback_model: str = "gemini/gemini-2.0-flash"
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 1
    llm_temperature: float = 0.2
    #: Anahtar yokken (CI, çevrimdışı demo) deterministik sahte sağlayıcı koşar.
    #: Üretimde açık kalırsa gerçek kullanıcıya sahte cevap gider — bu yüzden
    #: aşağıdaki doğrulayıcı üretim ortamında açık bırakılmasını reddeder.
    llm_fake_provider: bool = False

    # --- Sokratik mod (Faz D) -----------------------------------------------
    #: İpucu kademesi çarpanları mastery'de kullanılır; kademe sayısı buradan.
    socratic_max_stage: int = 4

    # --- Sohbet sınırları (FR-035) ------------------------------------------
    # Bu iki sayı paralel geliştirme süresince `api/chat.py`'de sabit duruyordu:
    # bu dosya beş oturuma açık olmadığı için oraya yazılamamıştı ve borç olarak
    # kayda geçmişti (07_SERIT_RAPORLARI §6). Buraya taşınmalarının pratik faydası,
    # demo makinesinde yeniden derlemeden gevşetilebilmeleri.
    #
    #: Kullanıcı başına, pencere başına azami sohbet isteği.
    chat_rate_limit_requests: int = 20
    #: Sınırın penceresi (saniye).
    chat_rate_limit_window_seconds: float = 60.0

    @model_validator(mode="after")
    def _resolve_evidence_threshold(self) -> Settings:
        """Eşiği, açıkça verilmediyse embedding sağlayıcısından çözer.

        `model_fields_set` ayrımı önemli: ortamda `EVIDENCE_THRESHOLD` verilmişse
        (kalibrasyon taramaları bunu yapar) ona dokunulmaz. Verilmemişse
        sağlayıcının uzayına ait değer kullanılır — çünkü sınıf üzerindeki
        varsayılan tek bir uzaya aittir ve başka bir uzayda sessizce yanlıştır.
        """
        if "evidence_threshold" not in self.model_fields_set:
            resolved = EVIDENCE_THRESHOLD_BY_PROVIDER.get(self.embedding_provider)
            if resolved is not None:
                # `model_config` frozen değil; doğrudan atama meşru.
                object.__setattr__(self, "evidence_threshold", resolved)
        return self

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @model_validator(mode="after")
    def _check_auth_configuration(self) -> Settings:
        if self.dev_auth_enabled and self.is_production:
            raise ValueError(
                "DEV_AUTH_ENABLED üretim ortamında açılamaz. "
                "Bu bayrak yalnızca yerel geliştirme ve çevrimdışı demo içindir."
            )
        if not self.dev_auth_enabled and not self.supabase_jwt_secret:
            raise ValueError("SUPABASE_JWT_SECRET tanımlı olmalı ya da DEV_AUTH_ENABLED açılmalı.")
        return self

    @model_validator(mode="after")
    def _check_llm_configuration(self) -> Settings:
        """Sahte sağlayıcı üretimde açılamaz — DEV_AUTH ile aynı fail-closed kural.

        Sahte sağlayıcı testleri ağsız koşturmak ve çevrimdışı demo yedeği için
        vardır. Üretimde açık kalırsa gerçek öğrenciye uydurulmuş bir cevap
        gider ve bunu fark etmenin yolu yoktur; bu yüzden uygulama hiç açılmaz.
        """
        if self.llm_fake_provider and self.is_production:
            raise ValueError(
                "LLM_FAKE_PROVIDER üretim ortamında açılamaz. "
                "Bu bayrak yalnız test ve çevrimdışı demo içindir."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
