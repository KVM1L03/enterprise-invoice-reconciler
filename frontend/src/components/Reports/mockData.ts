import type { FinOpsDailyPoint, FinOpsSummaryStats } from "@/types";

const MINUTES_PER_INVOICE_MANUAL = 5;
const ACCOUNTANT_HOURLY_RATE_USD = 35;

export const finOpsMockData: FinOpsDailyPoint[] = [
  { date: "Mon", apiCostUsd: 0.62, invoicesProcessed: 78 },
  { date: "Tue", apiCostUsd: 1.15, invoicesProcessed: 142 },
  { date: "Wed", apiCostUsd: 1.84, invoicesProcessed: 203 },
  { date: "Thu", apiCostUsd: 0.97, invoicesProcessed: 121 },
  { date: "Fri", apiCostUsd: 2.31, invoicesProcessed: 248 },
  { date: "Sat", apiCostUsd: 0.54, invoicesProcessed: 56 },
  { date: "Sun", apiCostUsd: 1.42, invoicesProcessed: 167 },
];

export function calculateHoursSaved(invoicesProcessed: number): number {
  return (invoicesProcessed * MINUTES_PER_INVOICE_MANUAL) / 60;
}

export function calculateLaborSavingsUsd(hoursSaved: number): number {
  return hoursSaved * ACCOUNTANT_HOURLY_RATE_USD;
}

export function summarizeFinOps(
  data: FinOpsDailyPoint[],
): FinOpsSummaryStats {
  const totalApiCostUsd = data.reduce((sum, d) => sum + d.apiCostUsd, 0);
  const totalInvoicesProcessed = data.reduce(
    (sum, d) => sum + d.invoicesProcessed,
    0,
  );
  const hoursSaved = calculateHoursSaved(totalInvoicesProcessed);
  const laborSavingsUsd = calculateLaborSavingsUsd(hoursSaved);
  const costPerInvoiceUsd =
    totalInvoicesProcessed > 0 ? totalApiCostUsd / totalInvoicesProcessed : 0;

  return {
    totalApiCostUsd,
    totalInvoicesProcessed,
    hoursSaved,
    laborSavingsUsd,
    costPerInvoiceUsd,
  };
}
