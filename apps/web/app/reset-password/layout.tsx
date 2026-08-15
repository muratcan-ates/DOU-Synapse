import type { Metadata } from "next";

/** Yeni parolayı kaydetme rotasının sekme başlığı. */
export const metadata: Metadata = {
  title: "Yeni parola",
};

export default function ResetPasswordLayout({ children }: { children: React.ReactNode }) {
  return children;
}
