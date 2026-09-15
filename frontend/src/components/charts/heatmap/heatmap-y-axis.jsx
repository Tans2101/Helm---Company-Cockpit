"use client";;
import { memo, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { useHeatmap } from "./heatmap-context";
import {
  formatHeatmapYAxisLabel,
  getHeatmapDayLabels,
  resolveHeatmapRowOpacity,
  shouldShowHeatmapYAxisTick,
} from "./heatmap-utils";

export const HeatmapYAxis = memo(function HeatmapYAxis({
  className,
  tickFilter = "odd",
  labelFormat = "full",
  rowOpacity
}) {
  const { containerRef, margin, binHeight, gap, yScale, weekStartDay } =
    useHeatmap();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const labels = useMemo(
    () =>
      getHeatmapDayLabels(weekStartDay)
        .map((label, row) => ({
          row,
          label: formatHeatmapYAxisLabel(label, labelFormat),
          y: margin.top + yScale(row) + (binHeight - gap) / 2,
        }))
        .filter((tick) => shouldShowHeatmapYAxisTick(tick.row, tickFilter)),
    [binHeight, gap, labelFormat, margin.top, tickFilter, weekStartDay, yScale]
  );

  const container = containerRef.current;
  if (!(mounted && container)) {
    return null;
  }

  return createPortal(
    labels.map((tick) => (
      <div
        className="pointer-events-none absolute"
        key={tick.row}
        style={{
          top: tick.y,
          left: 4,
          width: Math.max(margin.left - 12, 0),
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          transform: "translateY(-50%)",
        }}
      >
        <span
          className={cn(
            "whitespace-nowrap text-chart-label text-xs",
            className
          )}
          style={{ opacity: resolveHeatmapRowOpacity(tick.row, rowOpacity) }}
        >
          {tick.label}
        </span>
      </div>
    )),
    container
  );
});

HeatmapYAxis.displayName = "HeatmapYAxis";

export default HeatmapYAxis;
