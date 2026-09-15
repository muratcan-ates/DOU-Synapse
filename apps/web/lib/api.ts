/**
 * API istemcisi.
 *
 * Backend'in hata sözleşmesi tekildir: { error: { code, message, request_id } }.
 * Buradaki tek iş, o mesajı kullanıcıya olduğu gibi taşımak — arayüz kendi hata
 * metnini uydurmaz, backend zaten anlaşılır Türkçe üretir (app/core/errors.py).
 * `request_id` 002 lider turunda zarfa eklendi: destek kodu yanıt başlığında
 * değil gövdede taşınır, böylece tarayıcının başlık politikasına bağlı kalmaz.
 *
 * 002 güvenilirlik turunda üç kural daha buraya taşındı ve hepsi ÇAĞRI
 * YERİNDEN alınmadı, istekten türetildi (T401, T402): süre bütçesi, yeniden
 * deneme sayısı ve hangi hatanın yeniden denenebilir olduğu. Gerekçe her
 * üçünde de aynı: bu kararlar unutulabilir olduğu sürece er geç bir çağrı
 * yerinde yanlış verilir (Anayasa XI), ve yanlış verildiği gün sessizdir —
 * bir POST iki kez gider, bir sohbet isteği 20 saniyede kesilir.
 */

import { captureAuthEpoch, isAuthEpochCurrent, type AuthEpochSnapshot } from "@/lib/auth-events";
import { accessToken, expireAuthSession } from "@/lib/auth-session";

export { getStoredUser, signIn, signOut, signInWithPassword, requestPasswordReset, updateCurrentPassword, signOutWithLocalCleanup, signOutCurrent, getCurrentUser, type DemoUser } from "@/lib/auth-session";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
    /**
     * Sunucunun ürettiği istek kimliği; destek için kullanıcıya gösterilir ve
     * aynı kimlik sunucu loglarında aranabilir.
     *
     * `null` olabilir: ağ hatası gibi sunucuya hiç ulaşmayan durumlarda ortada
     * bir istek kaydı yoktur. Sunucudan dönen HER hata zarfı taşır
     * (`apps/api/app/core/errors.py::ErrorDetail`), dolayısıyla `null` "sunucu
     * vermedi" değil "sunucuya varılamadı" demektir.
     *
     * Bu alan lider turunda sözleşme olarak sabitlendi; ekranda nasıl
     * gösterileceği güvenilirlik şeridinin işi (T406 frontend).
     */
    public readonly requestId: string | null = null,
  ) {
    super(message);
  }
}

/* -------------------------------------------------------------------------
 * T401 · Süre bütçeleri
 * ---------------------------------------------------------------------- */

/**
 * İstek türüne göre süre bütçesi. TEK sözlük: çağrı yerlerine dağıtılan bir
 * bütçe, üçüncü çağrı yerinde farklı bir sayı olur.
 *
 * Neden tek bir global bütçe YANLIŞ: 001 ölçümlerinde ilk soru 11,7 saniye,
 * ilk sayfa yüklemesi 19,1 saniye sürdü ve gerçek sağlayıcıyla sohbet cevabı
 * 60 saniyeye çıkabiliyor (`docs/runbook.md`). Tek bir 10 saniyelik bütçe
 * listeleri korurken sohbeti kırardı; tek bir 120 saniyelik bütçe ise ölü bir
 * sunucuyu iki dakika boyunca "yükleniyor" diye gösterirdi.
 *
 * Sayılar ölçüme dayanır ama ölçümün kendisi değildir: her biri gözlenen en
 * kötü duruma pay eklenerek seçildi. Ölçüm değişirse burası değişir.
 */
export const BUDGET_MS = {
  /** Liste ve detay okumaları. Gözlenen ilk yükleme 19,1 sn idi ama o süre
   *  soğuk başlangıcın tamamıdır; tek bir GET bu bütçeyi aşıyorsa hat bozuktur. */
  read: 12_000,
  /** Yazma: kısa DB işlemleri. */
  write: 20_000,
  /** Dosya yükleme: ağ hızına bağlı, kullanıcı beklemeyi göze almıştır. */
  upload: 90_000,
  /** Model çağıran uçlar (sohbet, puanlama, soru üretimi). */
  llm: 120_000,
} as const;

