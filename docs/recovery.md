# PostgreSQL backup and restore

8 Eylül 2026: ayrı sentetik PostgreSQL16 hedeflerinde gerçek restore, içerik/rol/RLS karşılaştırması ve beş olumsuz senaryo ölçüldü. Güncel 22 göçlü kaynakla ek deneyde 30 ilişki ve toplam 14 sentetik satırın eşliği de geçti. Yerel v4 araç kodu 018 dalına entegredir; yeni kaynakların hosted kabulü ayrıca gerekir. [Ölçüm ve sınırlar](../specs/018-codex-production-line/evidence/d3-local/README.md). Bu, canlı bulut/yedek saklama veya bütün sürümün üretime hazır olduğuna ilişkin onay değildir.

## Supported scope

The scripts require Python 3.11+, a POSIX filesystem with `O_NOFOLLOW` and directory descriptors, PostgreSQL 16 client tools, and an explicitly selected PostgreSQL 16 DBA superuser connection. Backup and restore execution also require the already-installed psycopg runtime from the API environment; no new dependency is added. Set `DOU_RECOVERY_PYTHON=/absolute/repository/apps/api/.venv/bin/python` before using the wrappers for real backup or restore, or invoke that interpreter on `scripts/recovery.py backup ...`. Default dry-run and offline tests require only the standard library. A missing psycopg runtime fails before a bundle is created. These are standalone, single-thread CLI tools; do not embed their temporary libpq-environment isolation in a multithread application. This is a local DBA operation, not a general Supabase or managed-cloud backup interface. Superuser is required for the cluster identity/role inspection, object ownership transfer and connection fence. The tools do not grant themselves that role or create roles/databases.

This implementation accepts only one numeric loopback address and one explicit port, connected directly to the local PostgreSQL server. DNS names (including `localhost`), socket paths, multi-host/port lists, service routing and non-loopback endpoints are refused. Local TCP proxies, tunnels, load balancers, port remapping and administrative cluster/listener replacement are outside the support contract; an address syntax check cannot prove that an operator has not installed a proxy. Keep the source DBA/cluster and role/database administration quiescent during capture. This is not a universal cloud identity-binding claim.

The archive is a complete custom-format `pg_dump` of one ordinary DOU-Synapse database. Ownership, object grants, default grants, policies, RLS/FORCE RLS and security-definer metadata remain in the archive; neither `--no-owner` nor `--no-acl` is used. Required cluster roles and their attributes/memberships must already match on the target cluster. The source role scope is the complete two-way membership component starting from the database owner/object roles: incoming members, their transitive members and outgoing memberships are included. All SET/INHERIT/ADMIN flags and every scoped role's attributes are preserved. This conservative component can include more roles than a minimal reachability calculation; it intentionally refuses an extra target login or indirect bridge into that component. A completely disconnected target membership component does not block restore. The same incoming source membership is supported. Old one-direction membership manifests are explicitly refused; roles are never silently added, weakened or revoked to make a restore pass. Role passwords and authentication-provider identities are not exported. Database owner and database grants are applied to the distinct target name, with their normalized values checked before commit.

The source and target must have matching PostgreSQL major, encoding/locale/collation version, default tablespace name, connection limit and template status. The extension default versions available on the target must equal the source versions. This intentionally conservative condition avoids claiming arbitrary extension-version migration support. Additional tablespaces, if used by application objects, must be provisioned beforehand; missing tablespaces fail the restore transaction. Database-specific settings, database security labels and database grants issued by non-owner grantors are currently refused instead of silently omitted. Roles and database administration must stay quiescent throughout the operation; the database connection fence cannot lock cluster-wide DBA changes.

The target must be a fresh, trusted `template0`-based database with ordinary public schema and plpgsql only. A namespace check alone is insufficient: the empty-target guard also rejects normal user OIDs in relation, procedure, type, namespace, operator, collation, text-search, cast, transform and language catalogs, plus extensions, large objects, event triggers, replication publications/subscriptions, foreign data wrappers/servers and default privileges. This is deliberately more restrictive than “no application tables.” Custom templates can be rejected even if an operator considers them empty. This does not certify a maliciously altered PostgreSQL system catalog as trustworthy.

## Private bundle and completion

