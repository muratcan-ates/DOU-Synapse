import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { TITLE_TEMPLATE } from "@/lib/metadata";
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

/*
 * Rota başlıkları neden `layout.tsx` dosyalarında: ekran bileşenlerinin hepsi
 * `"use client"` ve istemci bileşeninde `metadata` export'u çalışmaz. Her rota
 * segmentine `children`'ı geçiren ince bir sunucu layout'u konuldu; başlık
 * orada tanımlı. Böylece Next'in rota duyurucusu sayfa değişimini ekran
 * okuyucuya gerçekten bildirir; sabit tek başlıkla hiçbir geçiş duyurulmuyordu.
 *
 * Son ek ("· DOU-Synapse") burada tanımlanır ve alt layout'lar bu sabiti
 * içe aktarır — yedi dosyaya elle yazılan bir sonek er geç birinde unutulur
 * (Anayasa XI: ürün kararı tek sözlükte yaşar).
 *
 * Neden ara segmentlerin de şablonu tekrar bildirmesi gerekiyor: Next şablonu
 * yalnız bir kademe taşır. `resolve-metadata.js` her katmandan sonra
 * `titleTemplates.title`'ı O KATMANIN kendi `template`'i ile değiştirir; bir
 * katman başlığı düz metin verirse şablon `null` olur ve torunlara ulaşmaz.
 * Bu yüzden çocuğu olan her layout `{ default, template }` biçimini kullanır,
 * yaprak layout'lar düz metin.
 *
 * Giriş ekranı (`/`) kök segmentin kendisidir; şablon kendi segmentindeki
 * `page.tsx`'e uygulanmaz, o yüzden orada `default` görünür — doğru davranış.
 */
export const metadata: Metadata = {
  title: {
    template: TITLE_TEMPLATE,
    default: "DOU-Synapse",
  },
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
