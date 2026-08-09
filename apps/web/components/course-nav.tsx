"use client";

/**
 * Ders içi sekme navigasyonu.
 * Aktif sekme kırmızı alt çizgiyle işaretlenir — kırmızının üç meşru kullanımından
 * biri (DESIGN.md: aktif navigasyon göstergesi).
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { getStoredUser } from "@/lib/api";

const TABS = [
  { slug: "", label: "Materyaller" },
  { slug: "/chat", label: "Asistan" },
  { slug: "/exam", label: "Sınav provası" },
  { slug: "/questions", label: "Soru havuzu", instructorOnly: true },
  { slug: "/analytics", label: "İlerleme" },
  { slug: "/members", label: "Katılımcılar", instructorOnly: true },
];

export function CourseNav({ courseId }: { courseId: string }) {
  const pathname = usePathname();
  const base = `/courses/${courseId}`;
  const isInstructor = getStoredUser()?.role === "instructor";

  return (
    <nav className="mb-8 flex gap-1 overflow-x-auto border-b border-border">
      {TABS.filter((tab) => !tab.instructorOnly || isInstructor).map((tab) => {
        const href = `${base}${tab.slug}`;
        const active = pathname === href;
        return (
          <Link
            key={tab.slug}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm transition-colors ${
              active
                ? "border-brand font-medium text-fg"
                : "border-transparent text-fg-muted hover:border-border-strong hover:text-fg"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
