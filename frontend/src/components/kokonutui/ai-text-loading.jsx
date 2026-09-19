/**
 * @author: @kokonutui / Trenston
 * @description: AI Text Loading — Ask Trenston waiting state (KokonutUI, restyled)
 * @website: https://kokonutui.com
 */

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";
import { ShimmeringText } from "@/components/shimmering-text";
import { cn } from "@/lib/utils";

const DEFAULT_TEXTS = [
  "Reading your data…",
  "Thinking…",
  "Drafting a reply…",
];

export default function AITextLoading({
  texts = DEFAULT_TEXTS,
  className,
  interval = 1800,
}) {
  const reduceMotion = useReducedMotion();
  const [currentTextIndex, setCurrentTextIndex] = useState(0);

  useEffect(() => {
    if (reduceMotion || texts.length <= 1) return undefined;
    const timer = setInterval(() => {
      setCurrentTextIndex((prev) => (prev + 1) % texts.length);
    }, interval);
    return () => clearInterval(timer);
  }, [interval, texts.length, reduceMotion]);

  const text = texts[currentTextIndex] || texts[0] || "";

  return (
    <div className={cn("flex items-center min-h-[1.25rem]", className)} aria-live="polite">
      <AnimatePresence mode="wait">
        <motion.div
          key={reduceMotion ? "static" : currentTextIndex}
          initial={reduceMotion ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduceMotion ? undefined : { opacity: 0, y: -6 }}
          transition={{ duration: 0.25 }}
        >
          <ShimmeringText
            text={text}
            duration={1.2}
            isStopped={!!reduceMotion}
            className="text-sm font-medium [--color:var(--helm-muted)] [--shimmering-color:var(--helm-fg)]"
          />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
