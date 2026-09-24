import { request } from "../request";

export interface ServiceStatus {
  service_mode: "systemd" | "launchd" | null;
  desktop: boolean;
}

export interface ServiceRestartResponse {
  status: "restarting";
  service_mode: string;
}

export const serviceApi = {
  getStatus: () => request<ServiceStatus>("/admin/service/status"),
  restart: () =>
    request<ServiceRestartResponse>("/admin/service/restart", {
      method: "POST",
    }),
};
