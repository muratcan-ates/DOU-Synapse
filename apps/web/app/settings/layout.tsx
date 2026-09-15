import type { Metadata } from "next";
import { TITLE_TEMPLATE } from "@/lib/metadata";

export const metadata: Metadata = {
  title: { default: "Ayarlar", template: TITLE_TEMPLATE },
};

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
