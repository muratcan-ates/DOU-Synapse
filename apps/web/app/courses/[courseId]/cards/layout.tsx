import type { Metadata } from "next";

/** Tekrar kartları rotasının başlığı; ad, ders içi sekme şeridiyle aynı. */
export const metadata: Metadata = {
  title: "Hızlı tekrar",
};

export default function CardsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
