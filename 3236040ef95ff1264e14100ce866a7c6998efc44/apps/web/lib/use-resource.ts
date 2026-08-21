"use client";

/**
 * Veri çekme kancası — yükleniyor / hata / tazeleme üçlüsü tek yerde.
 *
 * Her sayfa aynı beş satırı tekrarlıyordu: iki state, bir useCallback, bir
 * useEffect ve aynı catch bloğu. Tekrarın maliyeti satır sayısı değil; bir
 * sayfanın hatayı temizlemeyi unutması ya da polling'i durdurmayı atlaması
 * gibi sessiz farklar. Tek kanca olunca o davranış her ekranda aynı.
 *
 * `pollWhile` opsiyonu: veri "hâlâ değişiyor" olduğu sürece kısa aralıkla
 * tazeler, koşul düşünce durur. Materyal işlenirken canlı durum rozetleri
 * bunun üzerine kurulu.
 *
 * Kancanın üç kuralı saf fonksiyonlara çıkarıldı (`createRequestGate`,
 * `resourceReducer` ve `isFirstLoadSettled`): DOM'suz koşan
 * `use-resource.test.ts` bunları doğrudan sınıyor. React'ın içinde kalsalardı
 * üçü de yalnız tarayıcıda, yalnız şanslı zamanlamada gözlenebilirdi — yani
 * pratikte hiç.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "@/lib/errors";

/* -------------------------------------------------------------------------
 * Saf çekirdek 1: istek sıra kapısı
 * ---------------------------------------------------------------------- */

/**
 * "Yalnız en son başlayan istek yazar" kapısı.
 *
 * Neden gerekli: `reload()` çağrıları üst üste binebiliyor — elle tazeleme,
 * polling turu, `pulse` penceresi ve ders değişimi aynı anda uçabilir.
 * Cevapların başlama sırasıyla dönme garantisi YOKTUR. Ağ eski isteği geç
 * teslim ettiğinde, o eski cevap taze veriyi kalıcı olarak eziyordu: silinen
 * belge listeye geri geliyor, kullanıcı sayfayı elle yenileyene kadar da
 * orada kalıyordu. Eski kod bunu sökülme (unmount) sorunu sanıp `cancelled`
 * bayrağı koymuştu; bayrak `setData`'yı hiç korumadığı için hiçbir şey
 * yapmıyordu.
 *
 * Kapı yalnız iki sayı tutar; yarış çözümü zamanlayıcıya değil sıraya bağlı.
 */
export interface RequestGate {
  /** Yeni istek başlatır ve ona bir kimlik verir. */
  begin(): number;
  /** Bu kimlik hâlâ en son başlatılan istek mi? Değilse yazma yapılmaz. */
  isCurrent(token: number): boolean;
  /** Uçuştaki tüm istekleri geçersizler (deps değişimi, sökülme). */
  invalidate(): void;
}

export function createRequestGate(): RequestGate {
  let latest = 0;
  return {
    begin: () => (latest += 1),
    isCurrent: (token) => token === latest,
    invalidate: () => {
      latest += 1;
    },
  };
}

/* -------------------------------------------------------------------------
 * Saf çekirdek 2: durum makinesi
 * ---------------------------------------------------------------------- */

export interface ResourceState<T> {
  data: T | null;
  error: string | null;
  refreshError: string | null;
}

export type ResourceAction<T> =
  | { type: "reset" }
  | { type: "loaded"; data: T }
  | { type: "failed"; message: string };

export const EMPTY_RESOURCE_STATE: ResourceState<never> = {
  data: null,
  error: null,
  refreshError: null,
};

/**
 * Tek kural: elde gösterilecek sağlam veri varken hata onu SİLMEZ.
 *
 * Eskiden tazeleme sırasındaki tek bir geçici hata (kilitli ekran, uyanan
 * dizüstü, bir saniyelik kopma) `error`'ı doldurup sayfaları erken döndürüyordu:
 * başlık, sekmeler, liste — hepsi gidiyordu ve geri dönüş yolu yoktu, çünkü
 * ekranda artık hiçbir düğme kalmıyordu. Polling saniyede bir koştuğu için bu
 * "nadir" değil, sıradan bir olaydı.
 *
 * Bu yüzden hata iki yere ayrıldı: `error` ekranı kapatan (elde veri yokken
 * oluşan) hatadır, `refreshError` ise veri dururken başarısız olan tazelemedir.
 * `refreshError` satır içinde gösterilir, sayfa yerinde kalır.
 */
