import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Database,
  ShieldCheck,
  Cpu,
  FolderOpen,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface AppLoadingScreenProps {
  stepLabel?: string;
  progress?: number;
  stages?: {
    engine: "pending" | "loading" | "done" | "error";
    database: "pending" | "loading" | "done" | "error";
    workspace: "pending" | "loading" | "done" | "error";
  };
  onBypass?: () => void;
}

export const AppLoadingScreen: React.FC<AppLoadingScreenProps> = ({
  stepLabel = "Menyiapkan lingkungan kerja AKSA...",
  progress = 30,
  stages = {
    engine: "loading",
    database: "pending",
    workspace: "pending",
  },
  onBypass,
}) => {
  const [showTimeoutHelp, setShowTimeoutHelp] = useState(false);

  useEffect(() => {
    // If loading takes more than 7 seconds, offer bypass action so user is never locked out
    const timer = setTimeout(() => {
      setShowTimeoutHelp(true);
    }, 7000);
    return () => clearTimeout(timer);
  }, []);

  const getStageIcon = (status: "pending" | "loading" | "done" | "error") => {
    switch (status) {
      case "done":
        return <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />;
      case "loading":
        return <Loader2 size={15} className="animate-spin text-[#D97757] shrink-0" />;
      case "error":
        return <AlertCircle size={15} className="text-rose-400 shrink-0" />;
      case "pending":
      default:
        return <span className="h-2 w-2 rounded-full bg-white/20 shrink-0 mx-1" />;
    }
  };

  const stageItems = [
    {
      id: "engine",
      label: "Mesin Layanan Lokal & Keamanan",
      description: "Memverifikasi handshake autentikasi dan isolasi sandbox",
      status: stages.engine,
      icon: <Cpu size={14} className="text-zinc-400" />,
    },
    {
      id: "database",
      label: "Basis Data SQLite (aksa.db) & Brankas Kunci",
      description: "Memeriksa tabel, migrasi data, dan status token terenkripsi",
      status: stages.database,
      icon: <Database size={14} className="text-zinc-400" />,
    },
    {
      id: "workspace",
      label: "Struktur Tim AI & Folder Ruang Kerja",
      description: "Menyiapkan hierarki agen, izin akses folder, dan preferensi",
      status: stages.workspace,
      icon: <FolderOpen size={14} className="text-zinc-400" />,
    },
  ];

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-0 z-50 flex flex-col items-center justify-center p-6 bg-[#191918] text-[#ECECEB] select-none"
    >
      <div className="w-full max-w-md space-y-6 text-center animate-in fade-in zoom-in-95 duration-300">
        {/* Brand Icon & Heading */}
        <div className="flex flex-col items-center space-y-3">
          <div className="relative flex items-center justify-center h-16 w-16 rounded-3xl bg-gradient-to-br from-[#D97757] to-[#b85332] shadow-2xl shadow-[#D97757]/20 border border-white/10">
            <Sparkles size={30} className="text-white animate-pulse" />
            <div className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-[#21211F] border border-white/15">
              <ShieldCheck size={13} className="text-emerald-400" />
            </div>
          </div>

          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center justify-center gap-2">
              <span>AKSA</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[#D97757]/20 text-[#F09373] border border-[#D97757]/30 font-semibold tracking-normal">
                Desktop
              </span>
            </h1>
            <p className="text-xs text-zinc-400">
              Asisten Kerja Cerdas & Otonom • Produktivitas Kantor Indonesia
            </p>
          </div>
        </div>

        {/* Loading Progress Card */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.09] p-5 shadow-xl text-left space-y-4">
          {/* Progress Bar & Current Step */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-zinc-300 truncate max-w-[280px]">
                {stepLabel}
              </span>
              <span className="text-[#F09373] font-semibold">{Math.round(progress)}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-black/40 border border-white/[0.06]">
              <div
                className="h-full bg-gradient-to-r from-[#D97757] to-[#F09373] transition-all duration-300 ease-out rounded-full"
                style={{ width: `${Math.max(5, Math.min(100, progress))}%` }}
              />
            </div>
          </div>

          {/* Detailed Verification Steps */}
          <div className="pt-2 border-t border-white/[0.06] space-y-2.5">
            {stageItems.map((item) => (
              <div
                key={item.id}
                className={cn(
                  "flex items-start gap-2.5 rounded-xl p-2.5 transition-colors text-xs",
                  item.status === "loading"
                    ? "bg-white/[0.04] border border-white/[0.08]"
                    : "bg-transparent"
                )}
              >
                <div className="pt-0.5">{getStageIcon(item.status)}</div>
                <div className="flex-1 min-w-0 space-y-0.5">
                  <div className="flex items-center gap-1.5 font-medium text-zinc-200">
                    {item.icon}
                    <span className="truncate">{item.label}</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-snug truncate">
                    {item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Fallback Option if Loading is taking long */}
        {showTimeoutHelp && (
          <div className="rounded-xl bg-amber-500/10 border border-amber-500/25 p-3 text-xs text-amber-200 text-left space-y-2 animate-in fade-in duration-300">
            <p className="leading-relaxed">
              Membutuhkan waktu lebih lama dari perkiraan? AKSA tetap dapat dibuka dalam mode lokal.
            </p>
            {onBypass && (
              <button
                type="button"
                onClick={onBypass}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 text-zinc-950 font-semibold text-xs hover:bg-amber-400 transition-colors"
              >
                <span>Lanjutkan Buka Aplikasi</span>
                <ArrowRight size={13} />
              </button>
            )}
          </div>
        )}

        <div className="text-[11px] text-zinc-500">
          Data tersimpan 100% lokal di perangkat Anda • Mematuhi aturan izin akses pengguna
        </div>
      </div>
    </div>
  );
};
