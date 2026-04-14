"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Inbox,
  XCircle,
  Upload,
  Paperclip,
  FileText,
  FolderOpen,
  History,
  Search,
  SlidersHorizontal,
  Activity,
  LifeBuoy,
} from "lucide-react";
import {
  getDashboardStats,
  getRecentBatches,
  saveBatchResult,
  type DashboardStats,
} from "@/app/actions";

const API = "http://localhost:8000";

type RecentBatch = Awaited<ReturnType<typeof getRecentBatches>>[number];

// ---------- Editorial Enterprise palette (Stitch "Corporate Dashboard Redesign") ----------
// Primary: #00502e, primary-container: #006b3f, primary-fixed: #9df5bd
// Surface: #f7f9fb, surface-container-low: #f2f4f6, surface-container-lowest: #ffffff
// on-surface: #191c1e, on-surface-variant: #3f4941
// error: #ba1a1a, error-container: #ffdad6, on-error-container: #93000a

const CARD_SHADOW = "shadow-[0_12px_40px_rgba(25,28,30,0.04)]";

type InvoiceResult = {
  invoice_id?: string;
  status: string;
  reason?: string;
  erp_expected_amount?: number | null;
  error?: string;
};

type WorkflowResult = Record<string, InvoiceResult>;

type PollResponse = {
  status: string;
  result?: WorkflowResult;
  message?: string;
};

type UploadToast = { kind: "success" | "error"; message: string };

// ---------- KPI Card (Editorial "Display-lg" numerics) ----------

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

// ---------- Status Badge (Editorial pill) ----------

