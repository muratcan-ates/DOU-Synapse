import type { Metadata } from "next";

/** Açık izinli AI kalite incelemelerinin eğitmen rotası. */
export const metadata: Metadata = {
  title: "AI kalite",
};

export default function QualityLayout({ children }: { children: React.ReactNode }) {
  return children;
}
