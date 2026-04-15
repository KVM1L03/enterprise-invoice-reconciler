import { CalendarRange, ChevronDown } from "lucide-react";

export type ReportHeaderProps = {
  title: string;
  description: string;
  dateRangeLabel?: string;
};

export function ReportHeader({
  title,
  description,
  dateRangeLabel = "Last 7 days",
}: ReportHeaderProps) {
  return (
    <header className="mb-10 flex justify-between items-end gap-6 flex-wrap">
      <div className="max-w-2xl">
        <h1 className="text-[1.75rem] font-semibold text-[#191c1e] tracking-tight leading-tight">
          {title}
        </h1>
        <p className="text-[#3f4941] mt-2 text-sm max-w-lg leading-relaxed">
          {description}
        </p>
      </div>

      <button
        type="button"
        title="Date range (mock)"
        className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-[#191c1e] shadow-sm hover:border-[#00502e]/40 transition-colors whitespace-nowrap"
      >
        <CalendarRange className="h-4 w-4 text-[#00502e]" />
        {dateRangeLabel}
        <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
      </button>
    </header>
  );
}
