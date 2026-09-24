import { request } from "../request";

export interface ConnectorInstance {
  instance_id: string;
  kind: "custom-mcp";
  display_name: string;
  status: "active" | "disabled";
  mcp_server_name: string;
  has_credentials: boolean;
  default_open?: boolean;
  shared: boolean;
  owner_user_id: number;
  owner_username?: string | null;
  owner_display_name?: string | null;
  can_manage: boolean;
  created_at: number;
  updated_at: number;
}

export interface ConnectorProbeResult {
  ok: boolean;
  tool_count?: number;
  tools?: { name: string; description: string }[];
  error?: string;
  error_type?: string;
  status_code?: number;
  oauth?: { available: boolean; issuer?: string; resource?: string };
}

export type CustomMcpTransport = "streamable_http" | "stdio";

export interface CustomMcpOAuthPreview {
  configured?: boolean;
  required?: boolean;
  expires_at?: number;
}

export interface CustomMcpServerSpec {
  transport: CustomMcpTransport;
  url?: string;
  headers?: Record<string, string>;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  enabled?: boolean;
  display_name?: string;
  default_open?: boolean;
  shared?: boolean;
  oauth?: CustomMcpOAuthPreview;
}

export type CustomMcpServers = Record<string, CustomMcpServerSpec>;

export const connectorsApi = {
  listInstances: () => request<ConnectorInstance[]>("/connector-instances"),

  deleteInstance: (instanceId: string) =>
    request<void>(`/connector-instances/${encodeURIComponent(instanceId)}`, {
      method: "DELETE",
    }),

  oauthStart: (
    target: { type: "custom_mcp"; server_name: string },
    redirectAfter?: string,
  ) =>
    request<{ authorize_url: string; state_id: string }>(
      "/connectors/oauth/start",
      {
        method: "POST",
        body: JSON.stringify({ target, redirect_after: redirectAfter }),
      },
    ),

  oauthPending: (stateId: string) =>
    request<{ kind: string; server_name?: string; applied?: boolean }>(
      `/connectors/oauth/pending/${stateId}`,
    ),

  getCustomMcp: () =>
    request<{ servers: CustomMcpServers }>("/connectors/custom-mcp"),

  putCustomMcp: (servers: CustomMcpServers) =>
    request<{ servers: CustomMcpServers }>("/connectors/custom-mcp", {
      method: "PUT",
      body: JSON.stringify({ servers }),
    }),

  patchCustomMcpServer: (
    name: string,
    body: { enabled?: boolean; default_open?: boolean; shared?: boolean },
  ) =>
    request<{ servers: CustomMcpServers }>(
      `/connectors/custom-mcp/servers/${encodeURIComponent(name)}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),

  testCustomMcp: (body: { name?: string; server?: CustomMcpServerSpec }) =>
    request<ConnectorProbeResult>("/connectors/custom-mcp/test", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
