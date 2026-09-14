/** Sentetik taşıma gerçek kurulu SDK'yi sınar; canlı sağlayıcı kanıtı değildir. */
import assert from "node:assert/strict";
import { createClient } from "@supabase/supabase-js";

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return { getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
    key: (index: number) => [...values.keys()][index] ?? null,
    get length() { return values.size; }, clear: () => values.clear() };
}
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
function locks() {
  const tails = new Map<string, Promise<unknown>>();
  let active = 0;
  return { get active() { return active; }, request<T>(name: string, callback: () => Promise<T>): Promise<T> {
    const run = (tails.get(name) ?? Promise.resolve()).catch(() => {}).then(async () => {
      active += 1;
      try { return await callback(); } finally { active -= 1; }
    });
    tails.set(name, run); return run;
  } };
}
const storage = memoryStorage();
const sessionStorage = memoryStorage();
const browser = { location: new URL("https://l5-web.invalid/"), localStorage: storage, sessionStorage,
  addEventListener() {}, removeEventListener() {}, setTimeout,
  history: { state: null, replaceState(_data: unknown, _unused: string, url?: string | URL | null) { if (url) browser.location = new URL(url, browser.location); } },
};
Object.defineProperty(globalThis, "window", { value: browser, configurable: true });
Object.defineProperty(globalThis, "document", { value: { visibilityState: "hidden", addEventListener() {}, removeEventListener() {} }, configurable: true });
Object.defineProperty(globalThis, "localStorage", { value: storage, configurable: true });
Object.defineProperty(globalThis, "navigator", { value: { locks: locks(), userAgent: "L5 synthetic transport" }, configurable: true });
Object.defineProperty(globalThis, "BroadcastChannel", { value: undefined, configurable: true });

const oldId = "11111111-1111-4111-8111-111111111111";
const newId = "22222222-2222-4222-8222-222222222222";
function session(id: string, suffix = "current", expires = 3600) {
  const exp = Math.floor(Date.now() / 1000) + expires;
  const user = { id, email: `${id === oldId ? "old" : "new"}@dogus.edu.tr`, role: "authenticated", app_metadata: { provider: "email" }, user_metadata: { full_name: "Sentetik Kullanıcı", role: "instructor" }, aud: "authenticated", created_at: "2026-01-01T00:00:00Z" };
  const encode = (value: unknown) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return { access_token: `${encode({ alg: "HS256", typ: "JWT" })}.${encode({ sub: id, role: "authenticated", exp, iat: exp - 3600, marker: suffix })}.synthetic-signature`, refresh_token: `synthetic-refresh-${id}-${suffix}`, token_type: "bearer", expires_in: expires, expires_at: exp, user };
}
const requests: { path: string; body: Record<string, unknown>; authorization: string | null; authLockHeld: boolean }[] = [];
let logoutGate: ReturnType<typeof deferred<void>> | null = null;
let logoutStarted: ReturnType<typeof deferred<void>> | null = null;
let apiGate: ReturnType<typeof deferred<Response>> | null = null;
let tokenReads = 0;
const transport = (async (input: string | URL | Request, init?: RequestInit) => {
  const request = new Request(input, init);
  const url = new URL(request.url);
  const body = request.method === "GET" ? {} : await request.json().catch(() => ({}));
  requests.push({ path: url.pathname + url.search, body, authorization: request.headers.get("Authorization"), authLockHeld: (navigator.locks as unknown as { active: number }).active > 0 });
  if (!url.pathname.startsWith("/auth/v1/")) {
    if (apiGate) return apiGate.promise.then((response) => response.clone());
    return Response.json({ ok: true });
  }
  if (url.pathname.endsWith("/logout")) {
    logoutStarted?.resolve();
    if (logoutGate) await logoutGate.promise;
    return new Response(null, { status: 204 });
  }
  if (url.pathname.endsWith("/token")) {
    tokenReads += 1;
    if (url.searchParams.get("grant_type") === "refresh_token") return Response.json(session(newId, "refreshed"));
    return Response.json(session(body.email === "old@dogus.edu.tr" ? oldId : newId));
  }
  if (url.pathname.endsWith("/verify")) return Response.json(session(newId, "verified"));
  if (url.pathname.endsWith("/user")) return Response.json(session(newId).user);
  if (url.pathname.endsWith("/recover") || url.pathname.endsWith("/resend")) return Response.json({});
  throw new Error(`Beklenmeyen sentetik istek: ${url.pathname}`);
}) as typeof fetch;
Object.defineProperty(globalThis, "fetch", { value: transport, configurable: true });

