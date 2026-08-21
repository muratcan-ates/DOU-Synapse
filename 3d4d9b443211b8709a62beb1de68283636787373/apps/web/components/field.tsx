"use client";

/**
 * Etiketli form alanı — etiket ile girdi arasındaki bağ tek yerde kurulur.
 *
 * Neden ayrı bir bileşen: DESIGN.md'nin "Yapma" listesinde açık bir madde var —
 * "Placeholder metni etiket yerine kullanma (odaklanınca kaybolur)". Bu kural
 * her form ekranında elle hatırlanmak zorunda kalırsa er geç unutulur
 * (Anayasa XI). Üç şey burada birlikte yaşar ve birbirinden ayrışamaz:
 *
 *   1. görünür `<label>` ve `htmlFor` ↔ `id` eşleşmesi,
 *   2. hata/yardım metninin `aria-describedby` ile girdiye bağlanması,
 *   3. `aria-invalid`.
 *
 * `id` `useId` ile üretilir: aynı form iki kez render edilirse (ör. bir listede)
 * elle yazılmış sabit id'ler çakışır ve etiket yanlış girdiyi işaret eder.
 *
 * Kabuk (yükseklik, kenarlık, odak halkası) BURADA DEĞİL: girdinin kendisi
 * çağrı yerinden gelir (`components/ui.tsx` → `Input`, ya da ham `<select>`).
 * Böylece bileşen `<input>`, `<select>` ve `<textarea>` için aynı şekilde
 * çalışır ve ölçüler tek yerde (`ui.tsx`) kalır.
 *
 * Etiket boyu `text-sm` / `--fg-muted`: DESIGN.md §Typography "etiket"i
 * `text-sm` satırında, §Colors `--fg-muted`'i "ikincil metin, etiket" olarak
 * listeler.
 */

import { useId } from "react";
import type { ReactNode } from "react";

/** Girdiye olduğu gibi yayılacak erişilebilirlik özellikleri. */
export interface FieldControl {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
}

export function Field({
  label,
  describedBy,
  invalid = false,
  children,
}: {
  label: string;
  /**
   * Alanı açıklayan metnin id'si — yardım cümlesi, ya da formun altındaki hata
   * kutusu. Boşlukla ayırarak birden çok id verilebilir. Hata metni alanın
   * dışında yaşayabildiği için bileşen onu kendisi çizmez: aynı hata birden
   * çok alanı ilgilendirebilir (gönderim reddi) ve iki kez okunmamalıdır.
   */
  describedBy?: string;
  /**
   * Yalnız GİRİLEN DEĞER reddedildiyse true. Ağ kopması ya da sunucu hatası
   * girdinin suçu değildir; o durumda `aria-invalid` vermek ekran okuyucuya
   * "geçersiz giriş" dedirtir ve kullanıcı olmayan bir yazım hatası arar.
   */
  invalid?: boolean;
  children: (control: FieldControl) => ReactNode;
}) {
  const id = useId();

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm text-fg-muted">
        {label}
      </label>
      {children({
        id,
        "aria-describedby": describedBy,
        "aria-invalid": invalid ? true : undefined,
      })}
    </div>
  );
}
