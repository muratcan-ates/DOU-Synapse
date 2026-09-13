"use client";

import { clearAllExamDrafts, type DraftStorage } from "@/lib/exam-drafts";
import { isDevAuthEnabled } from "@/lib/auth-config";
import { getSupabase } from "@/lib/supabase";

export const AUTH_EVENT_KEY = "dou-synapse:auth-event:v1";
export const DEMO_TOKEN_KEY = "dou-synapse-token";
export const DEMO_USER_KEY = "dou-synapse-user";
export type AuthChange = "signed-out" | "identity-changed";
type Listener = (change: AuthChange) => void;
const listeners = new Set<Listener>();
let stopListening: (() => void) | null = null;
let lastMarker: string | null = null;
let locallySignedOut = false;
let authEpoch = 0;

function browserLocalStorage(): DraftStorage | null {
  try { return typeof window === "undefined" ? null : window.localStorage; }
  catch { return null; }
}

/** Yalnız bu uygulamanın öğrenci taslakları ve açık oturum seçimleri silinir. */
export function clearPrivateSessionData(
  drafts?: DraftStorage | null,
  remembered = browserLocalStorage(),
): void {
  clearAllExamDrafts(drafts);
  if (!remembered) return;
  try {
    for (let index = remembered.length - 1; index >= 0; index -= 1) {
      const key = remembered.key(index);
      if (key?.startsWith("dou-synapse-chat-session:") ||
          key?.startsWith("dou-synapse-exam-session:")) remembered.removeItem(key);
    }
  } catch { /* Depo hatası arayüzün kapanmasını engellemez. */ }
}

function saveTabMarker(marker: string | null): void {
  try {
    if (marker === null) window.sessionStorage.removeItem(AUTH_EVENT_KEY);
    else window.sessionStorage.setItem(AUTH_EVENT_KEY, marker);
  } catch { /* Kapalı depo aynı sekmenin geçersizlemesini engellemez. */ }
}

function readMarker(): string | null {
  try { return browserLocalStorage()?.getItem(AUTH_EVENT_KEY) ?? null; }
  catch { return null; }
}

export function authChangeFromMarker(marker: string | null): AuthChange | null {
  if (marker?.startsWith("signed-out:")) return "signed-out";
  if (marker?.startsWith("identity-changed:")) return "identity-changed";
  return null;
}

export function isAuthLocallySignedOut(): boolean {
  return locallySignedOut || authChangeFromMarker(readMarker()) === "signed-out";
}

export interface AuthEpochSnapshot { epoch: number; marker: string | null }
export function captureAuthEpoch(): AuthEpochSnapshot {
  return { epoch: authEpoch, marker: readMarker() };
}
export function isAuthEpochCurrent(snapshot: AuthEpochSnapshot): boolean {
  return snapshot.epoch === authEpoch && snapshot.marker === readMarker();
}

/** SDK kilidi/yenilemesi beklenirken değişen kimliğin eski cevabı kullanılamaz. */
export async function readWithinAuthEpoch<T>(read: () => Promise<T>): Promise<T | null> {
  if (isAuthLocallySignedOut()) return null;
  const requestedEpoch = captureAuthEpoch();
  const result = await read();
  // storage olayı bu sekmede henüz çalışmamış olsa da ortak işaret değişmiştir.
  if (!isAuthEpochCurrent(requestedEpoch) || isAuthLocallySignedOut()) return null;
  return result;
}

function applyChange(change: AuthChange): void {
  authEpoch += 1;
  locallySignedOut = change === "signed-out";
  clearPrivateSessionData();
  // Kimlik/özel içerik yayınlanmaz. Dinleyici yalnız eski görünümü geçersizler;
  // yeni kimlik ve ders rolü hâlâ normal auth/API okumasından doğrulanır.
  for (const listener of listeners) listener(change);
}

export function notifyAuthChange(change: AuthChange): void {
  if (change === "signed-out" && locallySignedOut && readMarker() === lastMarker) return;
  const marker = `${change}:${crypto.randomUUID()}`;
  lastMarker = marker;
  saveTabMarker(marker);
  try { browserLocalStorage()?.setItem(AUTH_EVENT_KEY, marker); }
  catch { /* Aynı sekmenin temizliği depoya bağlı değildir. */ }
  applyChange(change);
}

