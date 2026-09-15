"use client";

import { useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui";
import { useAccessibilityPreferences } from "@/components/accessibility-provider";
import type { AccessibilityPreferences } from "@/lib/accessibility";

function SettingsContent() {
  const { preferences, ready, systemReducedMotion, updatePreferences, resetPreferences } = useAccessibilityPreferences();
  const [message, setMessage] = useState("");
  function update(patch: Partial<Omit<AccessibilityPreferences, "version">>) {
    const saved = updatePreferences(patch);
    setMessage(saved ? "Tercihiniz uygulandı ve bu tarayıcıya kaydedildi." : "Tercihiniz bu oturumda uygulandı. Tarayıcı kalıcı kayda izin vermedi.");
  }
  function openAppearance() {
    const control = document.getElementById("appearance-control");
    if (!control) return;
    control.focus({ preventScroll: true });
    const disclosure = control.closest("details");
    if (disclosure) disclosure.open = true;
  }
  const choice = "flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border border-border-strong bg-surface px-4 py-3 text-sm has-checked:border-brand has-checked:bg-brand-subtle has-checked:text-brand has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-brand";
  const input = "h-5 w-5 shrink-0 accent-brand focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand";

  return <div className="mx-auto max-w-[960px]">
    <header className="mb-8 border-b border-border pb-7">
      <p className="mb-2 text-sm font-medium text-brand">Size uygun çalışma alanı</p>
      <h1 className="text-3xl font-semibold tracking-tight text-fg">Ayarlar</h1>
      <p className="mt-3 max-w-[65ch] text-base text-fg-muted">Görünümü ve okuma deneyimini kendinize göre düzenleyin. Tercihler bu cihaz ve tarayıcı için geçerlidir; hesabınıza gönderilmez.</p>
    </header>

    <section aria-labelledby="appearance-heading" className="mb-5 flex flex-col gap-5 rounded-[20px] border border-border bg-surface p-5 sm:flex-row sm:items-center sm:justify-between sm:p-7">
      <div className="min-w-0">
        <h2 id="appearance-heading" className="text-lg font-semibold">Görünüm</h2>
        <p className="mt-1 max-w-[48ch] text-sm text-fg-muted">Açık, koyu veya sistem temasını üst çubuktaki görünüm menüsünden seçin.</p>
      </div>
      <Button type="button" variant="secondary" className="shrink-0" onClick={openAppearance}>Tema seçeneklerini aç</Button>
    </section>

    <section aria-labelledby="accessibility-heading" className="rounded-[20px] border border-border bg-surface p-5 sm:p-7">
      <div className="mb-6">
        <h2 id="accessibility-heading" className="text-lg font-semibold">Erişilebilirlik</h2>
        <p className="mt-1 text-sm text-fg-muted">Değişiklikler hemen uygulanır. Tarayıcınızın yakınlaştırmasını da kullanabilirsiniz.</p>
      </div>
      {!ready ? <p role="status" className="py-4 text-sm text-fg-muted">Tercihleriniz yükleniyor…</p> : <div className="space-y-7">
        <fieldset>
          <legend className="mb-1 text-base font-semibold">Yazı boyutu</legend>
          <p id="text-size-help" className="mb-3 text-sm text-fg-muted">Büyük yazı seçeneği, metinleri ve onlarla ölçeklenen kontrolleri %25 büyütür.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {([{ value: "default", label: "Standart", detail: "Varsayılan boyut" }, { value: "large", label: "Büyük", detail: "%25 daha büyük" }] as const).map(option => <label key={option.value} className={choice}>
              <input type="radio" name="text-size" value={option.value} checked={preferences.textSize === option.value} onChange={() => update({ textSize: option.value })} aria-describedby="text-size-help" className={input} />
              <span><span className="block font-semibold">{option.label}</span><span className="mt-0.5 block text-xs text-fg-muted">{option.detail}</span></span>
            </label>)}
          </div>
        </fieldset>
        <fieldset className="border-t border-border pt-6">
          <legend className="float-left mb-1 w-full text-base font-semibold">Hareket</legend>
          <p id="motion-help" className="clear-both mb-3 text-sm text-fg-muted">Azaltıldığında dekoratif animasyonlar ve sayfa geçişleri durur.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {([{ value: "system", label: "Sistem ayarını kullan", detail: systemReducedMotion ? "Sisteminiz hareketi azaltıyor" : "Sisteminiz harekete izin veriyor" }, { value: "reduce", label: "Hareketi azalt", detail: "Bu tarayıcıda her zaman" }] as const).map(option => <label key={option.value} className={choice}>
              <input type="radio" name="motion" value={option.value} checked={preferences.motion === option.value} onChange={() => update({ motion: option.value })} aria-describedby="motion-help" className={input} />
              <span><span className="block font-semibold">{option.label}</span><span className="mt-0.5 block text-xs text-fg-muted">{option.detail}</span></span>
            </label>)}
          </div>
        </fieldset>
        <div className="divide-y divide-border border-y border-border">
          <label className="flex min-h-20 cursor-pointer items-center justify-between gap-5 py-5">
            <span><span id="contrast-label" className="block text-base font-semibold">Yüksek kontrast</span><span id="contrast-help" className="mt-1 block text-sm text-fg-muted">Metinleri ve kontrol kenarlıklarını her iki temada daha belirgin yapar.</span></span>
            <input type="checkbox" checked={preferences.contrast === "more"} onChange={event => update({ contrast: event.target.checked ? "more" : "standard" })} aria-labelledby="contrast-label" aria-describedby="contrast-help" className={input} />
          </label>
          <label className="flex min-h-20 cursor-pointer items-center justify-between gap-5 py-5">
            <span><span id="links-label" className="block text-base font-semibold">Bağlantıların altını çiz</span><span id="links-help" className="mt-1 block text-sm text-fg-muted">Sayfalara giden bağlantıları metinden ayırt etmeyi kolaylaştırır.</span></span>
            <input type="checkbox" checked={preferences.underlineLinks} onChange={event => update({ underlineLinks: event.target.checked })} aria-labelledby="links-label" aria-describedby="links-help" className={input} />
          </label>
        </div>
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-[45ch] text-sm text-fg-muted">Sıfırlama yalnız bu erişilebilirlik tercihlerini değiştirir. Tema seçiminiz korunur.</p>
          <Button type="button" variant="secondary" className="shrink-0" onClick={() => {
            const saved = resetPreferences();
            setMessage(saved ? "Erişilebilirlik tercihleri varsayılanlara döndürüldü." : "Varsayılanlar bu oturumda uygulandı. Tarayıcı kalıcı kayda izin vermedi.");
          }}>Varsayılanlara dön</Button>
        </div>
      </div>}
      <p role="status" aria-live="polite" aria-atomic="true" className="mt-4 min-h-6 text-sm text-fg-muted">{message}</p>
    </section>
    <aside aria-labelledby="reading-preview-heading" className="mt-6 border-l-2 border-brand pl-5">
      <h2 id="reading-preview-heading" className="text-base font-semibold">Okuma görünümünüz</h2>
      <p className="mt-2 max-w-[62ch] text-base text-fg-muted">Ders kaynakları, sorular ve açıklamalar seçtiğiniz görünümle gösterilir. Çalışmaya devam etmek için <Link href="/courses" className="rounded-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand">derslerinize geçebilirsiniz</Link>.</p>
    </aside>
  </div>;
}

export default function SettingsPage() {
  return <AppShell><SettingsContent /></AppShell>;
}