const STATUS_STYLES: Record<string, string> = {
  APPROVED: "bg-[#9df5bd] text-[#00522f]",
  DISCREPANCY: "bg-[#ffdad6] text-[#93000a]",
  HUMAN_REVIEW_NEEDED: "bg-[#ffdad6] text-[#93000a]",
  SYSTEM_ERROR: "bg-[#ffdad6] text-[#93000a]",
  FAILED: "bg-[#ffdad6] text-[#93000a]",
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

// ---------- Results Table (Editorial Ledger) ----------

function ResultsTable({ result }: { result: WorkflowResult }) {
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
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {rows.map(([key, data]) => (
            <tr
              key={key}
              className="hover:bg-slate-50/50 transition-colors"
            >
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------- Batch History (persisted in Postgres via Prisma) ----------

function batchToWorkflowResult(batch: RecentBatch): WorkflowResult {
  const result: WorkflowResult = {};
  batch.invoices.forEach((inv, idx) => {
    result[`invoice_${idx}`] = {
      invoice_id: inv.invoiceId,
      status: inv.status,
      reason: inv.reason || undefined,
      erp_expected_amount: inv.expectedAmount,
    };
  });
  return result;
}

function BatchHistoryList({ batches }: { batches: RecentBatch[] }) {
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
            <ResultsTable result={batchToWorkflowResult(batch)} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------- Loading Skeleton ----------

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

// ---------- Empty State ----------

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

// ---------- Main Dashboard ----------

export default function DashboardPage() {
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadToast, setUploadToast] = useState<UploadToast | null>(null);
  const [recentBatches, setRecentBatches] = useState<RecentBatch[]>([]);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(
    null,
  );
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const reloadPersistedDashboard = useCallback(async () => {
    try {
      const [batches, stats] = await Promise.all([
        getRecentBatches(),
        getDashboardStats(),
      ]);
      setRecentBatches(batches);
      setDashboardStats(stats);
    } catch (err) {
      console.error("Failed to load batch history:", err);
    }
  }, []);

  useEffect(() => {
    void reloadPersistedDashboard();
  }, [reloadPersistedDashboard]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setPolling(false);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    setSelectedFiles(Array.from(files));
    setUploadToast(null);
  };

  const clearSelection = () => {
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const uploadFiles = async () => {
    if (selectedFiles.length === 0) return;
    setUploading(true);
    setUploadToast(null);

    try {
      const formData = new FormData();
      for (const file of selectedFiles) {
        formData.append("files", file);
      }

      const res = await fetch(`${API}/upload-invoices`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}: ${detail}`);
      }

      const data: { count: number; files: string[] } = await res.json();
      setUploadToast({
        kind: "success",
        message: `Uploaded ${data.count} file${data.count !== 1 ? "s" : ""} successfully.`,
      });
      clearSelection();
    } catch (err) {
      setUploadToast({
        kind: "error",
        message: err instanceof Error ? err.message : "Upload failed",
      });
    } finally {
      setUploading(false);
    }
  };

  useEffect(() => {
    if (!uploadToast) return;
    const t = setTimeout(() => setUploadToast(null), 4000);
    return () => clearTimeout(t);
  }, [uploadToast]);

  const startBatch = async () => {
    setError(null);
    setResult(null);
    setStatus(null);
    stopPolling();

    try {
      const res = await fetch(`${API}/reconcile-batch`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setWorkflowId(data.workflow_id);
      setStatus("RUNNING");
      setPolling(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start batch");
    }
  };

  useEffect(() => {
    if (!polling || !workflowId) return;

    const poll = async () => {
      try {
        const res = await fetch(`${API}/status/${workflowId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: PollResponse = await res.json();
        setStatus(data.status);

        if (data.status === "COMPLETED" && data.result) {
          setResult(data.result);
          stopPolling();
          if (workflowId) {
            const saveRes = await saveBatchResult(workflowId, data.result);
            if (saveRes.ok) {
              await reloadPersistedDashboard();
            } else {
              console.error("Failed to persist batch:", saveRes.error);
            }
          }
        } else if (data.status === "FAILED") {
          setError(data.message ?? "Workflow failed");
          stopPolling();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Polling error");
        stopPolling();
      }
    };

    intervalRef.current = setInterval(poll, 2000);
    return () => stopPolling();
  }, [polling, workflowId, stopPolling, reloadPersistedDashboard]);

  // KPIs: primary source = Prisma (survives refresh). While a run finishes, overlay success/pending from live `result` until DB reload.
  const resultEntries = result ? Object.values(result) : [];
  const liveApproved = resultEntries.filter((r) => r.status === "APPROVED").length;
  const liveTotal = resultEntries.length;
  const liveSuccessPct =
    liveTotal > 0 ? ((liveApproved / liveTotal) * 100).toFixed(1) : null;
  const livePending = resultEntries.filter(
    (r) => r.status !== "APPROVED" && r.status !== "SYSTEM_ERROR",
  ).length;

  const batchesLabel =
    dashboardStats == null ? "—" : String(dashboardStats.batchCount);
  const successRateDisplay =
    liveSuccessPct ??
    (dashboardStats != null ? dashboardStats.successRatePct : "0.0");
  const pendingDisplay =
    liveTotal > 0 ? livePending : (dashboardStats?.pendingReviews ?? 0);
  const successBarWidth = Math.min(
    100,
    Math.max(0, parseFloat(successRateDisplay) || 0),
  );

  return (
    <div className="bg-[#f7f9fb] min-h-full text-[#191c1e] font-['Inter',system-ui,sans-serif]">
      <div className="px-10 py-10 max-w-[1600px] mx-auto">
        {/* Header — editorial asymmetry */}
        <header className="mb-10 flex justify-between items-end gap-6 flex-wrap">
          <div className="max-w-2xl">
            <h1 className="text-[1.75rem] font-semibold text-[#191c1e] tracking-tight leading-tight">
              Invoice Reconciliation Hub
            </h1>
            <p className="text-[#3f4941] mt-2 text-sm max-w-lg leading-relaxed">
              Centralized oversight for cross-referencing ledger entries
              against vendor documentation. Maintain accuracy and integrity
              in your financial pipeline.
            </p>
          </div>
          <button
            onClick={startBatch}
            disabled={polling}
            className="bg-gradient-to-r from-[#00502e] to-[#006b3f] text-white px-6 py-2.5 rounded-md text-sm font-semibold flex items-center gap-2 shadow-md hover:shadow-lg disabled:opacity-60 disabled:cursor-not-allowed transition-all whitespace-nowrap"
          >
            {polling ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Processing…
              </>
            ) : (
              <>
                <FolderOpen className="h-4 w-4" />
                Scan &amp; Process Directory
              </>
            )}
          </button>
        </header>

        {/* KPI Row — Tonal Layering with dramatic display numerics */}
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

        {/* Asymmetric 12-column split: main (8) + aside (4) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* --- Main column (8) --- */}
          <section className="lg:col-span-8 space-y-8">
            {/* Upload Card */}
            <div
              className={`bg-white rounded-xl ${CARD_SHADOW} border border-slate-100 p-6`}
            >
              <div className="flex items-start gap-3 mb-5">
                <div className="rounded-lg bg-[#9df5bd] p-2 flex items-center justify-center">
                  <Upload className="h-5 w-5 text-[#00522f]" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-[#191c1e]">
                    Upload Invoices
                  </h2>
                  <p className="mt-0.5 text-xs text-[#3f4941]">
                    Drop PDF files into the processing queue before running
                    the batch.
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,application/pdf"
                  onChange={handleFileChange}
                  className="hidden"
                  id="invoice-upload-input"
                />
                <label
                  htmlFor="invoice-upload-input"
                  className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-[#e6e8ea] px-4 py-2.5 text-sm font-semibold text-[#191c1e] hover:bg-[#dcdedf] transition-colors whitespace-nowrap"
                >
                  <Paperclip className="h-4 w-4" />
                  Select PDFs
                </label>

                <button
                  onClick={uploadFiles}
                  disabled={
                    selectedFiles.length === 0 || uploading || polling
                  }
                  className="inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-[#00502e] to-[#006b3f] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-all whitespace-nowrap"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Uploading…
                    </>
                  ) : (
                    <>
                      <Upload className="h-4 w-4" />
                      Upload Selected Invoices
                    </>
                  )}
                </button>

                {selectedFiles.length > 0 && !uploading && (
                  <button
                    onClick={clearSelection}
                    className="text-xs font-medium text-slate-500 hover:text-[#00502e] underline underline-offset-2"
                  >
                    Clear
                  </button>
                )}
              </div>

              {selectedFiles.length > 0 && (
                <div className="mt-4 rounded-lg bg-[#f2f4f6] p-3">
                  <p className="text-[0.7rem] font-bold text-slate-500 uppercase tracking-wider mb-2">
                    {selectedFiles.length} file
                    {selectedFiles.length !== 1 ? "s" : ""} selected
                  </p>
                  <ul className="space-y-1">
                    {selectedFiles.slice(0, 3).map((file, idx) => (
                      <li
                        key={`${file.name}-${idx}`}
                        className="flex items-center gap-2 text-xs text-slate-700 font-mono"
                      >
                        <FileText className="h-3 w-3 text-slate-400 shrink-0" />
                        <span className="truncate">{file.name}</span>
                        <span className="text-slate-400 shrink-0">
                          {(file.size / 1024).toFixed(1)} KB
                        </span>
                      </li>
                    ))}
                    {selectedFiles.length > 3 && (
                      <li className="text-xs text-slate-500 italic pl-5">
                        +{selectedFiles.length - 3} more…
                      </li>
                    )}
                  </ul>
                </div>
              )}

              {uploadToast && (
                <div
                  className={`mt-4 rounded-md p-3 text-sm ${
                    uploadToast.kind === "success"
                      ? "bg-[#9df5bd] text-[#00522f]"
                      : "bg-[#ffdad6] text-[#93000a]"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {uploadToast.kind === "success" ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <XCircle className="h-4 w-4" />
                    )}
                    <span className="font-semibold">{uploadToast.message}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Workflow ID strip */}
            {workflowId && (
              <div className="flex items-center gap-2 text-xs text-[#3f4941] font-mono -mt-4">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#00502e] animate-pulse" />
                Workflow ID: {workflowId}
                {status && !result && <span>· Status: {status}</span>}
              </div>
            )}

            {/* Error strip */}
            {error && (
              <div className="bg-[#ffdad6] text-[#93000a] rounded-md p-4 text-sm">
                <div className="flex items-center gap-2 font-semibold">
                  <AlertTriangle className="h-4 w-4" />
                  Error
                </div>
                <div className="mt-1 font-mono text-xs">{error}</div>
              </div>
            )}

            {/* Results Table Card */}
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
                </div>
              </div>

              {polling && <LoadingSkeleton />}
              {!polling && result && <ResultsTable result={result} />}
              {!polling && !result && recentBatches.length > 0 && (
                <BatchHistoryList batches={recentBatches} />
              )}
              {!polling && !result && recentBatches.length === 0 && !error && (
                <EmptyState />
              )}

              {result && (
                <div className="px-6 py-4 bg-slate-50/30 flex justify-center border-t border-slate-50">
                  <button className="text-[#00502e] text-xs font-bold hover:underline tracking-widest uppercase">
                    View All Transactions
                  </button>
                </div>
              )}
            </div>
          </section>

          {/* --- Aside column (4) --- */}
          <aside className="lg:col-span-4 space-y-6">
            {/* Processing Health — Primary green hero card */}
            <div className="bg-gradient-to-br from-[#00502e] to-[#006b3f] text-white p-6 rounded-xl shadow-lg relative overflow-hidden group">
              <div className="absolute -right-6 -top-6 w-36 h-36 bg-white/10 rounded-full blur-2xl group-hover:bg-white/20 transition-colors pointer-events-none" />
              <div className="relative">
                <h4 className="text-[0.7rem] font-semibold uppercase tracking-[0.15em] text-[#9df5bd]">
                  Pipeline Health
                </h4>
                <div className="mt-4 flex items-end gap-2">
                  <span className="text-3xl font-bold">
                    {polling
                      ? "Running"
                      : error
                        ? "Degraded"
                        : "Stable"}
                  </span>
                  <span className="text-[#9df5bd]/80 text-xs pb-1">
                    {polling ? "Workflow active" : "Normal volume"}
                  </span>
                </div>
                <p className="mt-4 text-sm text-[#9df5bd] opacity-90 leading-relaxed">
                  {error
                    ? "Reconciliation encountered an issue. Review error log."
                    : "System is performing within optimal parameters. DSPy extraction and ERP verification pipelines nominal."}
                </p>
                <div className="mt-5 flex items-center gap-2 text-xs text-[#9df5bd]/90">
                  <Activity className="h-3.5 w-3.5" />
                  <span className="font-mono">
                    {polling ? "polling · 2s interval" : "idle"}
                  </span>
                </div>
              </div>
            </div>

            {/* Audit History — tonal recess card */}
            <div className="bg-[#f2f4f6] p-6 rounded-xl">
              <div className="flex items-center gap-3 mb-4">
                <History className="h-4 w-4 text-[#004c60]" />
                <h4 className="text-sm font-bold text-[#191c1e]">
                  Audit History
                </h4>
              </div>
              <ul className="space-y-4">
                <li className="flex items-start gap-3">
                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-[#00502e] shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-slate-700">
                      Q3 Tax Reconciliation
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      Completed 2 days ago
                    </p>
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-[#00502e] shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-slate-700">
                      Vendor Audit: Apex Corp
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      Completed 5 days ago
                    </p>
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-[#81d9a2] shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-slate-700">
                      CloudData Networks Intake
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      Completed 1 week ago
                    </p>
                  </div>
                </li>
              </ul>
            </div>

            {/* Support Glass Card */}
            <div className="bg-white/60 backdrop-blur-md p-5 rounded-xl border border-white/70 shadow-sm">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-[#d5e3fc] flex items-center justify-center shrink-0">
                  <LifeBuoy className="h-5 w-5 text-[#57657a]" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-[#191c1e]">
                    Support Needed?
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                    Our concierge is ready to assist with complex
                    reconciliation.
                  </p>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
