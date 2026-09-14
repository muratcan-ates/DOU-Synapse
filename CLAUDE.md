@AGENTS.md

- Bu oturum kendi `git worktree` klasöründe çalışır; `~/code/DOU-Synapse` dâhil başka ağaca dokunma.
- `pytest` her zaman oturuma özgü `TEST_DB_NAME=...` ile koşar — paralel şeritler aynı veritabanını siler.
- `.ai/policy.json`'daki hassas yola dokunan commit, aynı commit'te dossier + kanıt taşımak zorundadır.