export function resourceReducer<T>(
  state: ResourceState<T>,
  action: ResourceAction<T>,
): ResourceState<T> {
  switch (action.type) {
    case "reset":
      return settle(state, null, null, null);
    case "loaded":
      // Başarılı tur her iki hatayı da temizler: ekranda eskimiş uyarı kalmaz.
      return settle(state, action.data, null, null);
    case "failed":
      return state.data === null
        ? settle(state, null, action.message, null)
        : settle(state, state.data, null, action.message);
  }
}

/**
 * Saf çekirdek 3: "ilk tur bitti mi?" kuralı.
 *
 * `loading` eskiden `data === null && error === null` diye TÜRETİLİYORDU. Türev
 * iki varsayıma yaslanıyordu ve ikincisi doğru değil: (1) ilk tur bitince ya veri
 * ya hata olur, (2) veri asla `null` olamaz. Bir uç meşru olarak JSON `null`
 * döndürürse — "aktif sınav oturumu yok", "henüz özet üretilmedi" gibi bir yokluk
 * cevabı — tur BAŞARIYLA biter ama iki alan da `null` kalır ve ekran sonsuza
 * kadar "Yükleniyor…" gösterir. Kullanıcı için fark yok: sistem donmuş görünür.
 *
 * Bayrak artık sonuca değil TURUN KENDİSİNE bakıyor: `reset` yeniden bekletir
 * (deps değişti, yeni dersin ilk turu başlıyor), `loaded` ve `failed` ise sonucu
 * ne olursa olsun ilk turu kapatır.
 *
 * Kural neden ayrı bir fonksiyon: `ResourceState`'e dördüncü alan eklemek
 * sözleşmeyi değiştirirdi (dokuz ekran ve mevcut testler o üç alanı biliyor).
 * Bayrak kancada ayrı tutuluyor ama kararı burada, tek satırda ve DOM'suz
 * sınanabilir biçimde veriliyor.
 */
export function isFirstLoadSettled(action: ResourceAction<unknown>): boolean {
  return action.type !== "reset";
}

/**
 * Üç alan da aynıysa ESKİ nesneyi döndür.
 *
 * React durumu `Object.is` ile karşılaştırır; her seferinde yeni nesne
 * dönersek hiçbir şey değişmese bile render tetiklenir. Bu iki yerde bedava
 * değil: her ekranın ilk `reset`i (kanca dokuz ekranda) ve saniyede bir koşan
 * polling'in aynı hatayı tekrar tekrar yazması.
 */
function settle<T>(
  state: ResourceState<T>,
  data: T | null,
  error: string | null,
  refreshError: string | null,
): ResourceState<T> {
  const same =
    state.data === data && state.error === error && state.refreshError === refreshError;
  return same ? state : { data, error, refreshError };
}

/* -------------------------------------------------------------------------
 * Kanca
 * ---------------------------------------------------------------------- */

export interface Resource<T> {
  data: T | null;
  /**
   * Ekranı kapatan hata: elde gösterilecek veri YOKKEN oluşmuştur.
   * `if (error) return <ErrorNote .../>` kalıbı bunu kullanır.
   */
  error: string | null;
  /**
   * Veri ekranda dururken başarısız olan tazeleme. Sayfa çizilmeye devam
   * eder; bu metin satır içinde, tercihen "Tekrar dene" ile gösterilir.
   */
  refreshError: string | null;
  /**
   * İlk yükleme tamamlanmadı. Anlamı değişmedi; yalnız ölçümü düzeldi —
   * eskiden `data`/`error` boşluğundan türetiliyordu, artık turun bitişinden
   * geliyor (bkz. `isFirstLoadSettled`). `null` dönen bir uç artık ekranı
   * "Yükleniyor…" hâlinde kilitlemez.
   */
  loading: boolean;
  /** Elle tazeleme — yazma işleminden sonra çağrılır. */
  reload: () => Promise<void>;
  /**
   * Yazma sonrası kısa süreli tazeleme penceresi açar.
   *
   * Neden gerekli (ölçülmüş): backend yükleme ucu `202` döndürüyor ama satır
   * yanıttan SONRA commit ediliyor — FastAPI `yield` bağımlılığını yanıt
   * üretildikten sonra kapatıyor. Ölçüm: POST'tan hemen sonraki GET 0 belge,
   * bir saniye sonraki GET 1 belge.
   *
   * Tek bir `reload()` bu yarışı kaybediyor. Daha kötüsü, normal polling
   * yalnız listede işlenen belge varken çalıştığı için BOŞ bir derse yapılan
   * ilk yükleme hiç görünmüyordu: kullanıcı dosyayı seçiyor, hiçbir şey
   * olmuyor, elle yenileyene kadar da olmuyor.
   */
  pulse: (durationMs?: number) => void;
}