`backup.sh` creates a previously nonexistent, absolute bundle directory with mode `0700`. It refuses symlink components, traversal, existing bundles and overwrites. Its two final files have mode `0600`:

- `database.dump`: custom PostgreSQL archive, with TOC parsing checked by `pg_restore --list`.
- `manifest.json`: a completion record written only after a successful dump, archive parsing and stable before/after source-security/schema-lineage snapshots. It records archive size/SHA-256, source identity, PostgreSQL/extension metadata, the versioned membership scope, schema migration hashes and Git commit. The source-capture version records the direct-loopback exported-snapshot protocol; old unbound source-capture manifests are refused. Tracked migration changes are explicitly recorded; migration content hashes are the exact local inputs, not proof that the running database has that schema.

The source identity is read inside a READ ONLY REPEATABLE READ transaction on one psycopg control connection. That transaction exports a snapshot and remains open while trusted `pg_dump --snapshot` reads it. The non-secret snapshot ID is passed as a pg_dump option; connection secrets are not. After dumping, the same connection is probed, its old transaction is closed, and fresh metadata is read in a new read-only transaction on that same connection. This catches identity/role/schema changes visible after capture, rather than rereading the old snapshot and calling it a fresh check. Loss of the control connection or a metadata mismatch prevents completion. It does not prove safety under malicious DBA/proxy intervention, or establish behavior outside the measured local exercise.

A failed dump can leave a private partial bundle, with no valid completion manifest. Do not retry into that directory. Inspect/remove it separately under the operator's retention policy and choose a new path. The tools never delete a previous backup. A manifest or directory `fsync` failure is an unsuccessful operation; use the receipt status and revalidate the bundle, rather than treating mere file presence as a durable backup guarantee.

The archive and private manifest contain personal data or administrative metadata. POSIX permissions are not encryption. Encryption, protected off-host storage, access logs, retention, expiry/deletion and restore-time privacy reconciliation are separate deployment controls. Restoring an older backup may reintroduce records deleted after its capture; reconcile the data lifecycle before allowing user traffic.

## Default dry run

Both wrappers default to a **zero-effect plan**. They read neither connection environment nor bundle contents, create nothing and contact nothing. This output is deliberately not called verification or a rehearsal. A missing bundle path can therefore be shown in a dry run.

```sh
scripts/backup.sh --bundle /absolute/private/backups/new-unique-bundle
scripts/restore.sh --bundle /absolute/private/backups/new-unique-bundle
```

The dry-run notice states that real restore requires explicit trust, a recorded source fingerprint, a distinct empty target and the connection fence. `--fence-empty-target` changes `ALLOW_CONNECTIONS` and can leave a failed target closed.

## Connection inputs and actual execution

Use the following environment-variable prefixes, supplied by a secret manager or a private environment setup. Do not place connection URLs/passwords in command arguments or check them into files:

| Operation | Required variables | Optional connection variables |
|---|---|---|
| Backup | `DOU_BACKUP_PGHOST`, `DOU_BACKUP_PGPORT`, `DOU_BACKUP_PGDATABASE`, `DOU_BACKUP_PGUSER` | same prefix + `PGPASSFILE`, `PGPASSWORD`, `PGSSLMODE`, `PGSSLROOTCERT`, `PGSSLCERT`, `PGSSLKEY`, `PGCONNECT_TIMEOUT` |
| Restore target | `DOU_RESTORE_PGHOST`, `DOU_RESTORE_PGPORT`, `DOU_RESTORE_PGDATABASE`, `DOU_RESTORE_PGUSER` | same suffixes under `DOU_RESTORE_` |
| Restore maintenance | `DOU_MAINTENANCE_PGHOST`, `DOU_MAINTENANCE_PGPORT`, `DOU_MAINTENANCE_PGDATABASE`, `DOU_MAINTENANCE_PGUSER` | same suffixes under `DOU_MAINTENANCE_` |

For restore, maintenance and target must have the same explicit numeric host and port and different database names. Their live cluster system identifiers, postmaster start times, server ports and backend identities are compared. No maintenance database or credentials are inferred from the target.

