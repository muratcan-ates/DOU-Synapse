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

export function getStoredUser(): DemoUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as DemoUser) : null;
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

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(
      error?.message ?? "İşlem tamamlanamadı. Lütfen tekrar deneyin.",
      error?.code ?? "unknown",
      response.status,
    );
  }
  return body as T;
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
