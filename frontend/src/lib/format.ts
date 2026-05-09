/**
 * USD formatter with adaptive precision.
 *
 * LLM API costs can be sub-dollar (e.g. $0.0034 for a small batch).
 * A fixed 2-decimal formatter would silently render those as "$0.00",
 * making the dashboard look broken when the cost is real but small.
 */
export function formatUsd(value: number): string {
  const abs = Math.abs(value);
  let fractionDigits: number;
  if (abs === 0 || abs >= 1) {
    fractionDigits = 2;
  } else if (abs >= 0.01) {
    fractionDigits = 4;
  } else {
    fractionDigits = 6;
  }
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })}`;
}
