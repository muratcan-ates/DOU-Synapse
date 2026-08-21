/**
 * Sokratik ipucu merdiveni (DESIGN.md §Components).
 *
 * Kademe göstergesi ilerleme çubuğu DEĞİL, ayrık noktalardır: "4 adımda biter"
 * hissi düşünmeyi hızlandırma baskısı yaratır. Verilen ipuçları silinmez, üst
 * üste birikir; öğrenci nereden geldiğini görür. Doğrudan cevap butonu yoktur.
 */

const STEPS = ["Yönlendirme", "Kavram ipucu", "Benzer örnek", "Kaynaklı açıklama"];

export interface SocraticHint {
  /** 0-3: NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE */
  level: number;
  text: string;
  source?: { fileName: string; location: string };
}

export function SocraticLadder({ hints }: { hints: SocraticHint[] }) {
  const reached = hints.length > 0 ? Math.max(...hints.map((h) => h.level)) : -1;

  return (
    <div className="rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <span className="text-sm font-medium text-fg">Sokratik mod</span>
        {/* Ayrık kademe noktaları */}
        <div className="flex items-center gap-2" aria-label="İpucu kademesi">
          {STEPS.map((step, index) => (
            <span
              key={step}
              title={step}
              className={`h-2 w-2 rounded-full transition-colors ${
                index <= reached ? "bg-brand" : "bg-border-strong"
              }`}
            />
          ))}
        </div>
      </div>

      <ol className="divide-y divide-border">
        {hints.map((hint) => (
          <li key={hint.level} className="px-5 py-4">
            <p className="text-xs font-medium text-fg-subtle">
              {STEPS[hint.level]}
            </p>
            <p className="prose-tr mt-1 text-sm leading-6 text-fg">{hint.text}</p>
            {hint.source && (
              <p className="mt-2 font-mono text-xs text-fg-subtle">
                {hint.source.fileName} · {hint.source.location}
              </p>
            )}
          </li>
        ))}
      </ol>

      <p className="border-t border-border px-5 py-3 text-xs text-fg-subtle">
        Cevabı doğrudan vermek yerine adım adım yaklaştırır; bir sonraki ipucu
        için önce kendi denemenizi yazın.
      </p>
    </div>
  );
}
