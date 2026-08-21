"use client";

/**
 * Ders içi sekme navigasyonu.
 * Aktif sekme kırmızı alt çizgiyle işaretlenir — kırmızının üç meşru kullanımından
 * biri (DESIGN.md: aktif navigasyon göstergesi).
 *
 * Rol doğrudan `localStorage`'dan değil `useSession()`'dan okunur: depo okuması
 * tek yerde yaşar (Anayasa XI) ve render gövdesinde sunucuda var olmayan bir
 * API'ye dokunulmaz.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useChatAvailability, type ChatLock } from "@/lib/chat-availability";
import { useSession } from "@/lib/session";

const TABS = [
  { slug: "", label: "Materyaller" },
  // `locksWithAssistant`: yürüyen sınav oturumu bu sekmeyi kapatır. Bayrak
  // `instructorOnly`'nin simetriği — hangi sekmenin neye bağlı olduğu tabloda
  // görünür kalsın diye koşul bileşen gövdesine yazılmadı.
  { slug: "/chat", label: "Asistan", locksWithAssistant: true },
  { slug: "/exam", label: "Sınav provası" },
  { slug: "/questions", label: "Soru havuzu", instructorOnly: true },
  { slug: "/blueprints", label: "Sınav blueprint'i", instructorOnly: true },
  { slug: "/settings", label: "AI politikası", instructorOnly: true },
  { slug: "/analytics", label: "İlerleme" },
  { slug: "/members", label: "Katılımcılar", instructorOnly: true },
];

/**
 * `lock` verilirse şerit kendi yoklamasını YAPMAZ.
 *
 * Sohbet ekranı kilidi zaten okumak zorunda (besteciyi çizip çizmeyeceğine
 * karar veriyor). İkisi de kendi kancasını çağırınca aynı uç sayfa başına iki
 * kez çağrılıyordu — Anayasa XI bunu açıkça kusur sayıyor ("aynı veriyi iki kez
 * çekme"). Kilidi zaten elinde olan çağıran onu aşağı verir; vermeyen sayfalar
 * (materyaller, sınav, ilerleme) kendi yoklamasını yapmaya devam eder, çünkü
 * kilit rozeti her sekmede görünmeli.
 */
export function CourseNav({ courseId, lock: providedLock }: { courseId: string; lock?: ChatLock }) {
  const pathname = usePathname();
  const { isInstructor, ready } = useSession(courseId);
  /*
   * Kilit kararı sunucudan okunur, burada hesaplanmaz. Sekmeyi gizlemek yerine
   * kilitli çizmek bilinçli: gizlenen sekme "sistem bozuldu" gibi okunur,
   * kilitli sekme sebebini söyler. Ayrıca gizleme bir yetki değildir — asıl
   * kapı sunucudadır ve bu yüzey yalnız kullanıcıyı duvara koşturmamak için var.
   */
  const ownLock = useChatAvailability(providedLock ? null : courseId);
  const lock = providedLock ?? ownLock;
  const base = `/courses/${courseId}`;

  return (
    /*
     * `ready` false iken rol bilinmiyor. Üç seçenekten ikisi kötü:
     *   - eğitmen sekmelerini eksik çizip sonradan ARAYA eklemek, halihazırda
     *     görünen sekmeleri yana kaydırır (tıklamak üzere olan hedef kayar);
     *   - hepsini çizip öğrenciden geri almak rolü sızdırır ve belirsizlikte
     *     kapanma kuralını çiğner (Anayasa IV).
     * Bu yüzden şerit `visibility: hidden` ile çizilir: yükseklik ve alt çizgi
     * yerinde kalır, altındaki içerik zıplamaz, sekmeler tek seferde belirir ve
     * görünürken hiçbir öğe yer değiştirmez. `display: none` bunu yapamaz —
     * şerit tamamen kalkar, sayfa dikey olarak zıplar.
     */
    <nav
      className={`mb-8 flex gap-1 overflow-x-auto border-b border-border ${
        ready ? "" : "invisible"
      }`}
      aria-label={lock.locked ? lock.message ?? undefined : undefined}
    >
      {TABS.filter((tab) => !tab.instructorOnly || isInstructor).map((tab) => {
        const href = `${base}${tab.slug}`;
        const active = pathname === href;
        const locked = Boolean(tab.locksWithAssistant) && lock.locked;
        if (locked) {
          /*
           * Kilitli sekme `Link` değil: tıklanabilir bırakılsaydı kullanıcı
           * boş bir ekrana giderdi. Durum renkle değil METİNLE işaretlenir —
           * renk tek başına bilgi taşımaz (Anayasa VII).
           */
          return (
            <span
              key={tab.slug}
              aria-disabled="true"
              title={lock.message ?? undefined}
              className="-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-4 py-3 text-sm text-fg-subtle"
            >
              {tab.label}
              <span className="rounded-sm border border-border px-1.5 py-0.5 text-xs text-fg-muted">
                Kilitli
              </span>
            </span>
          );
        }
        return (
          /*
           * Odak halkası negatif offset ile öğenin İÇİNE çizilir: şerit
           * `overflow-x-auto` olduğu için dışarı taşan halkanın üst ve alt
           * kenarı kırpılıyordu, klavyeyle gezen kullanıcı nerede olduğunu
           * göremiyordu. `py-3` dokunma hedefini 44px'e çıkarır
           * (DESIGN.md §Responsive Behavior).
           */
          <Link
            key={tab.slug}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`-mb-px flex items-center whitespace-nowrap border-b-2 px-4 py-3 text-sm transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
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
