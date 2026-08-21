/**
 * Kaynak referansı → kaynak kartı girdisi. Tek eşleme, tek dosya.
 *
 * Neden ayrı dosya: aynı üç alanlık dönüşüm üç lib dosyasında üç ayrı isimle
 * duruyordu (sohbet atfı, sınav kaynağı, soru havuzu). Üç kopya aynı anda
 * doğruyken de sorundu: alan adlarından biri sözleşmede değişirse ikisi
 * güncellenip üçüncüsü unutulur ve o ekran alıntı yerine başka bir alanı
 * gösterir — hiçbir şey patlamaz, kart yalnız yanlış şeyi yazar (Anayasa XI).
 */

import type { SourceInfo } from "@/components/source-card";

/**
 * Girdi tipi yapısal: çağıranlar kendi sözleşme tipleriyle geçer (`Citation`
 * ayrıca `chunk_id`/`claim` taşır, `SourceRef` yalnız `chunk_id`). Ortak olan
 * üç alan burada isteniyor, fazlası eşlemeyi ilgilendirmiyor.
 *
 * İki alan adı bilerek eşlenmiyor: sözleşmede `snippet`, bileşende `quote`.
 * Konum sunucudan "Sayfa 7" / "Slayt 3" olarak gelir; arayüz biçimlendirmez,
 * yalnız taşır (Anayasa I).
 */
export function toSourceInfo(source: {
  file_name: string;
  location: string;
  snippet: string;
}): SourceInfo {
  return {
    fileName: source.file_name,
    location: source.location,
    quote: source.snippet,
  };
}
