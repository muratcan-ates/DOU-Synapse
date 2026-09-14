/** Açık geliştirme izni ve Entra yapılandırmasının biçim kapısı. */
export function isDevAuthEnabled(value = process.env.NEXT_PUBLIC_DEV_AUTH): boolean {
  return value === "true";
}

export function entraTenantId(value = process.env.NEXT_PUBLIC_ENTRA_TENANT_ID): string | null {
  const tenant = value?.trim() ?? "";
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(tenant)
    && tenant !== "00000000-0000-0000-0000-000000000000" ? tenant : null;
}
