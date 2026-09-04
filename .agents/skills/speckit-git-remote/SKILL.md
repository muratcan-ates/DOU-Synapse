---
name: speckit-git-remote
description: Inspect and validate a Spec Kit repository’s fetch and push destinations for integrations; change only an explicitly requested remote after resolving its exact target.
---

# Inspect the repository destination

Resolve the actual task repository with `git rev-parse --show-toplevel`; the installed skill directory is not the repository. Begin read-only. List remote names and the current branch's upstream, then inspect the user-selected remote. Without an explicit name, prefer its upstream remote or an unambiguous `origin`; multiple plausible destinations require a choice before a write.

Capture the results of `git remote get-url --all <name>` and `git remote get-url --push --all <name>` programmatically. Remote URLs can contain credentials: redact user-info, tokens and sensitive query/fragment values before any tool output, logs or user-facing report. Inspect both fetch and push destinations; they may differ, and Git URL rewrites can change the effective host. A remote name by itself does not identify the destination.

Parse HTTPS, `ssh://` and scp-style SSH URLs. Report the host, owner/repository path where recognizable, selected remote, and fetch/push differences. Mark public GitHub only when the parsed effective hostname is exactly `github.com`; a similar suffix, local path, SSH alias, or another host is not evidence of that. Treat enterprise GitHub as a distinct, verified host. Do not invent an owner, repository or hosting provider when parsing is inconclusive.

An optional `git ls-remote --heads <remote>` checks read access and current refs when relevant to the request; use noninteractive authentication and a bounded timeout. Lack of network or credentials means access is unverified. It does not authorize credential setup or replacement of a remote. Redact captured command errors before reporting, because Git may include the original URL.

## When a remote change is requested

Confirm from the existing request the operation, repository, remote name and exact destination. Inspect the current value first. If it already matches, report a no-op. Use only the necessary `git remote add`, `set-url`, or `remove` operation; preserve other remotes, extra URLs, push URLs and credential configuration unless that precise change was requested. A request to detect a remote, prepare issues or review a repository is read-only.

Read the effective destination back after a mutation. Do not overwrite `origin` just because another URL appears in a document. If existing configuration conflicts with the intended target, prepare the exact proposed change and resolve that ambiguity before writing. Do not create a hosted repository, push commits, delete a remote repository, send issues, or change authentication as an incidental step. Existing explicit session authorization remains valid; do not ask for it again.

Return a concise, sanitized destination result and any unverified access. Missing Git, repository or remote is a reported absence that does not block unrelated Spec Kit work.
