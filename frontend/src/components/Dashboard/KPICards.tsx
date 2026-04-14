"use client";

import { CheckCircle2 } from "lucide-react";

import type { DashboardStats } from "@/types";

const CARD_SHADOW = "shadow-[0_12px_40px_rgba(25,28,30,0.04)]";

type KpiCardProps = {
  label: string;
  value: string;
  accent?: "primary" | "error";
  footer?: React.ReactNode;
};

function KpiCard({ label, value, accent = "primary", footer }: KpiCardProps) {
  const valueColor = accent === "error" ? "text-[#ba1a1a]" : "text-[#00502e]";
  return (
    <div
      className={`bg-white rounded-xl ${CARD_SHADOW} border border-slate-100 p-6 flex flex-col gap-1`}
    >
      <span className="text-[0.7rem] font-medium text-slate-500 uppercase tracking-[0.15em]">
        {label}
      </span>
      <span
        className={`text-[3.25rem] font-bold ${valueColor} leading-none mt-2 tracking-tight`}
      >
        {value}
      </span>
      <div className="mt-4">{footer}</div>
    </div>
  );
}

export type KPICardsProps = {
  batchesLabel: string;
  dashboardStats: DashboardStats | null;
  successRateDisplay: string;
  pendingDisplay: number;
  successBarWidth: number;
};

/** Top statistics row — presentational only (values computed by parent). */
export function KPICards({
  batchesLabel,
  dashboardStats,
  successRateDisplay,
  pendingDisplay,
  successBarWidth,
}: KPICardsProps) {
  return (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
      <KpiCard
        label="Batches Processed"
        value={batchesLabel}
        footer={
          <div className="text-xs text-slate-500">
            {dashboardStats == null && batchesLabel === "—" ? (
              <span className="text-slate-400">Loading…</span>
            ) : dashboardStats && dashboardStats.totalInvoices > 0 ? (
              <span>
                {dashboardStats.totalInvoices} invoice
                {dashboardStats.totalInvoices !== 1 ? "s" : ""} recorded
              </span>
            ) : (
              <span>No batches persisted yet</span>
            )}
          </div>
        }
      />
      <KpiCard
        label="Success Rate"
        value={`${successRateDisplay}%`}
        footer={
          <div className="w-full bg-[#f2f4f6] h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-[#00502e] h-full transition-all duration-500"
              style={{ width: `${successBarWidth}%` }}
            />
          </div>
        }
      />
      <KpiCard
        label="Pending Reviews"
        value={String(pendingDisplay)}
        accent={pendingDisplay > 0 ? "error" : "primary"}
        footer={
          pendingDisplay > 0 ? (
            <div className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-[#ba1a1a] animate-pulse" />
              <span className="text-xs text-[#ba1a1a] font-medium">
                Invoices needing follow-up
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-3 w-3 text-[#00502e]" />
              <span className="text-xs text-[#00502e] font-medium">
                No pending review queue
              </span>
            </div>
          )
        }
      />
    </section>
  );
}