Prefer a protected `PGPASSFILE` to storing a password in a shell history. The database value is a plain database name; DSNs are refused. A host such as `127.0.0.1` or `::1` and a decimal port from 1–65535 are mandatory. Host and hostaddr are pinned to the same numeric loopback address. Ambient `PG*` defaults, service routing and `PGOPTIONS` are discarded; the standalone psycopg control connect temporarily removes ambient `PG*` variables and restores them immediately afterward. The scripts set an explicit pg_catalog search path and a non-sensitive application name. PostgreSQL's implicit temporary-schema precedence still applies; this is not a namespace sandbox for untrusted restore SQL. `DOU_RECOVERY_PG_BIN` optionally chooses the trusted PostgreSQL executable directory; do not point it at untrusted programs. PostgreSQL connection parameters reach command-line client tools only through their environment. The psycopg controller receives them as keyword arguments, never process arguments or stdout. SQL reaches `psql` through private file descriptors/stdin.

After explicitly selecting an authorized source and a new backup directory:

```sh
scripts/backup.sh --bundle /absolute/private/backups/new-unique-bundle \
  --repository /absolute/path/to/DOU-Synapse --execute
```

Record the successful receipt's `source_identity_sha256` separately. It hashes the cluster system identifier and database OID, so two host aliases or a renamed database cannot bypass the same-source check. A physically cloned cluster with the same system identifier/OID is conservatively treated as the same source. The database name remains private descriptive metadata. The expected fingerprint must come from that separately retained source receipt, not an untrusted archive sender.

Once an operator has prepared and selected a **different, newly created empty synthetic target** for the exercise:

```sh
scripts/restore.sh --bundle /absolute/private/backups/new-unique-bundle \
  --expected-source <recorded-source-sha256> \
  --trust-own-backup --fence-empty-target --execute
```

The tools do not create the target. No `DROP`, `--clean`, termination of other sessions, target recreation or ownership bypass is part of their restore protocol. An archive is executable SQL: use only an operator's own trusted backup with trusted client tools. A hash detects byte corruption; it does **not** authenticate the backup's producer or make malicious SQL safe for a superuser.

## Restore ordering and race boundary

1. Open the private bundle without following symlinks, verify its completion structure and the independently recorded source fingerprint, and copy archive bytes into an anonymous private file while hashing those exact copied bytes. Compare size/SHA-256 before using them. `pg_restore` reads that same private copy; it never reopens the original pathname after verification. Replacement of the original archive cannot swap later restore input. Same-UID process compromise is outside this filesystem boundary.
2. Parse the custom archive and generate restore SQL into another private anonymous file. Use default DBA creation plus ALTER OWNER and preserve grants; do not use the SET SESSION AUTHORIZATION ownership mode. Neither phase connects to the target.
3. Open one persistent `psql` target session. That same session supplies empty-state/security metadata and its database OID/name, cluster system identifier, postmaster start time, backend PID/start time, application name and user. Validate source/target difference, format/settings, required roles and membership graph, extension versions and absence of other target connections; repeat the SQL guard in this live session. Prepare the complete restore script in the private inherited FD before changing connection policy.
4. Open a second physical connection through the separately supplied maintenance environment using psycopg. It must be a different database on the same explicit local server. Validate its superuser status, live cluster/postmaster/port identity, and the target's exact OID/name plus the single expected target backend PID/start/user/application name. The initial identity queries and each short fence transaction have time limits.
5. On the maintenance connection, begin a short transaction, acquire `SHARE ROW EXCLUSIVE` on `pg_catalog.pg_database`, repeat identity/session/count/fence checks, apply `ALLOW_CONNECTIONS false`, verify and commit. The catalog lock constrains database-name/OID administration between the check and ALTER; it is released immediately after fencing. It is **not** held throughout restoration and is **not** claimed to make concurrent CONNECT observations absolute. Each activity read clears the cached statistics snapshot. A fresh check follows the fence COMMIT.
6. The same surviving target `psql` receives a small stdin command to read `/dev/fd/N`, where N is the explicitly inherited anonymous restore-script FD. The pathname of the original archive is never reopened, and large SQL/COPY data is not streamed through the control pipe. The script begins one transaction and repeats fenced state, exact identity, empty state, role/membership and other-connection guards **after** the maintenance fence COMMIT. Existing/concurrently arriving sessions are never terminated; rejection can intentionally leave the target fenced. Operational isolation remains required.
7. Inside that transaction, obtain a transaction ID and apply the source database owner/grants before the generated DBA creation, ALTER OWNER and COPY SQL. Objects are created through the existing authorized DBA connection, then assigned their recorded source owners. No CREATE privilege is granted to restricted helper roles. The same final normalized security metadata check verifies ownership, grants, policies and security-definer properties. Commit once. On the same target session, query `pg_xact_status` for that exact `xid8`; only an exact fresh nonce-prefixed JSON line with `committed`, a valid transaction ID and the unchanged backend binding counts as observed commitment. Unknown status, malformed data, wrong session, EOF or timeout cannot authorize reopening. Stdout/stderr stay private; the bounded parser ignores unrelated lines and never relays their content.
8. Only after that commitment receipt does the maintenance connection repeat its exact cluster/backend identity and the target OID/name/PID/start/count/fence checks under another short catalog-lock transaction, then set `ALLOW_CONNECTIONS true` and confirm the committed state. A successful restore receipt explicitly states `commit_status: committed`. It is not yet a data-equivalence, RLS or retrieval acceptance result.

