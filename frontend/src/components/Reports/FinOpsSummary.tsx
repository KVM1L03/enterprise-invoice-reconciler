import { Clock, DollarSign, FileText, Wallet } from "lucide-react";

import { StatCard } from "@/components/shared/StatCard";
import type { FinOpsSummaryStats } from "@/types";

export type FinOpsSummaryProps = {
  stats: FinOpsSummaryStats;
};

function formatUsd(value: number): string {
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatHours(value: number): string {
  return `${value.toLocaleString("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}h`;
}

export function FinOpsSummary({ stats }: FinOpsSummaryProps) {
  const roiMultiplier =
    stats.totalApiCostUsd > 0
      ? (stats.laborSavingsUsd / stats.totalApiCostUsd).toFixed(1)
      : "∞";

  return (
    <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <StatCard
        label="Total API Spend"
        value={formatUsd(stats.totalApiCostUsd)}
        icon={DollarSign}
        trend={{ direction: "up", label: "+8.4% WoW" }}
        footer={
          <div className="text-xs text-slate-500">
            {formatUsd(stats.costPerInvoiceUsd)} per invoice
          </div>
        }
      />
      <StatCard
        label="Invoices Processed"
        value={stats.totalInvoicesProcessed.toLocaleString("en-US")}
        icon={FileText}
        trend={{ direction: "up", label: "+12.1% WoW" }}
        footer={
          <div className="text-xs text-slate-500">
            Across 7 days of operations
          </div>
        }
      />
      <StatCard
        label="Manual Hours Saved"
        value={formatHours(stats.hoursSaved)}
        icon={Clock}
        trend={{ direction: "up", label: "+12.1% WoW" }}
        footer={
          <div className="text-xs text-[#00502e] font-medium">
            vs. manual reconciliation baseline
          </div>
        }
      />
      <StatCard
        label="Labor Savings"
        value={formatUsd(stats.laborSavingsUsd)}
        icon={Wallet}
        trend={{ direction: "up", label: `${roiMultiplier}x ROI on AI` }}
        footer={
          <div className="text-xs text-slate-500">
            @ $35/h accountant rate
          </div>
        }
      />
    </section>
  );
}