async function flowScenario() {
  const auth = await import("./auth-session");
  const events = await import("./auth-events");
  const { api } = await import("./api");
  const { getSupabase } = await import("@/lib/supabase");
  const demo = { id: oldId, email: "demo@dogus.edu.tr", fullName: "Yerel Demo", role: "instructor" as const };
  events.notifyAuthChange("identity-changed");
  auth.signIn(demo);
  assert.equal(await auth.accessToken(), `dev:${oldId}`);
  assert.equal((await auth.getCurrentUser())?.id, oldId);
  assert.equal(requests.length, 0, "Açık demo yolu Supabase yapılandırılmış olsa da SDK ağına gitmez.");
  process.env.NEXT_PUBLIC_DEV_AUTH = "false";
  assert.throws(() => auth.signIn(demo), /Geliştirme/);
  assert.equal(auth.getStoredUser(), null);
  assert.equal(await auth.accessToken(), null, "Kapalı gate depoda kalan dev token'ı kullanamaz.");
  process.env.NEXT_PUBLIC_DEV_AUTH = "true";
  const provider = getSupabase()!;
  await provider.auth.stopAutoRefresh();
  const user = await auth.signInWithPassword("new@dogus.edu.tr", "synthetic-password");
  assert.equal(user.role, "student", "E-posta alanı veya metadata ders rolünü açamaz.");
  assert.equal(storage.getItem(events.DEMO_TOKEN_KEY), null);
  assert.equal((await auth.getCurrentUser())?.id, newId);
  const sdkKey = [...Array(storage.length)].map((_, i) => storage.key(i)).find((key) => key?.startsWith("sb-") && key.endsWith("-auth-token"));
  assert.ok(sdkKey);
  storage.setItem(sdkKey, JSON.stringify(session(oldId, "expired", -3600)));
  const beforeRefresh = tokenReads;
  const refreshedToken = await auth.accessToken();
  assert.ok(refreshedToken);
  assert.equal(JSON.parse(Buffer.from(refreshedToken.split(".")[1], "base64url").toString()).marker, "refreshed");
  assert.equal(tokenReads, beforeRefresh + 1);
  await auth.requestPasswordReset("new@dogus.edu.tr");
  const reset = requests.find((request) => request.path.startsWith("/auth/v1/recover"));
  assert.ok(reset);
  assert.equal(new URL(reset.path, "https://l5-auth.invalid").searchParams.get("redirect_to"), "https://l5-web.invalid/auth/callback?next=reset-password");
  await auth.updateCurrentPassword("synthetic-new-password");
  assert.ok(requests.some((request) => request.path === "/auth/v1/user" && request.body.password === "synthetic-new-password"));
  await auth.resendVerificationEmail("new@dogus.edu.tr");
  assert.ok(requests.some((request) => request.path.startsWith("/auth/v1/resend") && request.body.type === "signup"));
  browser.location = new URL("https://l5-web.invalid/auth/callback?token_hash=synthetic-hash&type=signup");
  assert.equal(await auth.completeAuthCallback(), "/dashboard");
  assert.equal(browser.location.search, "");
  browser.location = new URL("https://l5-web.invalid/auth/callback?token_hash=synthetic-hash&type=recovery");
  assert.equal(await auth.completeAuthCallback(), "/reset-password");
  browser.location = new URL("https://l5-web.invalid/auth/callback?next=https://evil.invalid");
  await assert.rejects(auth.completeAuthCallback(), /eksik/);
  process.env.NEXT_PUBLIC_ENTRA_TENANT_ID = "common";
  await assert.rejects(auth.signInWithEntra(), /yapılandırılmadı/);
  process.env.NEXT_PUBLIC_ENTRA_TENANT_ID = "11111111-1111-4111-8111-111111111111";
  let redirected = "";
  Object.assign(browser.location, { assign: (url: string) => { redirected = url; } });
  await auth.signInWithEntra();
  assert.equal(new URL(redirected).searchParams.get("provider"), "azure");
  assert.equal(new URL(redirected).searchParams.get("scopes"), "email");

  const errorResponse = (status: number) => Response.json({ error: { code: status === 401 ? "unauthenticated" : "permission_denied", message: "Sentetik ret", request_id: "synthetic" } }, { status });
  apiGate = deferred<Response>();
  const forbidden = api.get("/courses/forbidden");
  apiGate.resolve(errorResponse(403));
  await assert.rejects(forbidden);
  assert.equal(events.isAuthLocallySignedOut(), false, "403 oturumu kapatmaz.");
  apiGate = deferred<Response>();
  const delayed = api.get("/courses/delayed");
  await new Promise((resolve) => setTimeout(resolve, 0));
  await auth.signInWithPassword("old@dogus.edu.tr", "synthetic-password");
  apiGate.resolve(errorResponse(401));
  await assert.rejects(delayed);
  assert.equal(events.isAuthLocallySignedOut(), false, "Eski 401 yeni kimliği kapatamaz.");
  assert.equal((await auth.getCurrentUser())?.id, oldId);
  apiGate = deferred<Response>();
  const delayedSuccess = api.get("/courses/delayed-success");
  await new Promise((resolve) => setTimeout(resolve, 0));
  await auth.signInWithPassword("new@dogus.edu.tr", "synthetic-password");
  apiGate.resolve(Response.json({ private: "old-account-content" }));
  await assert.rejects(delayedSuccess, /Oturum değişti/);
  assert.equal(events.isAuthLocallySignedOut(), false);

  storage.setItem("dou-synapse-chat-session:course", "private-selection");
  sessionStorage.setItem("dou-synapse:exam-drafts:v1:old:course:exam", "private-answer");
  apiGate = deferred<Response>();
  logoutGate = deferred<void>(); logoutStarted = deferred<void>();
  const first = api.get("/courses/401-first");
  const second = api.get("/courses/401-second");
  const settled = Promise.allSettled([first, second]);
  await new Promise((resolve) => setTimeout(resolve, 0));
  apiGate.resolve(errorResponse(401));
  await logoutStarted.promise;
  assert.equal(events.isAuthLocallySignedOut(), true, "Çıkış ağı sürerken yerel görünüm kapanır.");
  assert.equal(storage.getItem("dou-synapse-chat-session:course"), null);
  assert.equal(sessionStorage.getItem("dou-synapse:exam-drafts:v1:old:course:exam"), null);
  assert.equal(await auth.getCurrentUser(), null);
  logoutGate.resolve();
  const rejected = await settled;
  assert.ok(rejected.every((result) => result.status === "rejected" && result.reason.code === "unauthenticated" && result.reason.requestId === "synthetic"));
  const logoutRequests = requests.filter((request) => request.path.startsWith("/auth/v1/logout"));
  assert.equal(logoutRequests.length, 1, "Paralel 401 tek sağlayıcı çıkışı başlatır.");
  apiGate = null; logoutGate = null; logoutStarted = null;
  await auth.signInWithPassword("new@dogus.edu.tr", "synthetic-password");
  const readGate = deferred<string>();
  const read = events.readWithinAuthEpoch(() => readGate.promise);
  await auth.signOutCurrent();
  readGate.resolve("old-private-token");
  assert.equal(await read, null);
  await provider.auth.stopAutoRefresh();
  process.stdout.write("L5_AUTH_FLOWS_PASS\n");
}

