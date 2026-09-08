/** Yalnız audit üreten E2E dosyalarının kullandığı otomatik yanıt toplayıcısı. */
import { test as base, type Request, type Response } from "@playwright/test";

import { AuditCapture, expectedAuditScope } from "./audit-receipts";
import { requireE2eRunId } from "./fixtures";

export const test = base.extend<{ auditCapture: AuditCapture; _auditAuto: void }>({
  auditCapture: async ({ context }, use) => {
    const directory = process.env.E2E_AUDIT_DIR;
    const databaseName = process.env.E2E_DATABASE_NAME;
    if (!directory || !databaseName) throw new Error("Audit koşusu global setup ile hazırlanmalı.");
    const capture = new AuditCapture(directory, expectedAuditScope(requireE2eRunId(), databaseName));
    let listenerFailed = false;
    const onRequest = (request: Request) => {
      try {
        capture.begin(request, request.url(), request.method(), request.headers().authorization);
      } catch { listenerFailed = true; }
    };
    const onResponse = (response: Response) => {
      const request = response.request();
      try {
        capture.record({ url: response.url(), method: request.method(),
          authorization: request.headers().authorization, status: response.status(),
          requestId: response.headers()["x-request-id"] }, request);
      } catch { listenerFailed = true; }
    };
    const onFailure = (request: Request) => capture.fail(request);
    context.on("request", onRequest);
    context.on("response", onResponse);
    context.on("requestfailed", onFailure);
    try { await use(capture); }
    finally {
      context.off("request", onRequest);
      context.off("response", onResponse);
      context.off("requestfailed", onFailure);
      if (listenerFailed) {
        // Hata halinde açık session makbuzu teardown'un başarı vermesini engeller.
        throw new Error("Audit yanıt dinleyicisi başarısız; makbuz tamamlanmadı.");
      }
      capture.finish();
    }
  },
  _auditAuto: [async ({ auditCapture }, use) => { void auditCapture; await use(); }, { auto: true }],
});
