import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

/*
 * Geist: taste-skill'in Inter yasağına uygun tercih; latin-ext ile Türkçe glifler
 * (ğ ş ı İ ö ü ç) tam. next/font dosyaları derlemede yerelleştirir — çevrimdışı
 * demo CDN'e bağlı kalmaz.
 */
const geist = Geist({ subsets: ["latin", "latin-ext"], variable: "--font-geist" });
const geistMono = Geist_Mono({
  subsets: ["latin", "latin-ext"],
  variable: "--font-geist-mono",
});

export const metadata: Metadata = {
  title: "DOU-Synapse",
  description:
    "Ders materyaliyle sınırlandırılmış, kaynak gösteren yapay zekâ ders asistanı. Doğuş Üniversitesi COME 492",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr">
      <body className={`${geist.variable} ${geistMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