async function raceScenario() {
  const { withAuthWriteLock } = await import(process.env.L5_AUTH_LOCK_MODULE ?? "./auth-lock");
  const shared = memoryStorage();
  const name = "l5-shared-sdk-session";
  const options = { auth: { storage: shared, storageKey: name, autoRefreshToken: false, detectSessionInUrl: false, persistSession: true }, global: { fetch: transport } };
  const first = createClient("https://l5-race.invalid", "synthetic-anon", options);
  const second = createClient("https://l5-race.invalid", "synthetic-anon", options);
  await Promise.all([first.auth.initialize(), second.auth.initialize()]);
  await first.auth.signInWithPassword({ email: "old@dogus.edu.tr", password: "synthetic-password" });
  const lockManager = locks();
  logoutGate = deferred<void>(); logoutStarted = deferred<void>();
  const signingOut = withAuthWriteLock(() => first.auth.signOut({ scope: "local" }), lockManager);
  await logoutStarted.promise;
  const signingIn = withAuthWriteLock(() => second.auth.signInWithPassword({ email: "new@dogus.edu.tr", password: "synthetic-password" }), lockManager);
  // Kapalı kapı yeni yazımın kuyrukta, mutant ise depoda olmasına izin verir.
  await new Promise((resolve) => setTimeout(resolve, 0));
  logoutGate.resolve();
  await Promise.all([signingOut, signingIn]);
  const persisted = JSON.parse(shared.getItem(name) ?? "null");
  assert.equal(persisted?.user.id, newId, "L5_AUTH_RACE_NEW_SESSION_PRESERVED");
  await Promise.all([first.auth.stopAutoRefresh(), second.auth.stopAutoRefresh()]);
  process.stdout.write("L5_AUTH_RACE_PASS\n");
}

