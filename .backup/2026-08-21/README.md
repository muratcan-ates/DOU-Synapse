# DOU-Synapse device-cleanup backup — 2026-08-21

This backup was created before removing local Codex worktrees and caches from the Mac.

## Primary snapshot

- Backup branch: `backup/device-cleanup-2026-08-21`
- API-observability working-tree snapshot: `6ce4f3561a7c25eeb0e7794090f2dd771f727a57`
- Snapshot parent: `db2f42a9ef7e75423c54db45fecedd1436ffa91b`
The branch contains a normal Git snapshot of the previously uncommitted API-observability work. Synthetic checkpoint commits then connect every commit that existed only in local refs or reflogs, plus every unreachable commit found by `git fsck` at cleanup time. Small holder commits connect dangling trees and blobs that were not owned by any commit. This keeps the backup Git-native and lets GitHub inspect the pushed objects.

## Verification performed

- The API-observability snapshot contains 49 explicitly staged files and no remaining unstaged or untracked files.
- No file in that snapshot exceeds GitHub's normal file-size limit.
- A high-confidence offline signature scan found no added private key or live token pattern in the snapshot diff.
- The final branch is accepted only if every frozen local-only commit is an ancestor of the remote backup tip after push.
- Push-protection failure must not be bypassed.

## Restore

1. Clone the repository and fetch the backup branch.
2. Inspect the manifests under `.backup/2026-08-21/`.
3. Verify the restored object database:

   ```sh
   git fsck --full
   git show-ref
   ```

4. Recover a required historical commit by SHA from the commit manifest, for example with `git branch recovered/<name> <sha>`.

Raw Codex and Claude transcript caches are not included in this public branch. They can contain private prompts, local paths, tool outputs, and credentials, and their raw size exceeds normal GitHub branch limits.
