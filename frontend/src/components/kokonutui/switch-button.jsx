/**
 * @author: @dorianbaffier / Trenston
 * @description: Switch Button — light/dark toggle visuals (KokonutUI, restyled)
 * Driven by Trenston ThemeContext — not next-themes.
 * @website: https://kokonutui.com
 */

import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Visual light↔dark switch. Parent owns theme state via Trenston `useTheme()`.
 * When `mode` is "system", the icon reflects `resolvedMode` but clicking
 * sets an explicit light/dark (caller decides).
 */
export default function SwitchButton({
  mode = "light",
  resolvedMode = "light",
  onToggle,
  className,
  "data-testid": testId,
  ...props
}) {
  const isDark = (mode === "system" ? resolvedMode : mode) === "dark";
  const Icon = isDark ? Moon : Sun;
  const label = isDark ? "Dark" : "Light";

  return (
    <button
      type="button"
      data-testid={testId || (isDark ? "theme-dark" : "theme-light")}
      aria-pressed={mode !== "system"}
      aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
      onClick={onToggle}
      className={cn(
        "group relative inline-flex h-10 items-center gap-2 overflow-hidden rounded-md border px-4",
        "border-helm-line bg-helm-card text-helm-fg",
        "hover:border-helm-gold/35 transition-colors duration-200",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-helm-gold/40",
        className,
      )}
      {...props}
    >
      <Icon
        className={cn(
          "h-4 w-4 text-helm-gold transition-transform duration-700 ease-in-out transform-gpu",
          "group-hover:rotate-[360deg] group-hover:scale-110",
          isDark ? "rotate-180" : "rotate-0",
        )}
      />
      <span className="relative text-sm font-medium capitalize">
        {label}
        <span
          className={cn(
            "absolute -bottom-px left-0 h-px w-full opacity-0 group-hover:opacity-100 transition-opacity",
            "bg-gradient-to-r from-transparent via-helm-gold/50 to-transparent",
          )}
        />
      </span>
      <span
        aria-hidden
        className={cn(
          "pointer-events-none absolute inset-0 z-[1]",
          "bg-gradient-to-r from-transparent via-helm-gold/[0.08] to-transparent",
          "translate-x-[-100%] group-hover:translate-x-[100%]",
          "transition-transform duration-500 ease-in-out",
        )}
      />
    </button>
  );
}
