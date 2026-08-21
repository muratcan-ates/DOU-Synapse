"use client";

/**
 * Oturum okuma — tek kaynak.
 *
 * Rol kontrolü altı ayrı yerde `getStoredUser()?.role === "instructor"` diye
 * tekrarlanıyordu. Rol mantığı tek yerde olmazsa, ileride rol eklendiğinde
 * (ör. asistan/gözlemci) hangi ekranın güncellendiği takip edilemez.
 *
 * Not: kimlik yalnızca ARAYÜZÜ şekillendirir. Yetki her zaman sunucuda
 * doğrulanır — localStorage'daki rol bir yetki belgesi değildir (Anayasa II).
 */

import { useEffect, useState } from "react";
import { getStoredUser, type DemoUser } from "@/lib/api";

export interface Session {
  user: DemoUser | null;
  isInstructor: boolean;
  /** localStorage yalnız istemcide okunur; ilk render'da henüz bilinmez. */
  ready: boolean;
}

export function useSession(): Session {
  const [user, setUser] = useState<DemoUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUser(getStoredUser());
    setReady(true);
  }, []);

  return { user, isInstructor: user?.role === "instructor", ready };
}
