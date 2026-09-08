"""İki bağlantılı restore adayının çevrimdışı protokol ve gizlilik kontrolleri."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import re
import tempfile
import types
import unittest
import sys
from unittest.mock import patch

import test_recovery as baseline

ARCHIVE, CANARY, CONNECTION, r, target_meta = (baseline.ARCHIVE, baseline.CANARY, baseline.CONNECTION, baseline.r, baseline.target_meta)


def bindings():
    target_env, maintenance_env = r.restore_environments()
    common = {'system_identifier': '100', 'postmaster_start': '1234567890.123456',
              'backend_start': '1234567891.123456', 'server_port': 55448, 'superuser': True}
    target = common | {'database_oid': '401', 'database_name': 'synthetic_target', 'pid': 101,
                      'user': 'synthetic_dba', 'application_name': target_env['PGAPPNAME']}
    maintenance = common | {'database_oid': '402', 'database_name': 'synthetic_maintenance', 'pid': 102,
                           'user': 'synthetic_dba', 'application_name': maintenance_env['PGAPPNAME']}
    return target_env, maintenance_env, target, maintenance


def state(target, maintenance, allowed):
    return {'maintenance': copy.deepcopy(maintenance), 'target': {
        'database_oid': target['database_oid'], 'database_name': target['database_name'],
        'connections_allowed': allowed, 'sessions': [
            {key: target[key] for key in ('pid', 'backend_start', 'user', 'application_name')}]}}


class FakeMaintenance:
    """SQL semantiği kanıtı değildir; gerçek orkestrasyonun yan etkilerini kaydeder."""
    def __init__(self, target, maintenance, events, fail_commit=False):
        self.target = target
        self.binding = maintenance
        self.events = events
        self.allowed = True
        self.committed_allowed = True
        self.fail_commit = fail_commit

    def __enter__(self):
        self.events.append('maintenance-open')
        return self

    def __exit__(self, *_args):
        self.events.append('maintenance-close')

    def execute(self, sql):
        self.events.append(sql)
        value = None
        if sql == 'SELECT ' + r.SESSION_BINDING_SQL:
            value = self.binding
        elif sql.startswith("SELECT jsonb_build_object('maintenance',"):
            value = state(self.target, self.binding, self.allowed)
        elif sql.startswith('ALTER DATABASE '):
            self.allowed = sql.endswith('true')
        elif sql == 'COMMIT':
            self.committed_allowed = self.allowed
            if self.fail_commit:
                raise RuntimeError(CANARY)
        elif sql == 'ROLLBACK':
            self.allowed = self.committed_allowed
        return types.SimpleNamespace(fetchone=lambda: (value,))


class RestoreProtocolContracts(unittest.TestCase):
    setUp = baseline.RecoveryContracts.setUp
    fixture_bundle = baseline.RecoveryContracts.fixture_bundle
    write_manifest = baseline.RecoveryContracts.write_manifest
    assertRefused = baseline.RecoveryContracts.assertRefused

    def test_maintenance_route_is_explicit_distinct_and_same_numeric_endpoint(self):
        with patch.dict(os.environ, CONNECTION):
            target, maintenance = r.restore_environments()
            self.assertEqual(target['PGPORT'], maintenance['PGPORT'])
            self.assertNotEqual(target['PGAPPNAME'], maintenance['PGAPPNAME'])
            self.assertNotIn('DOU_MAINTENANCE_PGPASSWORD', target)
        for replacement, code in (
            ({'DOU_MAINTENANCE_PGDATABASE': ''}, 'EXPLICIT_CONNECTION_ENV_REQUIRED'),
            ({'DOU_MAINTENANCE_PGDATABASE': 'synthetic_target'}, 'MAINTENANCE_DATABASE_MUST_DIFFER'),
            ({'DOU_MAINTENANCE_PGHOST': '127.0.0.2'}, 'MAINTENANCE_ENDPOINT_MISMATCH'),
            ({'DOU_MAINTENANCE_PGPORT': '55449'}, 'MAINTENANCE_ENDPOINT_MISMATCH'),
        ):
            with self.subTest(code=code), patch.dict(os.environ, CONNECTION | replacement):
                self.assertRefused(code, r.restore_environments)

    def test_all_physical_session_identity_fields_are_required(self):
        with patch.dict(os.environ, CONNECTION):
            target_env, _, target, _ = bindings()
        r.validate_binding(target, target_env)
        for key, value in (
            ('database_oid', 401), ('database_name', 'other'), ('pid', True), ('pid', 0),
            ('backend_start', ''), ('postmaster_start', ''), ('system_identifier', '-1'),
            ('user', 'other'), ('application_name', 'other'), ('superuser', False),
            ('server_port', 55449), ('server_port', '55448'),
        ):
            with self.subTest(key=key, value=value):
                self.assertRefused('INVALID_SESSION_BINDING', r.validate_binding,
                                   target | {key: value}, target_env)

    def test_identity_session_count_and_fence_negatives_precede_alter(self):
        with patch.dict(os.environ, CONNECTION):
            _, _, target, maintenance = bindings()
        mutations = [
            ('maintenance oid', lambda s: s['maintenance'].update(database_oid='999')),
            ('maintenance pid', lambda s: s['maintenance'].update(pid=999)),
            ('target missing', lambda s: s.update(target=None)),
            ('target oid', lambda s: s['target'].update(database_oid='999')),
            ('target name', lambda s: s['target'].update(database_name='replaced')),
            ('fence', lambda s: s['target'].update(connections_allowed=False)),
            ('target pid', lambda s: s['target']['sessions'][0].update(pid=999)),
            ('target start', lambda s: s['target']['sessions'][0].update(backend_start='0')),
            ('target app', lambda s: s['target']['sessions'][0].update(application_name='other')),
            ('no session', lambda s: s['target'].update(sessions=[])),
            ('extra session', lambda s: s['target']['sessions'].append({})),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                bad = state(target, maintenance, True)
                mutate(bad)
                events = []
                connection = FakeMaintenance(target, maintenance, events)
                with patch.object(r, 'maintenance_state', return_value=bad), self.assertRaises(r.Refused):
                    r.set_target_fence(connection, maintenance, target, allowed=False)
                self.assertFalse(any(sql.startswith('ALTER DATABASE') for sql in events))
        for key, value in (('system_identifier', '999'), ('postmaster_start', '0'), ('server_port', 1)):
            with self.subTest(key=key):
                changed = maintenance | {key: value}
                self.assertRefused('MAINTENANCE_CLUSTER_MISMATCH',
                    lambda: r.validate_maintenance_state(state(target, changed, True), changed,
                                                        target, allowed=True))
        changed = maintenance | {'database_oid': target['database_oid']}
        self.assertRefused('MAINTENANCE_DATABASE_MUST_DIFFER',
            lambda: r.validate_maintenance_state(state(target, changed, True), changed,
                                                target, allowed=True))

    def test_fence_commit_is_separate_and_fresh_state_is_checked_after_commit(self):
        with patch.dict(os.environ, CONNECTION):
            _, _, target, maintenance = bindings()
        events = []
        connection = FakeMaintenance(target, maintenance, events)
        r.set_target_fence(connection, maintenance, target, allowed=False)
        alter = next(i for i, item in enumerate(events) if item.startswith('ALTER DATABASE '))
        lock = events.index('LOCK TABLE pg_catalog.pg_database IN SHARE ROW EXCLUSIVE MODE')
        commit = events.index('COMMIT')
        self.assertLess(lock, alter)
        self.assertLess(alter, commit)
        self.assertEqual(events.count('SELECT pg_stat_clear_snapshot()'), 3)
        self.assertGreater(len(events) - 1, commit)
        self.assertFalse(connection.committed_allowed)
        self.assertNotIn('ALLOW_CONNECTIONS true', '\n'.join(events))
        self.assertIn("SET LOCAL lock_timeout='5s'", events)

    def test_generated_maintenance_query_has_balanced_sql_parentheses(self):
        # Tam PostgreSQL parseri değildir; ölçülmüş ekstra parantez kusurunu kilitler.
        with patch.dict(os.environ, CONNECTION):
            _, _, target, maintenance = bindings()
        events = []
        connection = FakeMaintenance(target, maintenance, events)
        r.maintenance_state(connection, target)
        query = events[-1]
        depth = 0
        for match in re.finditer(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[()]", query):
            token = match.group()
            if token == '(':
                depth += 1
            elif token == ')':
                depth -= 1
                self.assertGreaterEqual(depth, 0)
        self.assertEqual(depth, 0)

    def test_lost_fence_commit_ack_does_not_attempt_opposite_alter(self):
        with patch.dict(os.environ, CONNECTION):
            _, _, target, maintenance = bindings()
        events = []
        connection = FakeMaintenance(target, maintenance, events, fail_commit=True)
        with self.assertRaises(RuntimeError):
            r.set_target_fence(connection, maintenance, target, allowed=False)
        self.assertFalse(connection.committed_allowed)
        self.assertEqual([item for item in events if item.startswith('ALTER DATABASE')],
                         ['ALTER DATABASE "synthetic_target" ALLOW_CONNECTIONS false'])

    def fake_restore(self, failure=None, target_override=None, generated_sql=None):
        self.fixture_bundle()
        events = []
        with patch.dict(os.environ, CONNECTION):
            target_env, maintenance_env, target_binding, maintenance_binding = bindings()
        maint = FakeMaintenance(target_binding, maintenance_binding, events,
                                fail_commit=failure == 'fence-commit')
        observed = {}
        owner = self

        class FakeTarget:
            def __init__(self, env, script):
                owner.assertEqual(env, target_env)
                self.script = script

            def __enter__(self):
                events.append('target-open')
                return self

            def __exit__(self, *_args):
                events.append('target-close')

            def ready(self):
                events.append('target-ready')
                return target_override or target_meta(), target_binding

            def guard(self, source, target):
                events.append('target-pre-fence-guard')
                if failure == 'pre-guard':
                    raise r.Refused('TARGET_NOT_EMPTY_OR_UNAUTHORIZED')

            def apply(self, marker, expected_binding):
                owner.assertFalse(maint.committed_allowed)
                owner.assertEqual(expected_binding, target_binding)
                self.script.seek(0)
                observed['script'] = self.script.read().decode()
                observed['marker'] = marker
                events.append('restore-start')
                if failure in ('restore', 'commit-unknown'):
                    raise r.Refused('RESTORE_TARGET_EXITED_WITHOUT_RECEIPT')
                events.append('commit-confirmed')
                if failure == 'reopen-identity':
                    maint.binding = maintenance_binding | {'pid': 999}

        def command(name, args, **kwargs):
            owner.assertEqual(name, 'pg_restore')
            owner.assertEqual(kwargs['input'].read(), ARCHIVE)
            owner.assertNotIn(CANARY, json.dumps(args))
            events.append((name, args))
            if 'output' in kwargs:
                kwargs['output'].write(generated_sql or b'-- synthetic restored SQL boundary\nSELECT 1;\n')
            return b''

        with (patch.object(r, 'restore_environments', return_value=(target_env, maintenance_env)),
              patch.object(r, 'TargetSession', FakeTarget), patch.object(r, 'command', side_effect=command),
              patch.object(r, 'control_connection', return_value=maint)):
            try:
                observed['result'] = r.restore(self.bundle, self.expected)
            except r.Refused as error:
                observed['error'] = str(error)
        return events, observed

    def test_nonempty_and_pre_guard_failure_are_never_fenced(self):
        target = target_meta()
        target['empty'] = False
        events, seen = self.fake_restore(target_override=target)
        self.assertEqual(seen['error'], 'TARGET_NOT_EMPTY')
        self.assertNotIn('maintenance-open', events)
        self.assertNotIn('restore-start', events)

    def test_real_orchestrator_orders_guard_fence_restore_commit_reopen(self):
        events, seen = self.fake_restore()
        self.assertEqual(seen['result']['status'], 'restore-complete')
        self.assertEqual(seen['result']['commit_status'], 'committed')
        positions = [events.index(event) for event in (
            'target-open', 'target-ready', 'target-pre-fence-guard', 'maintenance-open',
            'ALTER DATABASE "synthetic_target" ALLOW_CONNECTIONS false',
            'restore-start', 'commit-confirmed',
            'ALTER DATABASE "synthetic_target" ALLOW_CONNECTIONS true', 'target-close')]
        self.assertEqual(positions, sorted(positions))
        script = seen['script']
        self.assertNotIn('ALLOW_CONNECTIONS', script)
        self.assertNotIn('DROP DATABASE', script)
        self.assertNotIn(CANARY, script)
        self.assertEqual(script.count('BEGIN;'), 1)
        self.assertEqual(script.count('\nCOMMIT;'), 1)
        self.assertLess(script.index('TARGET_IDENTITY_CHANGED'), script.index('-- synthetic restored SQL'))
        self.assertIn("IF (m->>'connections_allowed')::boolean IS TRUE", script)
        self.assertIn('OTHER_TARGET_CONNECTIONS', script)
        self.assertIn("? (value->>'member') OR", script)
        self.assertIn('DATABASE_OWNER_OR_ACL_MISMATCH', script)
        self.assertLess(script.index('RESTORED_SECURITY_CATALOG_MISMATCH'), script.index('\nCOMMIT;'))
        self.assertLess(script.index('\nCOMMIT;'), script.index("pg_xact_status(:'dou_restore_xid'::xid8)"))
        self.assertIn("pg_current_xact_id()::text AS dou_restore_xid \\gset", script)
        self.assertIn('SET ROLE "synthetic_dba"', script)
        self.assertLess(script.index('ALTER DATABASE "synthetic_target" OWNER TO'),
                        script.index('-- synthetic restored SQL boundary'))
        self.assertEqual(events[1][1], ['--exit-on-error', '--file=-'])
        self.assertNotIn('--use-set-session-authorization', events[1][1])
        self.assertFalse(any(flag in json.dumps(events[:2]) for flag in
                             ('--clean', '--create', '--no-owner', '--no-acl')))

    def test_restore_failure_cannot_reopen_or_claim_commit(self):
        events, seen = self.fake_restore('restore')
        self.assertEqual(seen['error'], 'RESTORE_FAILED_REVIEW_FENCE_AND_TRANSACTION_STATE')
        self.assertNotIn('ALTER DATABASE "synthetic_target" ALLOW_CONNECTIONS true', events)
        self.assertNotIn('commit-confirmed', events)
        self.assertEqual(events[-1], 'target-close')

    def test_default_owner_transfer_and_source_restricted_role_remain_in_script(self):
        # Bu çıktı sentetik pg_restore fixture'ıdır; gerçek CREATE yetkisini kanıtlamaz.
        restricted = baseline.named_role('dou_auth_bridge', login=False)
        self.source['roles'].append(restricted)
        self.source['required_role_seeds'].append('dou_auth_bridge')
        target = target_meta()
        target['roles'].append(restricted)
        generated = (b'-- synthetic restored SQL boundary\n'
                     b'CREATE FUNCTION app.synthetic_sync() RETURNS void LANGUAGE sql '
                     b'SECURITY DEFINER AS $$ SELECT NULL; $$;\n'
                     b'ALTER FUNCTION app.synthetic_sync() OWNER TO dou_auth_bridge;\n')
        events, seen = self.fake_restore(target_override=target, generated_sql=generated)
        self.assertEqual(seen['result']['status'], 'restore-complete')
        self.assertIn(generated.decode(), seen['script'])
        self.assertIn('SECURITY DEFINER', seen['script'])
        self.assertIn('ALTER FUNCTION app.synthetic_sync() OWNER TO dou_auth_bridge;', seen['script'])
        self.assertIn('RESTORED_SECURITY_CATALOG_MISMATCH', seen['script'])
        self.assertIn('RESTORED_ROLE_ATTRIBUTES_CHANGED', seen['script'])
        self.assertNotIn('--use-set-session-authorization', events[1][1])
        self.assertNotIn('--no-owner', events[1][1])
        self.assertNotIn('--no-acl', events[1][1])
        self.assertNotIn('GRANT CREATE ON SCHEMA', seen['script'])
        self.assertNotIn("SET SESSION AUTHORIZATION 'dou_auth_bridge'", seen['script'])

    def test_unknown_commit_cannot_reopen(self):
        events, seen = self.fake_restore('commit-unknown')
        self.assertEqual(seen['error'], 'RESTORE_FAILED_REVIEW_FENCE_AND_TRANSACTION_STATE')
        self.assertNotIn('ALTER DATABASE "synthetic_target" ALLOW_CONNECTIONS true', events)

    def test_lost_fence_commit_cannot_start_restore(self):
        events, seen = self.fake_restore('fence-commit')
        self.assertEqual(seen['error'], 'RESTORE_FAILED_REVIEW_FENCE_AND_TRANSACTION_STATE')
        self.assertNotIn('restore-start', events)
        self.assertNotIn('ALTER DATABASE "synthetic_target" ALLOW_CONNECTIONS true', events)

    def test_committed_reopen_failure_is_truthfully_distinct(self):
        events, seen = self.fake_restore('reopen-identity')
        self.assertEqual(seen['error'], 'RESTORE_COMMITTED_FENCE_REOPEN_UNCONFIRMED')
        self.assertIn('commit-confirmed', events)
        self.assertNotIn('ALTER DATABASE "synthetic_target" ALLOW_CONNECTIONS true', events)

    def test_commit_receipt_requires_server_committed_xid_and_exact_session_binding(self):
        with patch.dict(os.environ, CONNECTION):
            target_env, _, target, _ = bindings()
        valid = {'commit_status': 'committed', 'xid': '12345', 'binding': target}
        for mutation in (None, 'status', 'binding', 'xid', 'extra'):
            with self.subTest(mutation=mutation), tempfile.TemporaryFile() as script:
                session = r.TargetSession(target_env, script)
                receipt = copy.deepcopy(valid)
                if mutation == 'status': receipt['commit_status'] = 'in progress'
                if mutation == 'binding': receipt['binding']['pid'] += 1
                if mutation == 'xid': receipt['xid'] = 12345
                if mutation == 'extra': receipt['untrusted'] = True
                with patch.object(session, 'send') as send, patch.object(session, 'wait_json', return_value=receipt):
                    if mutation:
                        self.assertRefused('RESTORE_COMMIT_NOT_CONFIRMED', session.apply, 'nonce', target)
                    else:
                        session.apply('nonce', target)
                    self.assertEqual(send.call_args.args, (f'\\i /dev/fd/{script.fileno()}\n',))

    def transport(self, payload, marker='DOU_EXPECTED', close=True):
        read_fd, write_fd = os.pipe()
        reader = os.fdopen(read_fd, 'rb', buffering=0)
        output = tempfile.TemporaryFile()
        self.addCleanup(reader.close)
        self.addCleanup(output.close)
        session = r.TargetSession({}, output)
        session.process = types.SimpleNamespace(stdout=reader)
        session.output = output
        os.write(write_fd, payload)
        if close:
            os.close(write_fd)
        else:
            self.addCleanup(os.close, write_fd)
        return session, marker

    def test_protocol_ignores_wrong_nonce_or_embedded_prefix_and_accepts_exact_line(self):
        session, marker = self.transport((CANARY + '\nDOU_WRONG:{"ok":true}\n' +
            'prefix DOU_EXPECTED:{"wrong":true}\nDOU_EXPECTED:{"ok":true}\n').encode())
        self.assertEqual(session.wait_json(marker), {'ok': True})

    def test_protocol_rejects_malformed_nonobject_and_missing_receipt_without_disclosure(self):
        for payload, expected in (
            (b'DOU_EXPECTED:{broken secret}\n', 'INVALID_RESTORE_PROTOCOL_JSON'),
            (b'DOU_EXPECTED:[]\n', 'INVALID_RESTORE_PROTOCOL_JSON'),
            (b'DOU_EXPECTED:{"ok":true} trailing\n', 'INVALID_RESTORE_PROTOCOL_JSON'),
            ((CANARY + '\n').encode(), 'RESTORE_TARGET_EXITED_WITHOUT_RECEIPT'),
        ):
            with self.subTest(expected=expected):
                session, marker = self.transport(payload)
                self.assertRefused(expected, session.wait_json, marker)

    def test_protocol_timeout_and_oversized_line_are_bounded(self):
        session, marker = self.transport(b'x', close=False)
        with patch.object(r, 'PHASE_TIMEOUT_SECONDS', 0):
            self.assertRefused('RESTORE_PROTOCOL_TIMEOUT', session.wait_json, marker)
        session, marker = self.transport(b'long private line\n')
        with patch.object(r, 'MAX_PROTOCOL_LINE', 4):
            self.assertRefused('RESTORE_PROTOCOL_LINE_TOO_LARGE', session.wait_json, marker)

    def test_actual_child_reads_only_inherited_anonymous_fd_and_keeps_output_private(self):
        # Bu küçük Python çocuk PostgreSQL değildir; POSIX FD/boru aktarımını ölçer.
        tool = self.root / 'fake-psql'
        tool.write_text('#!' + sys.executable + '\n' + '''import sys, os, json
for line in sys.stdin:
    if line.startswith("\\\\i /dev/fd/"):
        fd = int(line.strip().rsplit("/", 1)[1])
        data = json.loads(os.read(fd, 65536))
        print("private synthetic output", flush=True)
        print("private synthetic stderr", file=sys.stderr, flush=True)
        print(data["marker"] + ":" + json.dumps(data["receipt"]), flush=True)
''')
        tool.chmod(0o700)
        with patch.dict(os.environ, CONNECTION):
            env, _, binding, _ = bindings()
        marker = 'DOU_COMMITTED_synthetic_transport_nonce'
        receipt = {'commit_status': 'committed', 'xid': '54321', 'binding': binding}
        with tempfile.TemporaryFile() as script:
            script.write(json.dumps({'marker': marker, 'receipt': receipt}).encode())
            script.flush()
            script.seek(0)
            with patch.object(r, 'executable', return_value=str(tool)):
                with r.TargetSession(env, script) as target:
                    target.apply(marker, binding)
                    target.output.seek(0)
                    self.assertIn(b'private synthetic output', target.output.read())
                    target.errors.seek(0)
                    self.assertIn(b'private synthetic stderr', target.errors.read())
                    self.assertEqual(os.fstat(target.errors.fileno()).st_mode & 0o777, 0o600)
                    child = target.process
                self.assertEqual(child.returncode, 0)

    def test_failure_terminates_only_owned_live_child_without_waiting_for_script_completion(self):
        tool = self.root / 'fake-psql-wait'
        tool.write_text('#!' + sys.executable + '\n' + '''import sys
print('DOU_CHILD_READY:{"ready":true}', flush=True)
for line in sys.stdin:
    pass
''')
        tool.chmod(0o700)
        with tempfile.TemporaryFile() as script, patch.object(r, 'executable', return_value=str(tool)):
            with self.assertRaisesRegex(r.Refused, 'SYNTHETIC_STOP'):
                with r.TargetSession({}, script) as target:
                    self.assertEqual(target.wait_json('DOU_CHILD_READY'), {'ready': True})
                    child = target.process
                    raise r.Refused('SYNTHETIC_STOP')
            self.assertEqual(child.returncode, -r.signal.SIGTERM)

    def test_sigterm_enters_cleanup_path_and_restores_previous_handler(self):
        original = r.signal.getsignal(r.signal.SIGTERM)
        with self.assertRaisesRegex(r.Refused, 'RECOVERY_INTERRUPTED'):
            with r.restore_interruption():
                handler = r.signal.getsignal(r.signal.SIGTERM)
                self.assertIsNot(handler, original)
                handler(r.signal.SIGTERM, None)
        self.assertIs(r.signal.getsignal(r.signal.SIGTERM), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