async function callbackScenario() {
  const value = session(newId, "callback");
  const hash = new URLSearchParams({ access_token: value.access_token, refresh_token: value.refresh_token, expires_in: "3600", token_type: "bearer", type: "signup" });
  browser.location = new URL(`https://l5-web.invalid/auth/callback#${hash}`);
  const auth = await import("./auth-session");
  assert.equal(await auth.completeAuthCallback(), "/dashboard");
  const initializationRequests = requests.filter((request) => request.path.startsWith("/auth/v1/"));
  assert.ok(initializationRequests.length > 0);
  assert.ok(initializationRequests.every((request) => request.authLockHeld), "Canonical callback ilk SDK kurulumu auth kilidi içinde olmalıdır.");
  assert.equal(browser.location.hash, "");
  assert.equal(await auth.accessToken(), value.access_token);
  const existingValue = session(newId, "existing-client");
  const existingHash = new URLSearchParams({ access_token: existingValue.access_token, refresh_token: existingValue.refresh_token, expires_in: "3600", token_type: "bearer", type: "recovery" });
  browser.location = new URL(`https://l5-web.invalid/auth/callback#${existingHash}`);
  assert.equal(await auth.completeAuthCallback(), "/reset-password");
  assert.equal(await auth.accessToken(), existingValue.access_token);
  const { getSupabase } = await import("@/lib/supabase");
  await getSupabase()!.auth.stopAutoRefresh();
  process.stdout.write("L5_AUTH_CALLBACK_PASS\n");
}

