export interface UserDataExport {
  schema_version: "1";
  generated_at: string;
  profile: {
    id: string;
    email: string;
    full_name: string | null;
    created_at: string;
  };
  memberships: unknown[];
  chat_sessions: unknown[];
  exam_sessions: unknown[];
  mastery: unknown[];
}

export interface ChatDeletion {
  deleted_sessions: number;
}

export interface AccountAnonymization {
  anonymized: boolean;
  deleted_chat_sessions: number;
  revoked_memberships: number;
  retained_owned_courses: number;
  identity_provider_action_required: boolean;
  message: string;
}

/** Dosya adı sunucunun Content-Disposition başlığına bağlı kalmadan kararlıdır. */
export function exportFilename(generatedAt: string): string {
  const date = generatedAt.slice(0, 10);
  const safeDate = /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : "veri";
  return "dou-synapse-verilerim-" + safeDate + ".json";
}

export function chatDeletionMessage(count: number): string {
  if (count === 0) return "Silinecek sohbet geçmişi bulunamadı.";
  return String(count) + " sohbet oturumu kalıcı olarak silindi.";
}

export function downloadDataExport(payload: UserDataExport): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = exportFilename(payload.generated_at);
  anchor.click();
  URL.revokeObjectURL(url);
}
