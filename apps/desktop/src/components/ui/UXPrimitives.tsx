import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ShieldCheck,
  Info,
  Loader2,
  ChevronDown,
  ChevronRight,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const PageHeader: React.FC<{
  badge?: string;
  icon?: React.ReactNode;
  title: string;
  description: string;
  actions?: React.ReactNode;
}> = ({ badge, icon, title, description, actions }) => (
  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-white/[0.07]">
    <div className="space-y-1.5">
      {badge && (
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#D97757]">
          {icon}
          <span>{badge}</span>
        </div>
      )}
      <h1 className="text-[22px] leading-tight font-semibold tracking-tight text-zinc-100 flex items-center gap-2.5">
        {!badge && icon}
        <span>{title}</span>
      </h1>
      <p className="text-[13.5px] text-zinc-300 max-w-3xl leading-relaxed">{description}</p>
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2.5 shrink-0">{actions}</div>}
  </div>
);

export const SectionHeader: React.FC<{
  icon?: React.ReactNode;
  title: string;
  description?: string;
  rightElement?: React.ReactNode;
}> = ({ icon, title, description, rightElement }) => (
  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
    <div className="space-y-0.5">
      <h2 className="text-[16px] font-semibold text-zinc-100 flex items-center gap-2">
        {icon}
        <span>{title}</span>
      </h2>
      {description && <p className="text-[13px] text-zinc-400 leading-relaxed">{description}</p>}
    </div>
    {rightElement && <div className="shrink-0">{rightElement}</div>}
  </div>
);

export const StatusBadge: React.FC<{
  tone: "success" | "danger" | "warning" | "neutral" | "accent";
  label: string;
  className?: string;
}> = ({ tone, label, className }) => {
  const styles = {
    success: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    danger: "bg-rose-500/15 text-rose-300 border-rose-500/30",
    warning: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    accent: "bg-[#D97757]/15 text-[#F09373] border-[#D97757]/35",
    neutral: "bg-zinc-800/90 text-zinc-300 border-white/[0.08]",
  };

  const icons = {
    success: <CheckCircle2 size={13} className="shrink-0 text-emerald-400" />,
    danger: <XCircle size={13} className="shrink-0 text-rose-400" />,
    warning: <AlertTriangle size={13} className="shrink-0 text-amber-400" />,
    accent: <ShieldCheck size={13} className="shrink-0 text-[#D97757]" />,
    neutral: <Info size={13} className="shrink-0 text-zinc-400" />,
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium",
        styles[tone],
        className
      )}
    >
      {icons[tone]}
      <span>{label}</span>
    </span>
  );
};

export const EmptyStateCard: React.FC<{
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}> = ({ icon, title, description, actionLabel, onAction }) => (
  <div className="rounded-2xl bg-[#21211F]/80 border border-dashed border-white/[0.1] p-8 text-center space-y-3">
    {icon && (
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/[0.04] border border-white/[0.07] text-[#D97757] mx-auto">
        {icon}
      </div>
    )}
    <div className="space-y-1 max-w-md mx-auto">
      <h3 className="text-[15px] font-semibold text-zinc-100">{title}</h3>
      <p className="text-[13px] text-zinc-400 leading-relaxed">{description}</p>
    </div>
    {actionLabel && onAction && (
      <div className="pt-1">
        <button
          type="button"
          onClick={onAction}
          className="inline-flex items-center gap-2 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-[13px] font-medium text-white transition-colors focus:outline-none focus:ring-2 focus:ring-[#D97757]/50"
        >
          {actionLabel}
        </button>
      </div>
    )}
  </div>
);

export const LoadingStateCard: React.FC<{
  title: string;
  description?: string;
}> = ({ title, description }) => {
  const [isLongWait, setIsLongWait] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsLongWait(true), 4500);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-6 flex items-start gap-3.5"
    >
      <div className="rounded-xl bg-[#D97757]/15 p-2.5 text-[#D97757] shrink-0">
        <Loader2 size={18} className="animate-spin" />
      </div>
      <div className="space-y-1">
        <div className="text-[14px] font-semibold text-zinc-100">{title}</div>
        {description && <p className="text-[13px] text-zinc-300 leading-relaxed">{description}</p>}
        {isLongWait && (
          <p className="text-xs text-amber-300/90 pt-1">
            Proses ini membutuhkan waktu sedikit lebih lama karena AKSA sedang memverifikasi keamanan
            dan menyiapkan data Anda. Mohon tunggu sebentar...
          </p>
        )}
      </div>
    </div>
  );
};

