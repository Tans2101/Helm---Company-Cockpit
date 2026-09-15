"use client";;
import { useMemo } from "react";
import { generateHeatmapSkeletonFromTarget } from "./generate-heatmap-skeleton-data";
import { HeatmapCells } from "./heatmap-cells";
import { HeatmapChart } from "./heatmap-chart";
import { HeatmapXAxis } from "./heatmap-x-axis";
import { HeatmapYAxis } from "./heatmap-y-axis";

export function HeatmapChartLoading({
  data,
  xDomain,
  margin,
  gap = 2,
  cornerRadius = 2,
  label = "Loading",
  className = ""
}) {
  const skeletonData = useMemo(
    () => generateHeatmapSkeletonFromTarget(data),
    [data]
  );

  return (
    <HeatmapChart
      className={className}
      data={skeletonData}
      gap={gap}
      loadingLabel={label}
      margin={margin}
      status="loading"
      xDomain={xDomain}
    >
      <HeatmapCells cornerRadius={cornerRadius} interactive={false} />
      <HeatmapXAxis />
      <HeatmapYAxis />
    </HeatmapChart>
  );
}

export default HeatmapChartLoading;
