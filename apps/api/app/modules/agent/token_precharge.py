"""Kota ön-şarjı: incelenmiş prompt için yerel, muhafazakâr token tavanı.

`app/api/chat.py`'den taşındı (modülerizasyon v2, PR 11). Sayılar ve davranış
birebir aynı; bekçi test (`test_role_aware_agent_application_guards`) bu adları
`app.api.chat` üzerinden import etmeye devam eder — chat re-export eder.

The role-aware path deliberately allows exactly one provider attempt. The
first configured model is therefore the only tokenizer contract relevant to
its pre-charge. Current server-owned system prompt variants were measured
offline with Xenova/llama-3-tokenizer at immutable revision
72bff9ee09897a16b3b4b2b9995fecb0bfa7dbe6. The largest was 1,021 tokens, so
1,024 is a conservative content ceiling. Runtime code never loads a tokenizer
or reaches the network: a changed model or prompt hash retains the original
UTF-8 byte ceiling until its tokenizer contract is reviewed.
"""

from __future__ import annotations

import hashlib

from app.modules.generation import prompts as generation_prompts

_EXACT_QUOTA_TOKENIZER_MODELS = frozenset({"groq/llama-3.3-70b-versatile"})
_KNOWN_SYSTEM_PROMPT_TOKEN_CEILING = 1_024
_KNOWN_SYSTEM_PROMPT_SHA256S = frozenset(
    {
        "04e64389ae8ae9d4927b8f2fc08bc73e27cf8e3b7cdf23887503c3124b46a731",
        "12ecae0c278f1f02438c5b84eba3e83018bb7bd1add3edd613dce6401c4768a6",
        "14b6340cf745a30968e2eb25baa60f85583d665863655c38322e3fd9d1759f97",
        "214d26a24498f89b91b24f63646a797bf9eb2eb7ff94e0262aa5d75b39ef610c",
        "21d12ef9470f1b55891ed994bbaaaadd7edfd37c0558059ee29c8110af256257",
        "25b66d67cdff9aebe26583482aec942fc935c480fdeac0078c1a8975d95709cf",
        "2986e32d663a2f9ec2a2c2e3ed68f1f3fd01201c2e704968138b3ac2492a969a",
        "2cae2f0ea35773dd8328a0379cda1d08a401b451b8c7981e48303ca5e3b2a4ac",
        "6be3c39bc5e5eaf78d3e2560f9b320b1568906dad44a1fd5add6b5e44c746c78",
        "707d21b48855d4dbbd1862e4861a2a4ef716777a29b154f724df1a596ae7ccdd",
        "73d86031f7f38729c8398358e0f3ec98b0c8ec1076dae251c816918eb514c336",
        "8d23337fde9688a02a57d2a18c11cd19aebe88764c3f1bc8b98fb65d8dff2a15",
        "8dee1ff9e2dce744cfcdcb8d84d6087d1befd38c54bede20cdd46cd9a717a262",
        "94fedefe163b204aa91e0ff1ae292e3bf4bc178a15488fccc484962073ce9e6c",
        "99840996caa3914a1b0785eba08f31c80c39bd5dd08f681f4486532fd39e2f16",
        "a555d952d429d5d5daaa44a84292387f0bf6bd82b7e3b4999aae46528923f1fc",
        "af52efec0404fbc936536a9f2c7e8a89fd490dfce416fdd0f16553b51fb9c84a",
        "b23c5ef3d91c17b543a14f1cc534df1f143721db8315a1a171788b207e8137e8",
        "c7dd3e44c4c1dff02c01171294e1a867774fee9cbc982d99f93f1f0820323728",
        "cd197f265e9ed408618dd8af26d6966af6921b367a0f5ac171cae9afeef19af7",
        "e0b5e509112a3b26e3f77c754f6a54c6728287e8fc5042aeb19cfa865d2f47b6",
        "e6ff7afba2a8ec42ecd517c5f84694e9254b11a51b132f54b78550e1aacb501e",
        "f2b75ee449c0f2ebaf5e3b7b79c11c5d0c4c370224e43267b3d957714a9d3323",
        "f4073973c1302b9cbe6b06437005e54f5be79cc2b17a3a5b9739ff95975c49d0",
    }
)


def _quota_input_token_ceiling(
    request: generation_prompts.LlmRequest,
    *,
    model: str,
    byte_safe_ceiling: int,
) -> int:
    """Return a local, conservative token pre-charge for a reviewed prompt.

    Dynamic user content retains one reserved token per UTF-8 byte, which is a
    safe ceiling for the reviewed byte-level tokenizer. The known system prompt
    uses its offline-measured ceiling and the existing framing allowance stays
    intact. Unknown model/prompt combinations fail closed to the all-byte
    ceiling; no request-path tokenizer, file, or network dependency exists.
    """

    if model not in _EXACT_QUOTA_TOKENIZER_MODELS:
        return byte_safe_ceiling
    system_prompt_hash = hashlib.sha256(request.system.encode()).hexdigest()
    if system_prompt_hash not in _KNOWN_SYSTEM_PROMPT_SHA256S:
        return byte_safe_ceiling

    tokenizer_ceiling = (
        _KNOWN_SYSTEM_PROMPT_TOKEN_CEILING
        + len(request.user.encode())
        + generation_prompts.MESSAGE_FRAMING_TOKEN_CEILING
    )
    return min(byte_safe_ceiling, tokenizer_ceiling)
