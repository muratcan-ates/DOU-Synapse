import { DEMO_TOKEN_KEY, DEMO_USER_KEY, captureAuthEpoch, isAuthEpochCurrent, isAuthLocallySignedOut, notifyAuthChange, readWithinAuthEpoch, type AuthEpochSnapshot } from "@/lib/auth-events";
import { entraTenantId, isDevAuthEnabled } from "@/lib/auth-config";
import { withAuthWriteLock } from "@/lib/auth-lock";
import { getSupabase, supabaseConfigured } from "@/lib/supabase";

const TOKEN_KEY = DEMO_TOKEN_KEY;
const USER_KEY = DEMO_USER_KEY;

export interface DemoUser {
  id: string;
  email: string;
  fullName: string;
  // Yalnız demo kartı etiketi; yetki sunucudaki profil/üyelikten gelir.
  role: "instructor" | "student" | "operator";
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
  if (!isDevAuthEnabled() || typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
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
    (u.role === "instructor" || u.role === "student" || u.role === "operator")
  );
}

export function signIn(user: DemoUser): void {
  if (!isDevAuthEnabled()) throw new Error("Geliştirme girişi etkin değil.");
  const previous = getStoredUser();
  localStorage.setItem(TOKEN_KEY, `dev:${user.id}`);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  if (previous?.id !== user.id || isAuthLocallySignedOut()) notifyAuthChange("identity-changed");
}

function clearDemoSession(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    // Depo engellense de eski kimlik kullanılamaz.
  } finally {
    // Depo kapalı olsa bile eski görünüm ve geç yanıtlar kapatılır.
    notifyAuthChange("signed-out");
  }
}

export function signOut(): void {
  clearDemoSession();
}

function requireProvider() {
  const client = getSupabase();
  if (!client) throw new Error("Supabase oturumu yapılandırılmadı.");
  return client;
}

function acceptProviderIdentity(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch { /* SDK oturumu kendi deposundan okunur. */ }
  notifyAuthChange("identity-changed");
}

/** Gerçek sağlayıcı parola oturumunu saklar; e-posta alan adı yetki vermez. */
export async function signInWithPassword(email: string, password: string): Promise<DemoUser> {
  return withAuthWriteLock(async () => {
    const { data, error } = await requireProvider().auth.signInWithPassword({ email, password });
    if (error) throw error;
    if (!data.session || !data.user) throw new Error("Oturum bilgisi alınamadı.");
    acceptProviderIdentity();
    return userFromSupabase(data.user);
  });
}

export async function requestPasswordReset(email: string): Promise<void> {
  await withAuthWriteLock(async () => {
    const redirectTo = `${window.location.origin}/auth/callback?next=reset-password`;
    const { error } = await requireProvider().auth.resetPasswordForEmail(email, { redirectTo });
    if (error) throw error;
  });
}

export async function updateCurrentPassword(password: string): Promise<void> {
  await withAuthWriteLock(async () => {
    const { error } = await requireProvider().auth.updateUser({ password });
    if (error) throw error;
  });
}