export type BudgetKind = keyof typeof BUDGET_MS;

/**
 * Model çağıran uçlar. Liste burada, çağrı yerinde değil.
 *
 * Neden yol eşlemesi: bu üç ucu çağıran dosyaların ikisi US1 kilidinin sahibi
 * (`chat/page.tsx`, `exam/page.tsx`) ve bu turda değiştirilmiyor. Bütçeyi
 * çağrı yerine parametre olarak eklemek, o dosyalar güncellenene kadar sohbeti
 * 20 saniyelik `write` bütçesine mahkûm ederdi — yani düzeltme, düzeltmeyi
 * beklerken ürünü kırardı.
 *
 * Doğrulandı (9 Ağustos, backend kaynağı okunarak): `POST /chat`
 * (`app/api/chat.py:581`), `POST /exams/{id}/answers` → `grade_with_llm`
 * (`app/modules/assessment/grading.py:335`), `POST /questions/generate`
 * (`app/api/questions.py:154`). `hint` ve `finish` uçları modeli ÇAĞIRMIYOR;
 * ipucu metni şablondan geliyor, bu yüzden listede yoklar.
 */
const LLM_PATHS = [
  /^\/courses\/[^/]+\/chat$/,
  /^\/courses\/[^/]+\/exams\/[^/]+\/answers$/,
  /^\/courses\/[^/]+\/questions\/generate$/,
];

/** İsteğin bütçe sınıfı — yoldan ve gövdeden türetilir, çağırandan alınmaz. */
export function budgetFor(path: string, init?: RequestInit): BudgetKind {
  if (LLM_PATHS.some((pattern) => pattern.test(path))) return "llm";
  if (init?.body instanceof FormData) return "upload";
  return methodOf(init) === "GET" || methodOf(init) === "HEAD" ? "read" : "write";
}

function methodOf(init?: RequestInit): string {
  return (init?.method ?? "GET").toUpperCase();
}

/* -------------------------------------------------------------------------
 * T402 · Yeniden deneme
 * ---------------------------------------------------------------------- */

/**
 * Yeniden deneme sayısı METOTTAN türetilir, çağırandan ALINMAZ (FR-152).
 *
 * Gerekçe: yeniden denenen bir POST çift kayıt üretir. Sohbete iki cevap,
 * havuza iki soru, sınava iki cevap satırı. "Çağıran karar versin" demek,
 * dokuz çağrı yerinden birinin er geç yanlış karar vermesi demektir ve o gün
 * hatanın kaynağı ağ değil bu dosya olur.
 *
 * GET/HEAD tanımı gereği yan etkisizdir; tekrarı en kötü ihtimalle boşa iştir.
 */
export function retriesFor(init?: RequestInit): number {
  const method = methodOf(init);
  return method === "GET" || method === "HEAD" ? 2 : 0;
}

/** Üstel geri çekilmenin tabanı. */
export const RETRY_BASE_MS = 400;

/**
 * Jitter'lı üstel geri çekilme: `[exp/2, exp)` aralığında rastgele bekleme.
 *
 * Neden jitter: sunucu kısa süre düşüp kalktığında bütün açık sekmeler aynı
 * anda hata alır. Sabit gecikmeyle hepsi aynı milisaniyede geri döner ve
 * sunucuyu ikinci kez düşürür. Rastgelelik o dalgayı yayar.
 *
 * `random` dışarıdan verilir ki test gecikmeyi tahmin etmek zorunda kalmasın;
 * gerçek çağrı `Math.random` geçer.
 */
export function backoffMs(attempt: number, random: number): number {
  const exponential = RETRY_BASE_MS * 2 ** attempt;
  return Math.round(exponential / 2 + random * (exponential / 2));
}

/** Yeniden denemeye değer mi? Yalnız geçici hatalar. */
function isRetryable(e: unknown): boolean {
  // `ApiError` olmayan hata = `fetch` hiç yanıt alamadı (ağ kopması). Sunucuya
  // varılamadıysa yan etki de oluşmamıştır; güvenli metotta tekrar denenebilir.
  if (!(e instanceof ApiError)) return true;
  return classifyApiError(e.status, e.code) === "transient";
}

