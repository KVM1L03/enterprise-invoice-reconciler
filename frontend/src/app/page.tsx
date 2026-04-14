"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FolderOpen, Loader2 } from "lucide-react";

import {
  clearAllBatches,
  getDashboardStats,
  getRecentBatches,
  saveBatchResult,
} from "@/app/actions";
import { BatchTable } from "@/components/Dashboard/BatchTable";
import { KPICards } from "@/components/Dashboard/KPICards";
import { ReviewModal } from "@/components/Dashboard/ReviewModal";
import { UploadWidget } from "@/components/Dashboard/UploadWidget";
import type {
  DashboardStats,
  PollResponse,
  RecentBatch,
  ReviewTarget,
  WorkflowResult,
} from "@/types";

const API = "http://localhost:8000";

export default function DashboardPage() {
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentBatches, setRecentBatches] = useState<RecentBatch[]>([]);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(
    null,
  );
  const [reviewTarget, setReviewTarget] = useState<ReviewTarget | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  const openReview = useCallback((row: ReviewTarget) => {
    setReviewTarget(row);
  }, []);

  const closeReview = useCallback(() => {
    setReviewTarget(null);
  }, []);

  const handleClearHistory = useCallback(async () => {
    if (
      !window.confirm("Are you sure you want to clear all batch history?")
    ) {
      return;
    }
    const res = await clearAllBatches();
    if (res.ok) {
      setResult(null);
      await reloadPersistedDashboard();
    } else {
      console.error("Failed to clear batch history:", res.error);
    }
  }, [reloadPersistedDashboard]);

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
              setResult(null);
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
            type="button"
            onClick={() => void startBatch()}
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

        <KPICards
          batchesLabel={batchesLabel}
          dashboardStats={dashboardStats}
          successRateDisplay={successRateDisplay}
          pendingDisplay={pendingDisplay}
          successBarWidth={successBarWidth}
        />

        <ReviewModal
          target={reviewTarget}
          onClose={closeReview}
          onAfterOverride={reloadPersistedDashboard}
        />

        <section className="space-y-8">
          <UploadWidget apiBaseUrl={API} polling={polling} />
          <BatchTable
            polling={polling}
            result={result}
            recentBatches={recentBatches}
            error={error}
            workflowId={workflowId}
            status={status}
            onReview={openReview}
            onClearHistory={() => void handleClearHistory()}
          />
        </section>
      </div>
    </div>
  );
}
