"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  FileText,
  Loader2,
  Paperclip,
  Upload,
  XCircle,
} from "lucide-react";

import type { UploadInvoicesResponse, UploadToast } from "@/types";

const DEFAULT_API = "http://localhost:8000";

const CARD_SHADOW = "shadow-[0_12px_40px_rgba(25,28,30,0.04)]";

export type UploadWidgetProps = {
  /** Base URL for FastAPI (no trailing slash). */
  apiBaseUrl?: string;
  /** Disables upload controls while batch polling is active. */
  polling: boolean;
};

export function UploadWidget({
  apiBaseUrl = DEFAULT_API,
  polling,
}: UploadWidgetProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadToast, setUploadToast] = useState<UploadToast | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

      const res = await fetch(`${apiBaseUrl}/upload-invoices`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}: ${detail}`);
      }

      const data: UploadInvoicesResponse = await res.json();
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

  return (
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
            Drop PDF files into the processing queue before running the batch.
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
          type="button"
          onClick={() => void uploadFiles()}
          disabled={selectedFiles.length === 0 || uploading || polling}
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
            type="button"
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
  );
}
