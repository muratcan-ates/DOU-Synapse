import type { Metadata } from "next";

/** Sınav çatısını kuran eğitmen rotasının sekme başlığı. */
export const metadata: Metadata = {
  title: "Sınav blueprint'i",
};

export default function BlueprintsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
