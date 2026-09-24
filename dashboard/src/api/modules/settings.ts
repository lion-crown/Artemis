import { request } from "../request";

export interface ArtemisTimezoneSettings {
  timezone: string;
}

export interface ArtemisUploadSettings {
  max_upload_mb: number;
  max_upload_bytes: number;
}

export interface ArtemisCapabilitiesSettings {
  mobile: { enabled: boolean; backend: string };
}

export const artemisSettingsApi = {
  timezone: () => request<ArtemisTimezoneSettings>("/settings/timezone"),
  upload: () => request<ArtemisUploadSettings>("/settings/upload"),
  capabilities: () =>
    request<ArtemisCapabilitiesSettings>("/settings/capabilities", {
      cache: "no-store",
    }),
};
