import type { Batch, Invoice } from "@prisma/client";

/** Single invoice row from reconciliation API or persisted DB. */
export type InvoiceResult = {
  id?: string;
  invoice_id?: string;
  status: string;
  reason?: string;
  erp_expected_amount?: number | null;
  error?: string;
};

export type WorkflowResult = Record<string, InvoiceResult>;

export type ReviewTarget = InvoiceResult & { id: string };

export type PollResponse = {
  status: string;
  result?: WorkflowResult;
  message?: string;
};

export type UploadToast = { kind: "success" | "error"; message: string };

export type UploadInvoicesResponse = {
  count: number;
  files: string[];
};

export type SaveBatchResponse = {
  ok: boolean;
  batchId?: string;
  error?: string;
};

export type DashboardStats = {
  batchCount: number;
  totalInvoices: number;
  approvedInvoices: number;
  successRatePct: string;
  pendingReviews: number;
};

export type OverrideStatus = "FORCE_APPROVED" | "REJECTED";

export type OverrideResponse = { ok: boolean; error?: string };

export type RecentBatch = Batch & { invoices: Invoice[] };

export type PaginatedBatches = {
  batches: RecentBatch[];
  totalPages: number;
  currentPage: number;
};

export type FinOpsDailyPoint = {
  date: string;
  apiCostUsd: number;
  invoicesProcessed: number;
};

export type FinOpsSummaryStats = {
  totalApiCostUsd: number;
  totalInvoicesProcessed: number;
  hoursSaved: number;
  laborSavingsUsd: number;
  costPerInvoiceUsd: number;
};
