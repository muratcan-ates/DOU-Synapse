"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

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
      <div className="mx-auto max-w-5xl space-y-7">
      <PageHeader
        eyebrow="Hesabım"
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

      <div className="space-y-5">
          <AccountAction
            step="01"
            title="Verilerimi indir"
            description="Profiliniz, ders üyelikleriniz, sohbetleriniz, sınav yanıtlarınız ve öğrenme ilerlemeniz tek bir JSON dosyasında hazırlanır. Yalnız size ait kayıtlar dışa aktarılır. Kota ve güvenlik operasyon kayıtları bu dosyaya dahil edilmez; kapsam açıklaması dosyada yer alır."
            action={
              <Button
                variant="secondary"
                aria-disabled={exporting}
                onClick={() => void exportData()}
              >
                {exporting ? "Hazırlanıyor…" : "JSON olarak indir"}
              </Button>
            }
          />

          <AccountAction
            step="02"
            title="Sohbet geçmişi"
            description="Tüm derslerdeki sohbet oturumlarınız, bağlı mesajlar ve geri bildirimler uygulama veritabanından silinir. Sınav ve ilerleme kayıtları etkilenmez. Daha önce indirdiğiniz dosyalar bu işlemle silinmez."
            action={
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
            }
          />

          <AccountAction
            step="03"
            title="Profil bilgilerimi kaldır"
            description="Uygulama profilinizdeki ad ve e-posta kaldırılır, sohbetleriniz silinir ve ders üyelikleriniz kapatılır. Sınav yanıtları, öğrenme ilerlemesi ve yüklediğiniz ders materyalleri mevcut profil kaydıyla bağlantılı kalır. Bu işlem bütün verilerinizi silmez ve kimliğinizle bağlantıyı tamamen kaldırmaz. Üniversite giriş hesabınız açık kalır; kapatılması için ayrıca işlem gerekir."
            action={
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
            }
          />
      </div>

      <p className="rounded-xl bg-surface-sunken px-5 py-4 text-base leading-7 text-fg-muted">
        Verilerin nasıl işlendiğini ayrıntılı görmek için{" "}
        <Link
          href="/kvkk"
          className="underline underline-offset-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          kişisel veriler ve gizlilik sayfasını
        </Link>{" "}
        okuyabilirsiniz.
      </p>
      <Link href="/profile" className="inline-flex min-h-11 items-center text-sm font-medium text-brand underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Profile dön</Link>
      </div>
    </AppShell>
  );
}

/** Keep the exact data scope beside each existing confirmed action. */
function AccountAction({
  step,
  title,
  description,
  action,
}: {
  step: string;
  title: string;
  description: string;
  action: ReactNode;
}) {
  return (
    <Card>
      <section className="grid gap-5 md:grid-cols-[200px_minmax(0,1fr)] md:gap-8">
        <div>
          <span aria-hidden className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-surface-sunken text-sm font-semibold tabular-nums text-fg-muted">{step}</span>
          <h2 className="text-xl leading-7 font-semibold text-fg">{title}</h2>
        </div>
        <div className="min-w-0">
          <p className="max-w-prose text-base leading-7 text-fg-muted">{description}</p>
          <div className="mt-5 border-t border-border pt-5">{action}</div>
        </div>
      </section>
    </Card>
  );
}
