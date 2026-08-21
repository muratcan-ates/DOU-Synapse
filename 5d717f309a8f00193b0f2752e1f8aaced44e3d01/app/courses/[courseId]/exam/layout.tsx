import type { Metadata } from "next";

/** Sınav rotasının başlığı; ad, ders içi sekme şeridiyle aynı. */
export const metadata: Metadata = {
  title: "Sınav provası",
};

export default function ExamLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
