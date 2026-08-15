"use client";

/**
 * Asistanın açık olup olmadığı — tek kaynak.
 *
 * Kararı sunucu verir. Arayüz "öğrencinin sınavı var mı" sorusunu KENDİ
 * hesaplamaz: hesaplasaydı aynı kural iki yerde yaşardı ve ikisi ayrıştığında
 * sapma sessiz olurdu — sekme açık görünüp istek 403 dönerdi (Anayasa XI).
 *
 * Kilit metni de sunucudan gelir; arayüz kendi metnini uydurmaz (Anayasa V,
 * `lib/errors.ts` ile aynı kural).
 *
 * Yoklama yalnız KİLİTLİYKEN koşar (`pollWhile`). Kilit kalkınca kendiliğinden
 * durur — durdurulmayan polling bir kusurdur (Anayasa XI). Aralık 30 saniye:
 * sınav bitişi saniyelik hassasiyet istemez ve kilitli öğrenci zaten sınav
 * sekmesinde çalışıyor.
 */

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { allowedChatUiModes } from "@/lib/course-assistant";
import { useResource } from "@/lib/use-resource";
import type { ErrorKind } from "@/lib/errors";
import type { ChatAgentProfile, ChatAudience, ChatAvailability } from "@/lib/types";
import type { ChatUiMode } from "@/lib/chat";

const POLL_INTERVAL_MS = 30_000;

/**
 * Kilidi okuyan yüzeyler. `examStateChanged()` hepsini yeniden sordurur.
 *
 * Neden gerekli: `pollWhile` yalnız KİLİTLİYKEN yokluyor ve bu doğru — kilit
 * kalkınca polling kendiliğinden dursun diye. Ama o kural, izlenmesi gereken
 * kenarı ters seçiyor: açık → kilitli geçişini hiçbir şey izlemiyordu. Öğrenci
 * sınavı başlattığında bulunduğu sekmedeki "Asistan" sekmesi açık kalıyor,
 * kilit ancak yeni bir mount'ta (yeni sekme, yenileme) görünüyordu. Sunucu her
 * yolu zaten reddediyordu, yani güvenlik açığı değil; ama etkin görünüp iş
 * yapmayan bir yüzey kusurdur (Anayasa XI).
 *
 * Çözüm sürekli yoklama DEĞİL: kilit yalnız öğrencinin kendi eylemiyle değişir
 * (sınavı o başlatır, o bitirir), dolayısıyla haber verilebilir bir olaydır.
 * Herkesi her sayfada sonsuza kadar yoklatmak, bilinen bir olayı tahmin etmeye
 * çalışmak olurdu.
 */
const subscribers = new Set<() => void>();

/** Sınav başladı ya da bitti: kilidi okuyan her yüzey sunucuya yeniden sorsun. */
export function examStateChanged(): void {
  for (const notify of [...subscribers]) notify();
}

export interface ChatLock {
  /** Sunucu "kapalı" demedikçe açık kabul edilir. */
  locked: boolean;
  /** Kilit sebebi, sunucudan. Kilit yoksa null. */
  message: string | null;
  /** İlk yanıt gelene kadar false — "kilitli değil" ile karıştırılmamalı. */
  ready: boolean;
  /** Üyelikten sunucunun türettiği hedef kitle; null iken persona çizilmez. */
  audience: ChatAudience | null;
  /** Kullanıcının seçebileceği bir alan değildir. */
  agentProfile: ChatAgentProfile | null;
  /** `exam` filtrelenir; sohbet bestecisi yalnız bu iki modu tanır. */
  allowedModes: ChatUiMode[];
  /** Sokratik yönlendirmenin sunucu politikasındaki üst sınırı. */
  hintLimit: number;
  /** İlk availability isteği başarısızsa ekranı kapatan, sunucudan gelen hata. */
  error: string | null;
  /** Sağlam availability ekrandayken sonraki yoklamanın geçici hatası. */
  refreshError: string | null;
  /** Hatanın yeniden denenebilir olup olmadığını belirleyen sınıf. */
  errorKind: ErrorKind | null;
  /** Sunucunun destek kaydını bulmak için verdiği istek kimliği. */
  errorRequestId: string | null;
  /** Availability kararını aynı ders için yeniden ister. */
  reload: () => Promise<void>;
}

interface ChatAvailabilityFailure {
  error?: string | null;
  refreshError?: string | null;
  errorKind?: ErrorKind | null;
  errorRequestId?: string | null;
  reload?: () => Promise<void>;
}

const NOOP_RELOAD = async (): Promise<void> => {};