/**
 * Yeniden deneme döngüsü — zamanlayıcıdan ve `Math.random`'dan arındırılmış.
 *
 * `sleep` ve `random` parametre olduğu için test gerçek süre beklemeden
 * gecikmelerin TAM dizisini ölçebiliyor. Aynı desen bu dosyanın komşusunda da
 * var (`use-resource.ts`'in saf çekirdekleri): tarayıcıda yalnız şanslı
 * zamanlamada gözlenebilen bir kural, testte doğrudan okunabilir olmalı.
 */
export async function withRetry<T>(
  run: () => Promise<T>,
  options: {
    retries: number;
    sleep: (ms: number) => Promise<void>;
    random: () => number;
  },
): Promise<T> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await run();
    } catch (e) {
      if (attempt >= options.retries || !isRetryable(e)) throw e;
      await options.sleep(backoffMs(attempt, options.random()));
    }
  }
}

/* -------------------------------------------------------------------------
 * T403 · Hata sınıflandırmasının çekirdeği
 * ---------------------------------------------------------------------- */

/**
 * Hatanın üç sınıfı. Kullanıcıya dönük karar (tekrar denenebilir mi, girişe
 * atılmalı mı) bu vokabülerden okunur.
 *
 * Tip ve alttaki saf kural `errors.ts`'te değil BURADA yaşıyor: `ApiError`'ın
 * `status`/`code` alanlarının sahibi bu dosya ve `request()` kendi yeniden
 * deneme kararı için aynı kurala ihtiyaç duyuyor. Kuralı `errors.ts`'e koyup
 * buradan çağırmak iki modül arasında döngüsel import yaratırdı; kopyalamak
 * ise aynı kuralı iki yerde tutmak olurdu (Anayasa XI). Kullanıcıya dönük
 * sarmalayıcı `classifyError` yine `errors.ts`'te (T403).
 */
export type ErrorKind = "transient" | "permanent" | "auth";

/**
 * `status` + `code` → sınıf.
 *
 * Sıra önemli: **kod durumdan önce gelir.** Sınav kilidi `403` döndürüyor
 * (`exam_state.py::ExamLockedError`) ve duruma bakan bir kural onu "yetki
 * hatası" sayıp sınav veren öğrenciyi sınavın ortasında giriş ekranına
 * fırlatırdı. `exam_in_progress` bir kimlik sorunu değildir: kullanıcı
 * kimdir bellidir, yapmak istediği şey şu an yasaktır. Yani `permanent`, ve
 * yeniden denenebilir DEĞİL — sınav bitene kadar cevap değişmez.
 */
export function classifyApiError(status: number, code: string): ErrorKind {
  // Sınav kilidi: 403 ama yetki hatası değil. Bu satır 401 kuralından ÖNCE
  // durmak zorunda değil (kilit 403'tür), ama okuyan herkes ilk bunu görsün.
  if (code === "exam_in_progress") return "permanent";

  // Oturum düştü: tek çare yeniden giriş. `permission_denied` (403) BU KÜMEDE
  // DEĞİL — üyesi olmadığın bir dersi açmak, kimliğinin geçersiz olduğu
  // anlamına gelmez ve kullanıcıyı çıkışa atmak veriyi kaybettirirdi.
  if (code === "unauthenticated" || status === 401) return "auth";

  // Sunucuya hiç varılamadı (`status === 0`): zaman aşımı ya da ağ kopması.
  if (status === 0) return "transient";

  // Yanıt geldi ama okunamadı: hat bozuk, içerik değil.
  if (code === "invalid_response") return "transient";

  // Kota tükendi: 429 ama YENİDEN DENENEBİLİR DEĞİL. Bu satır 429 kuralından
  // ÖNCE durmak zorunda; altında kalsaydı `transient` olur ve arayüz asla
  // çalışmayacak bir "Tekrar dene" düğmesi gösterirdi — kota gece yarısına
  // kadar dolu, tekrar denemek aynı 429'u üretir. `agent_concurrency_limited`
  // bu kümede DEĞİL: önceki istek bitince gerçekten denenebilir.
  if (code === "agent_quota_exhausted") return "permanent";

  // FR-151'in listesi: 408, 429 ve tüm 5xx.
  if (status === 408 || status === 429 || status >= 500) return "transient";

  return "permanent";
}

