"use client";

/**
 * Tema seçici: Sistem / Açık / Koyu.
 *
 * Neden ikon değil metin: bu üründe renk ve şekil tek başına bilgi taşımaz
 * (DESIGN.md §Erişilebilirlik) — ay/güneş ikonu seçili durumu ekran okuyucuya
 * anlatmaz ve depoda ikon kütüphanesi yoktur (tek elle çizilen SVG marka
 * işaretidir). Segment kontrolü ders sekmeleriyle aynı gramerdir.
 *
 * "Sistem" ayrı bir seçenektir çünkü çoğu kullanıcı temayı işletim sisteminde
 * yönetir; yalnız Açık/Koyu sunmak o bağı koparır ve akşam otomatik geçişi
 * sessizce bozar.
 */

import { useEffect, useState } from "react";
import {
  applyThemePreference,
  readThemePreference,
  THEME_OPTIONS,
  type ThemePreference,
} from "@/lib/theme";

export function ThemeControl({ tone = "ink" }: { tone?: "ink" | "canvas" }) {
  /*
   * Sunucu tercihi bilemez (depo tarayıcıda). Bu yüzden ilk render "system"
   * ile eşleşir ve gerçek tercih bağlandıktan SONRA okunur; hidrasyon uyuşmaz
   * hatası çıkmaz. Sayfanın rengi bundan etkilenmez: onu <head>'deki açılış
   * betiği zaten boyamadan önce ayarladı.
   */
  const [preference, setPreference] = useState<ThemePreference>("system");

  useEffect(() => {
    setPreference(readThemePreference());
  }, []);

  function choose(next: ThemePreference): void {
    setPreference(next);
    applyThemePreference(next);
  }

  const ink = tone === "ink";
  return (
    <div
      role="group"
      aria-label="Tema"
      className={`flex gap-0.5 rounded-lg p-0.5 ${
        ink ? "bg-ink-raised" : "bg-surface-sunken"
      }`}
    >
      {THEME_OPTIONS.map((option) => {
        const active = preference === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => choose(option.value)}
            className={[
              "min-h-9 flex-1 rounded-md px-2 text-xs font-medium transition-colors duration-200",
              ink
                ? "focus-visible:outline-brand-on-ink"
                : "focus-visible:outline-brand",
              "focus-visible:outline-2 focus-visible:outline-offset-2",
              active
                ? ink
                  ? "bg-ink text-ink-fg"
                  : "bg-surface text-fg shadow-e1"
                : ink
                  ? "text-ink-fg-muted hover:text-ink-fg"
                  : "text-fg-muted hover:text-fg",
            ].join(" ")}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
