"""Yalnız GitHub işinin kendi yeni PostgreSQL servisinde sentetik E2E kurulumu.

Güven kökü çağıranın job.services.postgres.id değeridir. Kimliği keşfetmek,
mevcut bir yerel kümeyi sahiplenme yetkisi vermez. DROP/kill veya rol genişletme
SQL'i eklenmez; mevcut göçler ve yerel sentetik kurulum dosyası aynen uygulanır.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

IMAGE = (
    "pgvector/pgvector:0.8.6-pg16-bookworm@"
    "sha256:a36250871de0833b8757561c72f2477ef1ddd1101afa4e617fb552e0de514c6b"
)
REPO_DIGEST = "pgvector/pgvector@" + IMAGE.split("@", 1)[1]
BOOTSTRAP_SHA = "6a50858baac0137b2c403435e9372d8bb66bc1ad24950d9a78d38c48511cef16"
DATABASE = "dou_synapse"
HEX = re.compile(r"[0-9a-f]{64}\Z")
RUN = re.compile(r"[a-z0-9]{6,20}\Z")
MIGRATION = re.compile(r"([0-9]{4})_[a-z0-9_]+\.sql\Z")
CREATE = "CREATE DATABASE dou_synapse TEMPLATE template0"
INSPECT = (
    '{"id":{{json .Id}},"imageReference":{{json .Config.Image}},'
    '"imageId":{{json .Image}},"running":{{json .State.Running}},'
    '"ports":{{json .NetworkSettings.Ports}},'
    '"networks":{{json .NetworkSettings.Networks}}}'
)
IMAGE_INSPECT = '{"id":{{json .Id}},"repoDigests":{{json .RepoDigests}}}'
IDENTITY = """
SELECT jsonb_build_object(
 'database', current_database(), 'oid', d.oid::text,
 'cluster', c.system_identifier::text,
 'version', current_setting('server_version_num')::integer,
 'serverAddress', host(inet_server_addr()), 'serverPort', inet_server_port(),
 'currentUser', current_user, 'sessionUser', session_user,
 'superuser', r.rolsuper, 'recovery', pg_is_in_recovery())
FROM pg_catalog.pg_database d CROSS JOIN pg_catalog.pg_control_system() c
JOIN pg_catalog.pg_roles r ON r.rolname=current_user
WHERE d.datname=current_database()
"""
INVENTORY = """
SELECT jsonb_build_object(
 'databases', (SELECT jsonb_agg(datname ORDER BY datname) FROM pg_catalog.pg_database),
 'roles', (SELECT jsonb_agg(rolname ORDER BY rolname) FROM pg_catalog.pg_roles
           WHERE left(rolname, 3) <> 'pg_'))
"""
ROLES = """
SELECT jsonb_agg(jsonb_build_array(rolname, rolcanlogin, rolsuper, rolbypassrls,
 rolcreatedb, rolcreaterole, rolreplication) ORDER BY rolname)
FROM pg_catalog.pg_roles WHERE left(rolname, 3) <> 'pg_' AND rolname <> 'postgres'
"""
MEMBERSHIPS = """
SELECT count(*)::integer FROM pg_catalog.pg_auth_members m
JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
JOIN pg_catalog.pg_roles member ON member.oid=m.member
WHERE granted.rolname IN ('dou_app','dou_worker','dou_auth_bridge')
   OR member.rolname IN ('dou_app','dou_worker','dou_auth_bridge')
"""
SUMMARY = """
SELECT jsonb_build_object(
 'vector', (SELECT extversion FROM pg_catalog.pg_extension WHERE extname='vector'),
 'profiles', (SELECT count(*) FROM public.profiles),
 'admins', (SELECT count(*) FROM public.platform_admins),
 'auditRows', (SELECT count(*) FROM public.platform_admin_access_audit))
"""
ROLE_IDENTITY = """
SELECT jsonb_build_object(
 'database', current_database(), 'oid', d.oid::text,
 'serverAddress', host(inet_server_addr()), 'serverPort', inet_server_port(),
 'version', current_setting('server_version_num')::integer,
 'currentUser', current_user, 'sessionUser', session_user,
 'superuser', r.rolsuper, 'bypassRls', r.rolbypassrls,
 'createDb', r.rolcreatedb, 'createRole', r.rolcreaterole,
 'replication', r.rolreplication)