export function useResource<T>(
  fetcher: () => Promise<T>,
  deps: readonly unknown[],
  options: { pollWhile?: (data: T) => boolean; intervalMs?: number } = {},
): Resource<T> {
  const [state, setState] = useState<ResourceState<T>>(EMPTY_RESOURCE_STATE);
  const [settled, setSettled] = useState(false);

  // Her eylem tek kapıdan geçer; bayrak ile durum böylece ayrışamaz. İkisini
  // ayrı ayrı güncelleyen bir çağrı yeri olsaydı, birini güncelleyip diğerini
  // unutan bir dal er geç yazılırdı (Anayasa XI).
  const dispatch = useCallback((action: ResourceAction<T>) => {
    setState((current) => resourceReducer(current, action));
    setSettled(isFirstLoadSettled(action));
  }, []);

  // Kapı kancanın ömrü boyunca tek: her render'da yenisi kurulursa geçmiş
  // istekleri hatırlayan kimse kalmaz.
  const gateRef = useRef<RequestGate | null>(null);
  if (gateRef.current === null) gateRef.current = createRequestGate();
  const gate = gateRef.current;

  // fetcher her render'da yeniden kurulur; kancayı bağımlılık döngüsüne
  // sokmamak için ref'te tutulur. Yenileme tetiği `deps`tir.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(async () => {
    const token = gate.begin();
    try {
      const next = await fetcherRef.current();
      // Geç dönen eski cevap taze veriyi ezmesin (bkz. RequestGate).
      if (!gate.isCurrent(token)) return;
      dispatch({ type: "loaded", data: next });
    } catch (e) {
      if (!gate.isCurrent(token)) return;
      dispatch({ type: "failed", message: errorMessage(e) });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    // Bağımlılık değişince eski veri ekranda kalmasın: yeni dersin listesi
    // gelene kadar öncekini göstermek yanlış derse bakıyormuş hissi verir.
    dispatch({ type: "reset" });
    void reload();
    // Sökülme ve deps değişimi: uçuştaki cevaplar artık hiçbir şey yazamaz.
    return () => gate.invalidate();
  }, [reload, dispatch, gate]);

  // Yazma sonrası kısa tazeleme penceresi (bkz. `pulse` docstring'i).
  const [pulsing, setPulsing] = useState(false);
  const pulseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pulse = useCallback((durationMs = 6000) => {
    setPulsing(true);
    if (pulseTimer.current) clearTimeout(pulseTimer.current);
    pulseTimer.current = setTimeout(() => setPulsing(false), durationMs);
  }, []);

  // Bileşen sökülürken zamanlayıcı kalmasın: sökülmüş bileşende setState uyarı üretir.
  useEffect(() => () => {
    if (pulseTimer.current) clearTimeout(pulseTimer.current);
  }, []);

  const { data, error, refreshError } = state;
  const { pollWhile, intervalMs = 2000 } = options;
  const activeByData = data !== null && pollWhile ? pollWhile(data) : false;
  const shouldPoll = activeByData || pulsing;

  useEffect(() => {
    if (!shouldPoll) return;
    const timer = setInterval(reload, intervalMs);
    return () => clearInterval(timer);
  }, [shouldPoll, intervalMs, reload]);

  return {
    data,
    error,
    refreshError,
    loading: !settled,
    reload,
    pulse,
  };
}
