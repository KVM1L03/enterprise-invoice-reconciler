"use server";

import { prisma } from "@/lib/prisma";

type InvoiceResultPayload = {
  invoice_id?: string;
  status: string;
  reason?: string;
  erp_expected_amount?: number | null;
  error?: string;
};

export type WorkflowResult = Record<string, InvoiceResultPayload>;

export type SaveBatchResponse = {
  ok: boolean;
  batchId?: string;
  error?: string;
};

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

export async function getRecentBatches() {
  return prisma.batch.findMany({
    take: 5,
    orderBy: { createdAt: "desc" },
    include: { invoices: true },
  });
}

export type DashboardStats = {
  batchCount: number;
  totalInvoices: number;
  approvedInvoices: number;
  successRatePct: string;
  pendingReviews: number;
};

/** Aggregate KPIs from all persisted batches (survives page refresh). */
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
