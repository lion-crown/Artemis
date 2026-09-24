import { request } from "../request";
import type {
  ArtemisCronRow,
  ArtemisCronCreateBody,
  ArtemisCronPatchBody,
} from "../types";

export interface ArtemisCronSettings {
  timezone: string;
}

export interface CronTaskExamples {
  zh?: string[];
  en?: string[];
}

export interface CronExamplesResponse {
  task_examples: CronTaskExamples | null;
}

export const artemisCronApi = {
  settings: () => request<ArtemisCronSettings>("/cron/settings"),

  examples: (agentId: string) =>
    request<CronExamplesResponse>(`/agents/${agentId}/cron/examples`),

  list: (agentId: string) => request<ArtemisCronRow[]>(`/agents/${agentId}/cron`),

  create: (agentId: string, body: ArtemisCronCreateBody) =>
    request<ArtemisCronRow>(`/agents/${agentId}/cron`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  get: (agentId: string, cronId: string) =>
    request<ArtemisCronRow>(`/agents/${agentId}/cron/${cronId}`),

  patch: (agentId: string, cronId: string, body: ArtemisCronPatchBody) =>
    request<ArtemisCronRow>(`/agents/${agentId}/cron/${cronId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  delete: (agentId: string, cronId: string) =>
    request<void>(`/agents/${agentId}/cron/${cronId}`, { method: "DELETE" }),

  runNow: (agentId: string, cronId: string) =>
    request<void>(`/agents/${agentId}/cron/${cronId}/run-now`, {
      method: "POST",
    }),
};
