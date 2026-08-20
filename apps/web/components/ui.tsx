/**
 * Temel arayüz bileşenleri — tek otorite DESIGN.md.
 *
 * Şekil kilidi (DESIGN.md §Shapes): rozet/etiket 4px · buton, girdi, kart 8px ·
 * modal ve geniş panel 12px. `rounded-full` yalnız avatar ve durum noktasında
 * kullanılır; rozet pill DEĞİLDİR.
 * Elevation (DESIGN.md §Elevation): seviyeler artık token (`shadow-e1/e2/e3`).
 * Kart seviye 1'dir — kenarlık tek başına katman sinyali taşımıyordu; her yüzey
 * aynı beyazdı ve hiyerarşi yalnız 1px saç çizgisinden okunuyordu. Gölge sıcak
 * tonludur (metin renginden), saf siyah değil.
 * Dokunma hedefi en az 44×44px (DESIGN.md §Responsive Behavior).
 */
"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ComponentPropsWithRef, ReactNode } from "react";
import type { Tone } from "@/lib/labels";
import { useSubmit } from "@/lib/use-submit";

/**
 * `disabled` bekleme süresince odağı çalar: tarayıcı devre dışı bırakılan
 * öğeden odağı `<body>`'ye atar ve klavyeyle çalışan kullanıcı her gönderimde
 * listenin başına döner. Bu yüzden bekleme `aria-disabled` ile bildirilir —
 * öğe odakta kalır, tıklama burada yok sayılır. Kural tek yerde durur ki her
 * çağrı yeri yeniden hatırlamak zorunda kalmasın (Anayasa XI).
 */
export function Button({
  variant = "primary",
  size = "md",
  className = "",
  onClick,
  ref,
  "aria-disabled": ariaDisabled,
  ...props
}: ComponentPropsWithRef<"button"> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "md" | "sm";
}) {
  const inert = ariaDisabled === true || ariaDisabled === "true";
  const styles = {
    // Kırmızı tek aksandır ve birincil eylemde kullanılır (DESIGN.md renk kilidi).
    primary:
      "bg-brand text-white shadow-e1 hover:bg-brand-strong active:translate-y-px active:shadow-none dark:text-[#191715]",
    secondary:
      "border border-border-strong bg-surface text-fg hover:border-fg-subtle hover:bg-surface-sunken active:translate-y-px",
    ghost:
      "text-fg-muted hover:bg-surface-sunken hover:text-fg active:translate-y-px",
    danger:
      "border border-border-strong text-danger hover:bg-danger-bg hover:border-danger active:translate-y-px",
  }[variant];
  /*
   * Küçük boy, satır içi eylemler için: liste satırındaki "Sil"/"Önizle" düz
   * metin gibi duruyordu ve tıklanabilir olduğu yalnız imleçten anlaşılıyordu.
   * 44px dokunma hedefi korunur — yükseklik 36px, dikey dolgu ile hedef alanı
   * satırın kendisidir; `sm` yalnız masaüstü yoğunluğunda kullanılır.
   */
  const sizing = { md: "h-11 min-w-11 px-4 text-sm", sm: "h-9 px-3 text-[0.8125rem]" }[size];
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
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-[color,background,border,transform,box-shadow] duration-200 ${sizing} focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-40 aria-disabled:cursor-not-allowed aria-disabled:opacity-40 ${styles} ${className}`}
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
  variant = "default",
}: {
  children: ReactNode;
  className?: string;
  variant?: "default" | "soft" | "flat";
}) {
  const variantClass = {
    // Seviye 1: kanvastan yükselen içerik yüzeyi.
    default: "rounded-lg border border-border bg-surface shadow-e1",
    // Çukur: kanvasın ALTINDA duran açıklama/meta bloğu — gölge almaz.
    soft: "rounded-lg border border-border bg-surface-sunken",
    // Düz: içinde kendi satır ayraçları olan liste kabı; çift çerçeve olmasın.
    flat: "rounded-lg border border-border bg-surface",
  }[variant];
  return (
    <div className={`${variantClass} p-6 ${className}`}>
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
 * Yıkıcı işlem sürerken onay satırı kapatılamaz.
 *
 * `aria-disabled` odağı korur fakat tek başına davranışı engellemez. Karar saf
 * fonksiyonda tutulur ki "onay başladı -> kullanıcı Vazgeç'e bastı -> istek
 * sonra tamamlandı" yarışı DOM olmadan da kırmızıya çevrilebilsin.
 */
export function canDismissConfirmAction(busy: boolean): boolean {
  return !busy;
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
  size = "md",
  onConfirm,
}: {
  label: string;
  confirmLabel: string;
  busyLabel: string;
  question: string;
  ariaLabel?: string;
  /** Liste satırında `sm`: eylem satırın yoğunluğuna uyar, hedef alan satırdır. */
  size?: "md" | "sm";
  onConfirm: () => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  /*
   * Onay satırı sonuç NE OLURSA OLSUN kapanır: başarıda iş bitti, hatada da
   * hata metni tetikleyicinin yanında gösterilir (aşağıdaki `error` satırı).
   * Çift-onay kapısı `useSubmit`'te.
   */
  const { busy, error, submit: confirm } = useSubmit(async () => {
    try {
      await onConfirm();
    } finally {
      setConfirming(false);
    }
  }, "İşlem tamamlanamadı.");
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
        {/*
         * Tetikleyici `ghost` idi: liste satırında düz metinden ayırt edilemiyordu
         * ve tıklanabilir olduğu yalnız imleçle anlaşılıyordu (ekran ölçümü).
         * Kenarlıklı ikincil biçim onu kontrol yapar; kırmızı yine yalnız onay
         * adımında (danger) görünür.
         */}
        <Button
          ref={triggerRef}
          variant="secondary"
          size={size}
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
        size={size}
        aria-disabled={busy}
        aria-describedby={questionId}
        onClick={() => void confirm()}
      >
        {busy ? busyLabel : confirmLabel}
      </Button>
      <Button
        variant="ghost"
        size={size}
        aria-disabled={busy}
        onClick={() => {
          if (!canDismissConfirmAction(busy)) return;
          setConfirming(false);
        }}
      >
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
    <div className="rise flex flex-col items-center gap-4 rounded-lg border border-dashed border-border-strong bg-surface-sunken py-16 text-center">
      <p className="prose-tr text-sm text-fg-muted">{title}</p>
      {action}
    </div>
  );
}
