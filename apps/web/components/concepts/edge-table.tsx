"use client";

/** Bütün bağlantılar tek tabloda — "parçalar"dan sonra gelen "sistem" katmanı. */

import { edgeRows, type ConceptMap } from "@/lib/concepts";
import { Card } from "@/components/ui";

export function EdgeTable({ map }: { map: ConceptMap }) {
  const rows = edgeRows(map);
  if (rows.length === 0) return null;
  return (
    <Card className="min-w-0">
      <h2 className="text-lg font-semibold text-fg">Bağlantılar</h2>
      <p className="mt-1 text-sm text-fg-muted">
        Aynı pasajda birlikte anlatılan terimler. Sayı, kaç pasajı paylaştıklarıdır.
      </p>
      {/* Tablo kendi yatay kaydırmasını taşır; sayfa gövdesi yana kaymaz. */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[420px] divide-y divide-border text-left text-sm">
          <thead className="text-sm text-fg-muted">
            <tr><th className="py-3 pr-4 font-medium">Terim</th><th className="py-3 pr-4 font-medium">Terim</th><th className="py-3 font-medium">Birlikte</th></tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row) => (
              <tr key={row.key}>
                <td className="prose-tr py-3 pr-4 text-fg">{row.left}</td>
                <td className="prose-tr py-3 pr-4 text-fg">{row.right}</td>
                <td className="py-3 tabular-nums text-fg-muted">{row.sharedChunks}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
