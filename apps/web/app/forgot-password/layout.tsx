import type { Metadata } from "next";

/** Parola yenileme bağlantısı isteme rotasının sekme başlığı. */
export const metadata: Metadata = {
  title: "Parola yenileme",
};

export default function ForgotPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}
