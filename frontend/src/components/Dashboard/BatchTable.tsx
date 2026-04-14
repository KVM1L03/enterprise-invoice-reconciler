"use client";

import {
  AlertTriangle,
  Eye,
  FileText,
  Inbox,
  Loader2,
  Search,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";

import type { RecentBatch, ReviewTarget, WorkflowResult } from "@/types";

const CARD_SHADOW = "shadow-[0_12px_40px_rgba(25,28,30,0.04)]";

const STATUS_STYLES: Record<string, string> = {
  APPROVED: "bg-[#9df5bd] text-[#00522f]",
  FORCE_APPROVED: "bg-[#9df5bd] text-[#00522f]",
  DISCREPANCY: "bg-[#ffdad6] text-[#93000a]",
  HUMAN_REVIEW_NEEDED: "bg-[#ffdad6] text-[#93000a]",
  SYSTEM_ERROR: "bg-[#ffdad6] text-[#93000a]",
  FAILED: "bg-[#ffdad6] text-[#93000a]",
  REJECTED: "bg-[#ffdad6] text-[#93000a]",
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700";
  return (
    <span
      className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-tight ${cls}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

type ResultsTableProps = {
  result: WorkflowResult;
  onReview?: (row: ReviewTarget) => void;
};

function ResultsTable({ result, onReview }: ResultsTableProps) {
  const rows = Object.entries(result);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="bg-[#f2f4f6]">
            <th className="px-6 py-3 text-[0.7rem] font-bold text-slate-500 uppercase tracking-wider">
              Invoice
            </th>
            <th className="px-6 py-3 text-[0.7rem] font-bold text-slate-500 uppercase tracking-wider text-right">
              Expected Amount
            </th>
            <th className="px-6 py-3 text-[0.7rem] font-bold text-slate-500 uppercase tracking-wider text-center">
              Status
            </th>
            <th className="px-6 py-3 text-[0.7rem] font-bold text-slate-500 uppercase tracking-wider">
              Reason
            </th>
            {onReview && (
              <th className="px-6 py-3 text-[0.7rem] font-bold text-slate-500 uppercase tracking-wider text-center">
                Actions
              </th>
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {rows.map(([key, data]) => (
            <tr key={key} className="hover:bg-slate-50/50 transition-colors">
              <td className="px-6 py-4">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded bg-[#9df5bd] flex items-center justify-center shrink-0">
                    <FileText className="h-4 w-4 text-[#00522f]" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#191c1e] truncate">
                      {data.invoice_id ?? key.replace(/_/g, " ").toUpperCase()}
                    </div>
                    {data.invoice_id && (
                      <div className="text-[10px] text-slate-400 font-mono uppercase tracking-widest">
                        {key.replace(/_/g, " ")}
                      </div>
                    )}
                  </div>
                </div>
              </td>
              <td className="px-6 py-4 text-right text-sm font-medium text-slate-700 font-mono">
                {data.erp_expected_amount != null
                  ? `$${data.erp_expected_amount.toLocaleString("en-US", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}`
                  : "—"}
              </td>
              <td className="px-6 py-4 text-center">
                <StatusBadge status={data.status} />
              </td>
              <td className="px-6 py-4 text-sm text-slate-600 max-w-xs">
                {data.reason ?? data.error ?? (
                  <span className="text-slate-400 italic">—</span>
                )}
              </td>
              {onReview && (
                <td className="px-6 py-4 text-center">
                  {data.status === "DISCREPANCY" && data.id ? (
                    <button
                      type="button"
                      onClick={() =>
                        onReview({ ...data, id: data.id as string })
                      }
                      className="inline-flex items-center gap-1.5 rounded-md bg-[#00502e] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-white hover:bg-[#006b3f] transition-colors"
                    >
                      <Eye className="h-3 w-3" />
                      Review
                    </button>
                  ) : (
                    <span className="text-slate-300">—</span>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function batchToWorkflowResult(batch: RecentBatch): WorkflowResult {
  const result: WorkflowResult = {};
  batch.invoices.forEach((inv, idx) => {
    result[`invoice_${idx}`] = {
      id: inv.id,
      invoice_id: inv.invoiceId,
      status: inv.status,
      reason: inv.reason || undefined,
      erp_expected_amount: inv.expectedAmount,
    };
  });
  return result;
}

type BatchHistoryListProps = {
  batches: RecentBatch[];
  onReview?: (row: ReviewTarget) => void;
};

function BatchHistoryList({ batches, onReview }: BatchHistoryListProps) {
  return (
    <div className="divide-y divide-slate-100">
      {batches.map((batch) => (
        <div key={batch.id} className="px-6 py-5">
          <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="text-[10px] font-mono text-slate-400 uppercase tracking-widest">
                {batch.workflowId}
              </div>
              <StatusBadge status={batch.status} />
            </div>
            <div className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
              {new Date(batch.createdAt).toLocaleString()}
            </div>
          </div>
          <div className="rounded-lg overflow-hidden border border-slate-100">
            <ResultsTable
              result={batchToWorkflowResult(batch)}
              onReview={onReview}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="p-12">
      <div className="flex flex-col items-center justify-center gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-[#00502e]" />
        <div className="text-center">
          <p className="text-sm font-semibold text-[#191c1e]">
            Processing invoices
          </p>
          <p className="mt-1 text-xs text-[#3f4941]">
            Running DSPy extraction and ERP verification…
          </p>
        </div>
        <div className="w-full max-w-md space-y-2 mt-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-10 rounded-lg bg-[#f2f4f6] animate-pulse"
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="p-12 text-center">
      <Inbox className="mx-auto h-10 w-10 text-slate-300" />
      <p className="mt-3 text-sm font-semibold text-[#191c1e]">
        No batches yet
      </p>
      <p className="mt-1 text-xs text-[#3f4941] max-w-sm mx-auto">
        Upload PDFs above and click{" "}
        <span className="font-semibold text-[#00502e]">
          Scan &amp; Process Directory
        </span>{" "}
        to reconcile.
      </p>
    </div>
  );
}

export type BatchTableProps = {
  polling: boolean;
  result: WorkflowResult | null;
  recentBatches: RecentBatch[];
  error: string | null;
  workflowId: string | null;
  status: string | null;
  onReview: (row: ReviewTarget) => void;
  onClearHistory: () => void;
};

export function BatchTable({
  polling,
  result,
  recentBatches,
  error,
  workflowId,
  status,
  onReview,
  onClearHistory,
}: BatchTableProps) {
  return (
    <>
      {workflowId && (
        <div className="flex items-center gap-2 text-xs text-[#3f4941] font-mono -mt-4">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#00502e] animate-pulse" />
          Workflow ID: {workflowId}
          {status && !result && <span>· Status: {status}</span>}
        </div>
      )}

      {error && (
        <div className="bg-[#ffdad6] text-[#93000a] rounded-md p-4 text-sm">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-4 w-4" />
            Error
          </div>
          <div className="mt-1 font-mono text-xs">{error}</div>
        </div>
      )}

      <div
        className={`bg-white rounded-xl ${CARD_SHADOW} border border-slate-100 overflow-hidden`}
      >
        <div className="px-6 py-5 border-b border-slate-50 flex justify-between items-center">
          <h3 className="text-base font-semibold text-[#191c1e]">
            Recent Batch Results
          </h3>
          <div className="flex items-center gap-3">
            {result && (
              <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
                {Object.keys(result).length} invoice
                {Object.keys(result).length !== 1 ? "s" : ""}
              </span>
            )}
            <SlidersHorizontal className="h-4 w-4 text-slate-400 cursor-pointer hover:text-[#00502e] transition-colors" />
            <Search className="h-4 w-4 text-slate-400 cursor-pointer hover:text-[#00502e] transition-colors" />
            <button
              type="button"
              onClick={onClearHistory}
              disabled={polling || recentBatches.length === 0}
              title="Clear batch history"
              className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 hover:text-[#ba1a1a] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Clear History
            </button>
          </div>
        </div>

        {polling && <LoadingSkeleton />}
        {!polling && result && <ResultsTable result={result} />}
        {!polling && !result && recentBatches.length > 0 && (
          <BatchHistoryList batches={recentBatches} onReview={onReview} />
        )}
        {!polling && !result && recentBatches.length === 0 && !error && (
          <EmptyState />
        )}

        {result && (
          <div className="px-6 py-4 bg-slate-50/30 flex justify-center border-t border-slate-50">
            <button
              type="button"
              className="text-[#00502e] text-xs font-bold hover:underline tracking-widest uppercase"
            >
              View All Transactions
            </button>
          </div>
        )}
      </div>
    </>
  );
}
