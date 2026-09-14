/** Deterministic presentation only: no course ordering, randomness or user data. */
export interface CourseCoverInput {
  title?: string | null;
  code?: string | null;
}

function normalize(value: string | null | undefined): string {
  return (value ?? "").normalize("NFC").trim().replace(/\s+/gu, " ").toLocaleUpperCase("tr-TR");
}

function words(value: string): string[] {
  return value.match(/[\p{L}\p{N}][\p{L}\p{M}\p{N}]*/gu) ?? [];
}

/** First two words, or the first two characters of a single word; then code. */
export function courseInitials({ title, code }: CourseCoverInput): string {
  const titleWords = words(normalize(title));
  const parts = titleWords.length > 0 ? titleWords : words(normalize(code));
  if (parts.length === 0) return "D";
  if (parts.length === 1) return Array.from(parts[0]).slice(0, 2).join("");
  return parts.slice(0, 2).map((part) => Array.from(part)[0]).join("");
}

export function courseCoverDesign(course: CourseCoverInput) {
  // FNV-1a is a stable visual seed, not a security or identity hash.
  const key = JSON.stringify([normalize(course.title), normalize(course.code)]);
  let seed = 0x811c9dc5;
  for (const character of key) {
    seed = Math.imul(seed ^ character.codePointAt(0)!, 0x01000193) >>> 0;
  }
  return {
    initials: courseInitials(course),
    seed,
    layout: seed % 3,
    rotation: ((seed >>> 4) % 25) - 12,
    offset: 8 + ((seed >>> 10) % 17),
  };
}
