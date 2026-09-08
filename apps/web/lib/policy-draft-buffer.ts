import type { PolicyDraft } from "./policy";

/** RAM-only draft ownership. Each mounted editor gets one revocable lease. */
export interface PolicyDraftLease {
  current(): boolean;
  read(): PolicyDraft | null;
  write(draft: PolicyDraft): boolean;
  close(): void;
}

export function createPolicyDraftBuffer() {
  let draft: PolicyDraft | null = null;
  let generation = 0;
  return {
    open(): PolicyDraftLease {
      const identity = ++generation;
      const current = () => generation === identity;
      return {
        current,
        read: () => current() ? draft : null,
        write(value) { if (!current()) return false; draft = value; return true; },
        close() { if (current()) generation += 1; },
      };
    },
    clear() { draft = null; generation += 1; },
  };
}
export type PolicyDraftBuffer = ReturnType<typeof createPolicyDraftBuffer>;