export async function resendVerificationEmail(email: string): Promise<void> {
  await withAuthWriteLock(async () => {
    const { error } = await requireProvider().auth.resend({
      type: "signup", email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) throw error;
  });
}

export async function signInWithEntra(): Promise<void> {
  if (!entraTenantId()) throw new Error("Üniversite hesabıyla giriş henüz yapılandırılmadı.");
  await withAuthWriteLock(async () => {
    // Gerçek tenant sınırı Supabase Azure Tenant URL ve tek tenant Entra kaydıdır.
    // Tarayıcıdaki tenant biçim kontrolü sunucu doğrulamasının yerine geçmez.
    const { error } = await requireProvider().auth.signInWithOAuth({
      provider: "azure", options: {
        scopes: "email", redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: { prompt: "select_account" },
      },
    });
    if (error) throw error;
  });
}

/** Canonical dönüşte SDK ilk oluşturulması dahil URL/oturum yazımı kilit içinde kalır. */
export async function completeAuthCallback(): Promise<"/dashboard" | "/reset-password"> {
  const url = new URL(window.location.href);
  const hash = new URLSearchParams(url.hash.slice(1));
  if (url.searchParams.has("error") || hash.has("error")) throw new Error("Doğrulama bağlantısı kabul edilmedi. Yeni bağlantı isteyin.");
  const tokenHash = url.searchParams.get("token_hash");
  const type = url.searchParams.get("type") ?? hash.get("type");
  if (!tokenHash && !url.searchParams.has("code") && !hash.has("access_token")) {
    throw new Error("Doğrulama bağlantısı eksik veya süresi dolmuş. Yeni bağlantı isteyin.");
  }
  return withAuthWriteLock(async () => {
    const client = requireProvider();
    const initialized = await client.auth.initialize();
    if (initialized.error) throw initialized.error;
    if (tokenHash) {
      if (type !== "signup" && type !== "email" && type !== "recovery") throw new Error("Doğrulama bağlantısı türü desteklenmiyor.");
      const { data, error } = await client.auth.verifyOtp({ token_hash: tokenHash, type });
      if (error) throw error;
      if (!data.session) throw new Error("Doğrulama oturumu alınamadı.");
    } else {
      // SDK daha önce kurulmuşsa URL'yi yeniden kendiliğinden tüketmez. Yalnız
      // bu dönüş sayfasının açık verisini kilit altında tamamlarız.
      const remaining = new URL(window.location.href);
      const code = remaining.searchParams.get("code");
      const remainingHash = new URLSearchParams(remaining.hash.slice(1));
      if (code) {
        const { data, error } = await client.auth.exchangeCodeForSession(code);
        if (error) throw error;
        if (!data.session) throw new Error("Doğrulama oturumu alınamadı.");
      } else if (remainingHash.has("access_token")) {
        const access_token = remainingHash.get("access_token");
        const refresh_token = remainingHash.get("refresh_token");
        if (!access_token || !refresh_token) throw new Error("Doğrulama bağlantısı eksik.");
        const { data, error } = await client.auth.setSession({ access_token, refresh_token });
        if (error) throw error;
        if (!data.session) throw new Error("Doğrulama oturumu alınamadı.");
      }
    }
    const { data, error } = await client.auth.getSession();
    if (error) throw error;
    if (!data.session) throw new Error("Oturum doğrulanamadı. Yeni bağlantı isteyin.");
    acceptProviderIdentity();
    window.history.replaceState(null, "", "/auth/callback");
    return type === "recovery" || url.searchParams.get("next") === "reset-password" ? "/reset-password" : "/dashboard";
  });
}

/** Yerel görünüm ağ/sağlayıcı kilidinden önce, aynı çağrıda kapanır. */
export async function signOutWithLocalCleanup(
  providerSignOut: (() => Promise<{ error: unknown }>) | null,
  clearLocalSession: () => void,
): Promise<void> {
  clearLocalSession();
  if (!providerSignOut) return;
  const { error } = await providerSignOut();
  if (error) throw error;
}

let pendingSignOut: Promise<void> | null = null;
export function signOutCurrent(): Promise<void> {
  if (isAuthLocallySignedOut()) return pendingSignOut ?? Promise.resolve();
  const demoSelected = demoAccessToken() !== null;
  clearDemoSession();
  const clearedEpoch = captureAuthEpoch();
  if (demoSelected || !supabaseConfigured) return Promise.resolve();
  const pending = withAuthWriteLock(async () => {
    // Kilit beklerken başka sekme yeni kimlik açtıysa eski çıkış onu silemez.
    if (!isAuthEpochCurrent(clearedEpoch)) return;
    const client = getSupabase();
    if (!client) return;
    const { error } = await client.auth.signOut({ scope: "local" });
    if (error) throw error;
  });
  pendingSignOut = pending;
  void pending.finally(() => { if (pendingSignOut === pending) pendingSignOut = null; }).catch(() => {});
  return pending;
}

/** Yalnız isteğin hâlâ güncel kimliği 401 aldıysa tek çıkış başlatılır. */
export function expireAuthSession(requestedEpoch: AuthEpochSnapshot): void {
  if (!isAuthEpochCurrent(requestedEpoch) || isAuthLocallySignedOut()) return;
  // Sağlayıcı reddi yerel özel görünümü açık tutamaz; sonraki giriş açık eylemdir.
  void signOutCurrent().catch(() => {});
}

function demoAccessToken(): string | null {
  if (!isDevAuthEnabled() || typeof window === "undefined") return null;
  try {
    const user = getStoredUser();
    const token = localStorage.getItem(TOKEN_KEY);
    return user && token === `dev:${user.id}` ? token : null;
  } catch { return null; }
}

/** Sayfa yenilemesinde gerçek SDK oturumunu geri yükler; demo yolu senkron kalır. */
export async function getCurrentUser(): Promise<DemoUser | null> {
  if (isAuthLocallySignedOut()) return null;
  if (demoAccessToken()) return getStoredUser();
  const client = getSupabase();
  if (!client) return null;
  const snapshot = await readWithinAuthEpoch(() => client.auth.getSession());
  if (snapshot === null) return null;
  const { data, error } = snapshot;
  if (error || !data.session?.user) return null;
  return userFromSupabase(data.session.user);
}

function userFromSupabase(user: {
  id: string;
  email?: string;
  user_metadata?: Record<string, unknown>;
}): DemoUser {
  const metadataName = user.user_metadata?.full_name;
  const email = user.email ?? "";
  return {
    id: user.id,
    email,
    fullName:
      typeof metadataName === "string" && metadataName.trim()
        ? metadataName.trim()
        : email.split("@")[0] || "Kullanıcı",
    // Rol bir auth claim'i değildir; ders sayfasında `/courses/{id}` yanıtından
    // yeniden çözülür. Bu değer yalnız ders dışı başlıkların geriye uyumlu alanıdır.
    role: "student",
  };
}

export async function accessToken(): Promise<string | null> {
  if (isAuthLocallySignedOut()) return null;
  const demoToken = demoAccessToken();
  if (demoToken) return demoToken;
  const client = getSupabase();
  if (client) {
    const snapshot = await readWithinAuthEpoch(() => client.auth.getSession());
    return snapshot?.data.session?.access_token ?? null;
  }
  return null;
}

