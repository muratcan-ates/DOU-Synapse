/**
 * Temel arayüz bileşenleri — tek otorite DESIGN.md.
 *
 * Şekil kilidi (DESIGN.md §Shapes): rozet/etiket 4px · buton, girdi, kart 8px ·
 * modal ve geniş panel 12px. `rounded-full` yalnız avatar ve durum noktasında
 * kullanılır; rozet pill DEĞİLDİR.
 * Gölge yok (DESIGN.md §Elevation seviye 0): kart ve panel kenarlıkla ayrılır.
 * Dokunma hedefi en az 44×44px (DESIGN.md §Responsive Behavior).
 */
"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ComponentPropsWithRef, ReactNode } from "react";
import { errorMessage } from "@/lib/errors";
import type { Tone } from "@/lib/labels";

/**
 * `disabled` bekleme süresince odağı çalar: tarayıcı devre dışı bırakılan
 * öğeden odağı `<body>`'ye atar ve klavyeyle çalışan kullanıcı her gönderimde
 * listenin başına döner. Bu yüzden bekleme `aria-disabled` ile bildirilir —
 * öğe odakta kalır, tıklama burada yok sayılır. Kural tek yerde durur ki her
 * çağrı yeri yeniden hatırlamak zorunda kalmasın (Anayasa XI).
 */
export function Button({
  variant = "primary",
  className = "",
  onClick,
  ref,
  "aria-disabled": ariaDisabled,
  ...props
}: ComponentPropsWithRef<"button"> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const inert = ariaDisabled === true || ariaDisabled === "true";
  const styles = {
    // Kırmızı tek aksandır ve birincil eylemde kullanılır (DESIGN.md renk kilidi).
    primary:
      "bg-brand text-white hover:bg-brand-strong active:scale-[0.98] dark:text-[#191715]",
    secondary:
      "border border-border-strong bg-surface text-fg hover:border-fg-subtle active:scale-[0.98]",
    ghost: "text-fg-muted hover:bg-brand-subtle/40 hover:text-fg active:scale-[0.98]",
    danger:
      "border border-border-strong text-danger hover:bg-danger-bg active:scale-[0.98]",
  }[variant];
  return (
    <button
      ref={ref}
      aria-disabled={ariaDisabled}
      onClick={(event) => {
        if (inert) {
          event.preventDefault();
          event.stopPropagation();
          return;
        }
        onClick?.(event);
      }}
      className={`inline-flex h-11 min-w-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition-[color,background,border,transform] duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-40 aria-disabled:cursor-not-allowed aria-disabled:opacity-40 ${styles} ${className}`}
      {...props}
    />
  );
}

export function Input({
  className = "",
  ref,
  ...props
}: ComponentPropsWithRef<"input">) {
  return (
    <input
      ref={ref}
      {...props}
      className={`h-11 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand ${className}`}
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
    <div className={`rounded-lg border border-border bg-surface p-6 ${className}`}>
      {children}
    </div>
  );
}

/**
 * Durum rozeti: soluk pastel zemin + koyu metin, 4px köşe (DESIGN.md §Shapes
 * rozeti `radius-sm` altında sayar).
 * Uppercase YOK — Türkçe i/İ dönüşümü bozulur (Anayasa V).
 * Renk tek başına bilgi taşımaz; etiket metni her zaman vardır.
 *
 * Ton listesi lib/labels.ts'teki `Tone` sözlüğüne bağlıdır: yeni bir ton
 * eklendiğinde stili unutulursa derleyici burada durdurur.
 */
const BADGE_STYLES: Record<Tone, string> = {
  success: "bg-success-bg text-success",
  warning: "bg-warning-bg text-warning",
  danger: "bg-danger-bg text-danger",
  info: "bg-info-bg text-info",
  neutral: "bg-bg text-fg-muted border border-border",
};

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm px-2.5 py-0.5 text-xs font-medium tracking-wide ${BADGE_STYLES[tone]}`}
    >
      {children}
    </span>
  );
}

/**
 * Onayla-sonra-uygula: yıkıcı eylemler tek tıkla gerçekleşmez.
 *
 * Yıkıcı eylemin tek onay bileşeni budur ve hata gösterimi burada zorunludur:
 * bu bileşeni atlayıp kendi onayını yazan her çağrı yeri, istek başarısız
 * olduğunda hatayı sessizce yutar — kullanıcı hiçbir şey görmez, satır da
 * yerinde durur. Yeni bir yıkıcı eylem yazılırken kopya çıkarılmaz (Anayasa XI).
 *
 * Modal yok: onay, eylemin kendi satırında açılır; bağlam kaybolmaz.
 * Odak bilinçli taşınır — bkz. aşağıdaki `useEffect`.
 */
export function ConfirmAction({
  label,
  confirmLabel,
  busyLabel,
  question,
  ariaLabel,
  onConfirm,
}: {
  label: string;
  confirmLabel: string;
  busyLabel: string;
  question: string;
  ariaLabel?: string;
  onConfirm: () => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const opened = useRef(false);
  const questionId = useId();

  /*
   * Onay moduna girip çıkarken tetikleyici buton DOM'dan kalkar; odak
   * kendiliğinden `<body>`'ye düşer ve klavyeyle çalışan kullanıcı listenin
   * başına atılır. Odak bu yüzden elle taşınır: moda girerken onay butonuna,
   * çıkarken tetikleyiciye. İlk render'da hiçbir şey yapılmaz — bileşen mount
   * olurken odak çalınmamalı; `opened` bunun için var.
   */
  useEffect(() => {
    if (confirming) {
      opened.current = true;
      confirmRef.current?.focus();
    } else if (opened.current) {
      opened.current = false;
      triggerRef.current?.focus();
    }
  }, [confirming]);

  if (!confirming) {
    return (
      <span className="flex flex-wrap items-center gap-2">
        <Button
          ref={triggerRef}
          variant="ghost"
          aria-label={ariaLabel}
          onClick={() => setConfirming(true)}
        >
          {label}
        </Button>
        {error && (
          <span role="alert" className="text-xs text-danger">
            {error}
          </span>
        )}
      </span>
    );
  }

  return (
    <span className="flex flex-wrap items-center gap-2">
      {/*
       * Eylemin sonucunu anlatan cümle onay butonuna bağlıdır. Dar ekranda
       * `hidden` (display:none) kullanılmaz: o cümle erişilebilirlik ağacından
       * da düşer ve `aria-describedby` boşa çıkar. `sr-only` görünmez yapar
       * ama okunur bırakır.
       */}
      <span
        id={questionId}
        className="sr-only text-xs text-fg-muted sm:not-sr-only"
      >
        {question}
      </span>
      <Button
        ref={confirmRef}
        variant="danger"
        aria-disabled={busy}
        aria-describedby={questionId}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await onConfirm();
            setConfirming(false);
          } catch (e) {
            setError(errorMessage(e, "İşlem tamamlanamadı."));
            setConfirming(false);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? busyLabel : confirmLabel}
      </Button>
      <Button variant="ghost" onClick={() => setConfirming(false)}>
        Vazgeç
      </Button>
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
    <div className="rise flex flex-col items-center gap-4 rounded-lg border border-dashed border-border-strong py-16 text-center">
      <p className="prose-tr text-sm text-fg-muted">{title}</p>
      {action}
    </div>
  );
}
