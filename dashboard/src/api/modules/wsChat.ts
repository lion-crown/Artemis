import { getAuthToken } from "../request";

export function buildDashboardChatWsUrl(agentId: string): string {
  const token = getAuthToken();
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const base = `${protocol}://${window.location.host}/api/agents/${agentId}/chat/ws`;
  const params = new URLSearchParams();
  if (token) params.set("token", token);
  return params.toString() ? `${base}?${params.toString()}` : base;
}
