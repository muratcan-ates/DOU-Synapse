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
        description="Uygulamadaki kayıtlarınızı indirebilir, sohbet geçmişinizi silebilir veya profilinizdeki ad ve e-postayı kaldırabilirsiniz."
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
              ait kayıtlar dışa aktarılır. Kota ve güvenlik operasyon kayıtları bu
              dosyaya dahil edilmez; kapsam açıklaması dosyada yer alır.
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
              Tüm derslerdeki sohbet oturumlarınız, bağlı mesajlar ve geri
              bildirimler uygulama veritabanından silinir. Sınav ve ilerleme
              kayıtları etkilenmez. Daha önce indirdiğiniz dosyalar bu işlemle
              silinmez.
            </p>
          </div>
          <ConfirmAction
            label="Tüm sohbet geçmişini sil"
            confirmLabel="Evet, geçmişi sil"
            busyLabel="Siliniyor…"
            question="Uygulamadaki tüm sohbet oturumlarınız, mesajlarınız ve geri bildirimleriniz silinecek. Sınav ve ilerleme kayıtlarınız korunacak. Devam edilsin mi?"
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
              Profil bilgilerimi kaldır
            </h2>
            <p className="prose-tr mt-2 text-sm leading-6 text-fg-muted">
              Uygulama profilinizdeki ad ve e-posta kaldırılır, sohbetleriniz
              silinir ve ders üyelikleriniz kapatılır. Sınav yanıtları, öğrenme
              ilerlemesi ve yüklediğiniz ders materyalleri mevcut profil kaydıyla
              bağlantılı kalır. Bu işlem bütün verilerinizi silmez ve kimliğinizle
              bağlantıyı tamamen kaldırmaz. Üniversite giriş hesabınız açık kalır;
              kapatılması için ayrıca işlem gerekir.
            </p>
          </div>
          <ConfirmAction
            label="Profil bilgilerimi kaldır"
            confirmLabel="Evet, profil bilgilerimi kaldır"
            busyLabel="Profil bilgileri kaldırılıyor…"
            question="Profilinizdeki ad ve e-posta kaldırılacak, sohbetleriniz silinecek ve ders üyelikleriniz kapatılacak. Sınav, ilerleme ve materyal kayıtları ile üniversite giriş hesabınız korunacak. Devam edilsin mi?"
            onConfirm={async () => {
              const result = await api.delete<AccountAnonymization>("/me");
              setNotice(result.message);
              setError(null);
              try {
                await signOutCurrent();
                router.replace("/");
              } catch (cause) {
                setError(
                  errorMessage(
                    cause,
                    "Profil bilgileriniz kaldırıldı. Kimlik sağlayıcısındaki oturumun kapanması doğrulanamadı.",
                  ),
                );
              }
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
