"""Gerçek bağlantı açmadan CI kurulumunun sınır ve sıralama sözleşmeleri."""

from __future__ import annotations

import argparse
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import provision_ci_e2e as provision

CONTAINER_ID = "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
ADDRESS = "172.18.0.2"
ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_JOB": "e2e",
    "GITHUB_RUN_ID": "123456789",
    "GITHUB_RUN_ATTEMPT": "1",
}


def inspect_fixture():
    return {
        "id": CONTAINER_ID,
        "imageReference": provision.IMAGE,
        "imageId": IMAGE_ID,
        "running": True,
        "ports": {
            "5432/tcp": [
                {"HostIp": "0.0.0.0", "HostPort": "5432"},  # noqa: S104 — sentetik inspect girdisi.
                {"HostIp": "::", "HostPort": "5432"},
            ]
        },
        "networks": {"github_network": {"IPAddress": ADDRESS}},
    }, {"id": IMAGE_ID, "repoDigests": [provision.REPO_DIGEST]}


def identity(database):
    return {
        "database": database,
        "oid": "5" if database == "postgres" else "12345",
        "cluster": "7683042491268153327",
        "version": 160014,
        "serverAddress": ADDRESS,
        "serverPort": 5432,
        "currentUser": "postgres",
        "sessionUser": "postgres",
        "superuser": True,
        "recovery": False,
    }


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return (self.row,)

    def nextset(self):
        return None


class Connection:
    def __init__(self, backend, database, user):
        self.backend = backend
        self.database = database
        self.user = user
        self.info = SimpleNamespace(transaction_status=0)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, **kwargs):
        self.backend.events.append(("host", self.database, self.user, statement))
        if statement == provision.IDENTITY:
            value = identity(self.database)
            if self.database == self.backend.host_mismatch_database:
                value["cluster"] = "99"
            return Cursor(value)
        if statement == provision.INVENTORY:
            return Cursor(self.backend.inventory)
        if statement == provision.ROLES:
            return Cursor(provision.expected_roles(self.backend.bootstrapped))
        if statement == provision.MEMBERSHIPS:
            return Cursor(self.backend.memberships)
        if statement == provision.SUMMARY:
            return Cursor({"vector": "0.8.6", "profiles": 2, "admins": 1, "auditRows": 0})
        if statement == provision.ROLE_IDENTITY:
            value = identity(self.database)
            value.pop("cluster")
            value.pop("recovery")
            value.update(
                currentUser=self.user,
                sessionUser=self.user,
                superuser=False,
                bypassRls=self.user == "dou_worker",
                createDb=False,
                createRole=False,
                replication=False,
            )
            return Cursor(value)
        assert kwargs == {"prepare": False}
        if statement == "select 'local bootstrap';":
            self.backend.bootstrapped = True
        self.backend.applied.append(statement)
        return Cursor()


class Backend:
    def __init__(self):
        self.events = []
        self.applied = []
        self.bootstrapped = False
        self.memberships = 0
        self.inventory = {
            "databases": ["postgres", "template0", "template1"],
            "roles": ["postgres"],
        }
        self.host_mismatch_database = None

    def inspect(self):
        self.events.append(("inspect",))
        return inspect_fixture()

    def container_sql(self, address, database, statement, *, result=True):
        self.events.append(("container", database, statement))
        assert address == ADDRESS
        if statement == provision.IDENTITY:
            return identity(database)
        if statement == provision.INVENTORY:
            return self.inventory
        assert statement == provision.CREATE and result is False
        return None

    def connect(self, port, database, passfile, user="postgres"):
        self.events.append(("connect", database, user))
        assert port == 5432
        assert passfile.is_file() and passfile.stat().st_mode & 0o077 == 0
        return Connection(self, database, user)


class ProvisionContracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name).resolve()
        self.args = argparse.Namespace(
            repo=self.base,
            output=self.base / "new",
            port=5432,
            api_port=8000,
            run_id="ci123456",
            container_id=CONTAINER_ID,
        )
        self.sources = {
            "supabase/migrations/0001_fixture.sql": b"select 'migration';",
            "supabase/local_dev_setup.sql": b"select 'local bootstrap';",
            "supabase/seed_demo.sql": b"select 'seed';",
        }

    def run_fake(self, backend):
        with patch.object(provision, "read_sql", return_value=self.sources):
            return provision.provision(self.args, ENV, backend)

    def test_create_order_host_target_identity_before_every_source_and_private_handoff(self):
        backend = Backend()
        result = self.run_fake(backend)
        self.assertEqual(result["status"], "PASS")
        created = backend.events.index(("container", "postgres", provision.CREATE))
        host_preflight = backend.events.index(("host", "postgres", "postgres", provision.IDENTITY))
        self.assertLess(host_preflight, created)
        previous_source = created
        for statement in [data.decode() for data in self.sources.values()]:
            event = ("host", provision.DATABASE, "postgres", statement)
            index = backend.events.index(event)
            # An earlier source's identity read cannot satisfy this source's gate.
            preceding = backend.events[previous_source + 1 : index]
            self.assertIn(("host", provision.DATABASE, "postgres", provision.IDENTITY), preceding)
            self.assertGreater(index, previous_source)
            previous_source = index
        self.assertEqual(backend.applied, [data.decode() for data in self.sources.values()])
        self.assertIn(("connect", provision.DATABASE, "dou_app"), backend.events)
        self.assertIn(("connect", provision.DATABASE, "dou_worker"), backend.events)
        for path in self.args.output.iterdir():
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        import json

        pins_raw = (self.args.output / "pins.json").read_bytes()
        pins = json.loads(pins_raw)
        self.assertEqual(result["pinsSha256"], provision.digest(pins_raw))
        self.assertEqual(
            pins["provisionSha256"],
            provision.digest((self.args.output / "provision.json").read_bytes()),
        )
        self.assertEqual(pins["issuer"], "github-owned-service")
        self.assertEqual(pins["databaseOid"], "12345")
        self.assertEqual(pins["cluster"], identity("postgres")["cluster"])
        self.assertEqual(
            set(pins),
            {
                "version",
                "issuer",
                "ownership",
                "provisionSha256",
                "host",
                "port",
                "databaseName",
                "databaseOid",
                "cluster",
                "dbaRole",
                "apiOrigin",
            },
        )

    def test_wrong_host_maintenance_cluster_stops_before_create(self):
        backend = Backend()
        backend.host_mismatch_database = "postgres"
        with self.assertRaisesRegex(provision.Refusal, "^CONTAINER_HOST_IDENTITY_MISMATCH$"):
            self.run_fake(backend)
        self.assertNotIn(("container", "postgres", provision.CREATE), backend.events)
        self.assertEqual(backend.applied, [])

    def test_wrong_host_new_database_stops_before_migrations(self):
        backend = Backend()
        backend.host_mismatch_database = provision.DATABASE
        with self.assertRaisesRegex(provision.Refusal, "^CONTAINER_HOST_IDENTITY_MISMATCH$"):
            self.run_fake(backend)
        self.assertIn(("container", "postgres", provision.CREATE), backend.events)
        self.assertEqual(backend.applied, [])
        self.assertTrue((self.args.output / "created.json").exists())
        self.assertFalse((self.args.output / "pins.json").exists())

    def test_identity_change_after_first_source_blocks_remaining_sql_and_handoff(self):
        backend = Backend()
        original_execute = Connection.execute

        def drift_after_first_source(connection, statement, **kwargs):
            cursor = original_execute(connection, statement, **kwargs)
            if (
                statement == provision.IDENTITY
                and connection.database == provision.DATABASE
                and len(connection.backend.applied) == 1
            ):
                changed = dict(cursor.row)
                changed["cluster"] = "99"
                return Cursor(changed)
            return cursor

        with patch.object(Connection, "execute", new=drift_after_first_source):
            with self.assertRaisesRegex(provision.Refusal, "^CONTAINER_HOST_IDENTITY_MISMATCH$"):
                self.run_fake(backend)

        # CREATE and source one already happened; the later authority failure
        # must block both the LOGIN/password source and the seed, without success.
        self.assertEqual(backend.applied, ["select 'migration';"])
        self.assertFalse(backend.bootstrapped)
        for later in ("select 'local bootstrap';", "select 'seed';"):
            self.assertNotIn(("host", provision.DATABASE, "postgres", later), backend.events)
        self.assertTrue((self.args.output / "created.json").exists())
        for success_file in ("provision.json", "pins.json", "handoff.json"):
            self.assertFalse((self.args.output / success_file).exists())

    def test_existing_database_or_shared_roles_refused_without_create(self):
        for key, added in (("databases", provision.DATABASE), ("roles", "dou_app")):
            with self.subTest(key=key):
                backend = Backend()
                backend.inventory[key].append(added)
                with self.assertRaisesRegex(provision.Refusal, "^FRESH_SERVICE_REQUIRED$"):
                    self.run_fake(backend)
                self.assertNotIn(("container", "postgres", provision.CREATE), backend.events)
                self.assertEqual(backend.applied, [])

    def test_unexpected_membership_stops_before_login_password_changes(self):
        backend = Backend()
        backend.memberships = 1
        with self.assertRaisesRegex(provision.Refusal, "^UNEXPECTED_ROLE_MEMBERSHIP$"):
            self.run_fake(backend)
        self.assertEqual(backend.applied, ["select 'migration';"])
        self.assertFalse(backend.bootstrapped)
        self.assertFalse((self.args.output / "pins.json").exists())

    def test_source_drift_stops_before_first_migration(self):
        backend = Backend()
        changed = {**self.sources, "supabase/seed_demo.sql": b"select 'changed';"}
        with patch.object(provision, "read_sql", side_effect=[self.sources, changed]):
            with self.assertRaisesRegex(provision.Refusal, "^SQL_SOURCE_CHANGED$"):
                provision.provision(self.args, ENV, backend)
        self.assertEqual(backend.applied, [])

    def test_context_rejects_local_execution_short_container_and_existing_output(self):
        for updates in (
            {"GITHUB_ACTIONS": "false"},
            {"GITHUB_JOB": "api"},
            {"GITHUB_RUN_ID": "abc"},
        ):
            with self.subTest(updates=updates), self.assertRaises(provision.Refusal):
                provision.validate_context(self.args, {**ENV, **updates})
        original = self.args.container_id
        self.args.container_id = original[:12]
        with self.assertRaisesRegex(provision.Refusal, "^FULL_SERVICE_CONTAINER_ID_REQUIRED$"):
            provision.validate_context(self.args, ENV)
        self.args.container_id = original
        self.args.output.mkdir()
        with self.assertRaisesRegex(provision.Refusal, "^NEW_PRIVATE_OUTPUT_REQUIRED$"):
            provision.validate_context(self.args, ENV)

    def test_wrong_id_digest_mapping_or_ambiguous_network_rejected(self):
        for variant in ("id", "digest", "port", "network", "cidr", "public", "stopped"):
            with self.subTest(variant=variant):
                raw, image = inspect_fixture()
                if variant == "id":
                    raw["id"] = "c" * 64
                elif variant == "digest":
                    image["repoDigests"] = ["pgvector/pgvector@sha256:" + "d" * 64]
                elif variant == "port":
                    raw["ports"]["5432/tcp"][0]["HostPort"] = "55448"
                elif variant == "network":
                    raw["networks"]["second"] = {"IPAddress": "172.19.0.2"}
                elif variant == "cidr":
                    raw["networks"]["github_network"]["IPAddress"] += "/16"
                elif variant == "public":
                    raw["networks"]["github_network"]["IPAddress"] = "8.8.8.8"
                else:
                    raw["running"] = False
                with self.assertRaises(provision.Refusal):
                    provision.validate_container(raw, image, CONTAINER_ID, 5432)

    def test_real_psql_and_docker_arguments_drop_ambient_routing_and_shell(self):
        runtime = provision.Runtime(CONTAINER_ID)
        captured = []

        def run(argv, **kwargs):
            captured.append((argv, kwargs))
            return SimpleNamespace(returncode=0, stdout=b"null\n", stderr=b"")

        with patch.object(provision.subprocess, "run", side_effect=run):
            with patch.dict(
                provision.os.environ,
                {
                    "DOCKER_HOST": "tcp://evil:2375",
                    "PGHOST": "evil",
                    "PGSERVICE": "personal",
                    "PGPASSFILE": "/personal/.pgpass",
                },
            ):
                runtime.container_sql(ADDRESS, "postgres", provision.INVENTORY)
        argv, kwargs = captured[0]
        self.assertEqual(argv[:3], ["/usr/bin/docker", "--host", "unix:///var/run/docker.sock"])
        self.assertNotIn("shell", kwargs)
        self.assertNotIn("DOCKER_HOST", kwargs["env"])
        self.assertFalse(any(key.startswith("PG") for key in kwargs["env"]))
        self.assertIn("env", argv)
        self.assertIn("-i", argv)
        self.assertIn("-X", argv)
        self.assertIn("ON_ERROR_STOP=1", argv)
        self.assertIn(ADDRESS, argv)
        self.assertEqual(kwargs["input"], (provision.INVENTORY + ";\n").encode())

    def test_all_identity_fields_compared_not_just_database_name(self):
        raw, image = inspect_fixture()
        target = provision.validate_container(raw, image, CONTAINER_ID, 5432)
        expected = identity(provision.DATABASE)
        for key, value in (
            ("oid", "54321"),
            ("cluster", "99"),
            ("version", 160013),
            ("serverAddress", "172.18.0.3"),
            ("serverPort", 55448),
            ("superuser", False),
            ("recovery", True),
        ):
            with self.subTest(key=key):
                actual = copy.deepcopy(expected)
                actual[key] = value
                with self.assertRaises(provision.Refusal):
                    provision.validate_identity(actual, target, provision.DATABASE, expected)

    def test_host_driver_uses_only_explicit_numeric_route_and_private_passfile(self):
        captured = []
        marker = object()

        def connect(**kwargs):
            captured.append(kwargs)
            return marker

        runtime = provision.Runtime(CONTAINER_ID)
        passfile = self.base / "postgres.pgpass"
        with patch.dict(sys.modules, {"psycopg": SimpleNamespace(connect=connect)}):
            with patch.dict(
                os.environ,
                {
                    "PGHOST": "evil",
                    "PGHOSTADDR": "8.8.8.8",
                    "PGSERVICE": "personal",
                    "PGPASSFILE": "/personal/.pgpass",
                    "PGOPTIONS": "-c search_path=hostile",
                    "PGPORT": "55448",
                },
            ):
                self.assertIs(runtime.connect(5432, provision.DATABASE, passfile), marker)
                self.assertFalse(any(name.startswith("PG") for name in os.environ))
        self.assertEqual(
            captured[0],
            {
                "host": "127.0.0.1",
                "hostaddr": "127.0.0.1",
                "port": 5432,
                "dbname": provision.DATABASE,
                "user": "postgres",
                "passfile": str(passfile),
                "sslmode": "disable",
                "connect_timeout": 3,
                "autocommit": True,
                "options": "-c statement_timeout=30000 -c lock_timeout=2000",
            },
        )

    def test_source_failure_is_not_converted_to_success_and_consumes_all_results(self):
        class FailingCursor:
            def nextset(self):
                raise RuntimeError("SYNTHETIC_LAST_STATEMENT_FAILURE")

        connection = SimpleNamespace(
            execute=lambda *args, **kwargs: FailingCursor(),
            info=SimpleNamespace(transaction_status=0),
        )
        with self.assertRaisesRegex(RuntimeError, "^SYNTHETIC_LAST_STATEMENT_FAILURE$"):
            provision.apply_source(connection, b"SELECT 1; SELECT missing;")

    def test_exact_existing_bootstrap_read_and_mutations_refuse(self):
        sql_root = self.base / "supabase"
        migrations = sql_root / "migrations"
        migrations.mkdir(parents=True)
        (migrations / "0001_fixture.sql").write_text("SELECT 1;\n")
        original = (Path(__file__).parent / "fixtures/ci_local_dev_setup.sql").read_bytes()
        (sql_root / "local_dev_setup.sql").write_bytes(original)
        (sql_root / "seed_demo.sql").write_text("SELECT 1;\n")
        self.assertEqual(provision.read_sql(self.base)["supabase/local_dev_setup.sql"], original)
        (sql_root / "local_dev_setup.sql").write_bytes(original + b"-- unauthorized drift\n")
        with self.assertRaisesRegex(provision.Refusal, "^EXACT_EXISTING_LOCAL_BOOTSTRAP_REQUIRED$"):
            provision.read_sql(self.base)
        (sql_root / "local_dev_setup.sql").write_bytes(original)
        (migrations / "0001_duplicate.sql").write_text("SELECT 2;\n")
        with self.assertRaisesRegex(provision.Refusal, "^DUPLICATE_MIGRATION_NUMBER$"):
            provision.read_sql(self.base)


if __name__ == "__main__":
    unittest.main()
