import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes safely. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Human-readable file size. */
export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
}

/** Format ISO date string for display. */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Confidence percentage → colour class. */
export function confidenceColor(pct: number): string {
  if (pct >= 90) return "text-green-600";
  if (pct >= 70) return "text-yellow-600";
  return "text-red-600";
}
