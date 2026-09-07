/*
 * Tema açılış betiği. `<head>` içinde bloklayıcı olarak yüklenir: sayfanın
 * gövdesi boyanmadan ÖNCE `data-theme` özniteliğini yazar, yoksa koyu tema
 * kullanıcısı her açılışta beyaz bir çakma görür (FOUC).
 *
 * Neden React ağacında satır içi bir <script> değil: React 19 ağaç içindeki
 * satır içi betikler için uyarı verir ("istemcide asla çalıştırılmaz") ve
 * `next/script` + `beforeInteractive` betiği geliştirme sunucusunda <body>
 * başına kuyruklar — ikisi de "boyamadan önce" garantisini zayıflatır.
 * Statik dosya CSP'nin `script-src 'self'` tarafında da sorunsuzdur.
 *
 * Anahtar adı lib/theme.ts ile AYNI olmak zorundadır; lib/theme.test.ts bu
 * dosyayı okuyup anahtarı karşılaştırır, ikisi ayrışırsa test kırılır.
 *
 * "system" tercihi burada çözülür ve işletim sistemi ayarı sonradan
 * değişirse (akşam otomatik geçişi) öznitelik tazelenir.
 */
(function () {
  var root = document.documentElement;

  function resolve() {
    var preference = "system";
    try {
      var stored = localStorage.getItem("dou-synapse-theme");
      if (stored === "light" || stored === "dark" || stored === "system") {
        preference = stored;
      }
    } catch (error) {
      /* gizli mod: depo okunamaz, sistem ayarına düşülür */
    }
    var dark =
      preference === "dark" ||
      (preference === "system" &&
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    root.setAttribute("data-theme", dark ? "dark" : "light");
  }

  resolve();

  if (window.matchMedia) {
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", resolve);
  }
})();
