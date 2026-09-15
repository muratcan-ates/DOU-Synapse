import type { Metadata } from "next";

/** Kavram haritası rotasının başlığı; ad, ders içi sekme şeridiyle aynı. */
export const metadata: Metadata = {
  title: "Kavram haritası",
};

export default function ConceptsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
