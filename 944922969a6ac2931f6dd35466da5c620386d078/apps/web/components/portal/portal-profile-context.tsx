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

export function PortalProfileProvider({ children }: { children: ReactNode }) {
  const fetchProfile = useCallback(() => getProfile(), []);
  const profile = useResource(fetchProfile, []);

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
