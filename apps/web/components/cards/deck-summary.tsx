"use client";

/**
 * Deste bitince ne oldu.
 *
 * Üç sayı var ve üçü farklı şey söylüyor:
 *   - "Biliyordum" / "Tekrar": öğrencinin KENDİ değerlendirmesi, hiçbir yere
 *     yazılmaz, puan değildir;
 *   - "bildiğini sandığın" listesi: kendi kararıyla sunucunun ölçümünün
 *     çeliştiği kartlar.
 *
 * Üçüncüsü bu ekranın asıl sebebi. Tekrar aracının değeri doğru bildiklerini
 * saymak değil, "bunu biliyorum" deyip yanlış yapmış olduğun yeri göstermektir;
 * öğrenci o listeye bakınca nereye döneceğini bilir. Sayı uydurulmaz: liste
 * yalnız sunucunun `is_correct=false` dediği kartlardan kurulur.
 */

import { VERDICT_LABEL, type DeckSummary as Summary, type ReviewCard } from "@/lib/cards";
import { Button, Card } from "@/components/ui";

function Sayi({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-3xl font-semibold tabular-nums tracking-tight text-fg">{value}</p>
      <p className="mt-1 text-sm text-fg-muted">{label}</p>
    </div>
  );
}

export function DeckSummary({
  summary,
  onRestart,
  onRestartMissed,
  onChangeSession,
}: {
  summary: Summary;
  onRestart: () => void;
  onRestartMissed: (cards: ReviewCard[]) => void;
  onChangeSession?: () => void;
}) {
  const { total, knew, review, reviewCards, overconfident } = summary;

  return (
    <div className="space-y-5">
      <Card>
        <h2 className="text-lg font-semibold text-fg">Deste bitti</h2>
        <p className="mt-1 text-sm text-fg-muted">
          Bu sayılar senin kendi değerlendirmen; not defterine ya da ilerlemene yazılmaz.
        </p>
        <div className="mt-6 flex flex-wrap gap-10">
          <Sayi label="kart" value={total} />
          <Sayi label={VERDICT_LABEL.knew} value={knew} />
          <Sayi label={VERDICT_LABEL.review} value={review} />
        </div>
      </Card>

      {overconfident.length > 0 && (
        <Card>
          <h3 className="text-base font-semibold text-fg">Bildiğini sandığın {overconfident.length} kart</h3>
          <p className="mt-1 text-sm text-fg-muted">
            Bu kartlarda &ldquo;biliyordum&rdquo; dedin ama sınavda yanlış yapmıştın. Tekrara buradan başlamak
            en çok kazandıran yer.
          </p>
          <ul className="mt-4 space-y-2">
            {overconfident.map((entry) => (
              <li
                key={entry.id}
                className="prose-tr rounded-xl border border-border bg-surface px-4 py-3 text-sm leading-6 text-fg"
              >
                {entry.view.kind === "unsupported" ? "Bu soru gösterilemiyor" : entry.view.prompt}
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <Button onClick={() => onRestartMissed(overconfident)}>Bu kartları tekrar et</Button>
          </div>
        </Card>
      )}

      <div className="flex flex-wrap gap-3">
        {reviewCards.length > 0 && (
          <Button onClick={() => onRestartMissed([...reviewCards])}>
            Yalnız &ldquo;{VERDICT_LABEL.review}&rdquo; dediklerin ({reviewCards.length})
          </Button>
        )}
        <Button variant="secondary" onClick={onRestart}>
          Desteyi baştan al
        </Button>
        {onChangeSession && (
          <Button variant="ghost" onClick={onChangeSession}>
            Başka oturum seç
          </Button>
        )}
      </div>
    </div>
  );
}
