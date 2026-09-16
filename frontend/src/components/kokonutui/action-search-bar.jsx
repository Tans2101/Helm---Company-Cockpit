/**
 * @author: @kokonutui / Helm
 * @description: Action Search Bar — ⌘K quick nav (KokonutUI, restyled)
 * @website: https://kokonutui.com
 */

import { Search } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import useDebounce from "@/hooks/use-debounce";
import { cn } from "@/lib/utils";

/**
 * @param {{ id: string, label: string, icon?: React.ReactNode, description?: string, to?: string }[]} actions
 * @param {(action) => void} onSelect
 * @param {boolean} open
 * @param {(open: boolean) => void} onOpenChange
 */
export default function ActionSearchBar({
  actions = [],
  onSelect,
  open: controlledOpen,
  onOpenChange,
}) {
  const reduceMotion = useReducedMotion();
  const [internalOpen, setInternalOpen] = useState(false);
  const isControlled = controlledOpen !== undefined;
  const isOpen = isControlled ? controlledOpen : internalOpen;
  const setOpen = useCallback(
    (next) => {
      if (!isControlled) setInternalOpen(next);
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange],
  );

  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);
  const debouncedQuery = useDebounce(query, 150);

  const filtered = useMemo(() => {
    if (!debouncedQuery.trim()) return actions;
    const q = debouncedQuery.toLowerCase().trim();
    return actions.filter((a) => {
      const haystack = [
        a.label,
        a.description,
        ...(Array.isArray(a.keywords) ? a.keywords : []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [actions, debouncedQuery]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!isOpen);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, setOpen]);

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
      setActiveIndex(0);
      return;
    }
    const t = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(t);
  }, [isOpen]);

  useEffect(() => {
    setActiveIndex(0);
  }, [debouncedQuery]);

  const choose = useCallback(
    (action) => {
      if (!action) return;
      onSelect?.(action);
      setOpen(false);
    },
    [onSelect, setOpen],
  );

  const onKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      return;
    }
    if (!filtered.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % filtered.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + filtered.length) % filtered.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(filtered[activeIndex]);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" data-testid="action-search-bar">
          <motion.div
            className="absolute inset-0 bg-helm-ink/60"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <motion.div
            role="dialog"
            aria-label="Quick navigation"
            className="relative z-[1] w-[min(100%,28rem)] rounded-lg border border-helm-line bg-helm-card shadow-2xl overflow-hidden"
            initial={reduceMotion ? false : { opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="relative border-b border-helm-line">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-helm-muted pointer-events-none" />
              <Input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Go to…"
                data-testid="action-search-input"
                className="h-11 border-0 rounded-none bg-transparent pl-10 pr-16 text-sm text-helm-fg placeholder:text-helm-muted focus-visible:ring-0 shadow-none"
                autoComplete="off"
                role="combobox"
                aria-expanded
                aria-autocomplete="list"
              />
              <kbd className="absolute right-3 top-1/2 -translate-y-1/2 font-mono text-[10px] text-helm-muted border border-helm-line rounded px-1.5 py-0.5">
                esc
              </kbd>
            </div>
            <ul role="listbox" className="max-h-72 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <li className="px-3 py-6 text-center text-sm text-helm-muted">No matches</li>
              ) : (
                filtered.map((action, i) => (
                  <li key={action.id} role="option" aria-selected={i === activeIndex}>
                    <button
                      type="button"
                      id={`action-${action.id}`}
                      className={cn(
                        "w-full flex items-center gap-3 px-3 py-2.5 text-left text-sm transition-colors",
                        i === activeIndex
                          ? "bg-helm-gold/12 text-helm-fg"
                          : "text-helm-fg hover:bg-helm-fg/[0.04]",
                      )}
                      onMouseEnter={() => setActiveIndex(i)}
                      onClick={() => choose(action)}
                    >
                      <span className={cn("shrink-0", i === activeIndex ? "text-helm-gold" : "text-helm-muted")}>
                        {action.icon}
                      </span>
                      <span className="truncate flex-1">{action.label}</span>
                      {action.description ? (
                        <span className="text-[10px] font-mono uppercase tracking-wider text-helm-muted shrink-0">
                          {action.description}
                        </span>
                      ) : null}
                    </button>
                  </li>
                ))
              )}
            </ul>
            <div className="border-t border-helm-line px-3 py-2 flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-helm-muted">
              <span>Navigate</span>
              <span>⌘K</span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
