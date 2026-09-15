import { cn } from "@/lib/utils"

function Skeleton({
  className,
  ...props
}) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-helm-fg/8", className)}
      {...props} />
  );
}

export { Skeleton }
