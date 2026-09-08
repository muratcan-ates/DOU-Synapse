"""Offline contracts. Subprocess fixtures are synthetic; no PostgreSQL is contacted."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('recovery', Path(__file__).with_name('recovery.py'))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
CANARY = 'SYNTHETIC_SECRET_NOT_FOR_OUTPUT_739'
ARCHIVE = b'PGDMPsynthetic-offline-fixture-not-a-valid-postgres-archive'
CONNECTION = {'DOU_BACKUP_PGHOST': '127.0.0.1', 'DOU_BACKUP_PGPORT': '55448', 'DOU_BACKUP_PGDATABASE': 'synthetic_source', 'DOU_BACKUP_PGUSER': 'synthetic_dba', 'DOU_BACKUP_PGPASSWORD': CANARY, 'DOU_RESTORE_PGHOST': '127.0.0.1', 'DOU_RESTORE_PGPORT': '55448', 'DOU_RESTORE_PGDATABASE': 'synthetic_target', 'DOU_RESTORE_PGUSER': 'synthetic_dba', 'DOU_RESTORE_PGPASSWORD': CANARY}
CONNECTION |= {key.replace('DOU_RESTORE_', 'DOU_MAINTENANCE_'): value for key, value in CONNECTION.copy().items() if key.startswith('DOU_RESTORE_')}
CONNECTION['DOU_MAINTENANCE_PGDATABASE'] = 'synthetic_maintenance'
ROLE = {'name': 'synthetic_dba', 'superuser': True, 'inherit': True, 'create_role': True, 'create_db': True, 'login': True, 'replication': True, 'bypass_rls': True}
ACL = [{'grantee': 'synthetic_dba', 'public': False, 'grantor': 'synthetic_dba', 'privilege': privilege, 'grantable': False} for privilege in ('CONNECT', 'CREATE', 'TEMPORARY')]
META = {'identity': {'system_identifier': '100', 'database_oid': '400', 'database_name': 'synthetic_source'}, 'server_version_num': 160010, 'database_format': {'encoding': 'UTF8', 'collate': 'C'}, 'database_settings': [], 'database_security_labels': 0, 'superuser': True, 'connections_allowed': True, 'other_connections': 0, 'empty': False, 'database_owner': 'synthetic_dba', 'database_acl': ACL, 'required_role_names': ['synthetic_dba'], 'roles': [ROLE], 'memberships': [], 'extensions': [{'name': 'plpgsql', 'schema': 'pg_catalog', 'version': '1.0'}], 'available_extensions': [{'name': 'plpgsql', 'version': '1.0'}], 'security_catalog_sha256': 'a' * 64}
LINEAGE = {'commit': 'b' * 40, 'schema_files_sha256': {'supabase/migrations/0001_synthetic.sql': 'c' * 64}, 'tracked_schema_dirty': False}


def target_meta():
    result = copy.deepcopy(META)
    result['identity'] = {'system_identifier': '100', 'database_oid': '401', 'database_name': 'synthetic_target'}
    result['empty'] = True
    return result


def named_role(name, **overrides):
    return dict(ROLE, name=name, superuser=False, create_role=False, create_db=False,
                replication=False, bypass_rls=False) | overrides


def membership(member, role, **overrides):
    return {'role': role, 'member': member, 'grantor': 'synthetic_dba',
            'admin': False, 'inherit': True, 'set': True} | overrides


def source_with_incoming_chain():
    source = copy.deepcopy(META)
    source['roles'].extend([named_role('expected_bridge', login=False), named_role('expected_login'),
                            named_role('unrelated_group', login=False), named_role('unrelated_login')])
    # Deliberately reversed order: the closure must not depend on row order or one pass.
    source['memberships'] = [membership('expected_login', 'expected_bridge'),
                             membership('expected_bridge', 'synthetic_dba'),
                             membership('unrelated_login', 'unrelated_group')]
    return source


SNAPSHOT_ID = '00000003-0000002A-1'


@contextlib.contextmanager
def fixture_snapshot(_env, after=None):
    before = r.source_metadata(copy.deepcopy(META))
    yield before, SNAPSHOT_ID
    if after is not None and r.source_metadata(after) != before:
        raise r.Refused('SOURCE_METADATA_CHANGED')


class FakeSourceConnection:
    """Synthetic protocol fixture, not PostgreSQL snapshot validation."""
    def __init__(self, after=None, fail_probe=False):
        self.after = copy.deepcopy(META if after is None else after)
        self.metadata_reads = 0
        self.events = []
        self.active = False
        self.snapshot_live = False
        self.closed = False
        self.fail_probe = fail_probe

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.active = False
        self.snapshot_live = False
        self.closed = True

    def execute(self, sql):
        self.events.append('METADATA' if sql == r.SNAPSHOT_SQL else sql)
        if sql.startswith('BEGIN '):
            self.active = True
            value = None
        elif sql == 'COMMIT':
            self.active = False
            self.snapshot_live = False
            value = None
        elif sql == r.SNAPSHOT_SQL:
            self.metadata_reads += 1
            value = copy.deepcopy(META if self.metadata_reads == 1 else self.after)
        elif sql == 'SELECT pg_export_snapshot()':
            if not self.active: raise RuntimeError('missing source transaction')
            self.snapshot_live = True
            value = SNAPSHOT_ID
        elif sql.startswith('SELECT rolsuper'):
            value = True
        elif sql == 'SELECT 1':
            if self.fail_probe: raise RuntimeError(CANARY)
            value = 1
        else:
            raise AssertionError('Unexpected controller query')
        return types.SimpleNamespace(fetchone=lambda: (value,))


class RecoveryContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dou-recovery-offline-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.bundle = self.root / 'new-bundle'
        self.source = r.source_metadata(copy.deepcopy(META))
        self.expected = r.identity_digest(self.source['identity'])

    def fixture_bundle(self):
        self.bundle.mkdir(mode=0o700)
        (self.bundle / r.DUMP).write_bytes(ARCHIVE)
        (self.bundle / r.DUMP).chmod(0o600)
        manifest = {'format': r.FORMAT, 'completed': True, 'source_capture': 'direct-loopback-exported-snapshot-v1', 'archive': {'name': r.DUMP, 'bytes': len(ARCHIVE), 'sha256': hashlib.sha256(ARCHIVE).hexdigest()}, 'source': self.source, 'source_identity_sha256': self.expected, 'lineage': LINEAGE}
        self.write_manifest(manifest)
        return manifest

    def write_manifest(self, manifest):
        (self.bundle / r.MANIFEST).write_text(json.dumps(manifest))
        (self.bundle / r.MANIFEST).chmod(0o600)

    def assertRefused(self, code, fn, *args):
        with self.assertRaisesRegex(r.Refused, '^' + code + '$'):
            fn(*args)

    def test_dry_run_does_not_read_connection_create_files_or_spawn(self):
        out = io.StringIO()
        with patch.dict(os.environ, CONNECTION), patch.object(r, 'command', side_effect=AssertionError('tool called')), patch.object(r, 'connection_env', side_effect=AssertionError('env read')), contextlib.redirect_stdout(out):
            self.assertEqual(r.cli(['restore', '--bundle', str(self.bundle)]), 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload['connections'], 'none')
        self.assertIn('ALLOW_CONNECTIONS', payload['fence_notice'])
        self.assertIn('closed', payload['fence_notice'])
        self.assertFalse(self.bundle.exists())
        self.assertNotIn(CANARY, out.getvalue())

    def test_execute_requires_explicit_trust_and_fence(self):
        for flags in ([], ['--trust-own-backup'], ['--fence-empty-target']):
            with self.subTest(flags=flags), patch.object(r, 'restore') as restore, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(r.cli(['restore', '--bundle', str(self.bundle), '--execute', *flags]), 2)
                restore.assert_not_called()

    def test_shell_wrappers_default_to_zero_effect_dry_run(self):
        fake_bin = self.root / 'bin'; fake_bin.mkdir()
        for tool_name in ('psql', 'pg_dump', 'pg_restore'):
            tool = fake_bin / tool_name
            tool.write_text('#!/bin/sh\nexit 99\n'); tool.chmod(0o700)
        env = os.environ | CONNECTION | {'DOU_RECOVERY_PG_BIN': str(fake_bin)}
        for operation in ('backup', 'restore'):
            proc = subprocess.run([str(Path(__file__).with_name(operation + '.sh')), '--bundle', str(self.bundle)], env=env, capture_output=True, check=False)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(json.loads(proc.stdout)['status'], 'dry-run')
            self.assertNotIn(CANARY.encode(), proc.stdout + proc.stderr)
        self.assertFalse(self.bundle.exists())

    def test_bad_arguments_do_not_echo_supplied_secret(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            r.cli(['backup', '--bundle', str(self.bundle), '--password', CANARY])
        self.assertNotIn(CANARY, err.getvalue())

    def test_connections_ignore_ambient_pg_and_secrets_stay_in_env(self):
        env = r.connection_env('DOU_RESTORE_', CONNECTION | {'PGSERVICE': CANARY, 'PGDATABASE': 'wrong', 'PGOPTIONS': '-c evil', 'DOU_BACKUP_PGHOST': CANARY})
        self.assertEqual(env['PGDATABASE'], 'synthetic_target')
        self.assertEqual(env['PGPASSWORD'], CANARY)
        self.assertNotIn('PGSERVICE', env)
        self.assertNotIn('DOU_BACKUP_PGHOST', env)
        self.assertEqual(env['PGOPTIONS'], '-c search_path=pg_catalog -c client_min_messages=warning')
        self.assertRefused('EXPLICIT_CONNECTION_ENV_REQUIRED', r.connection_env, 'DOU_RESTORE_', {'PGHOST': 'ambient', 'PGDATABASE': 'ambient', 'PGUSER': 'ambient'})
        self.assertRefused('DATABASE_NAME_MUST_NOT_BE_DSN', r.connection_env, 'DOU_RESTORE_', CONNECTION | {'DOU_RESTORE_PGDATABASE': 'postgresql://sensitive'})

    def test_non_loopback_multi_host_service_and_missing_port_are_refused(self):
        for host in ('localhost', 'db.example.test', '127.0.0.1,127.0.0.2', '/private/tmp', '192.0.2.1', '::1%lo0'):
            with self.subTest(host=host):
                self.assertRefused('DIRECT_NUMERIC_LOOPBACK_REQUIRED', r.connection_env, 'DOU_BACKUP_', CONNECTION | {'DOU_BACKUP_PGHOST': host})
        for port in ('0', '65536', '55448,5432', 'service', '-1'):
            with self.subTest(port=port):
                self.assertRefused('EXPLICIT_SINGLE_PORT_REQUIRED', r.connection_env, 'DOU_BACKUP_', CONNECTION | {'DOU_BACKUP_PGPORT': port})
        without_port = CONNECTION | {'DOU_BACKUP_PGPORT': ''}
        self.assertRefused('EXPLICIT_CONNECTION_ENV_REQUIRED', r.connection_env, 'DOU_BACKUP_', without_port)
        ipv6 = r.connection_env('DOU_BACKUP_', CONNECTION | {'DOU_BACKUP_PGHOST': '::1'})
        self.assertEqual(ipv6['PGHOSTADDR'], '::1')

    def test_backup_snapshot_lives_until_dump_finishes_then_same_connection_refreshes(self):
        control = FakeSourceConnection()
        seen_params = []
        def connect(**kwargs):
            self.assertFalse(any(key.startswith('PG') for key in os.environ))
            seen_params.append(kwargs)
            return control
        def fake(name, args, **kwargs):
            self.assertTrue(control.active)
            self.assertTrue(control.snapshot_live)
            self.assertFalse((self.bundle / r.MANIFEST).exists())
            if name == 'pg_dump':
                self.assertIn('--snapshot=' + SNAPSHOT_ID, args)
                self.assertEqual(kwargs['env']['PGHOSTADDR'], '127.0.0.1')
                self.assertNotIn(CANARY, json.dumps(args))
                kwargs['output'].write(ARCHIVE)
            return b''
        with patch.dict(os.environ, CONNECTION | {'PGSERVICE': CANARY, 'PGHOSTADDR': '192.0.2.1'}), patch.dict(sys.modules, {'psycopg': types.SimpleNamespace(connect=connect)}), patch.object(r, 'repository_lineage', return_value=LINEAGE), patch.object(r, 'command', side_effect=fake):
            result = r.backup(self.bundle, self.root)
            self.assertEqual(os.environ['PGSERVICE'], CANARY)
            self.assertEqual(os.environ['PGHOSTADDR'], '192.0.2.1')
        self.assertEqual(result['status'], 'backup-complete')
        self.assertEqual(len(seen_params), 1)
        self.assertEqual(seen_params[0]['password'], CANARY)
        self.assertEqual(seen_params[0]['host'], seen_params[0]['hostaddr'])
        self.assertEqual(seen_params[0]['port'], '55448')
        self.assertEqual(control.metadata_reads, 2)
        self.assertTrue(control.closed)
        self.assertLess(control.events.index('SELECT pg_export_snapshot()'), control.events.index('SELECT 1'))
        self.assertLess(control.events.index('SELECT 1'), control.events.index('COMMIT'))
        self.assertEqual(control.events[-3:], ['BEGIN READ ONLY', 'METADATA', 'COMMIT'])
        manifest = json.loads((self.bundle / r.MANIFEST).read_text())
        self.assertEqual(manifest['source_capture'], 'direct-loopback-exported-snapshot-v1')
        self.assertNotIn(CANARY, json.dumps(manifest))
        self.assertNotIn(SNAPSHOT_ID, json.dumps(manifest))

    def test_lost_snapshot_controller_never_finishes_manifest(self):
        control = FakeSourceConnection(fail_probe=True)
        def fake(name, args, **kwargs):
            if name == 'pg_dump': kwargs['output'].write(ARCHIVE)
            return b''
        with patch.dict(os.environ, CONNECTION), patch.dict(sys.modules, {'psycopg': types.SimpleNamespace(connect=lambda **_kwargs: control)}), patch.object(r, 'repository_lineage', return_value=LINEAGE), patch.object(r, 'command', side_effect=fake):
            self.assertRefused('SOURCE_SNAPSHOT_CONTROL_FAILED', r.backup, self.bundle, self.root)
        self.assertFalse((self.bundle / r.MANIFEST).exists())
        self.assertTrue(control.closed)

    def test_same_connection_fresh_metadata_identity_change_is_refused(self):
        after = copy.deepcopy(META); after['identity']['database_oid'] = '999'
        control = FakeSourceConnection(after=after)
        def fake(name, args, **kwargs):
            if name == 'pg_dump': kwargs['output'].write(ARCHIVE)
            return b''
        with patch.dict(os.environ, CONNECTION), patch.dict(sys.modules, {'psycopg': types.SimpleNamespace(connect=lambda **_kwargs: control)}), patch.object(r, 'repository_lineage', return_value=LINEAGE), patch.object(r, 'command', side_effect=fake):
            self.assertRefused('SOURCE_METADATA_CHANGED', r.backup, self.bundle, self.root)
        self.assertEqual(control.metadata_reads, 2)
        self.assertFalse((self.bundle / r.MANIFEST).exists())

    def test_controller_connect_failure_sanitizes_diagnostics_and_restores_pg_environment(self):
        with patch.dict(os.environ, CONNECTION | {'PGSERVICE': CANARY}), patch.dict(sys.modules, {'psycopg': types.SimpleNamespace(connect=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError(CANARY)))}), patch.object(r, 'repository_lineage', return_value=LINEAGE):
            self.assertRefused('SOURCE_SNAPSHOT_CONTROL_FAILED', r.backup, self.bundle, self.root)
            self.assertEqual(os.environ['PGSERVICE'], CANARY)
        self.assertFalse(self.bundle.exists())

    def test_missing_psycopg_is_explicit_and_cannot_create_bundle(self):
        with patch.dict(os.environ, CONNECTION), patch.dict(sys.modules, {'psycopg': None}), patch.object(r, 'repository_lineage', return_value=LINEAGE):
            self.assertRefused('BACKUP_PSYCOPG_RUNTIME_REQUIRED', r.backup, self.bundle, self.root)
        self.assertFalse(self.bundle.exists())

    def test_old_unbound_source_capture_is_refused_before_database_contact(self):
        manifest = self.fixture_bundle(); del manifest['source_capture']; self.write_manifest(manifest)
        with patch.dict(os.environ, CONNECTION), patch.object(r, 'metadata') as metadata, patch.object(r, 'command') as command:
            self.assertRefused('BOUND_SOURCE_CAPTURE_REQUIRED', r.restore, self.bundle, self.expected)
            metadata.assert_not_called(); command.assert_not_called()

    def test_tool_failure_does_not_disclose_stderr_or_stdout(self):
        tool = self.root / 'fake-psql'
        tool.write_text('#!/bin/sh\nprintf "%s" "$PGPASSWORD"\nprintf "%s" "$PGPASSWORD" >&2\nexit 1\n')
        tool.chmod(0o700)
        with patch.object(r, 'executable', return_value=str(tool)):
            self.assertRefused('DATABASE_TOOL_FAILED', r.command, 'psql', [])
            with self.assertRaises(r.Refused) as failure:
                r.command('psql', [], env={'PGPASSWORD': CANARY})
            self.assertNotIn(CANARY, str(failure.exception))

    def test_bundle_cannot_overwrite_or_follow_symlink_ancestors(self):
        self.bundle.mkdir()
        (self.bundle / 'keep').write_text('untouched')
        self.assertRefused('BUNDLE_EXISTS_OR_UNWRITABLE', r.new_bundle, self.bundle)
        self.assertEqual((self.bundle / 'keep').read_text(), 'untouched')
        alias = self.root / 'alias'; alias.symlink_to(self.bundle, target_is_directory=True)
        self.assertRefused('UNSAFE_BUNDLE_PATH', r.new_bundle, alias / 'nested')
        self.assertRefused('UNSAFE_BUNDLE_PATH', r.new_bundle, self.root / '..' / 'escape' / 'nested')
        self.assertFalse((self.bundle / 'nested').exists())

    def test_failed_dump_never_has_completed_manifest(self):
        def fake(name, args, **kwargs):
            if name == 'pg_dump':
                kwargs['output'].write(ARCHIVE[:7]); raise r.Refused('DATABASE_TOOL_FAILED')
            raise AssertionError('Unexpected tool after failed dump')
        with patch.dict(os.environ, CONNECTION), patch.object(r, 'source_snapshot', side_effect=fixture_snapshot), patch.object(r, 'repository_lineage', return_value=LINEAGE), patch.object(r, 'command', side_effect=fake):
            self.assertRefused('DATABASE_TOOL_FAILED', r.backup, self.bundle, self.root)
        self.assertFalse((self.bundle / r.MANIFEST).exists())
        self.assertEqual(stat.S_IMODE(self.bundle.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.bundle / r.DUMP).stat().st_mode), 0o600)

    def test_backup_manifest_only_after_archive_validation_and_stable_metadata(self):
        events = []
        def fake(name, args, **kwargs):
            events.append(name)
            self.assertFalse((self.bundle / r.MANIFEST).exists())
            self.assertNotIn(CANARY, json.dumps(args))
            if name == 'pg_dump': kwargs['output'].write(ARCHIVE)
            elif name == 'pg_restore': self.assertEqual(kwargs['input'].read(), ARCHIVE)
            return b''
        with patch.dict(os.environ, CONNECTION), patch.object(r, 'source_snapshot', side_effect=fixture_snapshot), patch.object(r, 'repository_lineage', return_value=LINEAGE), patch.object(r, 'command', side_effect=fake):
            result = r.backup(self.bundle, self.root)
        self.assertEqual(events, ['pg_dump', 'pg_restore'])
        self.assertEqual(result['source_identity_sha256'], self.expected)
        manifest = json.loads((self.bundle / r.MANIFEST).read_text())
        self.assertEqual(manifest['archive']['sha256'], hashlib.sha256(ARCHIVE).hexdigest())
        self.assertNotIn(CANARY, json.dumps(manifest))
        with tempfile.TemporaryFile() as output: r.verified_copy(self.bundle, self.expected, output)

    def test_metadata_drift_leaves_incomplete_bundle(self):
        changed = copy.deepcopy(META); changed['security_catalog_sha256'] = 'd' * 64
        def fake(name, args, **kwargs):
            if name == 'pg_dump': kwargs['output'].write(ARCHIVE)
            return b''
        with patch.dict(os.environ, CONNECTION), patch.object(r, 'source_snapshot', side_effect=lambda env: fixture_snapshot(env, after=changed)), patch.object(r, 'repository_lineage', return_value=LINEAGE), patch.object(r, 'command', side_effect=fake):
            self.assertRefused('SOURCE_METADATA_CHANGED', r.backup, self.bundle, self.root)
        self.assertFalse((self.bundle / r.MANIFEST).exists())

    def test_archive_hash_and_source_mismatch_before_any_database_contact(self):
        self.fixture_bundle()
        (self.bundle / r.DUMP).write_bytes(ARCHIVE + b'tampered')
        with patch.dict(os.environ, CONNECTION), patch.object(r, 'metadata') as metadata, patch.object(r, 'command') as command:
            self.assertRefused('ARCHIVE_HASH_MISMATCH', r.restore, self.bundle, self.expected)
            metadata.assert_not_called(); command.assert_not_called()
        with tempfile.TemporaryFile() as output:
            self.assertRefused('SOURCE_IDENTITY_MISMATCH', r.verified_copy, self.bundle, '0' * 64, output)

    def test_archive_manifest_path_traversal_and_incomplete_rejected(self):
        manifest = self.fixture_bundle(); manifest['archive']['name'] = '../database.dump'; self.write_manifest(manifest)
        with tempfile.TemporaryFile() as output:
            self.assertRefused('INVALID_MANIFEST', r.verified_copy, self.bundle, self.expected, output)
        (self.bundle / r.MANIFEST).unlink()
        with tempfile.TemporaryFile() as output:
            self.assertRefused('INCOMPLETE_OR_UNEXPECTED_BUNDLE_FILES', r.verified_copy, self.bundle, self.expected, output)

    def test_linked_or_public_files_are_rejected(self):
        self.fixture_bundle()
        dump = self.bundle / r.DUMP
        dump.chmod(0o644)
        with tempfile.TemporaryFile() as output:
            self.assertRefused('UNSAFE_BUNDLE_FILE', r.verified_copy, self.bundle, self.expected, output)
        dump.chmod(0o600); linked = self.root / 'link'; os.link(dump, linked)
        with tempfile.TemporaryFile() as output:
            self.assertRefused('UNSAFE_BUNDLE_FILE', r.verified_copy, self.bundle, self.expected, output)
        linked.unlink(); dump.unlink(); dump.symlink_to(self.root / 'missing')
        with tempfile.TemporaryFile() as output:
            self.assertRefused('UNSAFE_BUNDLE_FILE', r.verified_copy, self.bundle, self.expected, output)

    def test_verified_private_copy_survives_original_path_replacement(self):
        self.fixture_bundle()
        with tempfile.TemporaryFile() as output:
            r.verified_copy(self.bundle, self.expected, output)
            (self.bundle / r.DUMP).unlink(); (self.bundle / r.DUMP).write_bytes(b'PGDMPnew-untrusted-content')
            self.assertEqual(output.read(), ARCHIVE)

    def test_preflight_rejects_alias_nonempty_role_and_format_drift(self):
        cases = [('SOURCE_EQUALS_TARGET', lambda t: t['identity'].update(database_oid='400', database_name='alias')),
                 ('TARGET_NOT_EMPTY', lambda t: t.update(empty=False)),
                 ('DBA_SUPERUSER_REQUIRED', lambda t: t.update(superuser=False)),
                 ('OTHER_TARGET_CONNECTIONS', lambda t: t.update(other_connections=1)),
                 ('ROLE_ATTRIBUTES_MISSING_OR_DIFFERENT', lambda t: t['roles'][0].update(bypass_rls=False)),
                 ('ROLE_ATTRIBUTES_MISSING_OR_DIFFERENT', lambda t: t.update(roles=[])),
                 ('ROLE_MEMBERSHIPS_DIFFERENT', lambda t: t['memberships'].append({'member': 'synthetic_dba', 'role': 'extra'})),
                 ('EXTENSION_DEFAULT_VERSION_MISMATCH', lambda t: t.update(available_extensions=[])),
                 ('DATABASE_FORMAT_MISMATCH', lambda t: t['database_format'].update(encoding='LATIN1')),
                 ('CUSTOM_TARGET_DATABASE_SETTINGS_UNSUPPORTED', lambda t: t['database_settings'].append('custom'))]
        for code, mutation in cases:
            with self.subTest(code=code):
                target = target_meta(); mutation(target)
                self.assertRefused(code, r.preflight, self.source, target)

    def test_database_acl_distinguishes_public_pseudorole_and_quoted_role(self):
        source = copy.deepcopy(self.source); target = target_meta()
        source['database_acl'] = [
            {'grantee': 'PUBLIC', 'public': True, 'grantor': 'synthetic_dba', 'privilege': 'CONNECT', 'grantable': False},
            {'grantee': 'PUBLIC', 'public': False, 'grantor': 'synthetic_dba', 'privilege': 'CREATE', 'grantable': False},
        ]
        target['identity']['database_name'] = 'target"; SELECT secret; --'
        sql = r.database_acl_sql(source, target)
        self.assertIn('TO PUBLIC;', sql)
        self.assertIn('TO "PUBLIC";', sql)
        self.assertIn('DATABASE "target""; SELECT secret; --"', sql)
        self.assertNotIn('TO PUBLIC WITH GRANT OPTION', sql)

    def test_nonowner_database_grantor_refused_before_fence(self):
        source = copy.deepcopy(META)
        source['database_acl'][0]['grantor'] = 'other_grantor'
        self.assertRefused('NONOWNER_DATABASE_GRANTOR_UNSUPPORTED', r.source_metadata, source)
        target = target_meta(); target['database_acl'][0]['grantor'] = 'other_grantor'
        self.assertRefused('NONOWNER_TARGET_DATABASE_GRANTOR_UNSUPPORTED', r.preflight, self.source, target)

    def test_incoming_membership_component_includes_transitive_principals_only(self):
        captured = r.source_metadata(source_with_incoming_chain())
        self.assertEqual({role['name'] for role in captured['roles']},
                         {'synthetic_dba', 'expected_bridge', 'expected_login'})
        self.assertEqual({row['member'] for row in captured['memberships']},
                         {'expected_bridge', 'expected_login'})
        self.assertEqual(captured['role_membership_scope'], r.ROLE_SCOPE)
        r.validate_role_scope(captured)

    def test_identical_source_incoming_memberships_and_attributes_are_accepted(self):
        captured = r.source_metadata(source_with_incoming_chain())
        target = source_with_incoming_chain()
        target.update(identity=target_meta()['identity'], empty=True)
        r.preflight(captured, target)

    def test_unexpected_direct_incoming_login_is_rejected_before_fence(self):
        target = target_meta()
        target['roles'].append(named_role('synthetic_unexpected_login'))
        target['memberships'].append(membership('synthetic_unexpected_login', 'synthetic_dba'))
        self.assertRefused('ROLE_MEMBERSHIPS_DIFFERENT', r.preflight, self.source, target)

    def test_transitive_incoming_login_and_existing_edge_flag_changes_are_rejected(self):
        captured = r.source_metadata(source_with_incoming_chain())
        for mutation in ('incoming', 'set', 'inherit', 'admin', 'attributes'):
            with self.subTest(mutation=mutation):
                target = source_with_incoming_chain()
                target.update(identity=target_meta()['identity'], empty=True)
                expected_code = 'ROLE_MEMBERSHIPS_DIFFERENT'
                if mutation == 'incoming':
                    target['roles'].append(named_role('synthetic_unexpected_login'))
                    target['memberships'].append(membership('synthetic_unexpected_login', 'expected_login'))
                elif mutation == 'attributes':
                    next(role for role in target['roles'] if role['name'] == 'expected_login')['bypass_rls'] = True
                    expected_code = 'ROLE_ATTRIBUTES_MISSING_OR_DIFFERENT'
                else:
                    target['memberships'][0][mutation] = not target['memberships'][0][mutation]
                self.assertRefused(expected_code, r.preflight, captured, target)

    def test_unrelated_membership_component_does_not_block_restore(self):
        captured = r.source_metadata(source_with_incoming_chain())
        target = source_with_incoming_chain()
        target.update(identity=target_meta()['identity'], empty=True)
        target['roles'].append(named_role('unrelated_new_login'))
        target['memberships'].append(membership('unrelated_new_login', 'unrelated_group'))
        r.preflight(captured, target)

    def test_missing_transitive_role_metadata_cannot_be_silently_omitted(self):
        meta = source_with_incoming_chain()
        meta['roles'] = [role for role in meta['roles'] if role['name'] != 'expected_login']
        self.assertRefused('REQUIRED_ROLE_METADATA_MISSING', r.source_metadata, meta)

    def test_old_one_direction_manifest_is_refused_before_target_contact(self):
        manifest = self.fixture_bundle()
        del manifest['source']['role_membership_scope']
        self.write_manifest(manifest)
        with patch.dict(os.environ, CONNECTION), patch.object(r, 'metadata') as metadata, patch.object(r, 'command') as command:
            self.assertRefused('ROLE_MEMBERSHIP_SCOPE_REQUIRED', r.restore, self.bundle, self.expected)
            metadata.assert_not_called(); command.assert_not_called()

    def test_sql_race_guards_include_incoming_and_outgoing_edges(self):
        captured = r.source_metadata(source_with_incoming_chain())
        for sql in (r.restore_guard(captured, target_meta(), fenced=False),
                    r.restore_guard(captured, target_meta(), fenced=True), r.security_verify(captured)):
            self.assertIn("? (value->>'member') OR", sql)
            self.assertIn("? (value->>'role')", sql)
            self.assertIn('expected_login', sql)



if __name__ == '__main__':
    unittest.main(verbosity=2)
