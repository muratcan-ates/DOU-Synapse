"""Yerel değerlendirme demosu; kaynaklı JSON iskeleti, gerçek model kalitesi ölçümü değil."""

from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel

from app.core.errors import AppError
from app.core.provider_evidence import observe_provider_call
from app.schemas.assessment import OpenPayload


class GroundedSimulationForbidden(AppError):
    status_code = 503
    code = "grounded_simulation_forbidden"

    def __init__(self) -> None:
        super().__init__(
            "Kaynaklı demo değerlendirmesi yalnız yerel sahte sağlayıcıyla kullanılabilir."
        )


class LocalGradingFixture:
    """Açıkça seçilmiş fake istemcinin değerlendirme şemasını destekler."""

    def __init__(self, *, payload: BaseModel, sources: Sequence[tuple[UUID, str]]) -> None:
        self._payload = payload
        self._sources = list(sources)
        self.calls = 0

    async def complete(self, *, system: str, user: str) -> str:
        del system, user
        from app.modules.assessment.grading import literal_feedback_quote

        with observe_provider_call("fake", "fake/assessment-fixture-v1"):
            self.calls += 1
            readable = [(chunk_id, text) for chunk_id, text in self._sources if text.strip()]
            if not readable:
                return "{}"
            chunk_id, text = readable[0]
            # Sabit demo puanı bir anlam değerlendirmesi değildir. Kod puanını
            # çağıran oracle belirler ve aşağıdaki score/rubrik alanlarını okumaz.
            value: dict[str, object] = {
                "score": 0,
                "eksik_noktalar": [],
                "dayanak_chunk_id": str(chunk_id),
                "grounded_feedback": {
                    "chunk_id": str(chunk_id),
                    "quote": literal_feedback_quote(text),
                    "next_hint": (
                        "Yerel demo geri bildirimi: kaynak cümlesini yanıtınla karşılaştır; "
                        "farklı kalan adımı kendi cümlelerinle yeniden yaz."
                    ),
                },
            }
            if isinstance(self._payload, OpenPayload) and self._payload.rubric:
                value["rubrik"] = [
                    {"olcut": item.point, "puan": 0} for item in self._payload.rubric
                ]
            return json.dumps(value, ensure_ascii=False)
