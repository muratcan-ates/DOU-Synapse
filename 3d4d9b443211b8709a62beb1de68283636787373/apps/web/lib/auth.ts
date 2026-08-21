/** Parola kurtarma formunun sunucudan bağımsız, test edilebilir kuralları. */

export const PASSWORD_MIN_LENGTH = 8;

export function passwordValidationError(password: string, confirmation: string): string | null {
  if (password.length < PASSWORD_MIN_LENGTH) {
    return `Yeni parola en az ${PASSWORD_MIN_LENGTH} karakter olmalıdır.`;
  }
  if (password !== confirmation) return "Parolalar birbiriyle eşleşmiyor.";
  return null;
}

