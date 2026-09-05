import { AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export const panel = "rounded-xl border border-slate-200 bg-white shadow-sm";
export const buttonBase =
  "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600 disabled:cursor-not-allowed disabled:opacity-50";
export const buttonPrimary = cn(buttonBase, "bg-primary-600 text-white hover:bg-primary-700");
export const buttonSecondary = cn(buttonBase, "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50");

/** Section heading used across result panels. */
export function SectionTitle({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-700">{children}</h3>
      {hint && <span className="text-xs text-slate-500">{hint}</span>}
    </div>
  );
}

/** Small neutral/attention status pill. */
export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "review" | "error" | "success"; children: React.ReactNode }) {
  const tones = {
    neutral: "bg-slate-100 text-slate-700",
    review: "bg-amber-50 text-amber-800 border border-amber-200",
    error: "bg-red-50 text-red-700 border border-red-200",
    success: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  } as const;
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium", tones[tone])}>{children}</span>;
}

/** User-facing error message; never renders technical detail supplied by the caller. */
export function ErrorMessage({ message, className }: { message: string; className?: string }) {
  return (
    <div role="alert" className={cn("flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 p-3.5 text-sm text-red-800", className)}>
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  );
}

export function Spinner({ size = 16, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} className={cn("animate-spin", className)} aria-hidden />;
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-3 py-10 text-sm text-slate-600">
      <Spinner size={18} className="text-primary-600" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="py-12 text-center">
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
    </div>
  );
}
