"""Fail-closed staging readiness preflight.

This command gathers evidence.  It does not deploy, promote, or claim that a
staging environment is verified.  Secrets are read only from the environment
and are never intentionally copied into a report or command-line argument.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import UUID

from validate_evidence import EvidenceValidationError, validate_document

Status = Literal["passed", "failed", "blocked", "not_run"]
Overall = Literal["passed", "failed", "blocked"]

CLAIM_BOUNDARY = (
    "Bu kayıt promotion kanıtı ya da doğrulanmış staging iddiası değildir."
)
REQUIRED_SECRET_NAMES = (
    "STAGING_SMOKE_JWT",
    "DATABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
)
SECRET_ENV_NAMES = REQUIRED_SECRET_NAMES + ("STAGING_SMOKE_QUESTION",)
DEFAULT_SMOKE_QUESTION = "Ders kaynağındaki temel kavramı atıflarıyla açıkla."
IMAGE_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
MIGRATION_PATTERN = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str


@dataclass(frozen=True)
class HttpResponse:
    status: int
    payload: Any


@dataclass(frozen=True)
class MigrationFile:
    version: str
    name: str
    sha256: str


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    summary: str
    safe_details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "safe_details": dict(self.safe_details),
        }


@dataclass(frozen=True)
class PreflightReport:
    generated_at: str
    source_sha: str | None
    image_digest: str | None
    overall: Overall
    checks: tuple[CheckResult, ...]
    unrun: tuple[str, ...]

    def by_name(self, name: str) -> CheckResult:
        return next(check for check in self.checks if check.name == name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": "staging_preflight",
            "generated_at": self.generated_at,
            "source_sha": self.source_sha,
            "image_digest": self.image_digest,
            "overall": self.overall,
            "checks": [check.to_dict() for check in self.checks],
            "unrun": list(self.unrun),
            "claim_boundary": CLAIM_BOUNDARY,
        }


@dataclass(frozen=True)
class PreflightOptions:
    candidate: Path
    api_url: str
    web_url: str
    course_id: str
    migration_decision: Literal["none", "expand", "contract", "blocked"]
    backup_evidence_ref: str
    rollback_evidence_ref: str
    previous_digest: str
    timeout: float = 10.0


HttpClient = Callable[..., HttpResponse]
CommandRunner = Callable[..., CommandResult]


def _passed(name: str, summary: str, **details: Any) -> CheckResult:
    return CheckResult(name, "passed", summary, details)


def _failed(name: str, summary: str, **details: Any) -> CheckResult:
    return CheckResult(name, "failed", summary, details)


def _blocked(name: str, summary: str, **details: Any) -> CheckResult:
    return CheckResult(name, "blocked", summary, details)


def _not_run(name: str, summary: str) -> CheckResult:
    return CheckResult(name, "not_run", summary)


def _overall(checks: Iterable[CheckResult]) -> Overall:
    statuses = {check.status for check in checks}
    if "failed" in statuses:
        return "failed"
    if statuses & {"blocked", "not_run"}:
        return "blocked"
    return "passed"


def _utc_iso(now: datetime) -> str:
    aware = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")


def migration_inventory(repo_root: Path) -> tuple[MigrationFile, ...]:
    migrations_dir = repo_root / "supabase" / "migrations"
    records: list[MigrationFile] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        match = MIGRATION_PATTERN.fullmatch(path.name)
        if match is None:
            raise ValueError(f"Geçersiz migration dosya adı: {path.name}")
        records.append(
            MigrationFile(
                version=match.group(1),
                name=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    expected = [f"{index:04d}" for index in range(1, len(records) + 1)]
    actual = [record.version for record in records]
    if not records or actual != expected:
        raise ValueError("Migration sürümleri 0001'den başlayan ardışık bir seri olmalı.")
    return tuple(records)


def _manifest_digest(records: Iterable[MigrationFile]) -> str:
    payload = "\n".join(
        f"{record.version} {record.name} {record.sha256}" for record in records
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_base_url(raw: str) -> str:
    parts = urlsplit(raw.strip())
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("URL kullanıcı bilgisi, query veya fragment içeremez.")
    host = (parts.hostname or "").lower()
    local = host in {"localhost", "127.0.0.1", "::1"}
    if parts.scheme != "https" and not (parts.scheme == "http" and local):
        raise ValueError("Canlı URL HTTPS olmalı; yalnız localhost HTTP kullanabilir.")
    if not parts.netloc:
        raise ValueError("URL host içermeli.")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def _safe_reference(raw: str) -> dict[str, str] | None:
    value = raw.strip()
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme in {"http", "https"}:
        if parts.username or parts.password or not parts.netloc:
            return None
        normalized = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        return {
            "kind": "url",
            "reference_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        }
    path = Path(value).expanduser()
    if not path.is_file() or path.stat().st_size == 0:
        return None
    return {
        "kind": "file",
        "reference_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _load_candidate(
    path: Path, repo_root: Path
) -> tuple[CheckResult, dict[str, Any] | None]:
    try:
        schema = json.loads(
            (repo_root / ".release" / "evidence.schema.json").read_text(
                encoding="utf-8"
            )
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        validate_document(document, schema)
        if document.get("record_type") != "candidate":
            return _failed("candidate", "Kayıt candidate türünde değil."), None
        source_sha = document.get("source", {}).get("sha")
        image_digest = document.get("image", {}).get("digest")
        if not isinstance(source_sha, str) or not isinstance(image_digest, str):
            return _failed("candidate", "Candidate kaynak kimliği eksik."), None
    except (OSError, json.JSONDecodeError, EvidenceValidationError, TypeError):
        return _failed("candidate", "Candidate sözleşmesi doğrulanamadı."), None
    return (
        _passed(
            "candidate",
            "Candidate sözleşmesi doğrulandı.",
            record_type="candidate",
        ),
        document,
    )


def _source_check(
    document: dict[str, Any] | None, run_command: CommandRunner
) -> tuple[CheckResult, str | None, str | None]:
    if document is None:
        return (
            _not_run("source_main", "Geçerli candidate olmadan kaynak bağı kurulmadı."),
            None,
            None,
        )
    candidate_sha = str(document["source"]["sha"])
    image_digest = str(document["image"]["digest"])
    try:
        checkout = run_command(["git", "rev-parse", "HEAD"], env=None)
        remote = run_command(
            ["git", "ls-remote", "origin", "refs/heads/main"], env=None
        )
    except (OSError, subprocess.SubprocessError):
        return (
            _failed("source_main", "Git kaynak kimliği okunamadı."),
            candidate_sha,
            image_digest,
        )
    checkout_sha = checkout.stdout.strip() if checkout.returncode == 0 else ""
    remote_sha = remote.stdout.split(maxsplit=1)[0] if remote.returncode == 0 else ""
    if not (checkout_sha == remote_sha == candidate_sha):
        return (
            _failed(
                "source_main",
                "Candidate, checkout ve origin/main aynı SHA değil.",
                checkout_matches=checkout_sha == candidate_sha,
                remote_matches=remote_sha == candidate_sha,
            ),
            candidate_sha,
            image_digest,
        )
    return (
        _passed(
            "source_main",
            "Candidate exact current-main kaynağına bağlı.",
            exact_match=True,
        ),
        candidate_sha,
        image_digest,
    )


def _http_check(
    name: str,
    http: HttpClient,
    method: str,
    url: str,
    *,
    timeout: float,
    headers: Mapping[str, str] | None = None,
    payload: object | None = None,
) -> HttpResponse | CheckResult:
    try:
        return http(
            method,
            url,
            headers=headers,
            payload=payload,
            timeout=timeout,
        )
    except (OSError, TimeoutError, ValueError) as exc:
        return _failed(
            name,
            "Canlı kontrol tamamlanamadı.",
            error_type=type(exc).__name__,
        )


def _psql_environment(database_url: str, base: Mapping[str, str]) -> dict[str, str]:
    normalized = re.sub(r"^postgresql\+[^:]+://", "postgresql://", database_url)
    parts = urlsplit(normalized)
    if parts.scheme not in {"postgres", "postgresql"} or not parts.hostname:
        raise ValueError("DATABASE_URL PostgreSQL adresi olmalı.")
    result = dict(base)
    result.update(
        {
            "PGHOST": parts.hostname,
            "PGPORT": str(parts.port or 5432),
            "PGDATABASE": unquote(parts.path.lstrip("/")),
            "PGUSER": unquote(parts.username or ""),
            "PGPASSWORD": unquote(parts.password or ""),
            "PGCONNECT_TIMEOUT": "10",
        }
    )
    return result


def _migration_check(
    options: PreflightOptions,
    env: Mapping[str, str],
    repo_root: Path,
    run_command: CommandRunner,
) -> CheckResult:
    if options.migration_decision == "blocked":
        return _blocked("migrations", "Migration kararı açıkça blocked.")
    database_url = env.get("DATABASE_URL", "").strip()
    if not database_url:
        return _blocked("migrations", "DATABASE_URL yapılandırılmamış.")
    try:
        local = migration_inventory(repo_root)
        command_env = _psql_environment(database_url, env)
        result = run_command(
            [
                "psql",
                "--no-psqlrc",
                "--tuples-only",
                "--no-align",
                "--set",
                "ON_ERROR_STOP=1",
                "--command",
                "SELECT version FROM supabase_migrations.schema_migrations ORDER BY version;",
            ],
            env=command_env,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return _failed("migrations", "Migration ledger kontrolü çalıştırılamadı.")
    if result.returncode != 0:
        return _failed("migrations", "Uzak migration ledger okunamadı.")
    remote = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    local_versions = [record.version for record in local]
    if remote != local_versions:
        return _failed(
            "migrations",
            "Yerel migration envanteri uzak ledger ile tam eşleşmiyor.",
            local_count=len(local_versions),
            remote_count=len(remote),
            decision=options.migration_decision,
        )
    return _passed(
        "migrations",
        "Migration ledger yerel envanterle tam eşleşiyor.",
        count=len(local_versions),
        decision=options.migration_decision,
        manifest_sha256=_manifest_digest(local),
    )


def _recovery_check(options: PreflightOptions, image_digest: str | None) -> CheckResult:
    backup = _safe_reference(options.backup_evidence_ref)
    rollback = _safe_reference(options.rollback_evidence_ref)
    previous = options.previous_digest.strip()
    if backup is None or rollback is None:
        return _blocked(
            "recovery_evidence",
            "Backup veya rollback kanıt referansı eksik/geçersiz.",
            backup_configured=backup is not None,
            rollback_configured=rollback is not None,
        )
    if not IMAGE_DIGEST_PATTERN.fullmatch(previous) or previous == image_digest:
        return _blocked(
            "recovery_evidence",
            "Önceki immutable digest eksik, geçersiz veya candidate ile aynı.",
        )
    return _passed(
        "recovery_evidence",
        "Recovery referansları mevcut; içeriği promotion kapısında ayrıca incelenmeli.",
        backup=backup,
        rollback=rollback,
        previous_digest_configured=True,
    )


def run_preflight(
    options: PreflightOptions,
    *,
    env: Mapping[str, str],
    repo_root: Path,
    http: HttpClient,
    run_command: CommandRunner,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PreflightReport:
    checks: list[CheckResult] = []
    candidate_check, document = _load_candidate(options.candidate, repo_root)
    checks.append(candidate_check)
    source_check, source_sha, image_digest = _source_check(document, run_command)
    checks.append(source_check)

    try:
        api_url = _safe_base_url(options.api_url)
        web_url = _safe_base_url(options.web_url)
        UUID(options.course_id)
        checks.append(_passed("inputs", "Staging hedefleri ve ders kimliği geçerli."))
    except ValueError:
        checks.append(_failed("inputs", "Staging URL veya ders kimliği geçersiz."))
        api_url = ""
        web_url = ""

    if web_url:
        response = _http_check(
            "web", http, "GET", web_url, timeout=options.timeout
        )
        if isinstance(response, CheckResult):
            checks.append(response)
        elif response.status == 200:
            checks.append(_passed("web", "Staging web yüzeyi erişilebilir."))
        else:
            checks.append(_failed("web", "Staging web yüzeyi 200 dönmedi.", status=response.status))
    else:
        checks.append(_not_run("web", "Geçerli web URL olmadan kontrol çalışmadı."))

    if api_url:
        live = _http_check(
            "liveness",
            http,
            "GET",
            f"{api_url}/health/live",
            timeout=options.timeout,
        )
        if isinstance(live, CheckResult):
            checks.append(live)
        elif live.status == 200 and isinstance(live.payload, dict) and live.payload.get(
            "status"
        ) == "ok" and live.payload.get("environment") == "production":
            checks.append(_passed("liveness", "API production guard ile ayakta."))
        else:
            checks.append(
                _failed("liveness", "Liveness production sözleşmesini geçmedi.", status=live.status)
            )

        ready = _http_check(
            "readiness",
            http,
            "GET",
            f"{api_url}/health/ready",
            timeout=options.timeout,
        )
        ready_payload = ready.payload if isinstance(ready, HttpResponse) else None
        ready_checks = ready_payload.get("checks", {}) if isinstance(ready_payload, dict) else {}
        if isinstance(ready, CheckResult):
            checks.append(ready)
        elif (
            ready.status == 200
            and ready_payload.get("status") == "ok"
            and ready_checks.get("database") == "ok"
            and ready_checks.get("pgvector") == "ok"
            and ready_checks.get("embedding") in {"ready", "disabled"}
        ):
            checks.append(
                _passed(
                    "readiness",
                    "Database, pgvector ve embedding hazır.",
                    embedding=ready_checks.get("embedding"),
                )
            )
        else:
            checks.append(
                _failed(
                    "readiness",
                    "Readiness bağımlılıkları hazır değil.",
                    status=ready.status,
                )
            )
    else:
        checks.extend(
            [
                _not_run("liveness", "Geçerli API URL olmadan kontrol çalışmadı."),
                _not_run("readiness", "Geçerli API URL olmadan kontrol çalışmadı."),
            ]
        )

    jwt = env.get("STAGING_SMOKE_JWT", "").strip()
    auth_headers = {"Authorization": f"Bearer {jwt}"} if jwt else None
    if api_url and jwt:
        anonymous = _http_check(
            "auth",
            http,
            "GET",
            f"{api_url}/courses",
            timeout=options.timeout,
        )
        dev = _http_check(
            "auth",
            http,
            "GET",
            f"{api_url}/courses",
            headers={"Authorization": "Bearer dev:00000000-0000-0000-0000-000000000001"},
            timeout=options.timeout,
        )
        real = _http_check(
            "auth",
            http,
            "GET",
            f"{api_url}/courses",
            headers=auth_headers,
            timeout=options.timeout,
        )
        if any(isinstance(item, CheckResult) for item in (anonymous, dev, real)):
            checks.append(_failed("auth", "Kimlik kontrol çağrılarından biri tamamlanamadı."))
        elif (
            anonymous.status in {401, 403}
            and dev.status in {401, 403}
            and real.status == 200
        ):
            checks.append(
                _passed(
                    "auth",
                    "Anonim/dev kimliği reddedildi, staging JWT kabul edildi.",
                )
            )
        else:
            checks.append(
                _failed(
                    "auth",
                    "Kimlik sınırı beklenen fail-closed davranışı göstermedi.",
                    anonymous_status=anonymous.status,
                    dev_status=dev.status,
                    real_status=real.status,
                )
            )
    elif not jwt:
        checks.append(_blocked("auth", "STAGING_SMOKE_JWT yapılandırılmamış."))
    else:
        checks.append(_not_run("auth", "Geçerli API URL olmadan auth çalışmadı."))

    supabase_url = env.get("SUPABASE_URL", "").strip()
    service_key = env.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    bucket = env.get("SUPABASE_STORAGE_BUCKET", "course-materials").strip()
    if supabase_url and service_key and bucket:
        try:
            storage_base = _safe_base_url(supabase_url)
        except ValueError:
            checks.append(_failed("storage", "SUPABASE_URL geçersiz."))
        else:
            storage = _http_check(
                "storage",
                http,
                "GET",
                f"{storage_base}/storage/v1/bucket/{bucket}",
                headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
                timeout=options.timeout,
            )
            if isinstance(storage, CheckResult):
                checks.append(storage)
            elif (
                storage.status == 200
                and isinstance(storage.payload, dict)
                and storage.payload.get("public") is False
            ):
                checks.append(
                    _passed(
                        "storage",
                        "Supabase bucket mevcut ve private.",
                        bucket=bucket,
                        public=False,
                    )
                )
            else:
                checks.append(
                    _failed(
                        "storage",
                        "Storage bucket private olarak doğrulanamadı.",
                        status=storage.status,
                    )
                )
    else:
        checks.append(_blocked("storage", "Supabase storage yapılandırması eksik."))

    checks.append(_migration_check(options, env, repo_root, run_command))

    if api_url and jwt:
        availability = _http_check(
            "availability",
            http,
            "GET",
            f"{api_url}/courses/{options.course_id}/chat/availability",
            headers=auth_headers,
            timeout=options.timeout,
        )
        if isinstance(availability, CheckResult):
            checks.append(availability)
        elif (
            availability.status == 200
            and isinstance(availability.payload, dict)
            and availability.payload.get("available") is True
            and availability.payload.get("reason") is None
        ):
            checks.append(
                _passed(
                    "availability",
                    "Course agent staging smoke için açık.",
                    allowed_modes=availability.payload.get("allowed_modes", []),
                )
            )
        else:
            checks.append(
                _failed(
                    "availability",
                    "Course agent staging smoke için açık değil.",
                    status=availability.status,
                    reason=(
                        availability.payload.get("reason")
                        if isinstance(availability.payload, dict)
                        else None
                    ),
                )
            )

        question = env.get("STAGING_SMOKE_QUESTION", DEFAULT_SMOKE_QUESTION).strip()
        llm = _http_check(
            "real_provider_smoke",
            http,
            "POST",
            f"{api_url}/courses/{options.course_id}/chat",
            headers={**(auth_headers or {}), "Content-Type": "application/json"},
            payload={"question": question, "mode": "qa"},
            timeout=options.timeout,
        )
        if isinstance(llm, CheckResult):
            checks.append(llm)
        elif (
            llm.status == 200
            and isinstance(llm.payload, dict)
            and llm.payload.get("status") == "answered"
            and llm.payload.get("cached") is False
            and isinstance(llm.payload.get("citations"), list)
            and len(llm.payload["citations"]) > 0
        ):
            checks.append(
                _passed(
                    "real_provider_smoke",
                    "Cache dışı ve atıflı provider yanıtı gözlendi.",
                    citation_count=len(llm.payload["citations"]),
                    cached=False,
                )
            )
        else:
            checks.append(
                _failed(
                    "real_provider_smoke",
                    "Cache dışı atıflı provider yanıtı doğrulanamadı.",
                    status=llm.status,
                )
            )
    elif not jwt:
        checks.extend(
            [
                _blocked("availability", "STAGING_SMOKE_JWT yapılandırılmamış."),
                _blocked("real_provider_smoke", "STAGING_SMOKE_JWT yapılandırılmamış."),
            ]
        )
    else:
        checks.extend(
            [
                _not_run("availability", "Geçerli API URL olmadan kontrol çalışmadı."),
                _not_run("real_provider_smoke", "Geçerli API URL olmadan kontrol çalışmadı."),
            ]
        )

    checks.append(_recovery_check(options, image_digest))
    overall = _overall(checks)
    unrun = tuple(check.name for check in checks if check.status == "not_run")
    return PreflightReport(
        generated_at=_utc_iso(now()),
        source_sha=source_sha,
        image_digest=image_digest,
        overall=overall,
        checks=tuple(checks),
        unrun=unrun,
    )


def _scrub(value: Any, secrets: Iterable[str]) -> Any:
    secret_values = sorted(
        {secret for secret in secrets if isinstance(secret, str) and len(secret) >= 4},
        key=len,
        reverse=True,
    )
    if isinstance(value, str):
        result = value
        for secret in secret_values:
            result = result.replace(secret, "[REDACTED]")
        return result
    if isinstance(value, list):
        return [_scrub(item, secret_values) for item in value]
    if isinstance(value, tuple):
        return [_scrub(item, secret_values) for item in value]
    if isinstance(value, dict):
        return {key: _scrub(item, secret_values) for key, item in value.items()}
    return value


def _markdown(document: Mapping[str, Any]) -> str:
    lines = [
        "# Staging preflight",
        "",
        f"- Genel durum: `{document['overall']}`",
        f"- Kaynak SHA: `{document.get('source_sha') or 'yok'}`",
        f"- Image digest: `{document.get('image_digest') or 'yok'}`",
        "",
        "| Kontrol | Durum | Özet |",
        "|---|---|---|",
    ]
    for check in document["checks"]:
        summary = str(check["summary"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{check['name']}` | `{check['status']}` | {summary} |")
    lines.extend(["", str(document["claim_boundary"]), ""])
    return "\n".join(lines)


def write_report(
    report: PreflightReport,
    *,
    json_out: Path,
    markdown_out: Path,
    secrets: Iterable[str],
) -> None:
    document = _scrub(report.to_dict(), secrets)
    json_text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    markdown_text = _markdown(document)
    for path in (json_out, markdown_out):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json_text, encoding="utf-8")
    markdown_out.write_text(markdown_text, encoding="utf-8")


def exit_code(report: PreflightReport) -> int:
    if report.overall == "passed":
        return 0
    if report.overall == "failed":
        return 1
    return 2


def _real_http(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    payload: object | None = None,
    timeout: float = 10,
) -> HttpResponse:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=dict(headers or {}), method=method)
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as exc:
        response = exc
    raw = response.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("HTTP yanıtı güvenli boyut sınırını aştı.")
    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = None
    return HttpResponse(int(response.status), parsed)


def _real_runner(
    command: list[str], *, env: Mapping[str, str] | None = None
) -> CommandResult:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=dict(env) if env is not None else None,
        timeout=30,
    )
    return CommandResult(completed.returncode, completed.stdout)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed DOU-Synapse staging preflight"
    )
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--web-url", required=True)
    parser.add_argument("--course-id", required=True)
    parser.add_argument(
        "--migration-decision",
        choices=("none", "expand", "contract", "blocked"),
        required=True,
    )
    parser.add_argument("--backup-evidence-ref", required=True)
    parser.add_argument("--rollback-evidence-ref", required=True)
    parser.add_argument("--previous-digest", required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    options = PreflightOptions(
        candidate=args.candidate,
        api_url=args.api_url,
        web_url=args.web_url,
        course_id=args.course_id,
        migration_decision=args.migration_decision,
        backup_evidence_ref=args.backup_evidence_ref,
        rollback_evidence_ref=args.rollback_evidence_ref,
        previous_digest=args.previous_digest,
        timeout=args.timeout,
    )
    environment = dict(os.environ)
    repo_root = Path(__file__).resolve().parents[1]
    report = run_preflight(
        options,
        env=environment,
        repo_root=repo_root,
        http=_real_http,
        run_command=_real_runner,
    )
    write_report(
        report,
        json_out=args.json_out,
        markdown_out=args.markdown_out,
        secrets=(environment.get(name, "") for name in SECRET_ENV_NAMES),
    )
    code = exit_code(report)
    print(f"STAGING_PREFLIGHT={report.overall.upper()}")
    print(f"STAGING_PREFLIGHT_JSON={args.json_out}")
    print(f"STAGING_PREFLIGHT_MARKDOWN={args.markdown_out}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