The metadata digest covers schema/relations owners and grants, column/default grants, RLS flags/policies, security-definer/search-path settings and index definitions. It is **not** a data-row checksum, exhaustive DDL equivalence proof or proof that application RLS and retrieval work. Source security/schema metadata must be unchanged before and after dumping on the same control connection; concurrent ordinary data changes use the exported consistent snapshot shared with pg_dump. Maintenance that changes those metadata during capture is rejected.

## Failure handling

Tool stdout/stderr are never relayed on failure. The CLI prints fixed reason codes rather than SQL, connection details, answers or chat content. Private subprocess output is discarded after inspection of the bounded nonce-marked protocol and PostgreSQL commit-status receipt. SQL exceptions from the psycopg control connection are not disclosed. On failure the tool closes or terminates only its own psql child; the standalone restore SIGTERM handler enters that same cleanup path and then restores the prior signal handler; transaction outcome near COMMIT can still require manual review.

- Preflight refusal means no connection-policy or restore-data mutation was attempted; the persistent target connection may already have been opened. Archive failure likewise occurs before target contact.
- `RESTORE_FAILED_REVIEW_FENCE_AND_TRANSACTION_STATE` means execution failed without an observed PostgreSQL committed-status receipt. The target may be fenced. A connection loss around commit can leave transaction outcome uncertain; this code is **not** a blanket rollback guarantee.
- `RESTORE_COMMITTED_FENCE_REOPEN_UNCONFIRMED` means the PostgreSQL committed-status receipt was observed, but reopening was not confirmed. Do not rerun the restore into this now-populated target.

For either execution failure, an operator must inspect the selected target's identity, connection policy and transaction outcome from an explicitly chosen maintenance database. No maintenance database is guessed by the script and no failure triggers automatic reopening. A controlled reopen, if needed for inspection, requires maintaining the target's isolation from all other clients. Only then should the operator decide whether it is safe to permit traffic or retain the failed target for investigation. The tool never erases an uncertain target to make a retry work.

## Measured local acceptance and remaining exercises

The v4 restore completed on a distinct template0 target; all29 relation schemas and row-multiset hashes matched, including20000 synthetic vectors. Owners, grants, SECURITY DEFINER and actual dou_app RLS identities matched. The ANN recall@8 of one post-restore query was0.875; this is neither a semantic-quality score nor a replacement for the C1 retrieval evaluation.

Five actual negative exercises covered: nonempty-target refusal, real22012 before final COMMIT, a committed receipt withheld from orchestration, controlled reopen failure after commit, and rejection of a new real dou_app connection after the fence. Only the definite pre-COMMIT test target was separately reviewed and reopened by root; read-only empty/schema-owner/ACL/format/security-catalog/role-component equality with its original state passed. Unknown failed targets remained closed. These are controlled synthetic tests, not all network-loss possibilities.

