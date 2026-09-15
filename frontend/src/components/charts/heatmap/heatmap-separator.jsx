"use client";;
import { memo, useEffect, useId, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { useHeatmap } from "./heatmap-context";
import {
  buildHeatmapSeparatorGradientStops,
  getHeatmapSeparatorLineY,
  getHeatmapSeparatorX,
  resolveHeatmapSeparatorStrokeDasharray,
} from "./heatmap-utils";

/** Marker for reliably identifying {@link HeatmapSeparator} in chart child trees. */
export const HEATMAP_SEPARATOR_MARKER = "__isHeatmapSeparator";

export const HeatmapSeparator = memo(function HeatmapSeparator({
  className,
  paddingX = 0,
  paddingY = 0,
  startOffset,
  labelOffset = 0,
  showLabels = false,
  labelFormat = (quarter) => `Q${quarter}`,
  labelClassName,
  strokeStyle = "solid",
  strokeDasharray,
  stroke = "var(--border)",
  gradient,
  strokeWidth = 1,
  strokeOpacity = 1
}) {
  const { gap, innerHeight, margin, separatorLayout, xScale, containerRef } =
    useHeatmap();

  const [mounted, setMounted] = useState(false);
  const reactId = useId().replace(/:/g, "");
  const gradientId = `heatmap-separator-gradient-${reactId}`;

  useEffect(() => {
    setMounted(true);
  }, []);

  const separators = useMemo(() => {
    if (!separatorLayout) {
      return [];
    }

    return separatorLayout.atColumns.map((columnIndex) => ({
      columnIndex,
      x: getHeatmapSeparatorX(columnIndex, gap, separatorLayout, xScale),
    }));
  }, [gap, separatorLayout, xScale]);

  const labels = useMemo(() => {
    if (!(showLabels && separatorLayout?.groups.length)) {
      return [];
    }

    return separatorLayout.groups.map((group) => ({
      key: `${group.year}-Q${group.quarter}-${group.startColumnIndex}`,
      label: labelFormat(group.quarter, group.startDate),
      x: margin.left + xScale(group.startColumnIndex),
    }));
  }, [labelFormat, margin.left, separatorLayout, showLabels, xScale]);

  if (!separatorLayout) {
    return null;
  }

  const { y1: lineY1, y2: lineY2 } = getHeatmapSeparatorLineY({
    innerHeight,
    marginTop: margin.top,
    startOffset,
    paddingY,
  });

  const separatorTop = startOffset ?? margin.top;
  const labelTop = separatorTop + labelOffset;
  const resolvedStroke = gradient ? `url(#${gradientId})` : stroke;
  const resolvedStrokeDasharray = resolveHeatmapSeparatorStrokeDasharray(
    strokeStyle,
    strokeDasharray
  );
  const gradientStops = gradient
    ? buildHeatmapSeparatorGradientStops(gradient, strokeOpacity)
    : null;

  const container = containerRef.current;
  const labelPortal =
    mounted && container && labels.length > 0
      ? createPortal(
          labels.map((tick) => (
            <div
              className="pointer-events-none absolute"
              key={tick.key}
              style={{
                top: labelTop,
                left: tick.x,
                width: 0,
                display: "flex",
                justifyContent: "flex-start",
              }}
            >
              <span
                className={cn(
                  "whitespace-nowrap text-chart-label text-xs",
                  labelClassName
                )}
              >
                {tick.label}
              </span>
            </div>
          )),
          container
        )
      : null;

  if (separators.length === 0) {
    return labelPortal;
  }

  return (
    <>
      {gradientStops ? (
        <defs>
          <linearGradient
            gradientUnits="userSpaceOnUse"
            id={gradientId}
            x1={0}
            x2={0}
            y1={lineY1}
            y2={lineY2}
          >
            {gradientStops.map((stop) => (
              <stop
                key={stop.offset}
                offset={stop.offset}
                stopColor={stop.color}
                stopOpacity={stop.opacity}
              />
            ))}
          </linearGradient>
        </defs>
      ) : null}
      <g>
        {separators.map((separator) => (
          <g
            className={cn(className)}
            key={separator.columnIndex}
            transform={`translate(${separator.x}, 0)`}
          >
            {paddingX > 0 ? (
              <rect
                fill="transparent"
                height={lineY2 - lineY1}
                width={paddingX * 2}
                x={-paddingX}
                y={lineY1}
              />
            ) : null}
            <line
              stroke={resolvedStroke}
              strokeDasharray={resolvedStrokeDasharray}
              strokeOpacity={gradient ? undefined : strokeOpacity}
              strokeWidth={strokeWidth}
              x1={0}
              x2={0}
              y1={lineY1}
              y2={lineY2}
            />
          </g>
        ))}
      </g>
      {labelPortal}
    </>
  );
});

(HeatmapSeparator)[
  HEATMAP_SEPARATOR_MARKER
] = true;

HeatmapSeparator.displayName = "HeatmapSeparator";

export default HeatmapSeparator;
