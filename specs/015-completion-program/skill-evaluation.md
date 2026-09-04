# Completion skill forward test

Installed skill: /Users/muratates/.codex/skills/dou-synapse-completion-loop. Created with skill-creator initializer; quick_validate passed using the project's Python runtime. No scripts/assets were needed.

An independent agent received only the skill, actual ledger and two continuation scenarios. It verified branch/base/dirty state, selected read-only review when all implementation files were owned, and kept fake/local evidence separate from real/human/staging. It correctly avoided creating an unsolicited automation for a request to continue the current work. In the external-input scenario it prepared remaining offline packets and stopped repeated unchanged retries only after independent work was exhausted.

Two defects were clarified after the trial: a ready milestone excludes another active owner's files (including the ledger), and local/offline/real/human substates must remain separate within one milestone. The trial did not modify the repository or run paid model calls. This skill defines a reusable execution workflow; it is not itself a background scheduler.
