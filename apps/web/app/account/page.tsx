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

      {/*
       * Üç işlem tek kartta `divide-y` satırları: üç ayrı kutu, üçüncüsü
       * kırmızımsı kenarlıklı — "kutu içinde kutu" ve kırmızının dördüncü
       * kullanımıydı. Yıkıcı eylemler `ConfirmAction` üzerinden gider: tetik
       * secondary, onay `danger` (kenarlıklı, dolgusuz). Sayfada kırmızı dolgu yok.
       */}
      <Card>
        <div className="divide-y divide-border">
          <AccountAction
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
      </Card>

      {/* Satır içi bağlantı muted: kırmızı bu sayfada yalnız onay adımında görünür. */}
      <p className="mt-6 text-sm text-fg-muted">
        Verilerin nasıl işlendiğini ayrıntılı görmek için{" "}
        <Link
          href="/kvkk"
          className="underline underline-offset-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          kişisel veriler ve gizlilik sayfasını
        </Link>{" "}
        okuyabilirsiniz.
      </p>
    </AppShell>
  );
}

/** Kart içi işlem satırı: başlık, kapsam açıklaması, altında eylem. */
function AccountAction({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action: ReactNode;
}) {
  return (
    <section className="py-6 first:pt-0 last:pb-0">
      <h2 className="text-lg font-semibold text-fg">{title}</h2>
      <p className="prose-tr mt-2 max-w-prose text-sm leading-6 text-fg-muted">{description}</p>
      <div className="mt-4">{action}</div>
    </section>
  );
}
