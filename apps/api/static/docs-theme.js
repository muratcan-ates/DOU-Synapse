/*
 * Belge sayfasının teması. Anahtar uygulamayla AYNIDIR
 * (apps/web/lib/theme.ts · "dou-synapse-theme") ama `localStorage` origin
 * başına ayrıdır: geliştirmede uygulama :3030, API :8030 olduğu için tercih
 * KENDİLİĞİNDEN taşınmaz — her yüzey kendi tercihini tutar, hiç seçilmemişse
 * işletim sistemi ayarına düşer. Aynı anahtar üretimde iki yüzey tek origin
 * arkasında (ters vekil) servis edildiğinde tercihi tek seçime indirir; o
 * yüzden isim ayrıştırılmadan korunur (lib/theme.test.ts çivilar).
 *
 * Bu dosya <head> içinde bloklayıcı olarak yüklenir: sonradan koşarsa koyu
 * tema kullanıcısı her açılışta beyaz bir çakma görür. Ayrı dosya olmasının
 * sebebi bu yüzeyin katı politikası (`script-src 'self'`) — satır içi betik
 * bilinçli olarak yasak.
 *
 * Seçici rayda durur; kontrolü betik kendisi kurar çünkü sayfa statik HTML'dir
 * ve React ağacı yoktur.
 */
(function () {
  var KEY = "dou-synapse-theme";
  var root = document.documentElement;

  function stored() {
    try {
      var value = localStorage.getItem(KEY);
      if (value === "light" || value === "dark" || value === "system") return value;
    } catch (error) {
      /* gizli mod: depo okunamaz, sistem ayarına düşülür */
    }
    return "system";
  }

  function resolve() {
    var preference = stored();
    var dark =
      preference === "dark" ||
      (preference === "system" &&
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    root.setAttribute("data-theme", dark ? "dark" : "light");
  }

  /* Seçili segment: renk tek başına bilgi taşımaz, `aria-pressed` her zaman
     yazılır — ekran okuyucu seçili durumu duyar. */
  function paint(buttons) {
    var current = stored();
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute(
        "aria-pressed",
        buttons[i].getAttribute("data-theme-option") === current ? "true" : "false",
      );
    }
  }

  function wire() {
    var buttons = document.querySelectorAll("[data-theme-option]");
    if (!buttons.length) return;
    paint(buttons);
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function (event) {
        try {
          localStorage.setItem(KEY, event.currentTarget.getAttribute("data-theme-option"));
        } catch (error) {
          /* depo yazılamıyorsa seçim yine de bu sayfada uygulanır */
        }
        resolve();
        paint(buttons);
      });
    }
  }

  resolve();

  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", resolve);
  }

  /* Betik <head>'de koşar, ray henüz yoktur: kontrol DOM hazır olunca bağlanır.
     Tema ise yukarıda, ilk boyamadan önce çözüldü. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
