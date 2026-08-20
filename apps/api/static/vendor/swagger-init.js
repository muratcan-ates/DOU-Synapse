/* Swagger UI başlatma betiği — AYRI DOSYA olmak zorunda.
 *
 * Belge yüzeyinin politikası `script-src 'self'`; FastAPI'nin varsayılan
 * /docs sayfası inline <script> kullanır ve bu politikada hiç çalışmaz
 * (kullanıcı boş sayfa görür). Betiği dosyaya almak, politikayı gevşetmeden
 * sayfayı çalıştırmanın yoludur.
 */
window.addEventListener("load", function () {
  window.ui = SwaggerUIBundle({
    url: "/openapi.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    docExpansion: "list",
    defaultModelsExpandDepth: 0,
    tryItOutEnabled: true,
    presets: [SwaggerUIBundle.presets.apis],
    layout: "BaseLayout",
  });
});
