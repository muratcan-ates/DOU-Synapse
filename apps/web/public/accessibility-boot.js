/* İçerik ayrıştırılmadan önce yerel erişilebilirlik tercihlerini uygular.
 * Ayrıştırıcı eşliği lib/accessibility.test.ts içinde bu gerçek betikle sınanır.
 * Tema/oturum anahtarlarını değiştirmez; CSP script-src 'self' ile çalışır. */
(function () {
  var value = {};
  try {
    var parsed = JSON.parse(localStorage.getItem("dou-synapse-accessibility") || "null");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed) && parsed.version === 1) value = parsed;
  } catch (error) { /* Depo kapalıysa varsayılanlar ve sistem hareket tercihi kullanılır. */ }
  var root = document.documentElement;
  var reduce = value.motion === "reduce" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  root.setAttribute("data-text-size", value.textSize === "large" ? "large" : "default");
  root.setAttribute("data-motion", reduce ? "reduce" : "full");
  root.setAttribute("data-contrast", value.contrast === "more" ? "more" : "standard");
  root.setAttribute("data-links", value.underlineLinks === true ? "underlined" : "standard");
})();
