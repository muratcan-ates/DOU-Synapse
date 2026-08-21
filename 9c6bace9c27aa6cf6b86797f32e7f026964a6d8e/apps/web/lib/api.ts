/**
 * API istemcisi.
 *
 * Backend'in hata sözleşmesi tekildir: { error: { code, message } }.
 * Buradaki tek iş, o mesajı kullanıcıya olduğu gibi taşımak — arayüz kendi hata
 * metnini uydurmaz, backend zaten anlaşılır Türkçe üretir (app/core/errors.py).
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "dou-synapse-token";
const USER_KEY = "dou-synapse-user";

export interface DemoUser {
  id: string;
  email: string;
  fullName: string;
  role: "instructor" | "student";
}

/**
 * Depodaki oturumu okur.
 *
 * Bozuk değer uygulamayı ÇÖKERTMEMELİ: `JSON.parse` doğrudan çağrıldığında
 * hatalı bir localStorage kaydı bütün sayfayı düşürüyordu ve yenilemek de
 * kurtarmıyordu — kayıt hâlâ bozuk olduğu için kullanıcı kalıcı olarak kilitli
 * kalıyordu. Artık bozuk kayıt temizlenir ve giriş ekranına düşülür.
 *
 * Biçim de doğrulanır: eksik alanlı bir nesne daha sonra `user.role` okunurken
 * patlamak yerine burada reddedilir.
 */
export function getStoredUser(): DemoUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isDemoUser(parsed)) return parsed;
  } catch {
    // düşülecek: aşağıda temizlenir
  }
  signOut();
  return null;
}

function isDemoUser(value: unknown): value is DemoUser {
  if (typeof value !== "object" || value === null) return false;
  const u = value as Record<string, unknown>;
  return (
    typeof u.id === "string" &&
    typeof u.email === "string" &&
    typeof u.fullName === "string" &&
    (u.role === "instructor" || u.role === "student")
  );
}

export function signIn(user: DemoUser): void {
  localStorage.setItem(TOKEN_KEY, `dev:${user.id}`);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function signOut(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_URL}${path}`, { ...init, headers });

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
 * Hata zarfını okur — backend'in TEK biçimi: `{ error: { code, message } }`
 * (`app/core/errors.py`).
 *
 * FastAPI'nin ham `{detail: [...]}` doğrulama biçimi için istemcide savunma kodu
 * YOK, çünkü sunucu 9 Ağustos'ta `validation_error_handler` ile her 422'yi de bu
 * zarfa çeviriyor (main.py'de `RequestValidationError`'a kayıtlı, doğrulandı).
 * İki biçimi istemcide tanımaya çalışmak kapanmış bir deliği ikinci kez yamamak
 * olurdu ve ham İngilizce Pydantic metnini kullanıcıya taşırdı (Anayasa V).
 */
function errorEnvelope(body: unknown): { code?: string; message?: string } | null {
  if (typeof body !== "object" || body === null) return null;
  const error = (body as { error?: unknown }).error;
  if (typeof error !== "object" || error === null) return null;
  const { code, message } = error as { code?: unknown; message?: unknown };
  return {
    code: typeof code === "string" ? code : undefined,
    message: typeof message === "string" ? message : undefined,
  };
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, payload?: unknown) =>
    request<T>(path, {
      method: "POST",
      headers: payload ? { "Content-Type": "application/json" } : undefined,
      body: payload ? JSON.stringify(payload) : undefined,
    }),
  upload: <T>(path: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<T>(path, { method: "POST", body: form });
  },
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
