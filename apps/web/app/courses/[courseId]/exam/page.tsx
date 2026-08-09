"use client";

/**
 * Sınav provası — TASARIM ÖNİZLEMESİ (backend'i tasks.md D fazında bağlanacak).
 *
 * DESIGN.md sınav kuralları burada gövde bulur:
 * - Sayaç sağ üstte, nötr; son 60 saniyede --warning'e döner. Yanıp sönme YOK.
 * - Soru metni text-lg; şıklar arasında bol boşluk (yanlış tıklama kaygı üretir).
 * - İlerleme "3/10" biçiminde sayısal; ilerleme çubuğu yok.
 * - Giriş animasyonu yok: sınav ekranı hareketsizdir.
 *
 * Sorular lib/preview-data.ts'teki havuzun ONAYLANMIŞ çoktan seçmeli
 * kısmından gelir; bu ekranın kendi soru listesi yoktur.
 *
 * Önizlemede ileri-geri gezinme YEREL çalışır. Etkin görünüp hiçbir şey
 * yapmayan buton çalışmayan bir ürün izlenimi verir; akış oynatılabilir, ama
 * cevaplar kaydedilmez ve süre sunucudan gelmez.
 */

import { useEffect, useId, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { PreviewBanner } from "@/components/page-state";
import { Button, EmptyState } from "@/components/ui";
import { EXAM_PREVIEW_QUESTIONS } from "@/lib/preview-data";

const TOTAL_QUESTIONS = EXAM_PREVIEW_QUESTIONS.length;
const EXAM_SECONDS = 12 * 60;

/**
 * Süre duyuruları — eşikler ARTAN sırada; ilk eşleşen kazanır.
 *
 * Sayaç saniyede bir değişir ama duyurusu değişmez: iki eşik arasında metin
 * aynı kaldığı için canlı bölge yeniden okunmaz. Böylece ekran okuyucu kullanan
 * öğrenci 12 dakika boyunca 720 duyuru yerine dört duyuru duyar.
 */
const TIME_NOTICES = [
  { at: 0, text: "Süre doldu." },
  { at: 30, text: "30 saniye kaldı." },
  { at: 60, text: "1 dakika kaldı." },
  { at: 300, text: "5 dakika kaldı." },
] as const;

function timeNotice(remaining: number): string {
  return TIME_NOTICES.find((notice) => remaining <= notice.at)?.text ?? "";
}

export default function ExamPreviewPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const [remaining, setRemaining] = useState(EXAM_SECONDS);
  const [index, setIndex] = useState(0);
  // Soru başına seçim: geri dönüldüğünde önceki cevap yerinde durmalı.
  const [answers, setAnswers] = useState<Record<number, number>>({});

  const progressId = useId();
  const hintId = useId();
  const questionRef = useRef<HTMLHeadingElement>(null);
  const focusedIndex = useRef(index);

  const expired = remaining === 0;

  // Önizleme sayacı: gerçek sınavda kalan süre sunucudan gelir; istemci
  // saatine güvenilmez (mod politikaları backend'de). Süre bitince aralık
  // durdurulur — boşa dönen zamanlayıcı da gereksiz iştir (Anayasa XI).
  // Süre dolunca sınavın kapanması sunucunun işidir; önizleme yalnız
  // sayacı durdurur ve durumu duyurur.
  useEffect(() => {
    if (expired) return;
    const timer = setInterval(
      () => setRemaining((s) => Math.max(0, s - 1)),
      1000,
    );
    return () => clearInterval(timer);
  }, [expired]);

  /*
   * Soru değişince odak yeni soru metnine taşınır. Taşınmazsa odak "Sonraki
   * soru" düğmesinde kalır ve klavyeyle çalışan öğrenci ekranda ne değiştiğini
   * hiç duymaz; sayfanın tepesindeki metin sessizce başkalaşır.
   *
   * Karşılaştırma bayrakla değil son odaklanan soruyla yapılır: "ilk render mı"
   * bayrağı StrictMode'un efekti iki kez koşturduğu geliştirme ortamında sayfa
   * açılışında odağı çalardı.
   */
  useEffect(() => {
    if (focusedIndex.current === index) return;
    focusedIndex.current = index;
    questionRef.current?.focus();
  }, [index]);

  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const lastMinute = remaining <= 60;

  const selected = answers[index] ?? null;
  const isLast = index === TOTAL_QUESTIONS - 1;

  /*
   * Havuzda onaylanmış çoktan seçmeli soru yoksa sınav kurulamaz. Ölü dal
   * değil: sorular soru havuzundaki onay durumundan türüyor, yani liste
   * boşalabilir. Boşken çökmek yerine ne yapılacağını söyler (DESIGN.md
   * §Boş durumlar) — ve bu bir arıza olmadığı için kırmızı/uyarı yoktur.
   */
  if (TOTAL_QUESTIONS === 0) {
    return (
      <AppShell>
        <CourseNav courseId={courseId} />
        <PreviewBanner>
          sınav önizlemesi soru havuzundaki onaylanmış çoktan seçmeli
          sorulardan kurulur. Sınav motoru D fazında bağlanacak.
        </PreviewBanner>
        <EmptyState title="Sınav için onaylanmış çoktan seçmeli soru yok. Soru havuzundan en az bir soruyu onaylayın." />
      </AppShell>
    );
  }

  const question = EXAM_PREVIEW_QUESTIONS[index];

  return (
    <AppShell>
      <CourseNav courseId={courseId} />

      <PreviewBanner>
        sorular örnek veridir ve cevaplar kaydedilmez. Sınav motoru geliştirme
        planının D fazında bağlanacak.
      </PreviewBanner>

      <div className="mx-auto max-w-2xl">
        {/* Üst şerit: ilerleme + sayaç */}
        <div className="mb-8 flex items-center justify-between text-sm">
          <span id={progressId} className="text-fg-muted">
            Soru{" "}
            <span className="font-medium text-fg">
              {index + 1}/{TOTAL_QUESTIONS}
            </span>
          </span>
          {/*
            `role="timer"` örtük olarak aria-live="off" taşır: sayaç görsel
            olarak saniyede güncellenir ama kendiliğinden okunmaz. Burada
            aria-live="polite" vardı ve ekran okuyucu her saniye tüm satırı
            yeniden basıyordu — sınavı yapılamaz hale getiriyordu. Anlamlı
            duyuru aşağıdaki eşik bölgesinden gelir.
          */}
          <span
            role="timer"
            className={`font-mono tabular-nums ${
              lastMinute ? "font-medium text-warning" : "text-fg-muted"
            }`}
          >
            <span className="sr-only">Kalan süre </span>
            {minutes}:{String(seconds).padStart(2, "0")}
          </span>
        </div>

        {/* Yalnız eşiklerde konuşur; metin değişmediği sürece yeniden okunmaz. */}
        <p role="status" className="sr-only">
          {timeNotice(remaining)}
        </p>

        <h1
          ref={questionRef}
          tabIndex={-1}
          aria-describedby={progressId}
          className="prose-tr rounded-lg text-lg leading-7 font-medium text-fg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"
        >
          {question.stem}
        </h1>

        <fieldset className="mt-8 space-y-4">
          <legend className="sr-only">Cevap şıkları</legend>
          {question.options.map((option, optionIndex) => {
            const active = selected === optionIndex;
            return (
              <label
                key={option}
                className={`flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors ${
                  active
                    ? "border-brand bg-brand-subtle"
                    : "border-border bg-surface hover:border-border-strong"
                }`}
              >
                <input
                  type="radio"
                  name={`answer-${index}`}
                  checked={active}
                  onChange={() =>
                    setAnswers((prev) => ({ ...prev, [index]: optionIndex }))
                  }
                  className="mt-1 h-4 w-4 accent-brand"
                />
                <span className="prose-tr text-sm leading-6 text-fg">{option}</span>
              </label>
            );
          })}
        </fieldset>

        {/*
          Gezinme düğmeleri `disabled` yerine `aria-disabled` kullanır: tarayıcı
          devre dışı bırakılan öğeden odağı <body>'ye atar, yani "Önceki"ye
          basıp ilk soruya dönen klavye kullanıcısı odağını kaybederdi. Button
          aria-disabled'ta tıklamayı zaten yutar (components/ui.tsx).
        */}
        <div className="mt-10 flex items-center justify-between gap-4">
          <Button
            variant="secondary"
            aria-disabled={index === 0}
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
          >
            Önceki
          </Button>
          {isLast ? (
            /*
              Son soruda "Son soru" yazan ölü bir düğme vardı: etiketi bir eylem
              vaat ediyor, tıklaması hiçbir şey yapmıyordu. Sınavı bitirme akışı
              motorla birlikte gelecek; o zamana kadar burada düğme değil bilgi
              durur (Anayasa XI).
            */
            <p className="text-sm text-fg-muted">Bu önizlemenin son sorusu.</p>
          ) : (
            <Button
              aria-disabled={selected === null}
              aria-describedby={selected === null ? hintId : undefined}
              onClick={() =>
                setIndex((i) => Math.min(TOTAL_QUESTIONS - 1, i + 1))
              }
            >
              Sonraki soru
            </Button>
          )}
        </div>

        {selected === null && !isLast && (
          <p id={hintId} className="mt-3 text-right text-xs text-fg-subtle">
            Devam etmek için bir şık seçin.
          </p>
        )}

        <p className="mt-6 text-center text-xs text-fg-subtle">
          Sınav modunda ipucu kapalıdır ve her soruya tek deneme hakkı vardır;
          geri bildirim sınav bitiminde verilir.
        </p>
      </div>
    </AppShell>
  );
}
