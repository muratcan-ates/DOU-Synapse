"""Yalnız D1 sentetik PG testi için kökün önceden bildirdiği yerel hedefi doğrular.

Üretim bağlantı ayarlarını değiştirmez. Ağ erişimi ancak connect() çağrısında olur;
kimlik kontrolü salt okunurdur ve fixture yazımından önce tamamlanır.
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import os
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


class TargetGuardError(RuntimeError):
    """Sabit hata kodu; bağlantı metni, parola veya alt DB hatası yayımlanmaz."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise TargetGuardError(code)


@dataclass(frozen=True)
class TargetFingerprint:
    database: str
    database_oid: int
    system_identifier: str
    server_version_num: int
    server_address: str
    server_port: int


@dataclass(frozen=True, repr=False)
class ConnectionConfig:
    host: str
    port: int
    user: str
    password: str | None
    database: str
    expected: TargetFingerprint


def numeric_loopback(value: object) -> str:
    require(isinstance(value, str), "NUMERIC_LOOPBACK_REQUIRED")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise TargetGuardError("NUMERIC_LOOPBACK_REQUIRED") from None
    require(
        address.is_loopback and not getattr(address, "scope_id", None),
        "NUMERIC_LOOPBACK_REQUIRED",
    )
    return address.compressed


def expected_target(environment: dict[str, str], database: str) -> TargetFingerprint:
    """JSON'u kök provisioning sırasında yakalar; test hedefini kendisi öğrenip onaylamaz."""
    try:
        data = json.loads(environment.get("D1_EXPECTED_TARGET_JSON", ""))
    except (TypeError, ValueError):
        raise TargetGuardError("ROOT_EXPECTED_TARGET_REQUIRED") from None
    require(
        isinstance(data, dict)
        and set(data)
        == {
            "database",
            "database_oid",
            "system_identifier",
            "server_version_num",
            "server_address",
            "server_port",
        },
        "ROOT_EXPECTED_TARGET_REQUIRED",
    )
    require(data["database"] == database, "EXPECTED_DATABASE_MISMATCH")
    require(
        type(data["database_oid"]) is int and 1 <= data["database_oid"] <= 4294967295,
        "EXPECTED_DATABASE_OID_INVALID",
    )
    require(
        isinstance(data["system_identifier"], str)
        and bool(re.fullmatch(r"[1-9][0-9]{0,19}", data["system_identifier"]))
        and int(data["system_identifier"]) <= 18446744073709551615,
        "EXPECTED_CLUSTER_ID_INVALID",
    )
    require(
        type(data["server_version_num"]) is int and 100000 <= data["server_version_num"] <= 999999,
        "EXPECTED_SERVER_VERSION_INVALID",
    )
    require(
        type(data["server_port"]) is int and 1 <= data["server_port"] <= 65535,
        "EXPECTED_SERVER_PORT_INVALID",
    )
    return TargetFingerprint(
        database,
        data["database_oid"],
        data["system_identifier"],
        data["server_version_num"],
        numeric_loopback(data["server_address"]),
        data["server_port"],
    )


def configuration(environment: dict[str, str]) -> ConnectionConfig:
    database = environment.get("D1_TEST_DB_NAME", "")
    require(
        bool(re.fullmatch(r"dou_synapse_d1_[a-z0-9_]{1,30}", database)),
        "EXPLICIT_D1_DATABASE_REQUIRED",
    )
    expected = expected_target(environment, database)
    raw = environment.get("D1_ADMIN_DSN", "")
    try:
        parsed = urlsplit(raw)
        require(parsed.scheme == "postgresql+psycopg", "PSYCOPG_DSN_REQUIRED")
        require(
            not parsed.query and not parsed.fragment and "?" not in raw and "#" not in raw,
            "DSN_ROUTING_OPTIONS_REFUSED",
        )
        require(not any(char.isspace() for char in raw), "INVALID_CONNECTION_INPUT")
        host = numeric_loopback(parsed.hostname)
        port = parsed.port
        require(port is not None and 1 <= port <= 65535, "EXPLICIT_PORT_REQUIRED")
        require(parsed.path == "/" + database, "DATABASE_TARGET_MISMATCH")
        user = unquote(parsed.username or "")
        require(
            bool(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,62}", user))
            and user not in {"dou_app", "dou_worker"},
            "EXPLICIT_TEST_DBA_REQUIRED",
        )
        password = None if parsed.password is None else unquote(parsed.password)
        require(password is None or "\x00" not in password, "INVALID_CONNECTION_INPUT")
    except (ValueError, TypeError):
        raise TargetGuardError("INVALID_CONNECTION_INPUT") from None
    require(
        (host, port) == (expected.server_address, expected.server_port),
        "ROOT_EXPECTED_ENDPOINT_MISMATCH",
    )
    return ConnectionConfig(host, port, user, password, database, expected)


