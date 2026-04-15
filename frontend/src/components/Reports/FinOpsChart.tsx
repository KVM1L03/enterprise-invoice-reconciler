"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { FinOpsDailyPoint } from "@/types";

const COLOR_COST = "#00502e";
const COLOR_INVOICES = "#9df5bd";
const AXIS_COLOR = "#94a3b8";
const GRID_COLOR = "#e2e8f0";

const CARD_SHADOW = "shadow-[0_12px_40px_rgba(25,28,30,0.04)]";

type TooltipPayloadItem = {
  dataKey: string | number;
  name?: string | number;
  value: number;
  color?: string;
};

type ChartTooltipProps = {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
};

function formatCurrency(value: number): string {
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg">
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
        {label}
      </p>
      {payload.map((entry) => {
        const isCost = entry.dataKey === "apiCostUsd";
        return (
          <div
            key={String(entry.dataKey)}
            className="flex items-center justify-between gap-4 text-xs"
          >
            <span className="flex items-center gap-1.5 text-slate-600">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              {isCost ? "API Cost" : "Invoices"}
            </span>
            <span className="font-mono font-semibold text-[#191c1e]">
              {isCost ? formatCurrency(entry.value) : entry.value}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export type FinOpsChartProps = {
  data: FinOpsDailyPoint[];
  title?: string;
  description?: string;
};

export function FinOpsChart({
  data,
  title = "API Spend vs. Invoices Processed",
  description = "Daily LLM cost plotted against reconciled invoice volume.",
}: FinOpsChartProps) {
  return (
    <section
      className={`bg-white rounded-xl ${CARD_SHADOW} border border-slate-100 p-6`}
    >
      <div className="mb-5 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-base font-semibold text-[#191c1e]">{title}</h2>
          <p className="mt-0.5 text-xs text-[#3f4941]">{description}</p>
        </div>
        <div className="flex items-center gap-4 text-[10px] font-bold uppercase tracking-widest text-slate-500">
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: COLOR_COST }}
            />
            API Cost (USD)
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-4 rounded-sm"
              style={{ backgroundColor: COLOR_INVOICES }}
            />
            Invoices
          </span>
        </div>
      </div>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <ComposedChart
            data={data}
            margin={{ top: 10, right: 16, bottom: 0, left: 0 }}
          >
            <CartesianGrid
              stroke={GRID_COLOR}
              strokeDasharray="3 3"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              stroke={AXIS_COLOR}
              tick={{ fontSize: 11, fill: AXIS_COLOR }}
              axisLine={{ stroke: GRID_COLOR }}
              tickLine={false}
            />
            <YAxis
              yAxisId="invoices"
              orientation="left"
              stroke={AXIS_COLOR}
              tick={{ fontSize: 11, fill: AXIS_COLOR }}
              axisLine={{ stroke: GRID_COLOR }}
              tickLine={false}
              label={{
                value: "Invoices",
                angle: -90,
                position: "insideLeft",
                style: {
                  fontSize: 10,
                  fill: AXIS_COLOR,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                },
              }}
            />
            <YAxis
              yAxisId="cost"
              orientation="right"
              stroke={AXIS_COLOR}
              tick={{ fontSize: 11, fill: AXIS_COLOR }}
              axisLine={{ stroke: GRID_COLOR }}
              tickLine={false}
              tickFormatter={(v: number) => `$${v.toFixed(2)}`}
            />
            <Tooltip
              cursor={{ fill: "rgba(157, 245, 189, 0.15)" }}
              content={<ChartTooltip />}
            />
            <Legend
              wrapperStyle={{ display: "none" }}
            />
            <Bar
              yAxisId="invoices"
              dataKey="invoicesProcessed"
              name="Invoices Processed"
              fill={COLOR_INVOICES}
              radius={[4, 4, 0, 0]}
              maxBarSize={48}
            />
            <Line
              yAxisId="cost"
              type="monotone"
              dataKey="apiCostUsd"
              name="API Cost (USD)"
              stroke={COLOR_COST}
              strokeWidth={2.5}
              dot={{ r: 4, fill: COLOR_COST, strokeWidth: 0 }}
              activeDot={{ r: 6 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
