import type { VinmonopoletSummary } from "../types";

/** Format a VinmonopoletSummary into a compact single-line string. */
export function formatVinmonopolet(
  summary: VinmonopoletSummary | null,
): string {
  if (!summary || summary.type === "closed") return "Stengt";
  if (summary.type === "uniform") return `${summary.open}\u2013${summary.close}`;
  return `${summary.min_open}\u2013${summary.max_close}`;
}

/** Norwegian plural: "butikk" for 1, "butikker" for all other counts. */
export function storeLabel(count: number): string {
  return count === 1 ? "butikk" : "butikker";
}

/** Display a single value if min === max, otherwise "min–max". */
export function formatVinmonopoletRange(min: string, max: string): string {
  return min === max ? min : `${min}\u2013${max}`;
}
