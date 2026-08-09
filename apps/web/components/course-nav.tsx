"use client";

/**
 * Ders içi sekme navigasyonu.
 * Aktif sekme kırmızı alt çizgiyle işaretlenir — kırmızının üç meşru kullanımından
 * biri (DESIGN.md: aktif navigasyon göstergesi).
 *
 * Rol doğrudan `localStorage`'dan değil `useSession()`'dan okunur: depo okuması
 * tek yerde yaşar (Anayasa XI) ve render gövdesinde sunucuda var olmayan bir
 * API'ye dokunulmaz.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "@/lib/session";

const TABS = [
  { slug: "", label: "Materyaller" },
  { slug: "/chat", label: "Asistan" },
  { slug: "/exam", label: "Sınav provası" },
  { slug: "/questions", label: "Soru havuzu", instructorOnly: true },
  { slug: "/analytics", label: "İlerleme" },
  { slug: "/members", label: "Katılımcılar", instructorOnly: true },
];

export function CourseNav({ courseId }: { courseId: string }) {
  const pathname = usePathname();
  const { isInstructor, ready } = useSession();
  const base = `/courses/${courseId}`;

  return (
    /*
     * `ready` false iken rol bilinmiyor. Üç seçenekten ikisi kötü:
     *   - eğitmen sekmelerini eksik çizip sonradan ARAYA eklemek, halihazırda
     *     görünen sekmeleri yana kaydırır (tıklamak üzere olan hedef kayar);
     *   - hepsini çizip öğrenciden geri almak rolü sızdırır ve belirsizlikte
     *     kapanma kuralını çiğner (Anayasa IV).
     * Bu yüzden şerit `visibility: hidden` ile çizilir: yükseklik ve alt çizgi
     * yerinde kalır, altındaki içerik zıplamaz, sekmeler tek seferde belirir ve
     * görünürken hiçbir öğe yer değiştirmez. `display: none` bunu yapamaz —
     * şerit tamamen kalkar, sayfa dikey olarak zıplar.
     */
    <nav
      className={`mb-8 flex gap-1 overflow-x-auto border-b border-border ${
        ready ? "" : "invisible"
      }`}
    >
      {TABS.filter((tab) => !tab.instructorOnly || isInstructor).map((tab) => {
        const href = `${base}${tab.slug}`;
        const active = pathname === href;
        return (
          /*
           * Odak halkası negatif offset ile öğenin İÇİNE çizilir: şerit
           * `overflow-x-auto` olduğu için dışarı taşan halkanın üst ve alt
           * kenarı kırpılıyordu, klavyeyle gezen kullanıcı nerede olduğunu
           * göremiyordu. `py-3` dokunma hedefini 44px'e çıkarır
           * (DESIGN.md §Responsive Behavior).
           */
          <Link
            key={tab.slug}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`-mb-px flex items-center whitespace-nowrap border-b-2 px-4 py-3 text-sm transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
              active
                ? "border-brand font-medium text-fg"
                : "border-transparent text-fg-muted hover:border-border-strong hover:text-fg"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
