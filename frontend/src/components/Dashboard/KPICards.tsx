import { CheckCircle2 } from "lucide-react";

import { StatCard } from "@/components/shared/StatCard";
import type { DashboardStats } from "@/types";

export type KPICardsProps = {
  batchesLabel: string;
  dashboardStats: DashboardStats | null;
  successRateDisplay: string;
  pendingDisplay: number;
  successBarWidth: number;
};

export function KPICards({
  batchesLabel,
  dashboardStats,
  successRateDisplay,
  pendingDisplay,
  successBarWidth,
}: KPICardsProps) {
  return (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
      <StatCard
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
      <StatCard
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
      <StatCard
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
