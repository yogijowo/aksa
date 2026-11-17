import React from "react";
import {
  ShieldCheck,
  MonitorCog,
  FolderLock,
  OctagonAlert,
  PlugZap,
  Sparkles,
  FileSpreadsheet,
  FileText,
  Presentation,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";

export const PermissionsAndPCView: React.FC = () => {
  const {
    workspaces,
    mcpServers,
    emergencyStopActive,
    updateWorkspacePermissions,
    requestSampleApproval,
    toggleMcpServer,
    toggleEmergencyStop,
    sendUserPrompt,
    setActiveNav,
  } = useAksaStore();

  const handleQuickOfficeTask = async (prompt: string) => {
    setActiveNav("ruang_kerja");
    await sendUserPrompt(prompt);
  };

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-[#191918]">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header & Emergency Stop Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
              <ShieldCheck size={18} className="text-emerald-400" />
              Izin Akses Folder & 3-Tier PC Execution Engine
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Kelola Sandbox Folder Kerja, Auto-Backup (`.aksa_backup/`), server MCP, serta tombol
              darurat kontrol layar Tier 3.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => void requestSampleApproval()}
              className="rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 px-3.5 py-2 text-xs font-medium text-amber-300 transition-colors"
            >
              Simulasi Konfirmasi HITL
            </button>
            <button
              onClick={() => void toggleEmergencyStop(!emergencyStopActive)}
              className={`rounded-xl px-3.5 py-2 text-xs font-semibold flex items-center gap-1.5 border transition-colors ${
                emergencyStopActive
                  ? "bg-emerald-600/20 border-emerald-500/40 text-emerald-300"
                  : "bg-rose-600/20 hover:bg-rose-600/30 border-rose-500/40 text-rose-300"
              }`}
            >
              <OctagonAlert size={14} />
              {emergencyStopActive
                ? "Aktifkan Kembali Tier 3 GUI"
                : "Stop Darurat GUI (Ctrl+Shift+Q)"}
            </button>
          </div>
        </div>

        {/* Section 1: Workspace Folder Sandbox & Granular Permissions */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <FolderLock size={15} className="text-[#D97757]" />
              <span>Sandbox Folder Kerja Diizinkan (`allowed_paths` Path Jail)</span>
            </div>
            <span className="text-[11px] text-emerald-400">
              Path di luar daftar ini otomatis diblokir
            </span>
          </div>

          <div className="space-y-3">
            {workspaces.map((ws) => (
              <div
                key={ws.id}
                className="rounded-xl bg-[#262624] border border-white/[0.06] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="text-xs font-semibold text-zinc-100">{ws.name}</div>
                  <div className="text-[11px] font-mono text-zinc-400">{ws.folder_path}</div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-1.5 rounded-lg bg-[#21211F] border border-white/[0.07] px-3 py-1.5 text-[11px] text-zinc-200 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ws.allow_read}
                      onChange={(e) =>
                        updateWorkspacePermissions(ws.id, { allow_read: e.target.checked })
                      }
                      className="accent-indigo-500"
                    />
                    Baca & RAG
                  </label>
                  <label className="flex items-center gap-1.5 rounded-lg bg-[#21211F] border border-white/[0.07] px-3 py-1.5 text-[11px] text-zinc-200 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ws.allow_write}
                      onChange={(e) =>
                        updateWorkspacePermissions(ws.id, { allow_write: e.target.checked })
                      }
                      className="accent-indigo-500"
                    />
                    Tulis + Auto-Backup
                  </label>
                  <label className="flex items-center gap-1.5 rounded-lg bg-[#21211F] border border-white/[0.07] px-3 py-1.5 text-[11px] text-amber-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ws.allow_execute}
                      onChange={(e) =>
                        updateWorkspacePermissions(ws.id, { allow_execute: e.target.checked })
                      }
                      className="accent-amber-500"
                    />
                    Eksekusi Skrip (uv)
                  </label>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 2: Tier 1 Direct Office Engine Quick Actions */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <Sparkles size={15} className="text-emerald-400" />
              <span>Tier 1 — Direct Programmatic Office Engine (Uji Coba Cepat)</span>
            </div>
            <span className="rounded-lg bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-0.5 text-[11px] text-emerald-300">
              Tanpa Ganggu Mouse/Layar
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <button
              onClick={() =>
                void handleQuickOfficeTask(
                  "Buatkan file Excel rekap anggaran operasional lengkap dengan rumus SUM dan grafik batang."
                )
              }
              className="rounded-xl bg-[#262624] hover:bg-indigo-600/15 border border-white/[0.07] hover:border-[#D97757]/60/40 p-3.5 text-left space-y-1 transition-all"
            >
              <div className="flex items-center gap-2 text-xs font-semibold text-emerald-300">
                <FileSpreadsheet size={15} /> Buat Workbook Excel (.xlsx)
              </div>
              <p className="text-[11px] text-zinc-400">
                Format Rupiah otomatis, rumus `=SUM()`, dan grafik tertanam.
              </p>
            </button>

            <button
              onClick={() =>
                void handleQuickOfficeTask(
                  "Buatkan surat resmi penawaran kerja sama di Microsoft Word (.docx) lengkap dengan kop surat."
                )
              }
              className="rounded-xl bg-[#262624] hover:bg-indigo-600/15 border border-white/[0.07] hover:border-[#D97757]/60/40 p-3.5 text-left space-y-1 transition-all"
            >
              <div className="flex items-center gap-2 text-xs font-semibold text-sky-300">
                <FileText size={15} /> Buat Surat Resmi Word (.docx)
              </div>
              <p className="text-[11px] text-zinc-400">
                Preset surat bisnis Indonesia, heading, dan tabel rapi.
              </p>
            </button>

            <button
              onClick={() =>
                void handleQuickOfficeTask(
                  "Buatkan slide presentasi PowerPoint (.pptx) evaluasi kinerja kuartal untuk direksi."
                )
              }
              className="rounded-xl bg-[#262624] hover:bg-indigo-600/15 border border-white/[0.07] hover:border-[#D97757]/60/40 p-3.5 text-left space-y-1 transition-all"
            >
              <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                <Presentation size={15} /> Buat Presentasi PPT (.pptx)
              </div>
              <p className="text-[11px] text-zinc-400">
                Slide judul, poin bahasan, dua kolom, dan tabel ringkasan.
              </p>
            </button>
          </div>
        </div>

        {/* Section 3: Tier 2 Model Context Protocol (MCP) Servers */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <PlugZap size={15} className="text-[#D97757]" />
              <span>Tier 2 — Integrasi Server Model Context Protocol (MCP) & OS Bridge</span>
            </div>
            <span className="text-[11px] text-zinc-400">Win32 COM • AppleScript • uv Python</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {mcpServers.map((srv) => (
              <div
                key={srv.id}
                className="rounded-xl bg-[#262624] border border-white/[0.06] p-3.5 flex flex-col justify-between gap-3"
              >
                <div className="space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-zinc-100">{srv.name}</span>
                    <input
                      type="checkbox"
                      checked={srv.enabled}
                      onChange={(e) => void toggleMcpServer(srv.id, e.target.checked)}
                      className="accent-indigo-500 cursor-pointer"
                    />
                  </div>
                  <p className="text-[11px] text-zinc-400">{srv.description_id}</p>
                </div>
                <div className="flex flex-wrap gap-1">
                  {srv.discovered_tools.map((t) => (
                    <span
                      key={t}
                      className="rounded-md bg-[#21211F] px-2 py-0.5 text-[10px] font-mono text-zinc-200"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 4: Tier 3 Visual Computer Use Status */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-4 flex items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="text-xs font-semibold text-zinc-100 flex items-center gap-2">
              <MonitorCog size={15} className="text-[#D97757]" />
              Tier 3 — Visual Computer Use (Tangkapan Layar `mss` + Accessibility Tree)
            </div>
            <p className="text-xs text-zinc-400">
              Mengoperasikan aplikasi pihak ketiga menggunakan koordinat layar. Geser kursor ke
              sudut layar mana pun (`Failsafe Corner Abort`) untuk membatalkan otomatis.
            </p>
          </div>
          <span
            className={`shrink-0 rounded-xl px-3 py-1 text-[11px] font-medium border ${
              emergencyStopActive
                ? "bg-rose-500/15 border-rose-500/30 text-rose-300"
                : "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
            }`}
          >
            {emergencyStopActive ? "Dihentikan Darurat" : "Siaga • Wajib Izin HITL"}
          </span>
        </div>
      </div>
    </div>
  );
};

