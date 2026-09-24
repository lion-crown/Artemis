import { ARTEMIS_EMPTY_MASCOT_SRC } from "../../assets/mascot";
import styles from "./EmptyState.module.less";

interface ArtemisEmptyMascotProps {
  className?: string;
  /** Square edge in px; default 160. */
  size?: number;
}

/**
 * Artemis empty-state mascot image with shared sizing.
 * Use inside custom empty UIs or pass as ``EmptyState`` icon /
 * antd ``Empty`` ``image``.
 */
export function ArtemisEmptyMascot({
  className,
  size = 160,
}: ArtemisEmptyMascotProps) {
  return (
    <img
      src={ARTEMIS_EMPTY_MASCOT_SRC}
      alt=""
      draggable={false}
      className={className ? `${styles.mascot} ${className}` : styles.mascot}
      style={size === 160 ? undefined : { width: size, height: size }}
    />
  );
}
