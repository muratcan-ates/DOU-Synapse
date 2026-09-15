/**
 * Kavram haritasının saf çekirdeği: seçim, komşuluk ve okunabilir sayılar.
 *
 * Sunucu düz iki liste döndürüyor (terimler, kenarlar). Ekranın ihtiyacı ise
 * "şu terimin komşuları kimler" — bu dönüşüm JSX'in ortasında yapılsaydı her
 * render'da yeniden kurulur ve yalnız tarayıcıda sınanabilirdi. Buradaki her
 * fonksiyon DOM'suz koşar.
 *
 * Dosyanın tek kuralı: **sunucunun vermediği hiçbir şey üretilmez.** Terimin
 * tanımı, açıklaması ya da "önem puanı" yoktur; yalnız kaç pasajda geçtiği ve
 * hangi terimlerle aynı pasajı paylaştığı vardır.
 */

import type { SourceRef } from "@/lib/types";

export interface ConceptTerm {
  /** Katlanmış anahtar; kenarlar bununla bağlanır, ekranda gösterilmez. */
  key: string;
  /** Materyaldeki yazım. Ekranda görünen budur. */
  term: string;
  chunk_count: number;
  source: SourceRef;
}

export interface ConceptEdge {
  left: string;
  right: string;
  chunk_count: number;
}

export interface ConceptMap {
  course_id: string;
  terms: ConceptTerm[];
  edges: ConceptEdge[];
  chunk_count: number;
  truncated: boolean;
}

export interface Neighbour {
  term: ConceptTerm;
  /** Kaç pasajı paylaşıyorlar. İlişkinin türü değil, yalnız sayısı. */
  sharedChunks: number;
}

export function termIndex(map: ConceptMap): Map<string, ConceptTerm> {
  return new Map(map.terms.map((term) => [term.key, term]));
}

/**
 * Bir terimin komşuları, en çok pasaj paylaşandan aza.
 *
 * Kenarlar yönsüz: sunucu `left`/`right`'ı alfabetik yazıyor, bu yüzden her iki
 * uç da taranır. Listede karşılığı olmayan anahtar atlanır — kaynağı
 * gösterilemeyecek bir komşu satırı çizmek, ekranın vaadini bozardı.
 */
export function neighboursOf(map: ConceptMap, key: string): Neighbour[] {
  const index = termIndex(map);
  const neighbours: Neighbour[] = [];
  for (const edge of map.edges) {
    const otherKey = edge.left === key ? edge.right : edge.right === key ? edge.left : null;
    if (otherKey === null) continue;
    const term = index.get(otherKey);
    if (term === undefined) continue;
    neighbours.push({ term, sharedChunks: edge.chunk_count });
  }
  neighbours.sort(
    (left, right) =>
      right.sharedChunks - left.sharedChunks || left.term.term.localeCompare(right.term.term, "tr"),
  );
  return neighbours;
}

/** Bağlantı tablosu satırları: kenarlar okunur ada çevrilmiş hâlde. */
export interface EdgeRow {
  key: string;
  left: string;
  right: string;
  sharedChunks: number;
}

export function edgeRows(map: ConceptMap): EdgeRow[] {
  const index = termIndex(map);
  const rows: EdgeRow[] = [];
  for (const edge of map.edges) {
    const left = index.get(edge.left);
    const right = index.get(edge.right);
    if (left === undefined || right === undefined) continue;
    rows.push({
      key: `${edge.left}|${edge.right}`,
      left: left.term,
      right: right.term,
      sharedChunks: edge.chunk_count,
    });
  }
  return rows;
}

/**
 * İlk açılışta seçili terim: listenin başı (en çok pasajda geçen).
 *
 * Boş haritada `null` — ekran o durumda seçim değil boş durum çizer.
 */
export function defaultSelection(map: ConceptMap): string | null {
  return map.terms[0]?.key ?? null;
}

/** Seçim listede yoksa (harita yenilendi, terim düştü) başa dön. */
export function resolveSelection(map: ConceptMap, selected: string | null): string | null {
  if (selected !== null && map.terms.some((term) => term.key === selected)) return selected;
  return defaultSelection(map);
}

/**
 * "12 pasajda geçiyor" gibi tek satır.
 *
 * Sayı ekranda yalın bırakılmıyor: "12" tek başına neyin 12'si olduğunu
 * söylemez ve kullanıcı onu bir puan sanabilir.
 */
export function occurrenceLabel(chunkCount: number): string {
  return `${chunkCount} pasajda geçiyor`;
}

export function sharedLabel(sharedChunks: number): string {
  return `${sharedChunks} pasajda birlikte`;
}
