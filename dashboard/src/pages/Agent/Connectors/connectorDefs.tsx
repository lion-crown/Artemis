import { Cable } from "lucide-react";

import styles from "./index.module.less";

/** Generic icon for user-configured MCP servers. */
export function ConnectorLogo({
  size = 22,
}: {
  kind?: string;
  icon?: string | null;
  size?: number;
}) {
  return (
    <Cable
      size={size}
      className={styles.connectorMcpFallbackIcon}
      aria-hidden
    />
  );
}
