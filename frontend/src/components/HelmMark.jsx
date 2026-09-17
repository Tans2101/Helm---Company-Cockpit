import helmMark from "@/assets/helm-mark.svg";
import helmMarkNavy from "@/assets/helm-mark-navy.svg";

/**
 * Approved Helm-H emblem. Use `navy` for self-contained square (dark colorway);
 * omit for transparent light colorway on cream surfaces.
 */
export default function HelmMark({ size = 36, navy = true, className = "", alt = "" }) {
  const px = typeof size === "number" ? size : 36;
  return (
    <img
      src={navy ? helmMarkNavy : helmMark}
      alt={alt}
      width={px}
      height={px}
      className={`shrink-0 ${className}`}
      draggable={false}
    />
  );
}
