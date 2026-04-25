import { api } from "@/lib/api";

export interface UserPreferences {
  onboarding_completed: boolean;
  role: string | null;
  experience_level: string | null;
  primary_languages: string[];
  use_cases: string[];
  response_style: string | null;
  custom_context: string | null;
  memory_enabled: boolean;
  memory_compaction_day: number;
  memory_compaction_hour: number;
  memory_last_compacted_at: string | null;
  memory_next_run_at: string | null;
}

export interface UpdateUserPreferencesPayload {
  onboarding_completed?: boolean;
  role?: string | null;
  experience_level?: string | null;
  primary_languages?: string[];
  use_cases?: string[];
  response_style?: string | null;
  custom_context?: string | null;
  memory_enabled?: boolean;
  memory_compaction_day?: number;
  memory_compaction_hour?: number;
}

export async function getPreferences(): Promise<UserPreferences> {
  return api<UserPreferences>("/api/v1/user-preferences");
}

export async function updatePreferences(
  payload: UpdateUserPreferencesPayload
): Promise<UserPreferences> {
  return api<UserPreferences>("/api/v1/user-preferences", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
