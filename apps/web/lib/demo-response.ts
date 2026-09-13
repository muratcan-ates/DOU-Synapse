/** Sunucunun demo yedeğine eklediği açıklama; geçmişte de gövdenin parçasıdır. */
export const DEMO_RESPONSE_LABEL = "Önceden kaydedilmiş demo yanıtı";

/**
 * Doğrulanmış canlı yanıtta aynı açıklamayı rozet ve gövdede iki kez çizme.
 * Metin bir köken kanıtı değildir: alan yoksa geçmiş/önbellek gövdesi aynen kalır.
 */
export function demoResponseText(text: string, fixture?: true | null): string {
  const prefix = `${DEMO_RESPONSE_LABEL}\n\n`;
  return fixture === true && text.startsWith(prefix) ? text.slice(prefix.length) : text;
}
