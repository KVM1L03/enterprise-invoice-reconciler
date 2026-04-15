"use client";

import dynamic from "next/dynamic";

import type { FinOpsChartProps } from "./FinOpsChart";

const FinOpsChart = dynamic(
  () => import("./FinOpsChart").then((mod) => mod.FinOpsChart),
  {
    ssr: false,
    loading: () => (
      <div className="h-[28rem] w-full rounded-xl border border-slate-100 bg-white shadow-[0_12px_40px_rgba(25,28,30,0.04)] animate-pulse" />
    ),
  },
);

export function FinOpsChartLazy(props: FinOpsChartProps) {
  return <FinOpsChart {...props} />;
}
