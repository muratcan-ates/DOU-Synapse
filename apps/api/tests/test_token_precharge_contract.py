"""Tam-tokenizer kota yolunun yapılandırmayla ilişkisini sabitler.

Ölçülmüş durum (7 Eylül 2026): `_EXACT_QUOTA_TOKENIZER_MODELS` yalnız
`groq/llama-3.3-70b-versatile` içeriyor, ama yapılandırılmış varsayılan model
`groq/openai/gpt-oss-120b`. Yani offline ölçülmüş 24 prompt hash'i, ölçüm
betiği ve manifest bekçisi ÜRETİMDE HİÇ KOŞMAYAN bir dalı koruyor; her istek
muhafazakâr bayt tavanına düşüyor.

Bu dosya o durumu "kaza" olmaktan çıkarır: küme ile yapılandırılmış model
uyuşmadığı sürece testler bunu açıkça yazar, uyuşur hâle geldiğinde ise test
kırmızı yanar ve ölçümün yeni modelin tokenizer'ıyla yenilendiğini doğrulamaya
zorlar. İki durum da bilinçli karar ister; sessiz kalan hiçbir hâli yoktur.
"""

from __future__ import annotations

from app.core.provider_config import DEFAULT_LLM_FALLBACK_MODEL, DEFAULT_LLM_PRIMARY_MODEL
from app.modules.agent.token_precharge import _EXACT_QUOTA_TOKENIZER_MODELS


def test_tam_tokenizer_kumesi_yapilandirilmis_modelle_uyusmuyor() -> None:
    """Bugünkü gerçek: dal ölü. Bu değişirse burada karar verilmeli."""
    assert DEFAULT_LLM_PRIMARY_MODEL not in _EXACT_QUOTA_TOKENIZER_MODELS, (
        "Varsayılan model artık tam-tokenizer kümesinde. Bu iyi bir haber olabilir, "
        "ama ölçümün YENİ modelin tokenizer'ıyla yenilendiğini doğrula: llama-3 ile "
        "alınan 1.024 token tavanı gpt-oss için geçerli değil. "
        "scripts/measure_role_agent_prompt_tokens.py'yi koştur, manifesti tazele, "
        "sonra bu testi güncelle."
    )
    assert DEFAULT_LLM_FALLBACK_MODEL not in _EXACT_QUOTA_TOKENIZER_MODELS


def test_kume_bos_degil_ama_hicbir_yapilandirilmis_modeli_kapsamiyor() -> None:
    """Küme boşaltılırsa da haber verilir: ölü kod sessizce silinmiş olmasın."""
    assert _EXACT_QUOTA_TOKENIZER_MODELS, (
        "Küme boşaltılmış. Ölü dal bilinçli olarak kaldırıldıysa bu testi ve "
        "token_precharge.py'deki ölçüm aygıtını (manifest, ölçüm betiği, bekçi "
        "test) birlikte kaldır; yarısı kalırsa bir sonraki okuyucu var olmayan "
        "bir sözleşmeye güvenir."
    )
    yapilandirilmis = {DEFAULT_LLM_PRIMARY_MODEL, DEFAULT_LLM_FALLBACK_MODEL}
    assert not (_EXACT_QUOTA_TOKENIZER_MODELS & yapilandirilmis)
