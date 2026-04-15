import type { LucideIcon } from "lucide-react";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";

const CARD_SHADOW = "shadow-[0_12px_40px_rgba(25,28,30,0.04)]";

export type TrendIndicator = {
  direction: "up" | "down" | "flat";
  label: string;
};

export type StatCardProps = {
  label: string;
  value: string;
  accent?: "primary" | "error";
  icon?: LucideIcon;
  trend?: TrendIndicator;
  footer?: React.ReactNode;
};

const TREND_ICON: Record<TrendIndicator["direction"], LucideIcon> = {
  up: TrendingUp,
  down: TrendingDown,
  flat: Minus,
};

const TREND_COLOR: Record<TrendIndicator["direction"], string> = {
  up: "text-[#00502e]",
  down: "text-[#ba1a1a]",
  flat: "text-slate-500",
};

export function StatCard({
  label,
  value,
  accent = "primary",
  icon: Icon,
  trend,
  footer,
}: StatCardProps) {
  const valueColor = accent === "error" ? "text-[#ba1a1a]" : "text-[#00502e]";
  const TrendIcon = trend ? TREND_ICON[trend.direction] : null;
  const trendColor = trend ? TREND_COLOR[trend.direction] : "";

  return (
    <div
      className={`bg-white rounded-xl ${CARD_SHADOW} border border-slate-100 p-6 flex flex-col gap-1`}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-[0.7rem] font-medium text-slate-500 uppercase tracking-[0.15em]">
          {label}
        </span>
        {Icon && (
          <div className="rounded-md bg-[#9df5bd]/40 p-1.5 flex items-center justify-center shrink-0">
            <Icon className="h-4 w-4 text-[#00502e]" />
          </div>
        )}
      </div>

      <span
        className={`text-[3.25rem] font-bold ${valueColor} leading-none mt-2 tracking-tight`}
      >
        {value}
      </span>

      {trend && TrendIcon && (
        <div
          className={`mt-3 inline-flex items-center gap-1 text-xs font-semibold ${trendColor}`}
        >
          <TrendIcon className="h-3.5 w-3.5" />
          <span>{trend.label}</span>
        </div>
      )}

      {footer && <div className="mt-4">{footer}</div>}
    </div>
  );
}
