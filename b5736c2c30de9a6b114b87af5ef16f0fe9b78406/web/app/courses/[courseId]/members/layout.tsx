import type { Metadata } from "next";

/** Katılımcı yönetimi rotasının başlığı; ad, ders içi sekme şeridiyle aynı. */
export const metadata: Metadata = {
  title: "Katılımcılar",
};

export default function MembersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
