import { api } from "@/lib/api";

export type CourseRole = "instructor" | "student";

export interface ProfileMembership {
  course_id: string;
  course_code: string;
  course_title: string;
  role: CourseRole;
}

export interface Profile {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
  is_platform_admin: boolean;
  memberships: ProfileMembership[];
}

export interface ProfileUpdate {
  full_name: string;
}

export function getProfile(): Promise<Profile> {
  return api.get<Profile>("/me/profile");
}

export function updateProfile(payload: ProfileUpdate): Promise<Profile> {
  return api.patch<Profile>("/me/profile", payload);
}

/** Form ile API aynı temiz adı görür; boşluk yalnız sunucuya bırakılmaz. */
export function normalizedProfileName(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

export function roleLabel(role: CourseRole): string {
  return role === "instructor" ? "Eğitmen" : "Öğrenci";
}