/**
 * `courseId` null verilirse yoklama YAPILMAZ ve persona bilinmiyor döner.
 *
 * Kancalar koşullu çağrılamaz, ama iş koşullu yapılabilir: kilidi zaten
 * dışarıdan alan bir çağıran (bkz. `CourseNav`) aynı ucu ikinci kez çağırmasın
 * diye kapı burada. Kancanın kendisi her render'da aynı sırada çalışır.
 */
export function useChatAvailability(courseId: string | null): ChatLock {
  const requestedCourse = useRef<string | null>(null);
  const requestedExamEpoch = useRef<number | null>(null);
  const [examEpoch, setExamEpoch] = useState(0);
  const resource = useResource<ChatAvailability | null>(
    () => {
      requestedCourse.current = courseId;
      requestedExamEpoch.current = examEpoch;
      return courseId === null
        ? Promise.resolve(null)
        : api.get<ChatAvailability>(`/courses/${courseId}/chat/availability`);
    },
    [courseId, examEpoch],
    {
      pollWhile: (state) => state !== null && !state.available,
      intervalMs: POLL_INTERVAL_MS,
    },
  );

  /*
   * Sınav olayı yalnız yeniden istek açmaz; önce epoch'u değiştirir. Böylece
   * olay ile ağ cevabı arasındaki render'da eski `available=true` kararı
   * kullanılamaz. Sunucuya ulaşılamazsa besteci eski kararla açık kalmak yerine
   * gerçek hata ve yeniden deneme yolunu gösterir.
   */
  useEffect(() => {
    const invalidateForExamTransition = () => setExamEpoch((current) => current + 1);
    subscribers.add(invalidateForExamTransition);
    return () => {
      subscribers.delete(invalidateForExamTransition);
    };
  }, []);

  /*
   * `useResource` bağımlılık değişimini effect içinde sıfırlar. Açma tıklaması
   * ile o effect arasındaki tek render'da önceki `null` sonucu hâlâ elde olur;
   * onu "istek bitti" diye okumak paneli bir an doğrulanmamış persona ile
   * çizerdi. İstenen ders gerçekten fetcher'a ulaşmadan sonuç kullanılmaz.
   */
  if (
    courseId === null ||
    !isAvailabilitySnapshotCurrent(
      requestedCourse.current,
      courseId,
      requestedExamEpoch.current,
      examEpoch,
    )
  ) {
    return toChatLock(null, false);
  }
  return toChatLock(resource.data, !resource.loading, {
    error: resource.error,
    refreshError: resource.refreshError,
    errorKind: resource.errorKind,
    errorRequestId: resource.errorRequestId,
    reload: resource.reload,
  });
}

/** Eski ders ya da sınav epoch'una ait cevap persona/kilit kararı veremez. */
export function isAvailabilitySnapshotCurrent(
  requestedCourse: string | null,
  courseId: string,
  requestedExamEpoch: number | null,
  examEpoch: number,
): boolean {
  return requestedCourse === courseId && requestedExamEpoch === examEpoch;
}

/**
 * Saf karar — testin ölçtüğü yer.
 *
 * Yoklama başarısız olursa (`data === null`) sekme KİLİTLENMEZ; bunun yerine
 * hata sınıfı, destek kodu ve yeniden yükleme eylemi aynen çağırana taşınır.
 * Böylece ağ arızası "profil doğrulanamadı" diye yanlış anlatılmaz ve kullanıcı
 * sayfayı bütünüyle yenilemeden tekrar deneyebilir. Asıl yetki kapısı yine
 * sunucudadır; istemci hata anında rol ya da sınav durumu tahmin etmez.
 */
export function toChatLock(
  data: ChatAvailability | null,
  settled: boolean,
  failure: ChatAvailabilityFailure = {},
): ChatLock {
  const recovery = {
    error: failure.error ?? null,
    refreshError: failure.refreshError ?? null,
    errorKind: failure.errorKind ?? null,
    errorRequestId: failure.errorRequestId ?? null,
    reload: failure.reload ?? NOOP_RELOAD,
  };
  if (data === null) {
    return {
      locked: false,
      message: null,
      ready: settled,
      audience: null,
      agentProfile: null,
      allowedModes: [],
      hintLimit: 0,
      ...recovery,
    };
  }
  return {
    locked: !data.available,
    message: data.available ? null : (data.message ?? null),
    ready: true,
    audience: data.audience,
    agentProfile: data.agent_profile,
    allowedModes: allowedChatUiModes(data.allowed_modes),
    hintLimit: data.hint_limit,
    ...recovery,
  };
}
