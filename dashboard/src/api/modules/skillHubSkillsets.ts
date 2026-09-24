import { request } from "../request";

export interface SkillHubSkillset {
  slug: string;
  display_name: string;
  display_name_en: string;
  summary: string;
  summary_en: string;
  icon_url?: string | null;
  skill_count: number;
}

export const skillHubSkillsetsApi = {
  list: () =>
    request<{ items: SkillHubSkillset[] }>("/skill-packages/hub/skillsets"),
};
