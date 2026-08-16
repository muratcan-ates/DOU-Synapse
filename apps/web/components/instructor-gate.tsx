"use client";

/**
 * Eğitmen render-kapısı — yedi sayfada elle tekrarlanan üçlü dalın tek sahibi
 * (settings, quality, sources, members, questions, analytics + blueprints
 * varyantı).
 *
 * Kapı yalnız ARAYÜZÜ şekillendirir; güvenlik kontrolü DEĞİLDİR. Yetki her
 * zaman sunucuda doğrulanır (Anayasa II): eğitmen uçları
 * `require_course_instructor`'dan geçer, öğrenci isteği burada hiçbir kapı
 * olmasa bile 403 döner. Kapının işi dürüstlük: öğrenciye çalışmayan bir
 * eğitmen formu göstermemek (Anayasa XI).
 *
 * `ready` gelmeden role dair hiçbir dala girilmez (Anayasa IV, fail-closed):
 * rol istemcide sonradan çözülür; o ana kadar "eğitmen değil" varsayımı
 * eğitmene bir kare boyunca yanlış ekran gösterirdi. İyimser varyant
 * (`optimistic`) bu kuralı bilerek gevşetir — yalnız içeriği iki role de
 * zararsız biçimde erken çizen sayfa için (bugün: blueprints).
 *
 * Eğitmen içeriği `children` olarak AYRI bileşende verilmelidir: `useResource`
 * mount olur olmaz istek atar; kapı isteği hiç başlatmamak için içeriği ancak
 * rol bilindiğinde mount eder. (JSX'te `children` ifadesinin kurulması yalnız
 * eleman nesnesi üretir; bileşen fonksiyonu kapı o dalı döndürmeden çalışmaz.)
 */

import type { ReactNode } from "react";
import { Loading } from "@/components/page-state";

/**
 * Kapının üç çıkışından hangisi? Saf tutulur ki karar DOM'suz `bun test lib/`
 * ile sınanabilsin (aynı gerekçe `use-resource.ts`'in çekirdeklerinde yazılı).
 */
export type InstructorGateOutcome = "loading" | "fallback" | "content";

export function instructorGateOutcome(
  ready: boolean,
  isInstructor: boolean,
  optimistic: boolean,
): InstructorGateOutcome {
  if (!ready) return optimistic ? "content" : "loading";
  return isInstructor ? "content" : "fallback";
}

export function InstructorGate({
  ready,
  isInstructor,
  fallback,
  optimistic = false,
  children,
}: {
  ready: boolean;
  isInstructor: boolean;
  /**
   * Rol çözüldü ve eğitmen değil: gösterilecek sakin yüzey (genelde
   * `EmptyState`). Kırmızı/uyarı yok — yetkisiz sayfaya adres çubuğundan
   * girmek bir arıza değil, yönlendirme konusudur (DESIGN.md). Fonksiyon
   * `children` kullanılıyorsa gerekmez (o ekran iki role de içerik çizer).
   */
  fallback?: ReactNode;
  /**
   * `true` ise rol çözülene kadar `Loading` yerine içerik çizilir (blueprints
   * varyantı: sayfa iskeleti iki role de zararsız, kapı yalnız rol
   * netleşince kapanır). Varsayılan fail-closed: önce `Loading`.
   */
  optimistic?: boolean;
  /**
   * Eğitmen içeriği. Fonksiyon verilirse rol çözüldüğünde `isInstructor` ile
   * çağrılır ve `fallback` hiç kullanılmaz — iki role birden hizmet eden ama
   * "ready beklenir" kuralını paylaşan ekran için (bugün: analytics).
   */
  children: ReactNode | ((isInstructor: boolean) => ReactNode);
}) {
  if (typeof children === "function") {
    return ready ? <>{children(isInstructor)}</> : <Loading />;
  }
  const outcome = instructorGateOutcome(ready, isInstructor, optimistic);
  if (outcome === "loading") return <Loading />;
  return <>{outcome === "content" ? children : fallback}</>;
}
