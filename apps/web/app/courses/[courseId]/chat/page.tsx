"use client";

/**
 * Sohbet ekranı — TASARIM ÖNİZLEMESİ.
 *
 * Retrieval + cevap hattı backend'de G5-G6'da bağlanacak (PLAN.md); bu ekran o
 * güne kadar imza bileşenlerini (kaynak kartı, kapsam dışı bildirimi, Sokratik
 * kademe) gerçek yerleşimiyle gösterir. İçerik örnek veridir ve öyle etiketlenir —
 * kimse bunu çalışan retrieval sanmasın.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { AbstentionNotice, SourceCard } from "@/components/source-card";
import { Input, Button } from "@/components/ui";

export default function ChatPreviewPage() {
  const { courseId } = useParams<{ courseId: string }>();

  return (
    <AppShell>
      <nav className="mb-4 text-xs text-fg-subtle">
        <Link href="/courses" className="hover:text-fg">
          Derslerim
        </Link>{" "}
        /{" "}
        <Link href={`/courses/${courseId}`} className="hover:text-fg">
          Ders
        </Link>{" "}
        / <span className="text-fg-muted">Asistan</span>
      </nav>

      <div className="mb-6 rounded-lg border border-border bg-brand-subtle px-4 py-2">
        <p className="text-sm text-brand">
          Tasarım önizlemesi: aşağıdaki konuşma örnek veridir. Cevap hattı
          geliştirme planının 5-6. gününde bağlanacak.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Konuşma sütunu: max 70ch okuma genişliği */}
        <div className="space-y-6">
          {/* Öğrenci sorusu */}
          <div className="flex justify-end">
            <p className="max-w-[85%] rounded-lg bg-surface px-4 py-3 text-sm text-fg">
              Deadlock oluşması için hangi koşulların sağlanması gerekir?
            </p>
          </div>

          {/* Kaynaklı cevap */}
          <div className="prose-tr space-y-3">
            <p className="text-base text-fg">
              Bir sistemde deadlock oluşabilmesi için dört Coffman koşulunun{" "}
              <em>aynı anda</em> sağlanması gerekir: karşılıklı dışlama, tut ve
              bekle, kesintiye uğratamama ve döngüsel bekleme. Bu koşullardan
              herhangi biri kırılırsa deadlock oluşmaz.
            </p>
            <SourceCard
              source={{
                fileName: "os_hafta3.pdf",
                location: "Sayfa 12",
                quote:
                  "Deadlock için dört Coffman koşulunun birlikte sağlanması gerekir: mutual exclusion, hold and wait, no preemption, circular wait.",
              }}
            />
          </div>

          {/* Kapsam dışı örneği */}
          <div className="flex justify-end">
            <p className="max-w-[85%] rounded-lg bg-surface px-4 py-3 text-sm text-fg">
              Bugünkü dolar kuru ne kadar?
            </p>
          </div>
          <AbstentionNotice />

          {/* Girdi alanı */}
          <form
            className="flex gap-2"
            onSubmit={(e) => e.preventDefault()}
            aria-disabled
          >
            <Input placeholder="Ders materyaline soru sorun… (yakında)" disabled />
            <Button disabled>Gönder</Button>
          </form>
        </div>

        {/* Kaynak paneli: masaüstünde sabit sütun, mobilde içerik altına iner */}
        <aside className="space-y-3">
          <h2 className="text-sm font-medium text-fg">Bu dersin kaynakları</h2>
          <p className="text-xs text-fg-muted">
            Asistan yalnızca eğitmenin yüklediği bu materyallerden cevap verir;
            her cevap sayfa numarasıyla gelir.
          </p>
          <ul className="space-y-2 text-sm">
            <li className="rounded border border-border bg-surface px-3 py-2 font-mono text-xs text-fg-muted">
              os_hafta3.pdf · 24 sayfa
            </li>
            <li className="rounded border border-border bg-surface px-3 py-2 font-mono text-xs text-fg-muted">
              scheduler_slaytlari.pptx · 18 slayt
            </li>
          </ul>
        </aside>
      </div>
    </AppShell>
  );
}
