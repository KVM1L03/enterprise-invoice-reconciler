"use client";

import { AlertTriangle, Inbox, Loader2, Trash2 } from "lucide-react";

import type { Invoice } from "@prisma/client";
import type { RecentBatch, ReviewTarget, WorkflowResult } from "@/types";

import { Pagination } from "./Pagination";
import { ResultsTable } from "./ResultsTable";
import { StatusBadge } from "./StatusBadge";

const CARD_SHADOW = "shadow-[0_12px_40px_rgba(25,28,30,0.04)]";

function batchToWorkflowResult(batch: RecentBatch): WorkflowResult {
  const result: WorkflowResult = {};
  batch.invoices.forEach((inv: Invoice, idx: number) => {
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
  onReview: (row: ReviewTarget) => void;
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
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
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
  currentPage,
  totalPages,
  onPageChange,
  onReview,
  onClearHistory,
}: BatchTableProps) {
  const showHistory = !polling && !result && recentBatches.length > 0;
  const showEmpty =
    !polling && !result && recentBatches.length === 0 && !error;

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
        {showHistory && (
          <BatchHistoryList batches={recentBatches} onReview={onReview} />
        )}
        {showEmpty && <EmptyState />}

        {showHistory && totalPages > 1 && (
          <div className="px-6 py-4 bg-slate-50/30 border-t border-slate-50">
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={onPageChange}
              disabled={polling}
            />
          </div>
        )}
      </div>
    </>
  );
}
