import trenstonMark from "@/assets/trenston-mark.svg";
import trenstonMarkNavy from "@/assets/trenston-mark-navy.svg";

/**
 * Approved Trenston T-medallion. Use `navy` for self-contained square (dark colorway);
 * omit for transparent light colorway on cream surfaces.
 */
export default function HelmMark({ size = 36, navy = true, className = "", alt = "" }) {
  const px = typeof size === "number" ? size : 36;
  return (
    <img
      src={navy ? trenstonMarkNavy : trenstonMark}
      alt={alt}
      width={px}
      height={px}
      className={`shrink-0 ${className}`}
      draggable={false}
    />
  );
}