/* -------------------------------------------------------------------------
 * İstek
 * ---------------------------------------------------------------------- */

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Zaman aşımı metni. Backend susmuş durumda, o yüzden cümleyi arayüz kurar. */
const TIMEOUT_MESSAGE = "Sunucu zamanında yanıt vermedi. Lütfen tekrar deneyin.";

/**
 * Tek deneme: bütçeli `fetch` + zarf çözümü.
 *
 * Bütçe `AbortController` ile uygulanır, `Promise.race` ile DEĞİL. Fark önemli:
 * `race` yalnız beklemeyi bırakır, istek arka planda sunucuya gitmeye ve
 * bağlantıyı tutmaya devam eder. `abort()` isteği gerçekten iptal eder;
 * yeniden deneme bunun üstüne binerse aksi hâlde üç ölü bağlantı birikirdi.
 *
 * Zamanlayıcı gövde okunana kadar yaşar: yanıt başlıkları hızlı gelip gövdesi
 * asılı kalan bir sunucu da bütçeyi aşmış sayılır.
 */
async function attempt<T>(path: string, init: RequestInit | undefined, budgetMs: number, requestedEpoch: AuthEpochSnapshot, mode: BodyMode): Promise<T> {
  const token = await accessToken();
  if (!isAuthEpochCurrent(requestedEpoch)) throw new ApiError("Oturum değişti. Yeniden deneyin.", "unauthenticated", 401);
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), budgetMs);
  try {
    const response = await fetch(`${API_URL}${path}`, { ...init, headers, signal: controller.signal });
    // Gövde gecikse/bozulsa da 401 özel görünümü hemen kapatır; 403 kapatmaz.
    if (response.status === 401) expireAuthSession(requestedEpoch);
    const result = await readResponse<T>(response, mode);
    if (!isAuthEpochCurrent(requestedEpoch)) throw new ApiError("Oturum değişti. Yeniden deneyin.", "unauthenticated", 401);
    return result;
  } catch (e) {
    // Bütçe dolduysa `fetch` bir iptal hatasıyla düşer; kullanıcıya gösterilecek
    // olan o düşük seviyeli metin değil, ne olduğunu söyleyen cümledir.
    // `status: 0` "sunucuya varılamadı" demek, dolayısıyla `requestId` de yok.
    if (controller.signal.aborted) throw new ApiError(TIMEOUT_MESSAGE, "timeout", 0);
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Gövde biçimi. Varsayılan JSON; `text` yalnız sunucunun bilerek metin
 * döndürdüğü indirme uçları içindir (`text/markdown`).
 */
type BodyMode = "json" | "text";

async function readResponse<T>(response: Response, mode: BodyMode = "json"): Promise<T> {
  if (response.status === 204) return undefined as T;

  const raw = await response.text();
  let body: unknown = null;
  let parsed = false;
  try {
    body = raw.trim() === "" ? null : JSON.parse(raw);
    parsed = true;
  } catch {
    // Ayrıştırılamadı; aşağıda ele alınıyor.
  }

  if (!response.ok) {
    const error = errorEnvelope(body);
    throw new ApiError(
      error?.message ?? "İşlem tamamlanamadı. Lütfen tekrar deneyin.",
      error?.code ?? "unknown",
      response.status,
      error?.requestId ?? null,
    );
  }

  /*
   * Başarılı ama okunamayan yanıt bir HATADIR, boş veri değil.
   *
   * Eskiden ayrıştırma başarısız olunca sessizce `null` dönüyordu. `useResource`
   * "yükleniyor"u `data === null && error === null` diye tanımladığı için ekran
   * sonsuza kadar "Yükleniyor…" kalıyordu: kullanıcı bekliyor, yenilemek de
   * kurtarmıyor, hiçbir yerde hata görünmüyor. Fail-closed doğru davranış
   * (Anayasa IV): hattın bozuk olduğunu söyle.
   *
   * Gövdesiz başarılı yanıt da buraya düşer; 204 yukarıda zaten ayrıldı ve
   * başka hiçbir uç boş gövdeyle 2xx dönmüyor (contracts/openapi.json).
   */
  /*
   * Metin uçları buraya JSON beklentisiyle gelmemeli: `text/markdown` yanıtı
   * ayrıştırılamaz ve aşağıdaki fail-closed dal onu "bozuk yanıt" sayardı.
   * Hata yolu YUKARIDA ortak kalıyor — hata zarfı her uçta JSON'dur.
   */
  if (mode === "text") return raw as T;

  if (!parsed || body === null) {
    throw new ApiError(
      "Sunucudan beklenmeyen bir yanıt geldi. Lütfen tekrar deneyin.",
      "invalid_response",
      response.status,
    );
  }
  return body as T;
}

/**
 * Dışa bakan istek: bütçesini ve yeniden deneme sayısını KENDİ seçer.
 *
 * İkisi de `path` ve `init`ten türetiliyor, imzaya seçenek eklenmiyor. Seçenek
 * eklemek "hangi çağrı doğru değeri geçmiş" sorusunu dokuz dosyaya yayardı;
 * bugünkü kural tek satırda okunabilir: güvenli metot yeniden denenir, diğerleri
 * denenmez.
 */
async function request<T>(path: string, init?: RequestInit, mode: BodyMode = "json"): Promise<T> {
  const budgetMs = BUDGET_MS[budgetFor(path, init)];
  const requestedEpoch = captureAuthEpoch();
  return withRetry(() => attempt<T>(path, init, budgetMs, requestedEpoch, mode), {
    retries: retriesFor(init),
    sleep,
    random: Math.random,
  });
}

/**
 * Hata zarfını okur — backend'in TEK biçimi:
 * `{ error: { code, message, request_id } }` (`app/core/errors.py::ErrorEnvelope`).
 *
 * FastAPI'nin ham `{detail: [...]}` doğrulama biçimi için istemcide savunma kodu
 * YOK, çünkü sunucu 9 Ağustos'ta `validation_error_handler` ile her 422'yi de bu
 * zarfa çeviriyor (main.py'de `RequestValidationError`'a kayıtlı, doğrulandı).
 * İki biçimi istemcide tanımaya çalışmak kapanmış bir deliği ikinci kez yamamak
 * olurdu ve ham İngilizce Pydantic metnini kullanıcıya taşırdı (Anayasa V).
 */
function errorEnvelope(
  body: unknown,
): { code?: string; message?: string; requestId?: string } | null {
  if (typeof body !== "object" || body === null) return null;
  const error = (body as { error?: unknown }).error;
  if (typeof error !== "object" || error === null) return null;
  const { code, message, request_id: requestId } = error as {
    code?: unknown;
    message?: unknown;
    request_id?: unknown;
  };
  return {
    code: typeof code === "string" ? code : undefined,
    message: typeof message === "string" ? message : undefined,
    // Alan adı sunucuda `request_id`; burada tek yerde camelCase'e çevrilir ki
    // zarf biçimi arayüzün geri kalanına sızmasın.
    requestId: typeof requestId === "string" ? requestId : undefined,
  };
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  /**
   * Metin döndüren uçlar (Markdown dışa aktarımı). Ayrı bir `fetch` AÇMAZ:
   * yetki başlığı, zaman bütçesi, yeniden deneme ve hata zarfı aynı yoldan
   * geçer — deponun tek fetch çağrı yeri kuralı korunur.
   */
  text: (path: string) => request<string>(path, undefined, "text"),
  patch: <T>(path: string, payload: unknown) =>
    request<T>(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  put: <T>(path: string, payload: unknown) =>
    request<T>(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  post: <T>(path: string, payload?: unknown) =>
    request<T>(path, {
      method: "POST",
      headers: payload ? { "Content-Type": "application/json" } : undefined,
      body: payload ? JSON.stringify(payload) : undefined,
    }),
  upload: <T>(path: string, file: File, replacesDocumentId?: string | null) => {
    const form = new FormData();
    form.append("file", file);
    // T508: yeni sürüm eski belgeyi açıkça işaretler; alan yalnız verildiğinde gider.
    if (replacesDocumentId) form.append("replaces_document_id", replacesDocumentId);
    return request<T>(path, { method: "POST", body: form });
  },
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
