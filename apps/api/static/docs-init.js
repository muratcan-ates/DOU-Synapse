/* API belge sayfasının erişim kapısı ve Swagger başlatması.
 *
 * Sözleşme (`/openapi.json`) yalnız platform yöneticisine açıktır. Tarayıcı
 * gezinmesi `Authorization` başlığı taşıyamaz, bu yüzden sayfa şemayı kendisi
 * ister: jeton oturum belleğinde tutulur (sekme kapanınca silinir; kalıcı
 * depolamada tutmak jetonu XSS'e daha uzun süre açık bırakırdı).
 *
 * Ayrı dosya olmak zorunda: belge yüzeyinin politikası `script-src 'self'`.
 */
(function () {
  var KEY = "dou-synapse-docs-token";
  var gate = document.getElementById("gate");
  var form = document.getElementById("gate-form");
  var input = document.getElementById("gate-token");
  var note = document.getElementById("gate-note");
  var host = document.getElementById("swagger-ui");

  function show(message, tone) {
    note.textContent = message;
    note.dataset.tone = tone || "info";
  }

  function boot(token) {
    show("Sözleşme alınıyor…", "info");
    fetch("/openapi.json", { headers: { Authorization: "Bearer " + token } })
      .then(function (response) {
        if (response.status === 401 || response.status === 403) {
          throw new Error(
            "Bu sayfa yalnız Bilgi İşlem yöneticilerine açıktır. " +
              "Jeton geçerli değil ya da hesabın yönetici yetkisi yok."
          );
        }
        if (!response.ok) throw new Error("Sözleşme alınamadı (" + response.status + ").");
        return response.json();
      })
      .then(function (spec) {
        sessionStorage.setItem(KEY, token);
        gate.hidden = true;
        host.hidden = false;
        window.ui = SwaggerUIBundle({
          spec: spec,
          dom_id: "#swagger-ui",
          deepLinking: true,
          docExpansion: "list",
          defaultModelsExpandDepth: 0,
          tryItOutEnabled: true,
          presets: [SwaggerUIBundle.presets.apis],
          layout: "BaseLayout",
          /* "Try it out" da aynı kimlikle gider; yoksa her denemede 401 döner
             ve sayfa çalışıyormuş gibi görünüp hiçbir şey denenemezdi. */
          requestInterceptor: function (request) {
            request.headers.Authorization = "Bearer " + token;
            return request;
          },
        });
      })
      .catch(function (error) {
        sessionStorage.removeItem(KEY);
        gate.hidden = false;
        host.hidden = true;
        show(error.message, "error");
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var token = input.value.trim();
    if (!token) {
      show("Jeton boş olamaz.", "error");
      return;
    }
    boot(token);
  });

  var saved = sessionStorage.getItem(KEY);
  if (saved) boot(saved);
})();
