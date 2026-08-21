"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ErrorNote, PageHeader } from "@/components/page-state";
import { Button, Card, ConfirmAction } from "@/components/ui";
import { api, signOutCurrent } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import {
  chatDeletionMessage,
  downloadDataExport,
  type AccountAnonymization,
  type ChatDeletion,
  type UserDataExport,
} from "@/lib/privacy";

export default function AccountPage() {
  const router = useRouter();
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function exportData() {
    if (exporting) return;
    setExporting(true);
    setError(null);
    setNotice(null);
    try {
      const payload = await api.get<UserDataExport>("/me/export");
      downloadDataExport(payload);
      setNotice("Kişisel veri dosyanız indirildi.");
    } catch (cause) {
      setError(errorMessage(cause, "Kişisel veriler indirilemedi."));
    } finally {
      setExporting(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Verilerim"
        description="Kişisel verilerinizi indirebilir, sohbet geçmişinizi silebilir veya uygulama profilinizi anonimleştirebilirsiniz."
      />

      {(notice || error) && (
        <div className="mb-6" aria-live="polite">
          {notice && (
            <p role="status" className="text-sm text-success">
              {notice}
            </p>
          )}
          {error && <ErrorNote message={error} />}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex flex-col justify-between gap-5">
          <div>
            <h2 className="text-lg font-medium text-fg">Verilerimi indir</h2>
            <p className="prose-tr mt-2 text-sm leading-6 text-fg-muted">
              Profiliniz, ders üyelikleriniz, sohbetleriniz, sınav yanıtlarınız ve
              öğrenme ilerlemeniz tek bir JSON dosyasında hazırlanır. Yalnız size
              ait satırlar dışa aktarılır.
            </p>
          </div>
          <Button
            variant="secondary"
            aria-disabled={exporting}
            onClick={() => void exportData()}
          >
            {exporting ? "Hazırlanıyor…" : "JSON olarak indir"}
          </Button>
        </Card>

        <Card className="flex flex-col justify-between gap-5">
          <div>
            <h2 className="text-lg font-medium text-fg">Sohbet geçmişi</h2>
            <p className="prose-tr mt-2 text-sm leading-6 text-fg-muted">
              Tüm derslerdeki sohbet oturumlarınız ve bu oturumlara bağlı mesajlar
              kalıcı olarak silinir. Sınav ve ilerleme kayıtları etkilenmez.
            </p>
          </div>
          <ConfirmAction
            label="Tüm sohbet geçmişini sil"
            confirmLabel="Evet, geçmişi sil"
            busyLabel="Siliniyor…"
            question="Tüm sohbet geçmişiniz kalıcı olarak silinecek. Devam edilsin mi?"
            onConfirm={async () => {
              const result = await api.delete<ChatDeletion>("/me/chat-history");
              setError(null);
              setNotice(chatDeletionMessage(result.deleted_sessions));
            }}
          />
        </Card>

        <Card className="flex flex-col justify-between gap-5 border-danger/30 lg:col-span-2">
          <div>
            <h2 className="text-lg font-medium text-fg">
              Uygulama hesabını anonimleştir
            </h2>
            <p className="prose-tr mt-2 text-sm leading-6 text-fg-muted">
              Profil adınız ve e-posta adresiniz anonimleştirilir, ders
              üyelikleriniz kapatılır ve sohbetleriniz silinir. Akademik sınav
              kayıtları, bütünlük ve mevzuat yükümlülükleri için anonim profile
              bağlı kalır. Üniversite kimlik hesabınız bu işlemle kapanmaz; kimlik
              sağlayıcısında ayrıca işlem gerekir.
            </p>
          </div>
          <ConfirmAction
            label="Hesabımı anonimleştir"
            confirmLabel="Evet, hesabı anonimleştir"
            busyLabel="Anonimleştiriliyor…"
            question="Bu işlem sohbetleri siler ve tüm ders üyeliklerini kapatır. Devam edilsin mi?"
            onConfirm={async () => {
              const result = await api.delete<AccountAnonymization>("/me");
              window.alert(result.message);
              void signOutCurrent();
              router.replace("/");
            }}
          />
        </Card>
      </div>

      <p className="mt-6 text-sm text-fg-muted">
        Verilerin nasıl işlendiğini ayrıntılı görmek için{" "}
        <Link
          href="/kvkk"
          className="font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          KVKK aydınlatma metnini
        </Link>{" "}
        okuyabilirsiniz.
      </p>
    </AppShell>
  );
}
