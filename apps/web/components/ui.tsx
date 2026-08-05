/**
 * Temel arayüz bileşenleri — DESIGN.md + kurulu skill'lere tabi.
 * Shape lock: konteyner/buton/girdi radius 8px; pill YALNIZ rozetlerde.
 * Gölge yok denecek kadar az; ayrım kenarlık ve boşlukla kurulur.
 */
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const styles = {
    // Kırmızı tek aksandır ve birincil eylemde kullanılır (DESIGN.md renk kilidi).
    primary:
      "bg-brand text-white hover:bg-brand-strong active:scale-[0.98] dark:text-[#191715] disabled:opacity-40",
    secondary:
      "border border-border-strong bg-surface text-fg hover:border-fg-subtle active:scale-[0.98] disabled:opacity-40",
    ghost: "text-fg-muted hover:bg-brand-subtle/40 hover:text-fg",
    danger: "border border-border-strong text-danger hover:bg-danger-bg",
  }[variant];
  return (
    <button
      className={`inline-flex h-10 min-w-[44px] items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition-[color,background,border,transform] duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${styles} ${className}`}
      {...props}
    />
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className="h-10 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
      {...props}
    />
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-border bg-surface p-6 shadow-[0_1px_2px_rgba(28,25,23,0.03)] ${className}`}
    >
      {children}
    </div>
  );
}

/**
 * Durum rozeti: pill + soluk pastel zemin + koyu metin (minimalist-ui §5).
 * Uppercase YOK — Türkçe i/İ dönüşümü bozulur (DESIGN.md istisnası).
 * Renk tek başına bilgi taşımaz; etiket metni her zaman vardır.
 */
export function Badge({
  tone,
  children,
}: {
  tone: "success" | "warning" | "danger" | "info" | "neutral";
  children: ReactNode;
}) {
  const styles = {
    success: "bg-success-bg text-success",
    warning: "bg-warning-bg text-warning",
    danger: "bg-danger-bg text-danger",
    info: "bg-info-bg text-info",
    neutral: "bg-bg text-fg-muted border border-border",
  }[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium tracking-wide ${styles}`}
    >
      {children}
    </span>
  );
}

export function EmptyState({
  title,
  action,
}: {
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="rise flex flex-col items-center gap-4 rounded-xl border border-dashed border-border-strong py-16 text-center">
      <p className="prose-tr text-sm text-fg-muted">{title}</p>
      {action}
    </div>
  );
}
