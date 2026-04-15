import type { Metadata } from "next";

import { FinOpsChartLazy } from "@/components/Reports/FinOpsChartLazy";
import { FinOpsSummary } from "@/components/Reports/FinOpsSummary";
import { ReportHeader } from "@/components/Reports/ReportHeader";
import {
  finOpsMockData,
  summarizeFinOps,
} from "@/components/Reports/mockData";

export const metadata: Metadata = {
  title: "Reports — FinOps & Telemetry",
  description: "LLM FinOps telemetry: API spend vs. manual labor savings",
};

export default function ReportsPage() {
  const stats = summarizeFinOps(finOpsMockData);

  return (
    <div className="bg-[#f7f9fb] min-h-full text-[#191c1e] font-['Inter',system-ui,sans-serif]">
      <div className="px-10 py-10 max-w-[1600px] mx-auto">
        <ReportHeader
          title="FinOps & Telemetry"
          description="LLM cost observability and ROI analysis. Track API spend against automation savings to validate the AI pipeline's business impact."
        />

        <section className="space-y-8">
          <FinOpsSummary stats={stats} />
          <FinOpsChartLazy data={finOpsMockData} />
        </section>
      </div>
    </div>
  );
}
