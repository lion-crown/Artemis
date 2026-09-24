import { useEffect } from "react";

function isPwa(): boolean {
  if (window.matchMedia("(display-mode: standalone)").matches) return true;
  const nav = navigator as Navigator & { standalone?: boolean };
  return nav.standalone === true;
}

/**
 * Tracks `--keyboard-offset` on the document root for PWA soft-keyboard layout.
 */
export function useKeyboardOffset() {
  useEffect(() => {
    if (!isPwa()) return;
    const vv = window.visualViewport;
    if (!vv) return;

    const update = () => {
      const keyboardHeight = Math.max(
        0,
        window.innerHeight - vv.height - vv.offsetTop,
      );
      document.documentElement.style.setProperty(
        "--keyboard-offset",
        `${keyboardHeight}px`,
      );
    };

    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    update();

    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
      document.documentElement.style.removeProperty("--keyboard-offset");
    };
  }, []);
}
