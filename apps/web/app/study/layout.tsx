import type { Metadata } from "next";
import { TITLE_TEMPLATE } from "@/lib/metadata";

export const metadata: Metadata = {
  title: { default: "Ders tekrarı", template: TITLE_TEMPLATE },
};

export default function StudyLayout({ children }: { children: React.ReactNode }) {
  return children;
}