FROM pg_catalog.pg_database d JOIN pg_catalog.pg_roles r ON r.rolname=current_user
WHERE d.datname=current_database()
"""


class Refusal(Exception):
    """Çıktıya yalnız sabit kod taşır."""


def require(value: bool, code: str) -> None:
    if not value:
        raise Refusal(code)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def private_write(path: Path, value: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(value)


def validate_context(args: argparse.Namespace, env: dict[str, str]) -> None:
    require(
        env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_JOB") == "e2e",
        "GITHUB_E2E_JOB_REQUIRED",
    )
    require(bool(HEX.fullmatch(args.container_id)), "FULL_SERVICE_CONTAINER_ID_REQUIRED")
    require(bool(RUN.fullmatch(args.run_id)), "RUN_ID")
    require(type(args.port) is int and 0 < args.port < 65536, "HOST_PORT")
    require(type(args.api_port) is int and 0 < args.api_port < 65536, "API_PORT")
    require(
        args.output.is_absolute()
        and args.output.resolve() == args.output
        and args.output.parent.is_dir()
        and not args.output.exists()
        and not args.output.is_symlink(),
        "NEW_PRIVATE_OUTPUT_REQUIRED",
    )
    require(args.repo.is_absolute() and args.repo.resolve() == args.repo, "REPO_PATH")
    require(
        bool(re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ID", "")))
        and bool(re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ATTEMPT", ""))),
        "GITHUB_RUN_IDENTITY",
    )


def validate_container(raw: Any, image: Any, expected_id: str, host_port: int) -> dict[str, Any]:
    require(
        type(raw) is dict
        and set(raw)
        == {
            "id",
            "imageReference",
            "imageId",
            "running",
            "ports",
            "networks",
        },
        "CONTAINER_INSPECT_SCHEMA",
    )
    require(raw["id"] == expected_id and raw["running"] is True, "CONTAINER_IDENTITY")
    require(raw["imageReference"] == IMAGE, "SERVICE_IMAGE_REFERENCE")
    require(
        type(raw["imageId"]) is str
        and raw["imageId"].startswith("sha256:")
        and bool(HEX.fullmatch(raw["imageId"][7:])),
        "SERVICE_IMAGE_ID",
    )
    require(
        type(image) is dict
        and set(image) == {"id", "repoDigests"}
        and image["id"] == raw["imageId"]
        and type(image["repoDigests"]) is list
        and REPO_DIGEST in image["repoDigests"],
        "IMMUTABLE_IMAGE_DIGEST",
    )
    require(type(raw["ports"]) is dict and set(raw["ports"]) == {"5432/tcp"}, "SERVICE_PORTS")
    bindings = raw["ports"]["5432/tcp"]
    require(type(bindings) is list and 1 <= len(bindings) <= 2, "SERVICE_PORT_BINDINGS")
    seen = set()
    for binding in bindings:
        require(type(binding) is dict and set(binding) == {"HostIp", "HostPort"}, "PORT_SCHEMA")
        require(
            binding["HostIp"] in {"127.0.0.1", "0.0.0.0", "::"}  # noqa: S104 — yalnız inspect verisi.
            and binding["HostPort"] == str(host_port),
            "PORT_ROUTE_MISMATCH",
        )
        require(binding["HostIp"] not in seen, "DUPLICATE_PORT_BINDING")
        seen.add(binding["HostIp"])
    require(bool(seen & {"127.0.0.1", "0.0.0.0"}), "IPV4_ROUTE_REQUIRED")  # noqa: S104
    require(type(raw["networks"]) is dict and len(raw["networks"]) == 1, "ONE_SERVICE_NETWORK")
    network = next(iter(raw["networks"].values()))
    require(type(network) is dict and type(network.get("IPAddress")) is str, "NETWORK_ADDRESS")
    try:
        address = ipaddress.IPv4Address(network["IPAddress"])
    except ipaddress.AddressValueError as error:
        raise Refusal("NUMERIC_SERVICE_IPV4_REQUIRED") from error
    require(
        str(address) == network["IPAddress"]
        and address.is_private
        and not (
            address.is_loopback
            or address.is_link_local
            or address.is_unspecified
            or address.is_multicast
            or address.is_reserved
        ),
        "PRIVATE_BRIDGE_IPV4_REQUIRED",
    )
    return {
        "id": expected_id,
        "imageReference": IMAGE,
        "imageId": image["id"],
        "repoDigest": REPO_DIGEST,
        "serverAddress": str(address),
        "serverPort": 5432,
        "host": "127.0.0.1",
        "hostPort": host_port,
    }


def validate_identity(
    actual: Any, target: dict[str, Any], database: str, previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    require(
        type(actual) is dict
        and set(actual)
        == {
            "database",
            "oid",
            "cluster",
            "version",
            "serverAddress",
            "serverPort",
            "currentUser",
            "sessionUser",
            "superuser",
            "recovery",
        },
        "POSTGRES_IDENTITY_SCHEMA",
    )
    require(
        actual["database"] == database
        and actual["currentUser"] == "postgres"
        and actual["sessionUser"] == "postgres"
        and actual["superuser"] is True
        and actual["recovery"] is False,
        "POSTGRES_PRIVILEGED_IDENTITY",
    )
    require(
        actual["serverAddress"] == target["serverAddress"]
        and type(actual["serverPort"]) is int
        and actual["serverPort"] == 5432,
        "POSTGRES_SERVER_ROUTE",
    )
    require(
        type(actual["version"]) is int and 160000 <= actual["version"] < 170000,
        "POSTGRES_16_REQUIRED",
    )
    require(
        all(
            type(actual[key]) is str and bool(re.fullmatch(r"[1-9][0-9]*", actual[key]))
            for key in ("oid", "cluster")
        ),
        "POSTGRES_NUMERIC_IDENTITY",
    )
    if previous is not None:
        require(actual == previous, "CONTAINER_HOST_IDENTITY_MISMATCH")
    return actual


def require_fresh(inventory: Any) -> None:
    require(
        inventory == {"databases": ["postgres", "template0", "template1"], "roles": ["postgres"]},
        "FRESH_SERVICE_REQUIRED",
    )


def expected_roles(login: bool) -> list[list[Any]]:
    return [
        ["dou_app", login, False, False, False, False, False],
        ["dou_auth_bridge", False, False, True, False, False, False],
        ["dou_worker", login, False, True, False, False, False],
    ]


def read_sql(repo: Path) -> dict[str, bytes]:
    migrations = sorted((repo / "supabase/migrations").glob("*.sql"))
    require(bool(migrations), "MIGRATIONS_MISSING")
    numbers = []
    for path in migrations:
        match = MIGRATION.fullmatch(path.name)
        require(match is not None, "MIGRATION_FILENAME")
        numbers.append(match.group(1))
    require(len(set(numbers)) == len(numbers), "DUPLICATE_MIGRATION_NUMBER")
    paths = [*migrations, repo / "supabase/local_dev_setup.sql", repo / "supabase/seed_demo.sql"]
    result = {}
    for path in paths:
        require(path.resolve() == path and path.is_file(), "SQL_REGULAR_SOURCE_REQUIRED")
        data = path.read_bytes()
        require(0 < len(data) <= 1024 * 1024 and b"\x00" not in data, "SQL_SIZE")
        require(
            not any(line.lstrip().startswith("\\") for line in data.decode().splitlines()),
            "PSQL_META_COMMAND_NOT_SUPPORTED",
        )
        result[str(path.relative_to(repo))] = data
    require(
        digest(result["supabase/local_dev_setup.sql"]) == BOOTSTRAP_SHA,
        "EXACT_EXISTING_LOCAL_BOOTSTRAP_REQUIRED",
    )
    return result


def clean_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
    }


class Runtime:
    """Dış etkiler burada; çevrimdışı testler bu sınıf yerine çağrı kaydı kullanır."""

    def __init__(self, container_id: str) -> None:
        self.container_id = container_id

    def docker(self, arguments: list[str], payload: bytes | None = None) -> bytes:
        # Kabuk yok; tüm argümanlar sabit veya yukarıda doğrulanmış dar değerler.
        result = subprocess.run(  # noqa: S603
            ["/usr/bin/docker", "--host", "unix:///var/run/docker.sock", *arguments],
            input=payload,
            env=clean_environment(),
            capture_output=True,
            check=False,
            timeout=30,
        )
        require(
            result.returncode == 0 and len(result.stdout) <= 1024 * 1024, "DOCKER_COMMAND_FAILED"
        )
        return result.stdout

    def inspect(self) -> tuple[Any, Any]:
        raw = json.loads(
            self.docker(["container", "inspect", "--format", INSPECT, self.container_id])
        )
        image_id = raw.get("imageId") if type(raw) is dict else None
        require(
            type(image_id) is str
            and image_id.startswith("sha256:")
            and bool(HEX.fullmatch(image_id[7:])),
            "SERVICE_IMAGE_ID",
        )
        image = json.loads(self.docker(["image", "inspect", "--format", IMAGE_INSPECT, image_id]))
        return raw, image

    def container_sql(
        self, address: str, database: str, statement: str, *, result: bool = True
    ) -> Any:
        raw = self.docker(
            [
                "exec",
                "-i",
                self.container_id,
                "env",
                "-i",
                "PATH=" + clean_environment()["PATH"],
                "LANG=C.UTF-8",
                "PGPASSWORD=postgres",
                "psql",
                "-X",
                "-w",
                "-A",
                "-t",
                "-q",
                "-v",
                "ON_ERROR_STOP=1",
                "--host",
                address,
                "--port",
                "5432",
                "--username",
                "postgres",
                "--dbname",
                database,
                "--file",
                "-",
            ],
            (statement + ";\n").encode(),
        )
        return json.loads(raw) if result else None

    def connect(self, port: int, database: str, passfile: Path, user: str = "postgres") -> Any:
        # psycopg/libpq ortamı yalnız ayrı helper sürecinde temizlenir.
        for key in list(os.environ):
            if key.startswith("PG"):
                del os.environ[key]
        import psycopg

        return psycopg.connect(
            host="127.0.0.1",
            hostaddr="127.0.0.1",
            port=port,
            dbname=database,
            user=user,
            passfile=str(passfile),
            sslmode="disable",
            connect_timeout=3,
            autocommit=True,
            options="-c statement_timeout=30000 -c lock_timeout=2000",
        )


def value(connection: Any, statement: str) -> Any:
    return connection.execute(statement).fetchone()[0]


def apply_source(connection: Any, data: bytes) -> None:
    # Göçlerin kendi BEGIN/COMMIT sınırları korunur; son statement hatası da okunur.
    cursor = connection.execute(data.decode(), prepare=False)
    while cursor.nextset():
        pass
    require(connection.info.transaction_status == 0, "SOURCE_LEFT_OPEN_TRANSACTION")


def verify_role_connection(
    runtime: Runtime, port: int, passfile: Path, identity: dict[str, Any], role: str
) -> dict[str, Any]:
    with runtime.connect(port, DATABASE, passfile, role) as connection:
        observed = value(connection, ROLE_IDENTITY)
    expected = {
        key: identity[key]
        for key in (
            "database",
            "oid",
            "serverAddress",
            "serverPort",
            "version",
        )
    }
    expected.update(
        currentUser=role,
        sessionUser=role,
        superuser=False,
        bypassRls=role == "dou_worker",
        createDb=False,
        createRole=False,
        replication=False,
    )
    require(observed == expected, "APPLICATION_ROLE_CONNECTION_IDENTITY")
    return observed


def provision(args: argparse.Namespace, env: dict[str, str], runtime: Runtime) -> dict[str, Any]:
    validate_context(args, env)
    sources = read_sql(args.repo)
    hashes = {key: digest(data) for key, data in sources.items()}
    inspected, image = runtime.inspect()
    target = validate_container(inspected, image, args.container_id, args.port)
    before = validate_identity(
        runtime.container_sql(target["serverAddress"], "postgres", IDENTITY), target, "postgres"
    )
    require_fresh(runtime.container_sql(target["serverAddress"], "postgres", INVENTORY))
    args.output.mkdir(mode=0o700, exist_ok=False)
    passfile = args.output / "postgres.pgpass"
    entries = [
        ("postgres", "postgres", "postgres"),
        (DATABASE, "postgres", "postgres"),
        (DATABASE, "dou_app", "dou_app_local"),
        (DATABASE, "dou_worker", "dou_worker_local"),
    ]
    private_write(
        passfile,
        "".join(
            f"127.0.0.1:{args.port}:{db}:{role}:{password}\n" for db, role, password in entries
        ).encode(),
    )
    # CREATE öncesinde yanlış host hedefini de reddet; henüz göç/rol değişikliği yok.
    with runtime.connect(args.port, "postgres", passfile) as maintenance:
        validate_identity(value(maintenance, IDENTITY), target, "postgres", before)
        require_fresh(value(maintenance, INVENTORY))
        runtime.container_sql(target["serverAddress"], "postgres", CREATE, result=False)
        created = validate_identity(
            runtime.container_sql(target["serverAddress"], DATABASE, IDENTITY), target, DATABASE
        )
        require(
            created["cluster"] == before["cluster"]
            and created["version"] == before["version"]
            and created["oid"] != before["oid"],
            "CLUSTER_CHANGED_DURING_CREATE",
        )
        created_receipt = {
            "version": 1,
            "issuer": "github-owned-service",
            "target": target,
            "before": before,
            "created": created,
            "absentBefore": True,
            "createCompleted": True,
            "runId": args.run_id,
            "githubRunId": env["GITHUB_RUN_ID"],
            "githubRunAttempt": env["GITHUB_RUN_ATTEMPT"],
        }
        private_write(args.output / "created.json", canonical(created_receipt))
        # Göç/seed aynı doğrulanmış fiziksel host bağlantısında yürür.
        with runtime.connect(args.port, DATABASE, passfile) as database:
            validate_identity(value(database, IDENTITY), target, DATABASE, created)
            applied = []
            for relative, data in sources.items():
                require(read_sql(args.repo) == sources, "SQL_SOURCE_CHANGED")
                validate_identity(value(database, IDENTITY), target, DATABASE, created)
                if relative == "supabase/local_dev_setup.sql":
                    require(
                        value(database, ROLES) == expected_roles(False),
                        "EXPECTED_NEW_NOLOGIN_ROLES",
                    )
                    require(value(database, MEMBERSHIPS) == 0, "UNEXPECTED_ROLE_MEMBERSHIP")
                apply_source(database, data)
                applied.append(relative)
            validate_identity(value(database, IDENTITY), target, DATABASE, created)
            require(value(database, ROLES) == expected_roles(True), "POST_BOOTSTRAP_ROLE_FLAGS")
            require(value(database, MEMBERSHIPS) == 0, "UNEXPECTED_ROLE_MEMBERSHIP")
            summary = value(database, SUMMARY)
            require(
                summary == {"vector": "0.8.6", "profiles": 2, "admins": 1, "auditRows": 0},
                "SEED_OR_EXTENSION_CONTRACT",
            )
        role_connections = [
            verify_role_connection(runtime, args.port, passfile, created, role)
            for role in ("dou_app", "dou_worker")
        ]
        validate_identity(value(maintenance, IDENTITY), target, "postgres", before)
    require(
        validate_container(*runtime.inspect(), args.container_id, args.port) == target,
        "SERVICE_CHANGED_DURING_PROVISION",
    )
    require(read_sql(args.repo) == sources, "SQL_SOURCE_CHANGED")
    result = {
        "status": "PASS",
        "scope": "github-owned-fresh-synthetic-only",
        "runId": args.run_id,
        "createdReceiptSha256": digest(canonical(created_receipt)),
        "target": target,
        "identity": created,
        "filesSha256": hashes,
        "applied": applied,
        "seedSummary": summary,
        "applicationConnections": role_connections,
        "sourcesUnchanged": True,
        "dropExecuted": False,
        "bootstrap": "byte-exact-existing-local_dev_setup.sql",
        "sharedLocalRolesChanged": False,
        "helperSha256": digest(Path(__file__).read_bytes()),
    }
    result_bytes = canonical(result)
    private_write(args.output / "provision.json", result_bytes)
    pins = {
        "version": 1,
        "issuer": "github-owned-service",
        "ownership": "exclusive-synthetic",
        "provisionSha256": digest(result_bytes),
        "host": "127.0.0.1",
        "port": args.port,
        "databaseName": DATABASE,
        "databaseOid": created["oid"],
        "cluster": created["cluster"],
        "dbaRole": "postgres",
        "apiOrigin": f"http://127.0.0.1:{args.api_port}",
    }
    pin_bytes = canonical(pins)
    private_write(args.output / "pins.json", pin_bytes)
    handoff = {
        "pins": str(args.output / "pins.json"),
        "pinsSha256": digest(pin_bytes),
        "passfile": str(passfile),
        "runId": args.run_id,
    }
    private_write(args.output / "handoff.json", canonical(handoff))
    return {"status": "PASS", **handoff}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        validate_context(args, dict(os.environ))
        if not args.execute:
            print(json.dumps({"status": "PLAN", "dockerCalls": 0, "databaseCalls": 0}))
            return 0
        result = provision(args, dict(os.environ), Runtime(args.container_id))
        print(json.dumps(result))
        return 0
    except Refusal as error:
        code = str(error)
    except Exception:
        code = "CI_PROVISION_FAILED"
    failure = {"status": "FAIL", "code": code, "cleanupAttempted": False}
    # Hata makbuzu stdout'tadır; önceden var olan bir çıktı dizinine yazılmaz.
    print(json.dumps(failure))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
