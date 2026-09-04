"""Bounded HTTP evaluation session with opt-in, loopback-only runtime receipts."""

from __future__ import annotations

from typing import Any, Self
from uuid import uuid4

import httpx
from provenance import (
    EvidenceError,
    decode_receipt,
    require_loopback_url,
    response_evidence,
    validate_runtime,
)


class EvaluationStopped(RuntimeError):
    """Budget/quota/unavailable runtime: checkpoint and stop without retrying."""


class EvaluationClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        secret: str | None = None,
        run_id: str | None = None,
        candidate_sha: str | None = None,
        require_real: bool = False,
        max_requests: int = 30,
        timeout: float = 90.0,
    ) -> None:
        if not 1 <= max_requests <= 1000:
            raise EvidenceError("İstek bütçesi 1-1000 aralığında olmalı.")
        if secret:
            require_loopback_url(base_url)
        if require_real and not secret:
            raise EvidenceError("Gerçek koşu EVAL_RUNTIME_SECRET gerektirir.")
        self.base_url, self.token, self.secret = base_url.rstrip("/"), token, secret
        self.run_id = run_id or str(uuid4())
        self.candidate_sha, self.require_real = candidate_sha, require_real
        self.max_requests, self.timeout = max_requests, timeout
        self.requests = 0
        self.runtime: dict[str, Any] | None = None
        self.client: Any = None

    async def __aenter__(self) -> Self:
        headers = {"Authorization": f"Bearer {self.token}"}
        if self.secret:
            headers |= {
                "X-Eval-Runtime-Secret": self.secret,
                "X-Eval-Run-Id": self.run_id,
            }
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
            follow_redirects=False,
            trust_env=False,
        )
        if self.secret:
            try:
                response = await self.client.get(
                    "/internal/evaluation/runtime", params={"run_id": self.run_id}
                )
                response.raise_for_status()
                self.runtime = response.json()
                validate_runtime(self.runtime, run_id=self.run_id, candidate_sha=self.candidate_sha)
            except (httpx.HTTPError, ValueError):
                await self.client.aclose()
                self.client = None
                raise EvidenceError(
                    "Sunucunun gerçek değerlendirme çalışma kanıtı doğrulanamadı."
                ) from None
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self.client is not None:
            await self.client.aclose()

    async def post(self, path: str, *, json: Any) -> Any:
        if self.requests >= self.max_requests:
            raise EvaluationStopped(
                "HTTP istek bütçesi doldu; kayıtlı sonuçlarla devam edilebilir."
            )
        self.requests += 1
        try:
            response = await self.client.post(path, json=json)
        except httpx.HTTPError:
            raise EvaluationStopped(
                "API erişimi tamamlanamadı; yeniden denemeden duruldu."
            ) from None
        if response.status_code == 429 or response.status_code >= 500:
            raise EvaluationStopped(
                f"API {response.status_code}: kota/erişim nedeniyle koşu durdu."
            )
        return response

    def evidence(self, response: Any) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            body = None
        request = None
        if self.secret:
            import json

            fields = json.loads(response.request.content)
            parts = response.request.url.path.split("/")
            request = {
                "course_id": parts[parts.index("courses") + 1],
                "question": fields.get("question"),
                "mode": fields.get("mode", "qa"),
                "session_id": fields.get("session_id"),
                "student_attempt": fields.get("student_attempt"),
            }
        evidence = response_evidence(
            self.runtime, decode_receipt(response.headers.get("X-Eval-Receipt")), body, request
        )
        if (
            self.require_real
            and response.status_code == 200
            and evidence["classification"] in {"unknown", "fake"}
        ):
            raise EvaluationStopped("Yanıtın gerçek sunucu kanıtı doğrulanamadı.")
        return evidence
