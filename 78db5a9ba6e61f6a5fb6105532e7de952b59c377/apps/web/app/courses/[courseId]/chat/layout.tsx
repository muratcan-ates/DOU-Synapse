import type { Metadata } from "next";

/** Sohbet rotasının başlığı; ad, ders içi sekme şeridiyle aynı ("Asistan"). */
export const metadata: Metadata = {
  title: "Asistan",
};

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
