# Codex sohbetine yapıştırılacak ilk mesaj

> Olduğu gibi kopyala. Depo: `muratcan-ates/DOU-Synapse`; dal seçimi soruluyorsa **`018-codex-production-line`**.

---

Depo: `muratcan-ates/DOU-Synapse`, dal **`018-codex-production-line`** (hazır; 017-completion-integration'dan dallandı).
Bu sohbet kesintisiz bir geliştirme kuyruğudur; planlama başka yerde yapıldı, sen uygularsın.

1. Önce `docs/team/codex/CODEX-RUNBOOK.md` dosyasını **tamamen** oku (§0 kurallar, §1 durum, §2 döngü, §3 kuyruk Faz A→I,
   §4 bana sorulacaklar, §5 rapor biçimi). Kararların gerekçesi `docs/team/codex/40-BIRLESIK-PLAN.md`.
2. Dalı checkout et, §0'daki kurulum ve kapı komutlarını koştur, ilk çıktıyı §5 biçiminde raporla (hangi kapı yeşil, hangisi ortamında koşamıyor).
3. Faz A / İş A0'dan başla ve kuyruğu **yukarıdan aşağı**, sormadan tüket. Her iş bir commit; her commit'ten önce §0 kapıları;
   hassas yola dokunduysan aynı commit'te dossier + kanıt; her push'tan önce `refresh_aggregate_dossier.py`.
   İlk commit'ten sonra `017-completion-integration` hedefli **draft PR** aç ve her commit'i push'la.
4. Yalnız §4'teki maddelerde dur (bağımlılık onayı, sır, bulut hesabı, JWT, şema kararı): "ne · neden · alternatif · beklerken ne yapıyorum"
   yaz ve **sıradaki işe geç**. ⛔onay işaretli araçları onay gelmeden ekleme.
5. Ölçmediğin hiçbir şeyi yapılmış/geçmiş/kanıtlanmış yazma; koşamadığın kapıya `not-run`. Sayı/SHA/dosya uydurma; var olmayan dosyayı
   "yeni dosya:" diye işaretle. `Co-Authored-By` yok. `.env` oluşturma, sır yazma.

Başla: runbook'u oku ve 2. adımın raporunu ver.
