import type { Metadata } from "next";
import { TITLE_TEMPLATE } from "@/app/layout";

/**
 * Ders listesi rotasının başlığı. Sayfa `"use client"` olduğu için `metadata`
 * export'u orada çalışmaz; başlık bu ince sunucu layout'unda yaşar
 * (gerekçenin tamamı app/layout.tsx'te).
 *
 * `template` burada da bildirilir: bu segmentin altında başka rotalar var ve
 * Next şablonu yalnız bir kademe taşır. Düz metin başlık verilseydi
 * /courses/[courseId] ve altındaki beş ekran soneksiz kalırdı.
 */
export const metadata: Metadata = {
  title: {
    default: "Derslerim",
    template: TITLE_TEMPLATE,
  },
};

export default function CoursesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
