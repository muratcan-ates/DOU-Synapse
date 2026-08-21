import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Kaynak laboratuvarı",
};

export default function SourcesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
