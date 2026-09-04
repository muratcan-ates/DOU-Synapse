# 013 local verification

Candidate binding: SELF in the R3 dossier. Base ba69ff9eec0a2867614dd145eb6e995f6c0af5ac. Date 2026-09-04.

| Gate | Result |
|---|---:|
| Full backend | 946 passed |
| New authoring API cases | 37 passed |
| Frontend library | 406 passed |
| Real local API + browser, fake LLM | 37 passed, no skips |
| Authoring SQL | 26 checks + helper privileges passed |
| Authoring mutations / concurrency | 5 mutations caught / 6 assertions passed |
| Existing assessment SQL / isolation SQL | 59 / 115 checks passed |
| Existing assessment mutations | 24 caught |
| Ruff, format, mypy, TypeScript, production build | Passed |
| OpenAPI, docs, contrast, gold-set integrity | Passed |

The teacher journey creates material through the upload API, generates a classified question, edits the correct option and source mapping, saves, approves, creates a matching blueprint and publishes it. No privileged SQL question insertion is used in that browser journey. Both 375px themes were inspected.

The new database guard and old RLS tests run sequentially on the same disposable template. The before/after normalized database dumps match. SQL mutations independently remove protections and must turn the corresponding check red.

The first full backend run exposed an outdated route-count assertion and two test-environment overrides that masked configuration defaults. The assertion now checks the two actual new paths; the clean final environment passed the entire suite. No production behavior was relaxed to make tests pass.

Reproduction context and detailed commands: [local evidence](../../.ai/evidence/013-question-authoring-r1.json). Acceptance and known limits: [quickstart](quickstart.md). Human domain approval and real-provider/staging verification remain pending. No deployment or main-branch merge was performed.
