/**
 * Hata çözümleme — tek yer.
 *
 * `e instanceof ApiError ? e.message : "..."` yedi ayrı dosyada tekrarlanıyordu
 * ve her birinde farklı bir yedek metin vardı. Kural şudur: backend zaten
 * anlaşılır Türkçe üretir (app/core/errors.py), arayüz kendi hata metnini
 * UYDURMAZ — yalnız backend susarsa nötr bir cümle koyar.
 *
 * 002'de buraya ikinci bir iş eklendi (T403): metnin yanına hatanın SINIFI.
 * Eskiden `errorMessage` `status` ve `code`'u atıyordu, yani ağ kopması,
 * 503, 500 ve 404 çağrı yerine tek ve aynı biçimde — düz bir dize olarak —
 * ulaşıyordu. Ekran o dizeye bakıp "tekrar dene" gösterip göstermeyeceğine
 * karar veremezdi; karar geliştiricinin `onRetry` geçirmeyi hatırlamasına
 * kalmıştı ve hatırlanmadığı yerler ölçüldü (aşağıdaki `describeError`
 * docstring'i).
 */

import { ApiError, classifyApiError, type ErrorKind } from "@/lib/api";

/**
 * Sınıf vokabüleri `api.ts`'te tanımlı (`ApiError`'ın `status`/`code` alanlarının
 * sahibi orası ve `request()` aynı kuralı yeniden deneme için kullanıyor).
 * Buradan yeniden ihraç ediliyor ki arayüz tarafı tek modül tanısın.
 */
export type { ErrorKind };

export interface ErrorInfo {
  /** Kullanıcıya gösterilecek cümle. Backend verdiyse onunki. */
  message: string;
  /** Kararın dayanağı: tekrar denenebilir mi, giriş mi gerekiyor. */
  kind: ErrorKind;
  /**
   * Destek kodu (T406). `null` ise sunucuya HİÇ VARILAMADI — sunucudan dönen
   * her hata zarfı kimlik taşıyor (`app/core/errors.py::ErrorDetail`), yani
   * boşluk "sunucu vermedi" değil "ortada istek kaydı yok" demek.
   */
  requestId: string | null;
}

export function errorMessage(e: unknown, fallback = "Bağlantı kurulamadı."): string {
  if (e instanceof ApiError) return e.message;
  return fallback;
}

/**
 * Hatanın sınıfı (T403).
 *
 * `ApiError` olmayan her şey `transient`: oraya yalnız `fetch`in kendisi
 * düşerse gelinir (ağ kopması, DNS, kapalı sekme). Sunucu bir şey söyleyebilmiş
 * olsaydı `ApiError` olurdu. Sunucuya varılamamış bir istek yeniden
 * denenebilir; kalıcı saymak, kablosu bir saniye kopan kullanıcıya "bu iş
 * olmayacak" demek olurdu.
 */
export function classifyError(e: unknown): ErrorKind {
  if (!(e instanceof ApiError)) return "transient";
  return classifyApiError(e.status, e.code);
}

/**
 * "Tekrar dene" düğmesi çıkmalı mı (FR-153)?
 *
 * Karar bileşenin içinde bir `&&` zinciri olarak DURMUYOR, çünkü orada yalnız
 * tarayıcıda ve yalnız doğru hata sınıfı denk geldiğinde gözlenebilirdi. Saf
 * fonksiyon olarak `bun test lib/` bunu doğrudan okuyabiliyor; aynı gerekçe
 * `use-resource.ts`'in üç çekirdeğinde de yazılı.
 *
 * İki koşul birlikte: eylem gerçekten var mı (çalışmayan düğme kusurdur,
 * Anayasa XI) ve hata yeniden denemeye değer mi. Sınıf verilmemişse
 * ("sınıflandırılmadı") eski davranış korunur; sınıf yokluğunu "kalıcı"
 * saymak, hâlâ çalışan düğmeleri sessizce kaldırırdı.
 */
export function shouldOfferRetry(
  kind: ErrorKind | null | undefined,
  hasRetryHandler: boolean,
): boolean {
  if (!hasRetryHandler) return false;
  if (kind == null) return true;
  return kind === "transient";
}

/**
 * Metin + sınıf + destek kodu, tek geçişte.
 *
 * Neden üçü birlikte: ekranın bir hata için sorduğu üç sorunun cevabı bunlar ve
 * ayrı ayrı hesaplandıklarında ayrışıyorlar. Bugün ölçülen ayrışma:
 * `app/courses/page.tsx:59` 404'te bile "Tekrar dene" gösteriyor (düğme çalışır
 * ama sonuç değişmez), `chat/page.tsx:302` ise ağ hatasında düğmeyi HİÇ
 * göstermiyor (kullanıcının tek çıkışı sayfayı yenilemek). İki ekran, iki ayrı
 * yanlış, aynı sebep: kararı taşıyan bir değer yoktu.
 */
export function describeError(e: unknown, fallback = "Bağlantı kurulamadı."): ErrorInfo {
  return {
    message: errorMessage(e, fallback),
    kind: classifyError(e),
    requestId: e instanceof ApiError ? e.requestId : null,
  };
}
