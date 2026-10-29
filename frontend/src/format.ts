/** 75.4 -> "1:15", 3725 -> "1:02:05" */
export function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

export function formatMs(ms: number): string {
  return ms < 10 ? `${ms.toFixed(1)} ms` : `${Math.round(ms)} ms`;
}

export function plural(n: number, word: string): string {
  return `${n.toLocaleString("en-US")} ${word}${n === 1 ? "" : "s"}`;
}