The earlier 29-relation restore source predates D1/D2. A separate current-schema exercise now covers 22 exact migration hashes including 0025/0026: all 30 application relations (28 public, 2 app), their 14 synthetic rows and normalized security-catalog/role component matched. It includes pending/failed/completed jobs, quota rows and one vector. Actual dou_app teacher saw 1 course/3 documents/1 chunk/3 jobs; outsider saw 0. Both identities received 42501 when directly reading either quota table. No external Storage was copied and no semantic/ANN-quality claim is made. The root receipt recorded 1.252 s overall, 0.397 s backup and 0.422 s restore. This is a dirty working-tree source exercise, not a committed release: the backup's tracked_schema_dirty=false excludes untracked migration files; the exact 22-hash manifest and separate root dirty receipt establish its source lineage. The new archive target is `specs/018-codex-production-line/evidence/d-final-local/`; earlier receipts remain unchanged. Still open: cross-cluster exported-snapshot/control-loss exercises, real additional-role-graph negatives and concurrent writer between initial guard and fence (07). Offline tests cover relevant protocol decisions but cannot substitute for these actual scenarios. Encryption, off-host storage, scheduling, retention and restore-time deletion reconciliation depend on deployment. Store content-free results and source hashes, not backup bytes, in repository evidence.

## V3 protokolünün V4 içinde korunan çevrimdışı kanıt sınırı

V3 testleri; açık ve farklı bakım veritabanı, aynı endpoint/cluster/postmaster, hedef PID/başlangıç/sayısı, fence öncesi ve sonrası kontroller, COMMIT belirsizliğinde kapalı kalma ve başarılı COMMIT sonrası başarısız reopen durumunun doğru raporlanmasını kapsar. POSIX boru/anonim-FD testi gerçek küçük bir Python çocuk çalıştırır; bu çocuk PostgreSQL değildir. Eski snapshot ve iki yönlü rol grafiği kontrolleri korunur. Dokuz olumsuz mutant ayrı geçici kopyalarda çalıştırılır; aday kaynakları değiştirilmez.

V3 hazırlığındaki bu kabul, sonraki gerçek v4 restore ve karşılaştırma deneyleriyle sınırlı yerel kapsamda ölçüldü. Sıralı sahte bağlantı kontrolleri tek başına SQL davranışlarını kanıtlamaz. Önceki v2/v3 başarısız sonuçları korunur.


## V4 dar sahiplik düzeltmesi

V3'ün yeni sentetik target04 denemesinde fence COMMIT başarılı oldu; restore, `app.sync_profile_from_auth_user()` fonksiyonunu `dou_auth_bridge` oturum yetkisiyle oluştururken `SCHEMA_PERMISSION_DENIED` verdi. Bu rolün `app` şemasında CREATE yetkisinin olmaması bilinçlidir ve değiştirilmez. V4 üretim kodundaki tek fark, SQL üretim argümanından `--use-set-session-authorization` kaldırılmasıdır. `--no-owner` ve `--no-acl` eklenmez; bakım bağlantısı, tek restore transaction'ı, son katalog doğrulaması ve belirsiz COMMIT'te kapalı kalma değişmez.

Yerel resmi PostgreSQL 16 pg_restore belgesi, bu seçeneğin varsayılan ALTER OWNER yerine SET SESSION AUTHORIZATION çıktısı ürettiğini ve bazı nesne geçmişlerinde restore işleminin başarısız olabileceğini açıklar. Ayrıca yalnız kendi sentetik arşivden ilgili tek fonksiyon, veritabanı bağlantısı açılmadan iki modda gerçek pg_restore ile SQL'e dönüştürüldü. Eski modda fonksiyon sahibine SET SESSION AUTHORIZATION; varsayılan modda CREATE FUNCTION sonrasında aynı sahibine ALTER FUNCTION OWNER TO bulundu. Her iki çıktı SECURITY DEFINER niteliğini korudu; yeni mod restricted role için CREATE şema yetkisi eklemedi. Özel SQL dosyaları kanıt deposunun dışındadır; içeriksiz sonuç/hash özeti [owner-render.v4.json](../specs/018-codex-production-line/evidence/d3-local/owner-render.v4.json) içindedir. Bu ölçüm tüm verilerin geri yüklendiğini veya RLS'nin gerçek bağlantıda çalıştığını kanıtlamaz.

V4 target05 üzerinde gerçek CLI restore ile tamamlandı; ardından içerik/satır ve gerçek rol/RLS/retrieval incelemesi çalıştırıldı. Kesin kapsam ve0.875 tek-sorgu ANN ölçümü yukarıdaki kabul bölümündedir. V3 kaynakları ile target03/04 başarısız makbuzları ve kapalı hedefleri korunur; yeniden açılmaz veya yeniden kullanılmaz.
