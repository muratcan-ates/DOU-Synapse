import type { Metadata } from "next";

/**
 * İlerleme/analitik rotasının başlığı.
 *
 * Ekranın kendi başlığı role göre değişir ("İlerlemem" / "Sınıf analitiği"),
 * ama rol istemcide bilinir. Sekme şeridindeki ortak ad kullanıldı; başlık
 * rotayı tanımlamaya yeter, rolü anlatmak zorunda değil.
 */
export const metadata: Metadata = {
  title: "İlerleme",
};

export default function AnalyticsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
