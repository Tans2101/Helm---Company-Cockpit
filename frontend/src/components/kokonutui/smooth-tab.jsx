/**
 * @author: @kokonutui / Helm
 * @description: Smooth Tab — sliding tab bar (KokonutUI, restyled)
 * @website: https://kokonutui.com
 */

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import * as React from "react";
import { cn } from "@/lib/utils";

const slideVariants = {
  enter: (direction) => ({
    x: direction > 0 ? 24 : -24,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction) => ({
    x: direction < 0 ? 24 : -24,
    opacity: 0,
  }),
};

export default function SmoothTab({
  items = [],
  defaultTabId,
  value,
  className,
  onChange,
  panelClassName,
}) {
  const reduceMotion = useReducedMotion();
  const initialId = value ?? defaultTabId ?? items[0]?.id;
  const [selected, setSelected] = React.useState(initialId);
  const [direction, setDirection] = React.useState(0);
  const [dimensions, setDimensions] = React.useState({ width: 0, left: 0 });
  const buttonRefs = React.useRef(new Map());
  const containerRef = React.useRef(null);

  const activeId = value !== undefined ? value : selected;

  React.useEffect(() => {
    if (value !== undefined) setSelected(value);
  }, [value]);

  React.useLayoutEffect(() => {
    const updateDimensions = () => {
      const selectedButton = buttonRefs.current.get(activeId);
      const container = containerRef.current;
      if (selectedButton && container) {
        const rect = selectedButton.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        setDimensions({
          width: rect.width,
          left: rect.left - containerRect.left,
        });
      }
    };
    requestAnimationFrame(updateDimensions);
    window.addEventListener("resize", updateDimensions);
    return () => window.removeEventListener("resize", updateDimensions);
  }, [activeId, items]);

  const handleTabClick = (tabId) => {
    const currentIndex = items.findIndex((item) => item.id === activeId);
    const newIndex = items.findIndex((item) => item.id === tabId);
    setDirection(newIndex > currentIndex ? 1 : -1);
    if (value === undefined) setSelected(tabId);
    onChange?.(tabId);
  };

  const selectedItem = items.find((item) => item.id === activeId);

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div
        aria-label="Settings sections"
        className={cn(
          "relative flex w-full max-w-full overflow-x-auto",
          "rounded-md border border-helm-line bg-helm-card p-1",
        )}
        ref={containerRef}
        role="tablist"
      >
        <motion.div
          aria-hidden
          animate={{
            width: Math.max(0, dimensions.width - 4),
            x: dimensions.left + 2,
            opacity: dimensions.width ? 1 : 0,
          }}
          className="absolute z-[1] rounded-sm bg-helm-gold/20 border border-helm-gold/35"
          initial={false}
          style={{ height: "calc(100% - 8px)", top: "4px" }}
          transition={
            reduceMotion
              ? { duration: 0 }
              : { type: "spring", stiffness: 400, damping: 30 }
          }
        />

        <div
          className="relative z-[2] flex w-full gap-0.5"
          style={{ minWidth: `${items.length * 5.5}rem` }}
        >
          {items.map((item) => {
            const isSelected = activeId === item.id;
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={isSelected}
                aria-controls={`panel-${item.id}`}
                id={`tab-${item.id}`}
                data-testid={item.testId}
                tabIndex={isSelected ? 0 : -1}
                className={cn(
                  "relative flex flex-1 items-center justify-center rounded-sm px-3 py-2",
                  "font-mono text-[10px] uppercase tracking-[0.14em] transition-colors",
                  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-helm-gold/40",
                  isSelected ? "text-helm-fg" : "text-helm-muted hover:text-helm-fg",
                )}
                onClick={() => handleTabClick(item.id)}
                ref={(el) => {
                  if (el) buttonRefs.current.set(item.id, el);
                  else buttonRefs.current.delete(item.id);
                }}
              >
                <span className="truncate">{item.title}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className={cn("relative min-h-[12rem]", panelClassName)} role="tabpanel" id={`panel-${activeId}`}>
        <AnimatePresence mode="wait" custom={direction} initial={false}>
          <motion.div
            key={activeId}
            custom={direction}
            variants={reduceMotion ? undefined : slideVariants}
            initial={reduceMotion ? false : "enter"}
            animate="center"
            exit={reduceMotion ? undefined : "exit"}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            {selectedItem?.content ?? null}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
