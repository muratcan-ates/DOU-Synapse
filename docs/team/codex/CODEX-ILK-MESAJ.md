# Codex sohbetine yapıştırılacak ilk mesaj

> Aşağıdaki bloğu olduğu gibi kopyala. Codex'in depo erişimi `muratcan-ates/DOU-Synapse`
> olacak; dal seçimi soruluyorsa `017-completion-integration`.

---

Depo: `muratcan-ates/DOU-Synapse`, dal `017-completion-integration`. Bu sohbet kesintisiz
bir geliştirme kuyruğudur; planlama başka yerde yapıldı, sen uygularsın.

1. Önce `docs/team/codex/CODEX-RUNBOOK.md` dosyasını **tamamen** oku. §0 kurallar, §1
   doğrulanmış durum, §2 iş döngüsü, §3 iş kuyruğu (Faz A→I), §4 bana sorulacaklar, §5 rapor biçimi.
2. `018-codex-production-line` dalını 017'nin ucundan aç, §0'daki kurulum ve kapı komutlarını
   koştur, ilk çıktıyı §5 biçiminde raporla (hangi kapılar yeşil, hangileri ortamında koşamıyor).
3. Sonra Faz A / İş A1'den başla ve kuyruğu **yukarıdan aşağı**, sormadan tüket. Her iş bir
   commit; her commit'ten önce §0 kapıları; hassas yola dokunduysan aynı commit'te dossier +
   kanıt ve `refresh_aggregate_dossier.py`. İlk commit'ten sonra 017 hedefli draft PR aç ve her
   commit'i push'la.
4. Yalnız §4'teki maddelerde dur: sır, bulut hedefi, JWT algoritması, bağımlılık ekleme, şema
   kararı. Sorarken "ne · neden · alternatif · beklerken ne yapıyorum" yaz ve **sıradaki işe geç**.
5. Ölçmediğin hiçbir şeyi yapılmış, geçmiş, kanıtlanmış yazma. Koşamadığın kapıya `not-run`
   yaz. Sayı/SHA/dosya uydurma. `Co-Authored-By` yok. `.env` oluşturma, sır yazma.

Başla: runbook'u oku ve 2. adımın raporunu ver.
