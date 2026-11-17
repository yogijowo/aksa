import React from "react";
import { ShieldAlert, CheckCircle2, XCircle, Lock, FolderKey } from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";

export const HITLApprovalModal: React.FC = () => {
  const { pendingApprovals, resolveApproval, updateWorkspacePermissions, activeWorkspaceId } =
    useAksaStore();

  const current = pendingApprovals[0];
  if (!current) return null;

  const handleAllowAlwaysInFolder = async () => {
    updateWorkspacePermissions(activeWorkspaceId, {
      allow_read: true,
      allow_write: true,
      allow_execute: true,
    });
    await resolveApproval(current.id, true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl bg-[#161618] border border-amber-500/40 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="rounded-xl bg-amber-500/20 p-2 text-amber-400">
              <ShieldAlert size={18} />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-zinc-100">
                Konfirmasi Izin Akses (Human-in-the-Loop)
              </h3>
              <p className="text-[11px] text-amber-300/90">
                Risiko Tinggi • Memerlukan persetujuan eksplisit Anda
              </p>
            </div>
          </div>
          <span className="rounded-lg bg-amber-500/20 border border-amber-500/30 px-2.5 py-1 text-[10px] font-mono uppercase text-amber-300">
            {current.tool_name}
          </span>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-zinc-100">{current.title_id}</div>
            <p className="text-xs text-zinc-300 leading-relaxed">{current.description_id}</p>
          </div>

          <div className="rounded-xl bg-[#1E1E22] border border-white/[0.07] p-3.5 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Agen Peminta:</span>
              <span className="font-medium text-zinc-200">{current.agent_name}</span>
            </div>
            {current.target_path && (
              <div className="flex items-center justify-between gap-2">
                <span className="text-zinc-400 shrink-0 flex items-center gap-1">
                  <FolderKey size={12} /> Lokasi Target:
                </span>
                <span className="font-mono text-[11px] text-zinc-200 truncate">
                  {current.target_path}
                </span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Perlindungan Sandbox:</span>
              <span className="text-emerald-400 text-[11px]">
                Auto-Backup (.aksa_backup/) Aktif
              </span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-2 pt-2">
            <button
              onClick={() => void resolveApproval(current.id, false)}
              className="rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 px-3.5 py-2 text-xs font-medium text-rose-300 flex items-center justify-center gap-1.5 transition-colors"
            >
              <XCircle size={14} />
              Tolak Akses
            </button>
            <button
              onClick={() => void handleAllowAlwaysInFolder()}
              className="rounded-xl bg-zinc-800 hover:bg-zinc-700 border border-white/[0.1] px-3.5 py-2 text-xs font-medium text-zinc-200 flex items-center justify-center gap-1.5 transition-colors"
            >
              <Lock size={13} />
              Selalu Izinkan di Folder Ini
            </button>
            <button
              onClick={() => void resolveApproval(current.id, true)}
              className="rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-xs font-semibold text-white flex items-center justify-center gap-1.5 transition-colors shadow-lg shadow-emerald-600/20"
            >
              <CheckCircle2 size={14} />
              Izinkan Sekali
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

