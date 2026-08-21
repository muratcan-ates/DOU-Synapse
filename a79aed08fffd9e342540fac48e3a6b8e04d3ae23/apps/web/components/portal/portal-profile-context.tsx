"use client";

import {
  createContext,
  useCallback,
  useContext,
  type ReactNode,
} from "react";
import { getProfile, type Profile } from "@/lib/profile";
import { useResource, type Resource } from "@/lib/use-resource";

const PortalProfileContext = createContext<Resource<Profile> | null>(null);

export function PortalProfileProvider({
  children,
  userId,
}: {
  children: ReactNode;
  userId: string;
}) {
  // Profil sonucu kullanıcılar arasında paylaşılmaz. Aynı tarayıcıda çıkıştan
  // sonra başka hesap açıldığında eski admin bayrağı veya ad kısa süreliğine
  // bile yeni kullanıcıya taşınmamalıdır.
  const fetchProfile = useCallback(() => getProfile(), [userId]);
  const profile = useResource(fetchProfile, [userId]);

  return (
    <PortalProfileContext.Provider value={profile}>
      {children}
    </PortalProfileContext.Provider>
  );
}

export function usePortalProfile(): Resource<Profile> {
  const value = useContext(PortalProfileContext);
  if (!value) {
    throw new Error("usePortalProfile, PortalProfileProvider içinde kullanılmalıdır.");
  }
  return value;
}
