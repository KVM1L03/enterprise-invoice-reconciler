"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  XCircle,
} from "lucide-react";

import { overrideInvoiceStatus } from "@/app/actions";
import type { OverrideStatus, ReviewTarget } from "@/types";

export type ReviewModalProps = {
  target: ReviewTarget | null;
  onClose: () => void;
  /** Called after a successful status override (e.g. refresh Prisma-backed lists). */
  onAfterOverride: () => Promise<void>;
};

export function ReviewModal({
  target,
  onClose,
  onAfterOverride,
}: ReviewModalProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (target) {
      setError(null);
      setSubmitting(false);
    }
  }, [target]);

  const handleClose = useCallback(() => {
    if (submitting) return;
    setError(null);
    onClose();
  }, [submitting, onClose]);

  const handleDecide = useCallback(
    async (decision: OverrideStatus) => {
      if (!target) return;
      setSubmitting(true);
      setError(null);
      try {
        const res = await overrideInvoiceStatus(target.id, decision);
        if (res.ok) {
          await onAfterOverride();
          onClose();
        } else {
          setError(res.error ?? "Failed to update invoice");
        }
      } finally {
        setSubmitting(false);
      }
    },
    [target, onAfterOverride, onClose],
  );

  if (!target) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4"
      onClick={handleClose}
    >
      <div
        className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 mb-5">
          <div className="rounded-lg bg-[#9df5bd] p-2 flex items-center justify-center">
            <AlertTriangle className="h-5 w-5 text-[#00522f]" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-[#191c1e]">
              Manual Review Required
            </h3>
            <p className="mt-0.5 text-xs text-[#3f4941]">
              Override the AI decision for this invoice.
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="text-slate-400 hover:text-[#191c1e]"
            aria-label="Close"
          >
            <XCircle className="h-5 w-5" />
          </button>
        </div>

        <dl className="space-y-3 text-sm mb-6">
          <div>
            <dt className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              Invoice ID
            </dt>
            <dd className="mt-1 font-mono text-[#191c1e]">
              {target.invoice_id ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              Expected Amount
            </dt>
            <dd className="mt-1 font-mono text-[#191c1e]">
              {target.erp_expected_amount != null
                ? `$${target.erp_expected_amount.toLocaleString("en-US", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}`
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              AI Reasoning
            </dt>
            <dd className="mt-1 text-[#3f4941] leading-relaxed">
              {target.reason ?? target.error ?? (
                <span className="italic text-slate-400">No reason provided</span>
              )}
            </dd>
          </div>
        </dl>

        {error && (
          <div className="mb-4 rounded-md bg-[#ffdad6] text-[#93000a] p-3 text-xs font-mono">
            {error}
          </div>
        )}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => void handleDecide("FORCE_APPROVED")}
            disabled={submitting}
            className="flex-1 inline-flex items-center justify-center gap-2 rounded-md bg-gradient-to-r from-[#00502e] to-[#006b3f] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            Force Approve
          </button>
          <button
            type="button"
            onClick={() => void handleDecide("REJECTED")}
            disabled={submitting}
            className="flex-1 inline-flex items-center justify-center gap-2 rounded-md bg-[#ba1a1a] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <XCircle className="h-4 w-4" />
            )}
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}
