import React, { useEffect, useState } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  FolderKey,
  SlidersHorizontal,
  Info,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";

function describeHumanAction(toolName: string, fallbackTitle: string): string {
  switch (toolName) {
    case "run_custom_python_task":
      return "menjalankan pemrosesan data atau program di dalam folder kerja";
    case "control_live_office_app":
      return "mengoperasikan aplikasi Office di komputer Anda";
    case "computer_use_action":
      return "menggunakan kontrol layar dan keyboard";
    case "delete_file":
      return "menghapus file";
    case "write_file":
    case "word_create_document":
    case "excel_create_workbook":
      return "membuat atau mengubah file dokumen";
    default:
      return fallbackTitle.toLowerCase();
  }
}

export const HITLApprovalModal: React.FC = () => {
  const {
    pendingApprovals,
    resolveApproval,
    updateWorkspacePermissions,
    activeWorkspaceId,
    workspaces,
    teams,
    activeTeamId,
    setActiveNav,
  } = useAksaStore();

  const [showFolderSettings, setShowFolderSettings] = useState(false);
  const [grantRead, setGrantRead] = useState(true);
  const [grantWrite, setGrantWrite] = useState(false);

  const current = pendingApprovals[0];
  const activeWs = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];
  const activeTeam = teams.find((t) => t.id === activeTeamId) ?? teams[0];

  useEffect(() => {
    setShowFolderSettings(false);
    if (activeWs) {
      setGrantRead(activeWs.allow_read);
      setGrantWrite(activeWs.allow_write);
    }
  }, [current?.id, activeWs]);

  useEffect(() => {
    if (!current) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        void resolveApproval(current.id, false);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [current, resolveApproval]);

  if (!current) return null;

  const targetDisplay = current.target_path || activeWs?.folder_path || "folder Ruang Kerja aktif";
  const actionSummary = describeHumanAction(current.tool_name, current.title_id);
  const requestingAgent = activeTeam?.agents.find((a) => a.name === current.agent_name);
  const usesCloudModel = requestingAgent
    ? requestingAgent.provider !== "ollama" && requestingAgent.provider !== "lmstudio"
    : false;

  const handleApplyScopedFolderPermission = () => {
    if (activeWorkspaceId) {
      updateWorkspacePermissions(activeWorkspaceId, {
        allow_read: grantRead,
        allow_write: grantWrite,
        // Mandatory security rule: Never enable execute via folder read/write toggle
      });
    }
    setShowFolderSettings(false);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="aksa-hitl-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
    >
      <div className="w-full max-w-xl rounded-2xl bg-[#21211F] border border-amber-500/40 shadow-2xl overflow-hidden">
        {/* Header (Section 8.B: Gunakan judul bahasa sederhana: “AKSA meminta izin”) */}
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-5 py-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-amber-500/20 p-2.5 text-amber-400 shrink-0">
              <ShieldAlert size={20} />
            </div>
            <div>
              <h2 id="aksa-hitl-modal-title" className="text-[18px] font-semibold text-zinc-100">
                AKSA meminta izin
              </h2>
              <p className="text-xs text-amber-300/95">
                Tindakan berisiko memerlukan persetujuan Anda sebelum dijalankan
              </p>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {/* Primary Human-Readable Statement */}
          <div className="rounded-xl bg-[#262624] border border-white/[0.08] p-4 space-y-1.5">
            <p className="text-[14.5px] font-medium text-zinc-100 leading-relaxed">
              <strong>{current.agent_name}</strong> ingin <strong>{actionSummary}</strong> pada{" "}
              <code className="rounded bg-black/40 px-1.5 py-0.5 text-xs font-mono text-[#F09373]">
                {targetDisplay}
              </code>
              .
            </p>
            <p className="text-[13px] text-zinc-300 leading-relaxed">
              <strong>Alasan izin dibutuhkan:</strong> {current.description_id}
            </p>
          </div>

          {/* Transparent Structured Details (Section 8.B) */}
          <div className="rounded-xl bg-[#1C1C1A] border border-white/[0.07] p-4 space-y-2.5 text-[13px]">
            <div className="flex items-center justify-between gap-2">
              <span className="text-zinc-400">Agen yang meminta:</span>
              <span className="font-semibold text-zinc-100">{current.agent_name}</span>
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-zinc-400">Tindakan yang akan dilakukan:</span>
              <span className="font-medium text-zinc-200 text-right">{current.title_id}</span>
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-zinc-400 shrink-0 flex items-center gap-1.5">
                <FolderKey size={13} className="text-[#D97757]" /> Lokasi / objek terdampak:
              </span>
              <span className="font-mono text-xs text-zinc-200 truncate">{targetDisplay}</span>
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-zinc-400">Pengiriman data ke layanan Cloud:</span>
              <span className="text-xs text-zinc-200 text-right">
                {usesCloudModel
                  ? `Eksekusi alat berjalan lokal; ringkasan konteks diproses melalui penyedia ${requestingAgent?.provider.toUpperCase()}`
                  : "100% diproses secara lokal di komputer Anda"}
              </span>
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-zinc-400">Durasi persetujuan utama:</span>
              <span className="text-xs text-emerald-300">
                Sekali pakai (hanya berlaku untuk tindakan ini)
              </span>
            </div>
          </div>

          {/* Separate Permanent Scoped Folder Permission Panel (Section 8.B: Pisahkan izin permanen dari izin sekali pakai) */}
          {showFolderSettings && (
            <div className="rounded-xl bg-[#262624] border border-white/[0.1] p-4 space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-zinc-100 text-[13px]">
                  Atur Izin Permanen untuk Folder "{activeWs?.name || "Ruang Kerja"}"
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setActiveNav("izin_pc");
                  }}
                  className="text-[#D97757] hover:underline font-medium"
                >
                  Buka Pusat Akses →
                </button>
              </div>

              <div className="space-y-2">
                <label className="flex items-center justify-between rounded-lg bg-[#191918] border border-white/[0.07] px-3 py-2 cursor-pointer">
                  <span>Hak Baca: melihat dan membaca dokumen di folder ini</span>
                  <input
                    type="checkbox"
                    checked={grantRead}
                    onChange={(e) => setGrantRead(e.target.checked)}
                    className="accent-[#D97757]"
                  />
                </label>
                <label className="flex items-center justify-between rounded-lg bg-[#191918] border border-white/[0.07] px-3 py-2 cursor-pointer">
                  <span>Hak Tulis: membuat dan memperbarui file dokumen di folder ini</span>
                  <input
                    type="checkbox"
                    checked={grantWrite}
                    onChange={(e) => setGrantWrite(e.target.checked)}
                    className="accent-[#D97757]"
                  />
                </label>
              </div>

              <div className="rounded-lg bg-black/30 border border-white/[0.06] p-2.5 text-zinc-300 space-y-1 leading-relaxed">
                <div className="flex items-center gap-1.5 font-medium text-zinc-200">
                  <Info size={13} className="text-amber-400 shrink-0" />
                  <span>Ruang Lingkup &amp; Durasi Izin Permanen:</span>
                </div>
                <p>
                  • Berlaku khusus untuk folder{" "}
                  <strong>{activeWs?.name || "Ruang Kerja"}</strong> hingga Anda mencabutnya di
                  halaman Pusat Akses.
                </p>
                <p>
                  • Hak eksekusi program dan penghapusan permanen tidak pernah digabungkan ke tombol
                  ini dan tetap meminta izin sekali pakai.
                </p>
              </div>

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={handleApplyScopedFolderPermission}
                  className="rounded-lg bg-white/[0.1] hover:bg-white/[0.16] px-3 py-1.5 font-medium text-zinc-100 transition-colors"
                >
                  Simpan Izin Folder
                </button>
              </div>
            </div>
          )}

          {/* Action Buttons (Section 8.B: Jadikan "Izinkan sekali" pilihan utama, dan sediakan "Jangan izinkan") */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 pt-2">
            <button
              type="button"
              onClick={() => setShowFolderSettings((v) => !v)}
              className="rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.1] px-3.5 py-2.5 text-[13px] font-medium text-zinc-200 flex items-center justify-center gap-1.5 transition-colors"
            >
              <SlidersHorizontal size={14} />
              <span>Atur izin untuk folder ini</span>
            </button>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={() => void resolveApproval(current.id, false)}
                className="flex-1 sm:flex-initial rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 px-4 py-2.5 text-[13px] font-semibold text-rose-300 flex items-center justify-center gap-1.5 transition-colors"
              >
                <XCircle size={15} />
                <span>Jangan izinkan</span>
              </button>

              <button
                type="button"
                onClick={() => void resolveApproval(current.id, true)}
                className="flex-1 sm:flex-initial rounded-xl bg-emerald-600 hover:bg-emerald-500 px-5 py-2.5 text-[13px] font-semibold text-white flex items-center justify-center gap-1.5 transition-colors shadow-lg shadow-emerald-600/25"
              >
                <CheckCircle2 size={15} />
                <span>Izinkan sekali</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