async function bridgeScenario() {
  // Gerçek SDK yayınını alıcı sekmeye bilerek geç teslim ederiz. Olay sırası
  // ortak Web Lock'tan bağımsızdır; SDK istemcileri ve ortak depo gerçektir.
  type Message = { event: string; session: unknown };
  class QueuedBroadcastChannel {
    static peers = new Set<QueuedBroadcastChannel>();
    static pending: { target: QueuedBroadcastChannel; data: Message }[] = [];
    private listeners: ((event: { data: Message }) => unknown)[] = [];
    constructor(readonly name: string) { QueuedBroadcastChannel.peers.add(this); }
    addEventListener(_type: string, listener: (event: { data: Message }) => unknown) { this.listeners.push(listener); }
    postMessage(data: Message) {
      for (const target of QueuedBroadcastChannel.peers) {
        if (target !== this && target.name === this.name) QueuedBroadcastChannel.pending.push({ target, data: structuredClone(data) });
      }
    }
    close() { QueuedBroadcastChannel.peers.delete(this); }
    static async flush(event: string) {
      const matching = this.pending.filter((message) => message.data.event === event);
      this.pending = this.pending.filter((message) => message.data.event !== event);
      for (const message of matching) {
        for (const listener of message.target.listeners) await listener({ data: message.data });
      }
    }
  }
  Object.defineProperty(globalThis, "BroadcastChannel", { value: QueuedBroadcastChannel, configurable: true });
  const seed = createClient("https://l5-auth.invalid", "synthetic-anon", {
    auth: { storage, autoRefreshToken: false, detectSessionInUrl: false, persistSession: true },
    global: { fetch: transport },
  });
  await seed.auth.initialize();
  await seed.auth.signInWithPassword({ email: "old@dogus.edu.tr", password: "synthetic-password" });
  const auth = await import("./auth-session");
  const events = await import("./auth-events");
  const { getSupabase } = await import("@/lib/supabase");
  // Başarısız/yarım kalmış çıkış: uygulama kapalı, SDK'nin eski kaydı duruyor.
  events.notifyAuthChange("signed-out");
  const changes: string[] = [];
  const stop = events.subscribeAuthChanges((change) => { changes.push(change); });
  const provider = getSupabase()!;
  const settle = () => new Promise<void>((resolve) => setTimeout(resolve, 0));
  try {
    await provider.auth.initialize();
    await settle();
    assert.equal((await provider.auth.getSession()).data.session?.user.id, oldId);
    assert.equal(events.isAuthLocallySignedOut(), true, "L5_AUTH_BRIDGE_PASSIVE_SIGNED_IN_CANNOT_REOPEN");
    assert.equal(await auth.getCurrentUser(), null);
    assert.equal(await auth.accessToken(), null);
    assert.equal(changes.includes("identity-changed"), false);

    await auth.signInWithPassword("new@dogus.edu.tr", "synthetic-password");
    assert.equal(events.isAuthLocallySignedOut(), false, "Açık giriş yerel çıkışı kaldırabilir.");
    assert.equal((await auth.getCurrentUser())?.id, newId);
    const beforeRefresh = changes.length;
    await provider.auth.refreshSession();
    await settle();
    assert.equal(changes.length, beforeRefresh, "Normal refresh aynı kimliğin görünümünü/taslağını geçersizleştirmez.");
    assert.equal(events.isAuthLocallySignedOut(), false);

    await QueuedBroadcastChannel.flush("SIGNED_IN");
    await settle();
    // Eski sekme gerçekten çıkış yapar; bildirimi yeni giriş bitene dek tutulur.
    await seed.auth.signOut({ scope: "local" });
    await auth.signInWithPassword("new@dogus.edu.tr", "synthetic-password");
    const newIdentity = events.captureAuthEpoch();
    await QueuedBroadcastChannel.flush("SIGNED_OUT");
    await settle();
    assert.equal(events.isAuthLocallySignedOut(), false, "L5_AUTH_BRIDGE_STALE_SIGNED_OUT_CANNOT_CLOSE_NEW_SESSION");
    assert.equal(events.isAuthEpochCurrent(newIdentity), true);
    assert.equal((await auth.getCurrentUser())?.id, newId);
    await seed.auth.signInWithPassword({ email: "new@dogus.edu.tr", password: "synthetic-password" });
    await QueuedBroadcastChannel.flush("SIGNED_IN");
    await settle();
    assert.equal(events.isAuthEpochCurrent(newIdentity), true, "Geç çıkış gözlemcinin aynı kullanıcı belleğini bozamaz.");

    // Güncel SDK deposu gerçekten boşsa pasif çıkış hâlâ özel görünümü kapatır.
    await seed.auth.signOut({ scope: "local" });
    await QueuedBroadcastChannel.flush("SIGNED_OUT");
    await settle();
    assert.equal(events.isAuthLocallySignedOut(), true, "Gerçek pasif çıkış yok sayılmamalı.");
    assert.equal(await auth.getCurrentUser(), null);
    process.stdout.write("L5_AUTH_BRIDGE_PASS\n");
  } finally {
    stop();
    await Promise.all([seed.auth.stopAutoRefresh(), provider.auth.stopAutoRefresh()]);
  }
}

await (process.argv[2] === "race" ? raceScenario() : process.argv[2] === "callback" ? callbackScenario() : process.argv[2] === "bridge" ? bridgeScenario() : flowScenario());
