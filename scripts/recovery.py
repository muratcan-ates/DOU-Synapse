#!/usr/bin/env python3
"""DBA recovery candidate: no network until --execute; no secrets in diagnostics.

Archives contain personal data and executable SQL. Hashes detect corruption only.
Only an operator's trusted own archive is supported. This is a PostgreSQL bundle,
not storage/auth-provider backup, retention policy, PITR or production certification.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import select
import signal
import time
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Any, BinaryIO

FORMAT = "dou-synapse-postgres-v1"
DUMP = "database.dump"
MANIFEST = "manifest.json"
ROLE_SCOPE = "membership-connected-component-v1"
HEX = re.compile(r"^[a-f0-9]{64}$")
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
DIRECTORY = getattr(os, "O_DIRECTORY", 0)
FIELDS = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PGPASSFILE", "PGSSLMODE", "PGSSLROOTCERT", "PGSSLCERT", "PGSSLKEY", "PGCONNECT_TIMEOUT")


class Refused(Exception):
    """Only fixed, non-sensitive reason codes cross the CLI output boundary."""


def fail(code: str) -> None:
    raise Refused(code)


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def acl_sql(column: str, kind: str, owner: str) -> str:
    return f"""(SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'grantee', CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END, 'public', a.grantee=0,
      'grantor', pg_get_userbyid(a.grantor), 'privilege', a.privilege_type, 'grantable', a.is_grantable)
      ORDER BY (a.grantee=0), pg_get_userbyid(a.grantee), pg_get_userbyid(a.grantor), a.privilege_type), '[]'::jsonb)
      FROM aclexplode(COALESCE({column}, acldefault({kind}, {owner}))) a)"""


# Object security metadata only: no data rows, SQL error bodies or passwords.
# Role names/grant definitions stay in the private bundle, never CLI diagnostics.
CATALOG = f"""jsonb_build_object(
 'schemas', (SELECT COALESCE(jsonb_agg(jsonb_build_array(n.nspname,pg_get_userbyid(n.nspowner),
   {acl_sql('n.nspacl', "'n'", 'n.nspowner')}) ORDER BY n.nspname),'[]'::jsonb)
   FROM pg_namespace n WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
 'relations', (SELECT COALESCE(jsonb_agg(jsonb_build_array(n.nspname,c.relname,c.relkind,
   pg_get_userbyid(c.relowner),c.relrowsecurity,c.relforcerowsecurity,
   {acl_sql('c.relacl', "CASE WHEN c.relkind='S' THEN 's'::\"char\" ELSE 'r'::\"char\" END", 'c.relowner')})
   ORDER BY n.nspname,c.relname),'[]'::jsonb) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' AND c.relkind IN ('r','p','v','m','S','f')),
 'column_acls', (SELECT COALESCE(jsonb_agg(jsonb_build_array(n.nspname,c.relname,a.attname,
   (SELECT jsonb_agg(jsonb_build_array(pg_get_userbyid(x.grantee),pg_get_userbyid(x.grantor),x.privilege_type,x.is_grantable)
   ORDER BY pg_get_userbyid(x.grantee),pg_get_userbyid(x.grantor),x.privilege_type) FROM aclexplode(a.attacl) x))
   ORDER BY n.nspname,c.relname,a.attnum),'[]'::jsonb) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
   JOIN pg_namespace n ON n.oid=c.relnamespace WHERE a.attacl IS NOT NULL AND NOT a.attisdropped
   AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
 'default_acls', (SELECT COALESCE(jsonb_agg(jsonb_build_array(pg_get_userbyid(d.defaclrole),n.nspname,d.defaclobjtype,
   (SELECT jsonb_agg(jsonb_build_array(pg_get_userbyid(x.grantee),pg_get_userbyid(x.grantor),x.privilege_type,x.is_grantable)
   ORDER BY pg_get_userbyid(x.grantee),pg_get_userbyid(x.grantor),x.privilege_type) FROM aclexplode(d.defaclacl) x))
   ORDER BY pg_get_userbyid(d.defaclrole),n.nspname,d.defaclobjtype),'[]'::jsonb) FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace),
 'policies', (SELECT COALESCE(jsonb_agg(jsonb_build_array(schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check)
   ORDER BY schemaname,tablename,policyname),'[]'::jsonb) FROM pg_policies),
 'functions', (SELECT COALESCE(jsonb_agg(jsonb_build_array(n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),
   pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig,{acl_sql('p.proacl', "'f'", 'p.proowner')})
   ORDER BY n.nspname,p.proname,pg_get_function_identity_arguments(p.oid)),'[]'::jsonb)
   FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'),
 'indexes', (SELECT COALESCE(jsonb_agg(jsonb_build_array(schemaname,tablename,indexname,indexdef)
   ORDER BY schemaname,tablename,indexname),'[]'::jsonb) FROM pg_indexes WHERE schemaname !~ '^pg_' AND schemaname <> 'information_schema')
)"""
# A bare template0 database has no normal user OIDs in these object catalogs.
# This also rejects user objects hidden in pg_catalog, casts and languages that
# a namespace-only check would miss. This conservative v1 fence is PG16/local DBA.
USER_OBJECT_CATALOGS = ('pg_class', 'pg_proc', 'pg_type', 'pg_namespace', 'pg_operator',
    'pg_opclass', 'pg_opfamily', 'pg_collation', 'pg_conversion', 'pg_ts_config',
    'pg_ts_dict', 'pg_ts_parser', 'pg_ts_template', 'pg_cast', 'pg_transform', 'pg_language')
USER_OBJECTS_EMPTY = ' AND '.join(f'NOT EXISTS (SELECT 1 FROM {catalog} WHERE oid >= 16384)' for catalog in USER_OBJECT_CATALOGS)
EMPTY = """NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname NOT IN ('public','information_schema'))
 AND NOT EXISTS (SELECT 1 FROM pg_depend WHERE refclassid='pg_namespace'::regclass AND refobjid=(SELECT oid FROM pg_namespace WHERE nspname='public'))
 AND NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql')
 AND NOT EXISTS (SELECT 1 FROM pg_largeobject_metadata)
 AND NOT EXISTS (SELECT 1 FROM pg_event_trigger)
 AND NOT EXISTS (SELECT 1 FROM pg_publication)
 AND NOT EXISTS (SELECT 1 FROM pg_subscription)
 AND NOT EXISTS (SELECT 1 FROM pg_foreign_server)
 AND NOT EXISTS (SELECT 1 FROM pg_foreign_data_wrapper)
 AND NOT EXISTS (SELECT 1 FROM pg_default_acl)""" + ' AND ' + USER_OBJECTS_EMPTY
SNAPSHOT_SQL = f"""WITH RECURSIVE needed(oid) AS (
 SELECT datdba FROM pg_database WHERE datname=current_database()
 UNION SELECT m.roleid FROM pg_auth_members m JOIN needed n ON m.member=n.oid
), object_roles AS (
 SELECT oid FROM needed UNION SELECT refobjid FROM pg_shdepend
 WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) AND refclassid='pg_authid'::regclass
), closure(oid) AS (
 SELECT oid FROM object_roles UNION SELECT m.roleid FROM pg_auth_members m JOIN closure c ON m.member=c.oid
)
SELECT jsonb_build_object(
 'identity',jsonb_build_object('system_identifier',(SELECT system_identifier::text FROM pg_control_system()),
   'database_oid',d.oid::text,'database_name',d.datname),
 'server_version_num',current_setting('server_version_num')::int,
 'database_format',jsonb_build_object('encoding',pg_encoding_to_char(d.encoding),'locale_provider',d.datlocprovider,
   'collate',d.datcollate,'ctype',d.datctype,'icu_locale',d.daticulocale,'collation_version',d.datcollversion,
   'default_tablespace',(SELECT spcname FROM pg_tablespace WHERE oid=d.dattablespace),'connection_limit',d.datconnlimit,'is_template',d.datistemplate),
 'database_security_labels',(SELECT count(*) FROM pg_shseclabel WHERE classoid='pg_database'::regclass AND objoid=d.oid),
 'database_settings',(SELECT COALESCE(jsonb_agg(jsonb_build_array(setrole,setconfig)),'[]'::jsonb) FROM pg_db_role_setting WHERE setdatabase=d.oid),
 'superuser',(SELECT rolsuper FROM pg_roles WHERE rolname=session_user),
 'connections_allowed',d.datallowconn,
 'other_connections',(SELECT count(*) FROM pg_stat_activity WHERE datid=d.oid AND pid<>pg_backend_pid()),
 'empty',({EMPTY}), 'database_owner',pg_get_userbyid(d.datdba),
 'database_acl',{acl_sql('d.datacl', "'d'", 'd.datdba')},
 'required_role_names',(SELECT jsonb_agg(rolname ORDER BY rolname) FROM pg_roles WHERE oid IN (SELECT oid FROM closure)),
 'roles',(SELECT jsonb_agg(jsonb_build_object('name',rolname,'superuser',rolsuper,'inherit',rolinherit,'create_role',rolcreaterole,
   'create_db',rolcreatedb,'login',rolcanlogin,'replication',rolreplication,'bypass_rls',rolbypassrls) ORDER BY rolname) FROM pg_roles),
 'memberships',(SELECT COALESCE(jsonb_agg(jsonb_build_object('role',pg_get_userbyid(roleid),'member',pg_get_userbyid(member),
   'grantor',pg_get_userbyid(grantor),'admin',admin_option,'inherit',inherit_option,'set',set_option)
   ORDER BY pg_get_userbyid(roleid),pg_get_userbyid(member),pg_get_userbyid(grantor)),'[]'::jsonb) FROM pg_auth_members),
 'extensions',(SELECT jsonb_agg(jsonb_build_object('name',e.extname,'schema',n.nspname,'version',e.extversion)
   ORDER BY e.extname) FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace),
 'available_extensions',(SELECT jsonb_agg(jsonb_build_object('name',name,'version',default_version) ORDER BY name) FROM pg_available_extensions),
 'security_catalog_sha256',encode(sha256(convert_to(({CATALOG})::text,'UTF8')),'hex')
) FROM pg_database d WHERE d.datname=current_database()"""


def connection_env(prefix: str, environment: dict[str, str] | None = None) -> dict[str, str]:
    supplied = dict(os.environ if environment is None else environment)
    # Never inherit an accidental default/service/PGOPTIONS connection route.
    env = {key: value for key, value in supplied.items() if not key.startswith('PG') and not key.startswith('DOU_BACKUP_') and not key.startswith('DOU_RESTORE_') and not key.startswith('DOU_MAINTENANCE_')}
    for key in FIELDS:
        value = supplied.get(prefix + key)
        if value is not None:
            env[key] = value
    if not all(env.get(key) for key in ('PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER')):
        fail('EXPLICIT_CONNECTION_ENV_REQUIRED')
    try:
        address = ipaddress.ip_address(env['PGHOST'])
        if not address.is_loopback or '%' in env['PGHOST']:
            fail('DIRECT_NUMERIC_LOOPBACK_REQUIRED')
    except ValueError:
        fail('DIRECT_NUMERIC_LOOPBACK_REQUIRED')
    if not re.fullmatch(r'[1-9][0-9]{0,4}', env['PGPORT']) or int(env['PGPORT']) > 65535:
        fail('EXPLICIT_SINGLE_PORT_REQUIRED')
    env['PGHOST'] = env['PGHOSTADDR'] = str(address)
    if '=' in env['PGDATABASE'] or '://' in env['PGDATABASE']:
        fail('DATABASE_NAME_MUST_NOT_BE_DSN')
    env.setdefault('PGCONNECT_TIMEOUT', '10')
    env['PGAPPNAME'] = 'dou-recovery'
    env['PGOPTIONS'] = '-c search_path=pg_catalog -c client_min_messages=warning'
    return env


def executable(name: str) -> str:
    base = os.environ.get('DOU_RECOVERY_PG_BIN')
    return str(Path(base) / name) if base else name


def command(name: str, args: list[str], *, env: dict[str, str] | None = None,
            input: bytes | BinaryIO | None = None, output: BinaryIO | None = None) -> bytes:
    try:
        with tempfile.TemporaryFile() as errors:
            proc = subprocess.run([executable(name), *args], env=env, input=input if isinstance(input, bytes) else None,
                stdin=input if input is not None and not isinstance(input, bytes) else None,
                stdout=output if output is not None else subprocess.PIPE, stderr=errors, check=False)
            if proc.returncode != 0:
                fail('DATABASE_TOOL_FAILED')
            return proc.stdout if output is None else b''
    except (OSError, subprocess.SubprocessError):
        fail('DATABASE_TOOL_UNAVAILABLE')


def metadata(env: dict[str, str]) -> dict[str, Any]:
    raw = command('psql', ['-X', '-w', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1'], env=env, input=(SNAPSHOT_SQL + ';').encode())
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or not value.get('superuser'):
            fail('DBA_SUPERUSER_REQUIRED')
        return value
    except (ValueError, TypeError):
        fail('INVALID_DATABASE_METADATA')



def control_connection(env: dict[str, str], *, runtime_error: str):
    """Tek-thread DBA CLI'da açık libpq rotasıyla kalıcı bağlantı aç."""
    try:
        import psycopg
    except ImportError:
        fail(runtime_error)
    params = {'host': env['PGHOST'], 'hostaddr': env['PGHOSTADDR'], 'port': env['PGPORT'],
              'dbname': env['PGDATABASE'], 'user': env['PGUSER'],
              'connect_timeout': env['PGCONNECT_TIMEOUT'], 'application_name': env['PGAPPNAME'],
              'options': env['PGOPTIONS'], 'autocommit': True}
    for key in ('PGPASSWORD', 'PGPASSFILE', 'PGSSLMODE', 'PGSSLROOTCERT', 'PGSSLCERT', 'PGSSLKEY'):
        if key in env:
            params[key[2:].lower()] = env[key]
    ambient = {key: value for key, value in os.environ.items() if key.startswith('PG')}
    try:
        for key in ambient:
            del os.environ[key]
        return psycopg.connect(**params)
    finally:
        os.environ.update(ambient)


@contextmanager
def source_snapshot(env: dict[str, str]):
    """Aynı yerel kontrol bağlantısı kimliği ve dump snapshot'ını birbirine bağlar."""
    try:
        connection = control_connection(env, runtime_error='BACKUP_PSYCOPG_RUNTIME_REQUIRED')
        with connection:
            connection.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
            before = source_metadata(connection.execute(SNAPSHOT_SQL).fetchone()[0])
            if not connection.execute("SELECT rolsuper FROM pg_roles WHERE rolname=session_user").fetchone()[0]:
                fail('DBA_SUPERUSER_REQUIRED')
            snapshot = connection.execute('SELECT pg_export_snapshot()').fetchone()[0]
            if not isinstance(snapshot, str) or not re.fullmatch(r'[0-9A-Fa-f]+-[0-9A-Fa-f]+-[0-9]+', snapshot):
                fail('INVALID_EXPORTED_SNAPSHOT')
            yield before, snapshot
            # pg_dump bitmeden snapshot kapanmaz. Kontrol bağlantısı kaybolursa
            # bu sorgu başarısız olur ve tamamlanma manifesti yazılamaz.
            connection.execute('SELECT 1').fetchone()
            connection.execute('COMMIT')
            # Eski snapshot'ta metadata değişimi görünmez; aynı TCP bağlantısında
            # yeni snapshot ile kimlik ve güncel rol/şema durumunu tekrar oku.
            connection.execute('BEGIN READ ONLY')
            after = source_metadata(connection.execute(SNAPSHOT_SQL).fetchone()[0])
            if before != after:
                fail('SOURCE_METADATA_CHANGED')
            connection.execute('COMMIT')
    except Refused:
        raise
    except Exception:
        # psycopg istisnaları DSN, host veya SQL metni içerebilir; dışarı taşınmaz.
        fail('SOURCE_SNAPSHOT_CONTROL_FAILED')


def identity_digest(identity: dict[str, str]) -> str:
    # Name is metadata; system ID + database OID defeat host/URL aliases.
    raw = json.dumps([identity['system_identifier'], identity['database_oid']], separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()



def membership_component(seeds: set[str], memberships: list[dict[str, Any]]) -> set[str]:
    """Gerekli rollerin iki yönlü üyelik bileşeni; hiçbir SET/INHERIT bayrağı göz ardı edilmez."""
    neighbors: dict[str, set[str]] = {}
    for row in memberships:
        member, role = row['member'], row['role']
        neighbors.setdefault(member, set()).add(role)
        neighbors.setdefault(role, set()).add(member)
    names = set(seeds)
    pending = list(names)
    while pending:
        current = pending.pop()
        for name in neighbors.get(current, ()):
            if name not in names:
                names.add(name)
                pending.append(name)
    return names


def scoped_memberships(memberships: list[dict[str, Any]], names: set[str]) -> list[dict[str, Any]]:
    """Bileşene gelen ve bileşenden çıkan bütün üyelikleri karşılaştırmaya al."""
    return sorted((row for row in memberships if row['member'] in names or row['role'] in names),
                  key=lambda row: json.dumps(row, sort_keys=True))


def validate_role_scope(source: dict[str, Any]) -> None:
    # Eski tek yönlü manifestler eksik giriş kenarlarını güvenli biçimde temsil edemez.
    if source.get('role_membership_scope') != ROLE_SCOPE:
        fail('ROLE_MEMBERSHIP_SCOPE_REQUIRED')
    names = {role['name'] for role in source['roles']}
    if len(names) != len(source['roles']) or not names:
        fail('INVALID_REQUIRED_ROLE_METADATA')
    seeds = set(source['required_role_seeds'])
    if not seeds or not seeds <= names or membership_component(seeds, source['memberships']) != names:
        fail('INCOMPLETE_ROLE_MEMBERSHIP_COMPONENT')


def membership_filter_sql(names_json: str) -> str:
    return f"({names_json}::jsonb ? (value->>'member') OR {names_json}::jsonb ? (value->>'role'))"


def source_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    seeds = set(meta['required_role_names'])
    names = membership_component(seeds, meta['memberships'])
    if not names <= {role['name'] for role in meta['roles']}:
        fail('REQUIRED_ROLE_METADATA_MISSING')
    if meta['database_settings']: fail('CUSTOM_DATABASE_SETTINGS_UNSUPPORTED')
    if meta['database_security_labels']: fail('DATABASE_SECURITY_LABELS_UNSUPPORTED')
    if any(entry['grantor'] != meta['database_owner'] for entry in meta['database_acl']):
        fail('NONOWNER_DATABASE_GRANTOR_UNSUPPORTED')
    return {key: meta[key] for key in ('identity', 'server_version_num', 'database_format', 'database_owner', 'database_acl', 'extensions', 'security_catalog_sha256')} | {
        'role_membership_scope': ROLE_SCOPE,
        'required_role_seeds': sorted(seeds),
        'roles': [role for role in meta['roles'] if role['name'] in names],
        'memberships': scoped_memberships(meta['memberships'], names),
    }


def preflight(source: dict[str, Any], target: dict[str, Any]) -> None:
    validate_role_scope(source)
    if identity_digest(source['identity']) == identity_digest(target['identity']): fail('SOURCE_EQUALS_TARGET')
    if not target.get('empty'): fail('TARGET_NOT_EMPTY')
    if not target.get('connections_allowed'): fail('TARGET_ALREADY_FENCED')
    if not target.get('superuser'): fail('DBA_SUPERUSER_REQUIRED')
    if target.get('other_connections') != 0: fail('OTHER_TARGET_CONNECTIONS')
    if any(entry['grantor'] != target['database_owner'] for entry in target['database_acl']): fail('NONOWNER_TARGET_DATABASE_GRANTOR_UNSUPPORTED')
    if target['database_settings']: fail('CUSTOM_TARGET_DATABASE_SETTINGS_UNSUPPORTED')
    if target['database_security_labels']: fail('TARGET_DATABASE_SECURITY_LABELS_UNSUPPORTED')
    if source['database_format'] != target['database_format']: fail('DATABASE_FORMAT_MISMATCH')
    if target['server_version_num'] // 10000 != source['server_version_num'] // 10000: fail('POSTGRES_MAJOR_MISMATCH')
    if any(role not in target['roles'] for role in source['roles']): fail('ROLE_ATTRIBUTES_MISSING_OR_DIFFERENT')
    names = {role['name'] for role in source['roles']}
    current = scoped_memberships(target['memberships'], names)
    if current != source['memberships']: fail('ROLE_MEMBERSHIPS_DIFFERENT')
    for extension in source['extensions']:
        if {'name': extension['name'], 'version': extension['version']} not in target['available_extensions']:
            fail('EXTENSION_DEFAULT_VERSION_MISMATCH')


def directory_fd(path: Path) -> int:
    if not NOFOLLOW or not DIRECTORY or not path.is_absolute() or '..' in path.parts:
        fail('UNSAFE_BUNDLE_PATH')
    fd = os.open('/', os.O_RDONLY | DIRECTORY)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | DIRECTORY | NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = next_fd
        return fd
    except OSError:
        os.close(fd); fail('UNSAFE_BUNDLE_PATH')


def new_bundle(path: Path) -> int:
    if not path.name or path.name in ('.', '..') or not path.is_absolute(): fail('UNSAFE_BUNDLE_PATH')
    parent = directory_fd(path.parent)
    try:
        os.mkdir(path.name, 0o700, dir_fd=parent)
        fd = os.open(path.name, os.O_RDONLY | DIRECTORY | NOFOLLOW, dir_fd=parent)
        return fd
    except OSError:
        fail('BUNDLE_EXISTS_OR_UNWRITABLE')
    finally:
        os.close(parent)


def private_file(bundle: int, name: str, create: bool = False) -> BinaryIO:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL if create else os.O_RDONLY
    try:
        fd = os.open(name, flags | NOFOLLOW, 0o600, dir_fd=bundle)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            os.close(fd); fail('UNSAFE_BUNDLE_FILE')
        return os.fdopen(fd, 'w+b' if create else 'rb')
    except OSError:
        fail('UNSAFE_BUNDLE_FILE')


def repository_lineage(repository: Path) -> dict[str, Any]:
    try:
        migrations = repository / 'supabase' / 'migrations'
        schema = {}
        for path in sorted(migrations.glob('*.sql')):
            if path.is_symlink() or not re.fullmatch(r'[0-9]{4}_[A-Za-z0-9_]+\.sql', path.name): fail('UNSAFE_SCHEMA_PATH')
            schema['supabase/migrations/' + path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if not schema: fail('SCHEMA_LINEAGE_REQUIRED')
        commit = subprocess.run(['git', '-C', str(repository), 'rev-parse', 'HEAD'], capture_output=True, check=False).stdout.decode().strip()
        if not re.fullmatch(r'[a-f0-9]{40}', commit): fail('COMMIT_LINEAGE_REQUIRED')
        dirty = subprocess.run(['git', '-C', str(repository), 'diff', '--quiet', 'HEAD', '--', 'supabase/migrations'], capture_output=True, check=False).returncode
        if dirty not in (0, 1): fail('SCHEMA_LINEAGE_REQUIRED')
        return {'commit': commit, 'schema_files_sha256': schema, 'tracked_schema_dirty': dirty == 1}
    except OSError:
        fail('LINEAGE_UNREADABLE')


def backup(bundle_path: Path, repository: Path) -> dict[str, str]:
    env = connection_env('DOU_BACKUP_')
    lineage = repository_lineage(repository)
    bundle = None
    try:
        with source_snapshot(env) as (before, snapshot):
            bundle = new_bundle(bundle_path)
            with private_file(bundle, DUMP, create=True) as dump:
                command('pg_dump', ['-w', '--format=custom', '--quote-all-identifiers', '--snapshot=' + snapshot], env=env, output=dump)
                dump.flush(); os.fsync(dump.fileno()); dump.seek(0)
                if dump.read(5) != b'PGDMP': fail('INVALID_CUSTOM_ARCHIVE')
                dump.seek(0); digest = hashlib.file_digest(dump, 'sha256').hexdigest()
                size = os.fstat(dump.fileno()).st_size; dump.seek(0)
                command('pg_restore', ['--list'], input=dump)
        # Context'in çıkışı aynı bağlantıda snapshot yaşamını ve taze metadatayı
        # denetledi. Bu doğrulama bitmeden tamamlanmış manifest oluşmaz.
        if repository_lineage(repository) != lineage: fail('SOURCE_METADATA_CHANGED')
        manifest = {'format': FORMAT, 'completed': True, 'created_utc': datetime.now(timezone.utc).isoformat(),
            'archive': {'name': DUMP, 'bytes': size, 'sha256': digest}, 'source': before,
            'source_identity_sha256': identity_digest(before['identity']), 'lineage': lineage,
            'source_capture': 'direct-loopback-exported-snapshot-v1',
            'scope': 'postgresql-only; roles preprovisioned; external storage/auth/provider copies excluded'}
        with private_file(bundle, MANIFEST, create=True) as output:
            output.write((json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()); output.flush(); os.fsync(output.fileno())
        os.fsync(bundle)
        return {'status': 'backup-complete', 'source_identity_sha256': manifest['source_identity_sha256']}
    finally:
        if bundle is not None: os.close(bundle)


def verified_copy(path: Path, expected_source: str, output: BinaryIO) -> dict[str, Any]:
    if not HEX.fullmatch(expected_source): fail('EXPECTED_SOURCE_ID_REQUIRED')
    bundle = directory_fd(path)
    try:
        info = os.fstat(bundle)
        if stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid(): fail('BUNDLE_NOT_PRIVATE')
        if set(os.listdir(bundle)) != {MANIFEST, DUMP}: fail('INCOMPLETE_OR_UNEXPECTED_BUNDLE_FILES')
        with private_file(bundle, MANIFEST) as data:
            if os.fstat(data.fileno()).st_size > 2_000_000: fail('MANIFEST_TOO_LARGE')
            try: manifest = json.load(data)
            except (ValueError, UnicodeError): fail('INVALID_MANIFEST')
        try:
            archive = manifest['archive']; source = manifest['source']
            if manifest['format'] != FORMAT or manifest['completed'] is not True or archive['name'] != DUMP: fail('INVALID_MANIFEST')
            if manifest.get('source_capture') != 'direct-loopback-exported-snapshot-v1': fail('BOUND_SOURCE_CAPTURE_REQUIRED')
            if not HEX.fullmatch(archive['sha256']) or not isinstance(archive['bytes'], int) or archive['bytes'] <= 5: fail('INVALID_MANIFEST')
            actual_id = identity_digest(source['identity'])
            if actual_id != expected_source or actual_id != manifest['source_identity_sha256']: fail('SOURCE_IDENTITY_MISMATCH')
            if not HEX.fullmatch(source['security_catalog_sha256']): fail('INVALID_MANIFEST')
            validate_role_scope(source)
        except (KeyError, TypeError, ValueError): fail('INVALID_MANIFEST')
        digest = hashlib.sha256(); size = 0
        with private_file(bundle, DUMP) as data:
            if data.read(5) != b'PGDMP': fail('INVALID_CUSTOM_ARCHIVE')
            data.seek(0)
            while block := data.read(1024 * 1024):
                digest.update(block); output.write(block); size += len(block)
        output.flush(); os.fsync(output.fileno()); output.seek(0)
        if digest.hexdigest() != archive['sha256'] or size != archive['bytes']: fail('ARCHIVE_HASH_MISMATCH')
        return manifest
    finally:
        os.close(bundle)


def restore_guard(source: dict[str, Any], target: dict[str, Any], *, fenced: bool) -> str:
    expected_identity = sql_string(json.dumps(target['identity']))
    expected_roles = sql_string(json.dumps(source['roles']))
    expected_memberships = sql_string(json.dumps(source['memberships']))
    required_names = sql_string(json.dumps([role['name'] for role in source['roles']]))
    return f"""DO $dou_recovery$ DECLARE m jsonb; r jsonb; members jsonb; BEGIN
 SELECT ({SNAPSHOT_SQL}) INTO m;
 IF m->'identity' <> {expected_identity}::jsonb THEN RAISE EXCEPTION 'TARGET_IDENTITY_CHANGED'; END IF;
 IF NOT (m->>'superuser')::boolean OR NOT (m->>'empty')::boolean THEN RAISE EXCEPTION 'TARGET_NOT_EMPTY_OR_UNAUTHORIZED'; END IF;
 IF m->'database_format' <> {sql_string(json.dumps(source['database_format']))}::jsonb OR m->'database_settings' <> '[]'::jsonb OR (m->>'database_security_labels')::integer <> 0 THEN RAISE EXCEPTION 'TARGET_FORMAT_OR_SETTINGS_CHANGED'; END IF;
 IF (m->>'other_connections')::integer <> 0 THEN RAISE EXCEPTION 'OTHER_TARGET_CONNECTIONS'; END IF;
 IF (m->>'connections_allowed')::boolean IS {'TRUE' if fenced else 'FALSE'} THEN RAISE EXCEPTION 'TARGET_FENCE_STATE'; END IF;
 FOR r IN SELECT value FROM jsonb_array_elements({expected_roles}::jsonb) LOOP
   IF NOT (m->'roles') @> jsonb_build_array(r) THEN RAISE EXCEPTION 'TARGET_ROLES_CHANGED'; END IF;
 END LOOP;
 SELECT COALESCE(jsonb_agg(value ORDER BY value::text),'[]'::jsonb) INTO members FROM jsonb_array_elements(m->'memberships')
 WHERE {membership_filter_sql(required_names)};
 IF members <> (SELECT COALESCE(jsonb_agg(value ORDER BY value::text),'[]'::jsonb) FROM jsonb_array_elements({expected_memberships}::jsonb))
 THEN RAISE EXCEPTION 'TARGET_MEMBERSHIPS_CHANGED'; END IF;
 END $dou_recovery$;
"""


def database_acl_sql(source: dict[str, Any], target: dict[str, Any]) -> str:
    db = sql_ident(target['identity']['database_name'])
    owner = sql_ident(source['database_owner'])
    if any(entry['grantor'] != source['database_owner'] for entry in source['database_acl']): fail('NONOWNER_DATABASE_GRANTOR_UNSUPPORTED')
    result = [f'ALTER DATABASE {db} OWNER TO {owner};']
    grantees = {(entry['grantee'], entry['public']) for entry in target['database_acl'] + source['database_acl']} | {('PUBLIC', True)}
    for grantee, public in sorted(grantees):
        result.append(f'REVOKE ALL ON DATABASE {db} FROM ' + ('PUBLIC' if public else sql_ident(grantee)) + ';')
    result.append(f'SET ROLE {owner};')
    for entry in source['database_acl']:
        if entry['privilege'] not in ('CREATE', 'CONNECT', 'TEMPORARY'): fail('INVALID_DATABASE_PRIVILEGE')
        grantee = 'PUBLIC' if entry['public'] else sql_ident(entry['grantee'])
        result.append(f"GRANT {entry['privilege']} ON DATABASE {db} TO {grantee}" + (' WITH GRANT OPTION' if entry['grantable'] else '') + ';')
    result.append('RESET ROLE;')
    return '\n'.join(result) + '\n'



def security_verify(source: dict[str, Any]) -> str:
    roles = sql_string(json.dumps(source['roles']))
    names = sql_string(json.dumps([role['name'] for role in source['roles']]))
    memberships = sql_string(json.dumps(source['memberships']))
    acl = sql_string(json.dumps(source['database_acl']))
    owner = sql_string(source['database_owner'])
    digest = sql_string(source['security_catalog_sha256'])
    return f"""DO $dou_verify$ DECLARE m jsonb; r jsonb; members jsonb; BEGIN
 SELECT ({SNAPSHOT_SQL}) INTO m;
 FOR r IN SELECT value FROM jsonb_array_elements({roles}::jsonb) LOOP
   IF NOT (m->'roles') @> jsonb_build_array(r) THEN RAISE EXCEPTION 'RESTORED_ROLE_ATTRIBUTES_CHANGED'; END IF;
 END LOOP;
 SELECT COALESCE(jsonb_agg(value ORDER BY value::text),'[]'::jsonb) INTO members
 FROM jsonb_array_elements(m->'memberships') WHERE {membership_filter_sql(names)};
 IF members <> (SELECT COALESCE(jsonb_agg(value ORDER BY value::text),'[]'::jsonb) FROM jsonb_array_elements({memberships}::jsonb))
 THEN RAISE EXCEPTION 'RESTORED_MEMBERSHIPS_CHANGED'; END IF;
 IF m->>'database_owner' <> {owner} OR m->'database_acl' <> {acl}::jsonb
 THEN RAISE EXCEPTION 'DATABASE_OWNER_OR_ACL_MISMATCH'; END IF;
 IF m->>'security_catalog_sha256' <> {digest}
 THEN RAISE EXCEPTION 'RESTORED_SECURITY_CATALOG_MISMATCH'; END IF;
 END $dou_verify$;
"""


SESSION_BINDING_SQL = """jsonb_build_object(
 'system_identifier',(SELECT system_identifier::text FROM pg_control_system()),
 'postmaster_start',extract(epoch FROM pg_postmaster_start_time())::text,
 'database_oid',(SELECT oid::text FROM pg_database WHERE datname=current_database()),
 'database_name',current_database(), 'pid',pg_backend_pid(),
 'backend_start',(SELECT extract(epoch FROM backend_start)::text FROM pg_stat_activity WHERE pid=pg_backend_pid()),
 'user',session_user, 'application_name',current_setting('application_name'),
 'server_port',inet_server_port(),
 'superuser',(SELECT rolsuper FROM pg_roles WHERE rolname=session_user))"""
PHASE_TIMEOUT_SECONDS = 600
MAX_PROTOCOL_LINE = 2_000_000


def restore_environments() -> tuple[dict[str, str], dict[str, str]]:
    """Bakım rotası tahmin edilmez; hedef ve bakım aynı açık yerel sunucudadır."""
    target = connection_env('DOU_RESTORE_')
    maintenance = connection_env('DOU_MAINTENANCE_')
    if target['PGDATABASE'] == maintenance['PGDATABASE']:
        fail('MAINTENANCE_DATABASE_MUST_DIFFER')
    if any(target[key] != maintenance[key] for key in ('PGHOSTADDR', 'PGPORT')):
        fail('MAINTENANCE_ENDPOINT_MISMATCH')
    target['PGAPPNAME'] = 'dou-recovery-target-' + secrets.token_hex(12)
    maintenance['PGAPPNAME'] = 'dou-recovery-maintenance-' + secrets.token_hex(12)
    return target, maintenance


def validate_binding(binding: dict[str, Any], env: dict[str, str]) -> None:
    """Protokol yanıtındaki kimlik alanları hatalı/eksik türlerle kabul edilmez."""
    if not isinstance(binding, dict):
        fail('INVALID_SESSION_BINDING')
    for key in ('system_identifier', 'database_oid'):
        value = binding.get(key)
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]+', value):
            fail('INVALID_SESSION_BINDING')
    for key in ('postmaster_start', 'backend_start'):
        value = binding.get(key)
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value):
            fail('INVALID_SESSION_BINDING')
    if (type(binding.get('pid')) is not int or binding['pid'] <= 0
        or type(binding.get('server_port')) is not int
        or binding['server_port'] != int(env['PGPORT'])
        or binding.get('database_name') != env['PGDATABASE']
        or binding.get('user') != env['PGUSER']
        or binding.get('application_name') != env['PGAPPNAME']
        or binding.get('superuser') is not True):
        fail('INVALID_SESSION_BINDING')


class TargetSession:
    """Kalıcı psql oturumu; büyük COPY verisi yalnız miras alınmış özel FD'den okunur."""

    def __init__(self, env: dict[str, str], script: BinaryIO):
        self.env = env
        self.script = script
        self.process = None
        self.errors = None
        self.output = None
        self.buffer = b''

    def __enter__(self):
        self.errors = tempfile.TemporaryFile()
        self.output = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(
                [executable('psql'), '-X', '-w', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '--file=-'],
                env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.errors,
                pass_fds=(self.script.fileno(),), bufsize=0,
            )
            os.set_blocking(self.process.stdout.fileno(), False)
            os.set_blocking(self.process.stdin.fileno(), False)
            return self
        except (OSError, subprocess.SubprocessError):
            self.__exit__(None, None, None)
            fail('RESTORE_TARGET_PROCESS_UNAVAILABLE')

    def __exit__(self, exception_type, *_args):
        # Yalnız bu CLI'nın başlattığı çocuk kapatılır; diğer DB oturumları öldürülmez.
        if self.process is not None:
            if exception_type is not None and self.process.poll() is None:
                self.process.terminate()
            if self.process.stdin is not None:
                try:
                    self.process.stdin.close()
                except OSError:
                    pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            if self.process.stdout is not None:
                self.process.stdout.close()
        for private in (self.errors, self.output):
            if private is not None:
                private.close()

    def send(self, sql: str) -> None:
        payload = sql.encode('utf-8')
        if len(payload) > MAX_PROTOCOL_LINE:
            fail('RESTORE_PROTOCOL_COMMAND_TOO_LARGE')
        deadline = time.monotonic() + PHASE_TIMEOUT_SECONDS
        sent = 0
        try:
            # Kontrol borusu da sınırlı sürede yazılır; dump bu boruya hiç yazılmaz.
            while sent < len(payload):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    fail('RESTORE_PROTOCOL_TIMEOUT')
                _, writable, _ = select.select([], [self.process.stdin], [], remaining)
                if not writable:
                    fail('RESTORE_PROTOCOL_TIMEOUT')
                sent += os.write(self.process.stdin.fileno(), payload[sent:])
        except (OSError, ValueError):
            fail('RESTORE_TARGET_PIPE_CLOSED')

    def wait_json(self, marker: str) -> dict[str, Any]:
        """Yalnız yeni rastgele önekin tam satırındaki sınırlı JSON zarfı kabul edilir."""
        prefix = marker.encode() + b':'
        deadline = time.monotonic() + PHASE_TIMEOUT_SECONDS
        while True:
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                if len(line) > MAX_PROTOCOL_LINE:
                    fail('RESTORE_PROTOCOL_LINE_TOO_LARGE')
                if line.startswith(prefix):
                    try:
                        value = json.loads(line[len(prefix):])
                    except (ValueError, UnicodeError):
                        fail('INVALID_RESTORE_PROTOCOL_JSON')
                    if not isinstance(value, dict):
                        fail('INVALID_RESTORE_PROTOCOL_JSON')
                    return value
            if len(self.buffer) > MAX_PROTOCOL_LINE:
                fail('RESTORE_PROTOCOL_LINE_TOO_LARGE')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                fail('RESTORE_PROTOCOL_TIMEOUT')
            try:
                ready, _, _ = select.select([self.process.stdout], [], [], remaining)
                if not ready:
                    fail('RESTORE_PROTOCOL_TIMEOUT')
                block = os.read(self.process.stdout.fileno(), 65536)
            except OSError:
                fail('RESTORE_TARGET_PIPE_CLOSED')
            if not block:
                fail('RESTORE_TARGET_EXITED_WITHOUT_RECEIPT')
            self.output.write(block)
            self.buffer += block

    def ready(self) -> tuple[dict[str, Any], dict[str, Any]]:
        marker = 'DOU_READY_' + secrets.token_hex(24)
        self.send("SET standard_conforming_strings=on;\nSELECT " + sql_string(marker + ':') +
            " || jsonb_build_object('metadata',(" + SNAPSHOT_SQL + "),'binding'," +
            SESSION_BINDING_SQL + ")::text;\n")
        value = self.wait_json(marker)
        if set(value) != {'metadata', 'binding'} or not isinstance(value['metadata'], dict):
            fail('INVALID_RESTORE_PROTOCOL_JSON')
        validate_binding(value['binding'], self.env)
        identity = value['metadata'].get('identity', {})
        if any(identity.get(key) != value['binding'][key]
               for key in ('system_identifier', 'database_oid', 'database_name')):
            fail('TARGET_IDENTITY_CHANGED')
        return value['metadata'], value['binding']

    def guard(self, source: dict[str, Any], target: dict[str, Any]) -> None:
        marker = 'DOU_GUARDED_' + secrets.token_hex(24)
        self.send(restore_guard(source, target, fenced=False) +
            'SELECT ' + sql_string(marker + ':') + " || '{\"guarded\":true}';\n")
        if self.wait_json(marker) != {'guarded': True}:
            fail('INVALID_RESTORE_PROTOCOL_JSON')

    def apply(self, marker: str, binding: dict[str, Any]) -> None:
        self.script.flush()
        self.script.seek(0)
        self.send(f'\\i /dev/fd/{self.script.fileno()}\n')
        value = self.wait_json(marker)
        if (set(value) != {'commit_status', 'xid', 'binding'}
            or value.get('commit_status') != 'committed'
            or not isinstance(value.get('xid'), str)
            or not re.fullmatch(r'[0-9]+', value['xid'])
            or value.get('binding') != binding):
            fail('RESTORE_COMMIT_NOT_CONFIRMED')


def maintenance_state(connection, target_binding: dict[str, Any]) -> dict[str, Any]:
    # pg_stat_activity'nin işlem-içi eski görünümü tekrar kullanılmaz.
    connection.execute('SELECT pg_stat_clear_snapshot()')
    oid = sql_string(target_binding['database_oid'])
    sql = 'SELECT jsonb_build_object(\'maintenance\',' + SESSION_BINDING_SQL + f""",'target',(
      SELECT jsonb_build_object('database_oid',d.oid::text,'database_name',d.datname,
        'connections_allowed',d.datallowconn,'sessions',(
          SELECT COALESCE(jsonb_agg(jsonb_build_object('pid',a.pid,
            'backend_start',extract(epoch FROM a.backend_start)::text,
            'user',a.usename,'application_name',a.application_name) ORDER BY a.pid),'[]'::jsonb)
          FROM pg_stat_activity a WHERE a.datid=d.oid))
      FROM pg_database d WHERE d.oid={oid}::oid))"""
    return connection.execute(sql).fetchone()[0]


def validate_maintenance_state(state: dict[str, Any], maintenance_binding: dict[str, Any],
                               target_binding: dict[str, Any], *, allowed: bool) -> None:
    if not isinstance(state, dict) or state.get('maintenance') != maintenance_binding:
        fail('MAINTENANCE_IDENTITY_CHANGED')
    for key in ('system_identifier', 'postmaster_start', 'server_port'):
        if maintenance_binding.get(key) != target_binding.get(key):
            fail('MAINTENANCE_CLUSTER_MISMATCH')
    if maintenance_binding.get('database_oid') == target_binding.get('database_oid'):
        fail('MAINTENANCE_DATABASE_MUST_DIFFER')
    target = state.get('target')
    if not isinstance(target, dict) or any(target.get(key) != target_binding.get(key)
            for key in ('database_oid', 'database_name')):
        fail('TARGET_IDENTITY_CHANGED')
    if target.get('connections_allowed') is not allowed:
        fail('TARGET_FENCE_STATE')
    expected_session = {key: target_binding[key] for key in
                        ('pid', 'backend_start', 'user', 'application_name')}
    if target.get('sessions') != [expected_session]:
        fail('TARGET_SESSION_BINDING_OR_COUNT_CHANGED')


def set_target_fence(connection, maintenance_binding: dict[str, Any],
                     target_binding: dict[str, Any], *, allowed: bool) -> None:
    """Kısa katalog kilidi ad/OID denetimi ile ALTER arasındaki DDL yarışını sınırlar."""
    try:
        connection.execute('BEGIN')
        connection.execute("SET LOCAL lock_timeout='5s'")
        connection.execute("SET LOCAL statement_timeout='15s'")
        connection.execute('LOCK TABLE pg_catalog.pg_database IN SHARE ROW EXCLUSIVE MODE')
        validate_maintenance_state(maintenance_state(connection, target_binding), maintenance_binding,
                                   target_binding, allowed=not allowed)
        connection.execute('ALTER DATABASE ' + sql_ident(target_binding['database_name']) +
                           ' ALLOW_CONNECTIONS ' + ('true' if allowed else 'false'))
        validate_maintenance_state(maintenance_state(connection, target_binding), maintenance_binding,
                                   target_binding, allowed=allowed)
        connection.execute('COMMIT')
        # COMMIT makbuzu kaybolursa bu doğrulamaya ulaşılmaz; ters ALTER denenmez.
        validate_maintenance_state(maintenance_state(connection, target_binding), maintenance_binding,
                                   target_binding, allowed=allowed)
    except Exception:
        try:
            connection.execute('ROLLBACK')
        except Exception:
            pass
        raise


def restore_script(source: dict[str, Any], target: dict[str, Any], sql: BinaryIO,
                   script: BinaryIO, marker: str) -> None:
    """Fenced hedefte tek işlem; COMMIT sonrası sunucudan xid8 durumu alınır."""
    acl_statements = database_acl_sql(source, target)
    script.write(('BEGIN;\n' + restore_guard(source, target, fenced=True) +
                  "SELECT pg_current_xact_id()::text AS dou_restore_xid \\gset\n" +
                  acl_statements).encode())
    sql.seek(0)
    shutil.copyfileobj(sql, script)
    script.write(('\nRESET SESSION AUTHORIZATION;\nSET search_path=pg_catalog;\n' +
        security_verify(source) + '\nCOMMIT;\nSELECT ' + sql_string(marker + ':') +
        " || jsonb_build_object('commit_status',pg_xact_status(:'dou_restore_xid'::xid8)," +
        "'xid',:'dou_restore_xid','binding'," + SESSION_BINDING_SQL + ")::text;\n").encode())
    script.flush()
    os.fsync(script.fileno())
    script.seek(0)


def restore_database(bundle_path: Path, expected_source: str) -> dict[str, str]:
    # Bakım gereksinimi dahil bütün girdi doğrulamaları mutasyondan önce tamamlanır.
    with tempfile.TemporaryFile() as archive, tempfile.TemporaryFile() as sql, tempfile.TemporaryFile() as script:
        manifest = verified_copy(bundle_path, expected_source, archive)
        target_env, maintenance_env = restore_environments()
        command('pg_restore', ['--list'], input=archive)
        archive.seek(0)
        command('pg_restore', ['--exit-on-error', '--file=-'],
                input=archive, output=sql)
        source = manifest['source']
        fence_attempted = False
        committed = False
        try:
            with TargetSession(target_env, script) as target_session:
                target, target_binding = target_session.ready()
                preflight(source, target)
                target_session.guard(source, target)
                marker = 'DOU_COMMITTED_' + secrets.token_hex(24)
                restore_script(source, target, sql, script, marker)
                with control_connection(maintenance_env,
                        runtime_error='RESTORE_PSYCOPG_RUNTIME_REQUIRED') as maintenance:
                    maintenance.execute("SET statement_timeout='15s'")
                    maintenance.execute("SET lock_timeout='5s'")
                    maintenance_binding = maintenance.execute('SELECT ' + SESSION_BINDING_SQL).fetchone()[0]
                    validate_binding(maintenance_binding, maintenance_env)
                    validate_maintenance_state(maintenance_state(maintenance, target_binding),
                        maintenance_binding, target_binding, allowed=True)
                    fence_attempted = True
                    set_target_fence(maintenance, maintenance_binding, target_binding, allowed=False)
                    # Fence COMMIT sonrası aynı hedefte conncount/empty/role guard scriptin başındadır.
                    target_session.apply(marker, target_binding)
                    committed = True
                    set_target_fence(maintenance, maintenance_binding, target_binding, allowed=True)
                return {'status': 'restore-complete', 'commit_status': 'committed',
                        'target_identity_sha256': identity_digest(target['identity']),
                        'scope': 'database/security metadata; content and RLS application drill still required'}
        except Exception as error:
            if committed:
                fail('RESTORE_COMMITTED_FENCE_REOPEN_UNCONFIRMED')
            if fence_attempted:
                fail('RESTORE_FAILED_REVIEW_FENCE_AND_TRANSACTION_STATE')
            if isinstance(error, Refused):
                raise
            fail('RESTORE_CONTROL_FAILED_BEFORE_FENCE')


@contextmanager
def restore_interruption():
    """CLI SIGTERM sinyali de kendi çocuk oturumunun finally temizliğinden geçer."""
    def interrupted(_number, _frame):
        fail('RECOVERY_INTERRUPTED')
    original = signal.signal(signal.SIGTERM, interrupted)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, original)


def restore(bundle_path: Path, expected_source: str) -> dict[str, str]:
    with restore_interruption():
        return restore_database(bundle_path, expected_source)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, 'RECOVERY_ARGUMENTS_INVALID; use --help.\n')