def clean_postgres_environment(environment: dict[str, str]) -> dict[str, str]:
    """Kimlik ve yönlendirme yalnız D1 girdilerinden gelir; inherited libpq ayarları yoktur."""
    return {key: value for key, value in environment.items() if not key.startswith("PG")}


def validate_connected_identity(row: dict, config: ConnectionConfig) -> None:
    expected = config.expected
    require(row["database"] == expected.database, "CONNECTED_DATABASE_MISMATCH")
    require(row["database_oid"] == expected.database_oid, "CONNECTED_DATABASE_OID_MISMATCH")
    require(row["system_identifier"] == expected.system_identifier, "CONNECTED_CLUSTER_MISMATCH")
    require(
        numeric_loopback(row["server_address"]) == expected.server_address,
        "CONNECTED_SERVER_ADDRESS_MISMATCH",
    )
    require(row["server_port"] == expected.server_port, "CONNECTED_SERVER_PORT_MISMATCH")
    require(
        row["server_version_num"] == expected.server_version_num,
        "CONNECTED_SERVER_VERSION_MISMATCH",
    )
    numeric_loopback(row["client_address"])
    require(
        row["role"] == row["session_role"] == config.user and row["rolsuper"] is True,
        "CONNECTED_TEST_DBA_MISMATCH",
    )


_IDENTITY_SQL = """SELECT pg_catalog.current_database() AS database,
    current_user AS role, session_user AS session_role, r.rolsuper,
    d.oid::bigint AS database_oid,
    pg_catalog.host(pg_catalog.inet_server_addr()) AS server_address,
    pg_catalog.inet_server_port() AS server_port,
    pg_catalog.host(pg_catalog.inet_client_addr()) AS client_address,
    pg_catalog.current_setting('server_version_num')::integer AS server_version_num
    FROM pg_catalog.pg_roles r CROSS JOIN pg_catalog.pg_database d
    WHERE r.rolname=current_user AND d.datname=pg_catalog.current_database()"""


def connect(*, passfile: str):
    """Önce hedefi bağla/doğrula; ancak sonra fixture işlemlerine hazır bağlantı döndür."""
    from common import private_passfile

    passfile = private_passfile(passfile)
    config = configuration(dict(os.environ))
    safe = clean_postgres_environment(dict(os.environ))
    os.environ.clear()
    os.environ.update(safe)
    import psycopg
    from psycopg.rows import dict_row

    kwargs = {
        "host": config.host,
        "hostaddr": config.host,
        "port": config.port,
        "user": config.user,
        "dbname": config.database,
        "row_factory": dict_row,
        "connect_timeout": 3,
        "passfile": passfile,
        "sslmode": "disable",
        "application_name": "dou018-d1-synthetic-quota-test",
        "options": "-c statement_timeout=2000 -c lock_timeout=1000",
    }
    if config.password is not None:
        kwargs["password"] = config.password
    connection = None
    try:
        # Ham DSN veya inherited PG* seçenekleri libpq'ya aktarılmaz.
        connection = psycopg.connect("", **kwargs)
        connection.execute("SET TRANSACTION READ ONLY")
        row = dict(connection.execute(_IDENTITY_SQL).fetchone())
        row["system_identifier"] = connection.execute(
            "SELECT system_identifier::text AS system_identifier "
            "FROM pg_catalog.pg_control_system()"
        ).fetchone()["system_identifier"]
        validate_connected_identity(row, config)
        connection.commit()
        return connection
    except BaseException as exc:
        if connection is not None:
            # Kapatma hatası özgün reddi/iptali maskeleyemez; alt hata kayda alınmaz.
            with contextlib.suppress(Exception):
                connection.close()
        if isinstance(exc, TargetGuardError):
            raise
        if isinstance(exc, Exception):
            raise TargetGuardError("ISOLATED_D1_TARGET_UNAVAILABLE") from None
        raise
