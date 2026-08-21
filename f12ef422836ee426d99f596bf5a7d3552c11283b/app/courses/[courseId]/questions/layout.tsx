import type { Metadata } from "next";

/** Soru havuzu rotasının başlığı; ad, ders içi sekme şeridiyle aynı. */
export const metadata: Metadata = {
  title: "Soru havuzu",
};

export default function QuestionsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