export const ErrorStateCard: React.FC<{
  title: string;
  cause?: string;
  safetyNote?: string;
  nextStep?: string;
  technicalDetail?: string | null;
  onRetry?: () => void;
  onDismiss?: () => void;
}> = ({
  title,
  cause,
  safetyNote = "Data dan file di komputer Anda tetap aman serta tidak mengalami perubahan.",
  nextStep,
  technicalDetail,
  onRetry,
  onDismiss,
}) => {
  const [showTech, setShowTech] = useState(false);

  return (
    <div
      role="alert"
      className="rounded-2xl bg-rose-500/10 border border-rose-500/30 p-4 space-y-2.5 text-left"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <XCircle size={18} className="text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="text-[14px] font-semibold text-zinc-100">{title}</h4>
            {cause && <p className="text-[13px] text-zinc-200 leading-relaxed">{cause}</p>}
            <p className="text-xs text-emerald-300/90 flex items-center gap-1.5">
              <ShieldCheck size={13} className="shrink-0" />
              <span>{safetyNote}</span>
            </p>
            {nextStep && (
              <p className="text-xs text-zinc-300 leading-relaxed">
                <strong>Langkah yang dapat dilakukan:</strong> {nextStep}
              </p>
            )}
          </div>
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Tutup pesan kesalahan"
            className="rounded-lg p-1 text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.06]"
          >
            <X size={14} />
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 pl-7">
        {technicalDetail ? (
          <button
            type="button"
            onClick={() => setShowTech((v) => !v)}
            className="inline-flex items-center gap-1 text-xs text-zinc-300 hover:text-white underline-offset-2 hover:underline"
          >
            {showTech ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            <span>Detail kesalahan</span>
          </button>
        ) : (
          <span />
        )}

        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-xl bg-white/[0.08] hover:bg-white/[0.14] border border-white/[0.12] px-3 py-1.5 text-xs font-medium text-zinc-100 transition-colors"
          >
            Coba Lagi
          </button>
        )}
      </div>

      {showTech && technicalDetail && (
        <pre className="ml-7 rounded-xl bg-black/40 border border-white/[0.08] p-3 text-[11px] font-mono text-zinc-300 overflow-x-auto whitespace-pre-wrap">
          {technicalDetail}
        </pre>
      )}
    </div>
  );
};

export const ConfirmDialog: React.FC<{
  open: boolean;
  title: string;
  description: string;
  impactNote?: string;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({
  open,
  title,
  description,
  impactNote,
  confirmLabel,
  cancelLabel = "Batal",
  destructive = false,
  onConfirm,
  onCancel,
}) => {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="aksa-confirm-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
    >
      <div className="w-full max-w-md rounded-2xl bg-[#21211F] border border-white/[0.12] shadow-2xl p-5 space-y-4">
        <div className="space-y-1.5">
          <h3 id="aksa-confirm-dialog-title" className="text-[16px] font-semibold text-zinc-100">
            {title}
          </h3>
          <p className="text-[13.5px] text-zinc-300 leading-relaxed">{description}</p>
        </div>

        {impactNote && (
          <div className="rounded-xl bg-[#262624] border border-white/[0.07] p-3 text-xs text-zinc-300 leading-relaxed">
            {impactNote}
          </div>
        )}

        <div className="flex items-center justify-end gap-2.5 pt-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.1] px-4 py-2 text-[13px] font-medium text-zinc-200 transition-colors focus:outline-none focus:ring-2 focus:ring-white/20"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={cn(
              "rounded-xl px-4 py-2 text-[13px] font-semibold text-white transition-colors focus:outline-none focus:ring-2",
              destructive
                ? "bg-rose-600 hover:bg-rose-500 focus:ring-rose-500/50"
                : "bg-[#D97757] hover:bg-[#c96a4b] focus:ring-[#D97757]/50"
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
