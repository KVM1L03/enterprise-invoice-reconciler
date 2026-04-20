"use server";

import { prisma } from "@/lib/prisma";
import type {
  DashboardStats,
  FinOpsDailyPoint,
  OverrideResponse,
  OverrideStatus,
  PaginatedBatches,
  SaveBatchResponse,
  WorkflowResult,
} from "@/types";
import { finOpsMockData } from "@/components/Reports/mockData";

export type {
  DashboardStats,
  FinOpsDailyPoint,
  OverrideResponse,
  OverrideStatus,
  PaginatedBatches,
  SaveBatchResponse,
  WorkflowResult,
} from "@/types";

export async function saveBatchResult(
  workflowId: string,
  resultData: WorkflowResult,
): Promise<SaveBatchResponse> {
  const entries = Object.entries(resultData);

  const statuses = entries.map(([, v]) => v.status);
  const batchStatus = statuses.every((s) => s === "APPROVED")
    ? "APPROVED"
    : statuses.some((s) => s === "SYSTEM_ERROR")
      ? "PARTIAL"
      : "MIXED";

  try {
    const batch = await prisma.batch.create({
      data: {
        workflowId,
        status: batchStatus,
        invoices: {
          create: entries.map(([key, inv]) => ({
            invoiceId: inv.invoice_id ?? key,
            status: inv.status,
            expectedAmount: inv.erp_expected_amount ?? null,
            reason: inv.reason ?? inv.error ?? "",
          })),
        },
      },
    });
    return { ok: true, batchId: batch.id };
  } catch (err) {
    if (err instanceof Error && err.message.includes("Unique constraint")) {
      return { ok: true };
    }
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Unknown DB error",
    };
  }
}

export async function getRecentBatches(
  page: number = 1,
  pageSize: number = 1,
): Promise<PaginatedBatches> {
  const safePage = Math.max(1, Math.floor(page));
  const safePageSize = Math.max(1, Math.floor(pageSize));

  const [totalCount, batches] = await Promise.all([
    prisma.batch.count(),
    prisma.batch.findMany({
      skip: (safePage - 1) * safePageSize,
      take: safePageSize,
      orderBy: { createdAt: "desc" },
      include: { invoices: true },
    }),
  ]);

  const totalPages = totalCount === 0 ? 0 : Math.ceil(totalCount / safePageSize);
  const currentPage = totalPages === 0 ? 1 : Math.min(safePage, totalPages);

  return { batches, totalPages, currentPage };
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const [batchCount, grouped] = await Promise.all([
    prisma.batch.count(),
    prisma.invoice.groupBy({
      by: ["status"],
      _count: { _all: true },
    }),
  ]);

  const counts: Record<string, number> = {};
  for (const row of grouped) {
    counts[row.status] = row._count._all;
  }

  const totalInvoices = Object.values(counts).reduce((a, b) => a + b, 0);
  const approvedInvoices = counts["APPROVED"] ?? 0;
  const successRatePct =
    totalInvoices > 0
      ? ((approvedInvoices / totalInvoices) * 100).toFixed(1)
      : "0.0";

  const pendingReviews =
    (counts["DISCREPANCY"] ?? 0) +
    (counts["HUMAN_REVIEW_NEEDED"] ?? 0) +
    (counts["FAILED"] ?? 0);

  return {
    batchCount,
    totalInvoices,
    approvedInvoices,
    successRatePct,
    pendingReviews,
  };
}

export async function overrideInvoiceStatus(
  invoiceId: string,
  newStatus: OverrideStatus,
): Promise<OverrideResponse> {
  try {
    await prisma.invoice.update({
      where: { id: invoiceId },
      data: { status: newStatus },
    });
    return { ok: true };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Unknown DB error",
    };
  }
}

export async function clearAllBatches(): Promise<{
  ok: boolean;
  error?: string;
}> {
  try {
    await prisma.invoice.deleteMany({});
    await prisma.batch.deleteMany({});
    return { ok: true };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Unknown DB error",
    };
  }
}

const API_GATEWAY_URL =
  process.env.API_GATEWAY_URL ?? "http://localhost:8000";

export async function getFinOpsTelemetry(
  days: number = 7,
): Promise<FinOpsDailyPoint[]> {
  try {
    const res = await fetch(
      `${API_GATEWAY_URL}/telemetry/finops?days=${days}`,
      { signal: AbortSignal.timeout(2000), cache: "no-store" },
    );
    if (!res.ok) {
      console.error(
        `[getFinOpsTelemetry] Backend returned ${res.status}: ${res.statusText}`,
      );
      return finOpsMockData;
    }
    return (await res.json()) as FinOpsDailyPoint[];
  } catch (err) {
    console.error("[getFinOpsTelemetry] Falling back to mock data:", err);
    return finOpsMockData;
  }
}
