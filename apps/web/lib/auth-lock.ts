/** SDK'nin ayrı istemcilerdeki giriş/çıkış yazımları aynı origin kilidini paylaşır. */
export const AUTH_WRITE_LOCK = "dou-synapse:auth-write:v1";
export interface AuthWriteLocks {
  request<T>(name: string, callback: () => Promise<T>): Promise<T>;
}

export function browserAuthLocks(): AuthWriteLocks | null {
  return typeof navigator !== "undefined" && navigator.locks ? navigator.locks : null;
}

export function withAuthWriteLock<T>(
  write: () => Promise<T>,
  locks = browserAuthLocks(),
): Promise<T> {
  // Sekme içi bir Promise kuyruğu diğer sekmenin SDK yazımını durduramaz.
  if (!locks) return Promise.reject(new Error("Bu tarayıcıda güvenli oturum açılamıyor. Güncel bir tarayıcı ve güvenli bağlantı kullanarak tekrar deneyin."));
  return locks.request(AUTH_WRITE_LOCK, write);
}
