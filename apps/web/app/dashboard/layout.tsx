import type { Metadata } from "next";
import { TITLE_TEMPLATE } from "@/lib/metadata";

export const metadata: Metadata = {
  title: {
    default: "Genel Bakış",
    template: TITLE_TEMPLATE,
  },
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
