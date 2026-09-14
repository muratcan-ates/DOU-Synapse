# Mevcut Codex sohbetine (DOU-Synapse / "İncele ve yapılacak işleri çıkar") yapıştır

Onay: **Evet — S9/S10 kodu ve sentetik kanıt arşivi herkese açık depoya gönderilebilir; sentetik veridir, kişisel veri yok.**
Durum güncellemesi: PR #26 bugün 13/13 yeşil (CodeQL bulguları ve toplayıcı dossier Claude tarafından kapatıldı, commit'ler 9aa8e45, 3801f1d, 22a85d3).
Runbook **v2** geldi: `git checkout 018-codex-production-line && git pull --ff-only`, sonra `docs/team/codex/CODEX-RUNBOOK.md` §0–§3 ve `40-BIRLESIK-PLAN.md`'yi oku.

Yeni çalışma düzeni: entegrasyon dalı `018-codex-production-line`'a **doğrudan commit yok**; şeritler ayrı dallarda çalışır, Claude birleştirir.
Senin şeridin **L4 — Retrieval ve operasyon** (kendi açık işlerinin devamı): `git checkout -b 018-l4-retrieval-ops` ve aşağıdaki şerit dosyasındaki kuralları uygula.
`refresh_aggregate_dossier.py` **koşturma**; dossier numaraların 070–079; olası göç numaran 0028. PR hedefi `018-codex-production-line`, başlık `[L4] …`.
Zamanlanmış "her 15 dk devam" görevi kalabilir; her uyanışta önce `git status` ve şerit dosyasının sırasına bak.

(Altına L4-retrieval-ops.md dosyasının tamamını yapıştır.)