/** SDK yenilemeleri aynı kullanıcının taslağını silmez; kimlik geçişi siler. */
export function createProviderAuthObserver(onChange: Listener) {
  let initialized = false;
  let userId: string | null = null;
  return (event: string, nextUserId: string | null): void => {
    if (event === "INITIAL_SESSION") {
      initialized = true;
      userId = nextUserId;
      return;
    }
    if (event === "SIGNED_OUT") {
      initialized = true;
      userId = null;
      onChange("signed-out");
    } else if (event === "SIGNED_IN") {
      if (!initialized || userId !== nextUserId) onChange("identity-changed");
      initialized = true;
      userId = nextUserId;
    }
  };
}

/** Bir bridge, çok sayıda useSession/chat tüketicisi. SDK callback'i senkrondur. */
export function subscribeAuthChanges(listener: Listener): () => void {
  listeners.add(listener);
  if (typeof window !== "undefined" && stopListening === null) {
    const currentMarker = readMarker();
    if (lastMarker === null) {
      try { lastMarker = window.sessionStorage.getItem(AUTH_EVENT_KEY); } catch { /* Depo yok. */ }
    }
    // Dondurulmuş/yeniden açılan sekmenin sessionStorage'ı diğer sekmenin
    // çıkışından sonra da temizlenir; aynı kimliğin normal mount'u temizlenmez.
    if (currentMarker !== lastMarker || authChangeFromMarker(currentMarker) === "signed-out") {
      const change = authChangeFromMarker(currentMarker);
      if (change) applyChange(change);
    }
    lastMarker = currentMarker;
    saveTabMarker(currentMarker);
    const syncMarker = () => {
      const marker = readMarker();
      if (marker === lastMarker) return;
      lastMarker = marker;
      saveTabMarker(marker);
      const change = authChangeFromMarker(marker);
      if (change) applyChange(change);
    };
    const storage = (event: StorageEvent) => {
      if (event.key === AUTH_EVENT_KEY || event.key === null) syncMarker();
    };
    window.addEventListener("storage", storage);
    window.addEventListener("focus", syncMarker);
    window.addEventListener("pageshow", syncMarker);
    const provider = getSupabase();
    const observe = createProviderAuthObserver((change) => {
      if (change === "identity-changed") {
        // SDK depodan oturum kurtarırken de SIGNED_IN üretir. Yerel çıkışı
        // yalnız açık giriş/callback kabulü kaldırabilir; pasif olay kaldıramaz.
        if (!isAuthLocallySignedOut()) notifyAuthChange(change);
        return;
      }
      if (isAuthLocallySignedOut() || !provider) return;
      const requestedEpoch = captureAuthEpoch();
      // Diğer sekmenin eski SIGNED_OUT yayını yeni girişten sonra gelebilir.
      // SDK callback'i içinde oturum okumak kilitlenebilir; ayrı görevde güncel
      // depoyu doğrularız. Yeni kimlik veya hâlâ açık oturum varsa çıkış yoktur.
      window.setTimeout(() => {
        void provider.auth.getSession().then(({ data, error }) => {
          if (error || !isAuthEpochCurrent(requestedEpoch)) return;
          if (data.session) {
            // Geç yayın gözlemcinin kimlik belleğini de geriye götürmemeli.
            observe("INITIAL_SESSION", data.session.user.id);
            return;
          }
          notifyAuthChange("signed-out");
        }).catch(() => {
          // Okunamayan depo eski olayın doğruluğunu kanıtlamaz. API 401 kapısı
          // bundan bağımsız olarak yerel özel görünümü hemen kapatır.
        });
      }, 0);
    });
    const subscription = provider?.auth.onAuthStateChange((event, session) => {
      // Açıkça seçilen geliştirme kimliği arka plandaki SDK olayından etkilenmez.
      try {
        if (isDevAuthEnabled() && browserLocalStorage()?.getItem(DEMO_TOKEN_KEY)?.startsWith("dev:")) return;
      } catch { /* Depo yoksa normal sağlayıcı olayı uygulanır. */ }
      observe(event, session?.user.id ?? null);
    }).data.subscription;
    stopListening = () => {
      subscription?.unsubscribe();
      window.removeEventListener("storage", storage);
      window.removeEventListener("focus", syncMarker);
      window.removeEventListener("pageshow", syncMarker);
    };
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      stopListening?.();
      stopListening = null;
    }
  };
}
