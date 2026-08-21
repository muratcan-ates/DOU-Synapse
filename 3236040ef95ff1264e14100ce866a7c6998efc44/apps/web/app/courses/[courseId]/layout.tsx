import type { Metadata } from "next";
import { TITLE_TEMPLATE } from "@/app/layout";

/**
 * Ders detayı (materyal listesi) rotasının başlığı.
 *
 * Ders adı başlığa YAZILMAZ: bu layout sunucuda çalışır, sunucuda oturum
 * token'ı yoktur ve dersin adını çekmek için yapılacak istek yetkisiz döner.
 * Genel ama ayırt edici bir ad, sabit "DOU-Synapse"ten her hâlükârda iyidir.
 *
 * `default` bu sayfanın başlığıdır; `template` ise alt sekmelere (sohbet,
 * sınav, ...) soneki taşır — Next şablonu yalnız bir kademe iletir.
 */
export const metadata: Metadata = {
  title: {
    default: "Ders materyalleri",
    template: TITLE_TEMPLATE,
  },
};

export default function CourseLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
