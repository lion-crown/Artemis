import { useTranslation } from "react-i18next";

import PageShell from "../../../layouts/PageShell";
import { CustomMcpTab } from "./CustomMcpTab";

/** The connector page is intentionally limited to user-defined MCP servers. */
export default function ConnectorsPage() {
  const { t } = useTranslation();
  return (
    <PageShell
      title={t("pageShell.connectors.title")}
      subtitle={t("pageShell.connectors.subtitle")}
    >
      <CustomMcpTab />
    </PageShell>
  );
}
