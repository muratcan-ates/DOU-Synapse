"""Rol-ajanı sistem prompt'larının çevrimdışı token ölçümü (T-kota kanıtı).

Var oluş sebebi (P2 devir incelemesi): `_KNOWN_SYSTEM_PROMPT_TOKEN_CEILING = 1_024`
sabitinin tek kanıtı bir yorum satırıydı ve hash kümesi yenilenirken tavanın
yeniden ölçülmesini zorlayan hiçbir mekanizma yoktu — pay yalnız 3 token. Bu
betik ölçümü yeniden üretilebilir kılar ve sonucu bekçi testin okuduğu bir
manifest'e yazar: prompt metni değişince hash kümesi değişir, test manifest'le
uyuşmayan kümeyi KIRMIZI yakar ve tek doğal düzeltme bu betiği yeniden koşmaktır
— yani hash tazelemek, ölçümü tazelemeden mümkün değildir.

YALNIZ geliştirme zamanı çalışır: sabitlenmiş tokenizer'ı indirir (ağ!), bu
yüzden istek yolundan ve CI'nin zorunlu işlerinden çağrılMAZ. İstek yolu
tokenizer'sızdır ve `test_quota_token_ceiling_has_no_cold_start_network_dependency`
bunu ayrıca çiviler.

Kullanım (apps/api içinden):
    uv run python ../../scripts/measure_role_agent_prompt_tokens.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

TOKENIZER_REPO = "Xenova/llama-3-tokenizer"
TOKENIZER_REVISION = "72bff9ee09897a16b3b4b2b9995fecb0bfa7dbe6"
MANIFEST_PATH = (
    REPO_ROOT / "apps" / "api" / "tests" / "data" / "role_agent_prompt_token_manifest.json"
)


def enumerate_role_aware_variants() -> dict[str, str]:
    """Ajan yolundan erişilebilir sistem prompt varyantları (hash → metin).

    Sayım, bekçi testteki sayımın birebir aynısıdır: strict_retry dahil değildir
    çünkü rol-duyarlı HTTP yolu tek sağlayıcı denemesi yapar ve regeneration
    kapalıdır (service.py: schema_retry_limit=0, provider_attempt_limit=1).
    """
    from app.contracts import AssistantAudience, ChatMode, SocraticStage
    from app.modules.generation import prompts

    variants: dict[str, str] = {}
    for audience in AssistantAudience:
        for mode in (ChatMode.QA, ChatMode.SOCRATIC):
            stages: tuple[SocraticStage | None, ...] = (
                tuple(SocraticStage) if mode is ChatMode.SOCRATIC else (None,)
            )
            for stage in stages:
                for has_attempt in (False, True):
                    text = prompts.build_system_prompt(
                        mode,
                        audience=audience,
                        socratic_stage=stage,
                        has_student_attempt=has_attempt,
                    )
                    variants[hashlib.sha256(text.encode()).hexdigest()] = text
    return variants


def main() -> int:
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    tokenizer_file = hf_hub_download(
        TOKENIZER_REPO, "tokenizer.json", revision=TOKENIZER_REVISION
    )
    tokenizer = Tokenizer.from_file(tokenizer_file)

    variants = enumerate_role_aware_variants()
    measurements = {
        digest: len(tokenizer.encode(text).ids) for digest, text in variants.items()
    }

    manifest = {
        "tokenizer_repo": TOKENIZER_REPO,
        "tokenizer_revision": TOKENIZER_REVISION,
        "variant_count": len(measurements),
        "max_tokens": max(measurements.values()),
        "measurements": dict(sorted(measurements.items())),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"varyant: {len(measurements)} · max token: {manifest['max_tokens']}")
    print(f"manifest: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