def cli(argv: list[str] | None = None) -> int:
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('backup', 'restore'))
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--expected-source', default='')
    parser.add_argument('--trust-own-backup', action='store_true')
    parser.add_argument('--fence-empty-target', action='store_true')
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'status': 'dry-run', 'operation': args.operation, 'connections': 'none',
            'files_created': False, 'endpoint': 'direct numeric loopback and explicit single port; no DNS/proxy/service routing', 'restore_requires': 'trusted own archive; source identity; distinct empty target and explicit maintenance DB on same local server',
            'fence_notice': '--fence-empty-target changes ALLOW_CONNECTIONS; a failed restore can leave target closed. Reopen only from an explicitly selected maintenance DB after review.',
            'scope': 'PostgreSQL only; dry-run is not recovery evidence'}, ensure_ascii=False))
        return 0
    try:
        os.umask(0o077)
        if args.operation == 'restore' and not (args.trust_own_backup and args.fence_empty_target): fail('EXPLICIT_TRUST_AND_FENCE_REQUIRED')
        result = backup(args.bundle, args.repository) if args.operation == 'backup' else restore(args.bundle, args.expected_source)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except Refused as error:
        print(json.dumps({'status': 'refused', 'reason': str(error), 'note': 'No database-tool stderr is disclosed. If execution reached fencing, inspect the target from a maintenance DB before reopening.'}), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError):
        print('{"status":"refused","reason":"RECOVERY_INPUT_OR_IO_FAILURE"}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(cli())
