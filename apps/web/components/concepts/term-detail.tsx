"use client";

/** Seçili terim: materyaldeki alıntısı ve aynı pasajı paylaştığı terimler. */

import { neighboursOf, occurrenceLabel, sharedLabel, type ConceptMap, type ConceptTerm } from "@/lib/concepts";
import { toSourceInfo } from "@/lib/source";
import { sourceContextHref } from "@/lib/source-quality";
import { SourceCard } from "@/components/source-card";
import { Button, Card } from "@/components/ui";

export function TermDetail({ courseId, map, term, onSelect }: {
  courseId: string; map: ConceptMap; term: ConceptTerm; onSelect: (key: string) => void;
}) {
  const komsular = neighboursOf(map, term.key).filter((n) => n.term.key !== term.key);
  return (
    <Card className="min-w-0">
      <h2 className="text-xl font-semibold tracking-tight text-fg">{term.term}</h2>
      <p className="mt-1 text-sm text-fg-muted">{occurrenceLabel(term.chunk_count)}</p>

      <div className="mt-5">
        <h3 className="mb-2 text-sm font-semibold text-fg">Materyalde nerede geçiyor</h3>
        <SourceCard source={toSourceInfo(term.source)} href={sourceContextHref(courseId, term.source.chunk_id)} />
      </div>

      <div className="mt-6 border-t border-border pt-5">
        <h3 className="text-sm font-semibold text-fg">Birlikte anlatıldığı terimler</h3>
        {/*
          "Birlikte anlatılan" deniyor, "ilişkili" değil: ölçülen şey yalnız
          aynı pasajı paylaşmak. Anlamsal bir bağ iddia etmek, materyalin
          söylemediğini söylemek olurdu.
        */}
        {komsular.length === 0 ? (
          <p className="mt-2 text-sm text-fg-muted">Bu terim başka bir terimle aynı pasajı paylaşmıyor.</p>
        ) : (
          <ul className="mt-3 flex flex-wrap gap-2">
            {komsular.map((n) => (
              <li key={n.term.key}>
                <Button variant="secondary" size="sm" onClick={() => onSelect(n.term.key)}>
                  {n.term.term}
                  <span className="ml-2 text-xs font-normal text-fg-muted">{sharedLabel(n.sharedChunks)}</span>
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
