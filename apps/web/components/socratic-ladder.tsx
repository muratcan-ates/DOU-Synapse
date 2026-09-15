/**
 * Sokratik ipucu merdiveni (DESIGN.md §Components).
 *
 * Kademe göstergesi ilerleme çubuğu DEĞİL, ayrık noktalardır: "beş adımda biter"
 * hissi düşünmeyi hızlandırma baskısı yaratır. Verilen ipuçları silinmez, üst
 * üste birikir; öğrenci nereden geldiğini görür. Doğrudan cevap butonu yoktur.
 *
 * Kademeler sözleşmedeki `SocraticStage` enum'undan gelir (beş kademe, ilki
 * `diagnose`). Daha önce burada 0-3 arası bir sayı vardı; sunucunun beşinci
 * kademesi ekranda hiç görünmüyordu.
 */

import type { ReactNode } from "react";
import { demoResponseText } from "@/lib/demo-response";
import { DemoResponseNotice } from "@/components/demo-response-notice";
import { SOCRATIC_STAGES, stageIndex, stageLabel, type LadderRung } from "@/lib/chat";

export function SocraticLadder({
  rungs,
  footerForRung,
}: {
  rungs: LadderRung[];
  footerForRung?: (rung: LadderRung) => ReactNode;
}) {
  const reached = rungs.reduce((max, rung) => Math.max(max, stageIndex(rung.stage)), -1);
  const current = rungs.length > 0 ? rungs[rungs.length - 1] : null;

  return (
    <div className="overflow-hidden rounded-[20px] border border-border bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-sunken px-5 py-4">
        <span className="text-base font-semibold text-fg">Sokratik mod</span>
        <div className="flex items-center gap-2">
          {/*
            Kademe adı METİN olarak da duruyor: gösterge bilgiyi yalnız renkle
            taşımamalı. Noktalar bu metnin görsel yankısı olduğu için ekran
            okuyucudan gizlendi — iki kez okunması bilgi katmaz.
          */}
          <span className="text-sm text-fg-muted">{stageLabel(current?.stage ?? null)}</span>
          <span className="flex items-center gap-2" aria-hidden="true">
            {SOCRATIC_STAGES.map((stage, index) => (
              <span
                key={stage}
                className={`h-2 w-2 rounded-full ${
                  index <= reached ? "bg-fg" : "bg-border-strong"
                }`}
              />
            ))}
          </span>
        </div>
      </div>

      <ol className="divide-y divide-border">
        {rungs.map((rung) => (
          <li key={rung.id} className="px-5 py-6">
            {rung.attempt !== null && (
              <p className="prose-tr mb-3 border-l-2 border-border-strong pl-3 text-sm text-fg-subtle">
                Denemen: {rung.attempt}
              </p>
            )}
            <p className="text-sm font-medium text-fg-subtle">{stageLabel(rung.stage)}</p>
            {rung.fixture === true && (
              <div className="mt-2"><DemoResponseNotice fixture={rung.fixture} /></div>
            )}
            <p className="prose-tr mt-3 text-base whitespace-pre-line leading-7 text-fg">
              {demoResponseText(rung.text, rung.fixture)}
            </p>
            {/* Kaynak konumu her ipucunda görünür (Anayasa I). */}
            <p className="mt-4 break-words text-sm text-fg-subtle">
              {rung.source.fileName} · {rung.source.location}
            </p>
            {footerForRung?.(rung)}
          </li>
        ))}
      </ol>

      <p className="border-t border-border px-5 py-3 text-sm text-fg-subtle">
        Cevabı doğrudan vermek yerine adım adım yaklaştırır; bir sonraki ipucu
        için önce kendi denemenizi yazın.
      </p>
    </div>
  );
}
