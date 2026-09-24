import { Layout } from "antd";
import { Menu as MenuIcon } from "lucide-react";
import PwaInstallPrompt from "../components/PwaInstallPrompt";
import { typeSize } from "../utils/mobileTypeScale";

const { Header: AntHeader } = Layout;

interface HeaderProps {
  selectedKey?: string;
  collapsed?: boolean;
  onToggle?: () => void;
  isMobile?: boolean;
}

/**
 * Mobile-only top chrome: brand + nav toggle + install.
 * Desktop GitHub / theme controls moved into the account popover.
 */
export default function Header({ onToggle, isMobile }: HeaderProps) {
  if (!isMobile) return null;

  return (
    <AntHeader
      style={{
        height: "var(--fn-header-height)",
        padding: "0 calc(12px + var(--window-controls-inset-end, 0px)) 0 12px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "var(--fn-header-bg)",
        backdropFilter: "blur(var(--fn-header-blur))",
        WebkitBackdropFilter: "blur(var(--fn-header-blur))",
        borderBottom: "1px solid var(--fn-border-primary)",
        transition: "background var(--fn-transition)",
        flexShrink: 0,
        zIndex: 20,
      }}
    >
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}
      >
        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            aria-label="Open navigation"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: typeSize(34, true),
              height: typeSize(34, true),
              border: "none",
              borderRadius: "var(--fn-radius-md)",
              background: "transparent",
              color: "var(--fn-text-tertiary)",
              cursor: "pointer",
              transition: "all var(--fn-transition-fast)",
              flexShrink: 0,
            }}
          >
            <MenuIcon size={20} strokeWidth={1.8} />
          </button>
        )}
        <img
          src="/artemis-logo.webp"
          alt=""
          width={28}
          height={28}
          style={{ objectFit: "contain", flexShrink: 0 }}
        />
        <span
          style={{
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: 0.5,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            display: "block",
            flexShrink: 0,
          }}
        >
          Artemis
        </span>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          flexShrink: 0,
        }}
      >
        <PwaInstallPrompt compact />
      </div>
    </AntHeader>
  );
}
